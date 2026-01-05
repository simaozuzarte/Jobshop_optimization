"""
CP-SAT Solver Module for Job Shop Scheduling Problem
Uses Google OR-Tools CP-SAT solver
"""

import time
import logging
from ortools.sat.python import cp_model

logger = logging.getLogger(__name__)


def build_cp_model(n_jobs, n_machines, jobs, p):
    """Build CP-SAT model using OR-Tools."""
    model = cp_model.CpModel()
    
    # Create interval variables for each operation
    all_tasks = {}
    starts = {}
    ends = {}
    intervals = {}
    
    horizon = sum(p.values())  # Upper bound on makespan
    
    for j in range(n_jobs):
        for idx, (m, duration) in enumerate(jobs[j]):
            suffix = f"_{j}_{m}"
            start = model.NewIntVar(0, horizon, f"start{suffix}")
            end = model.NewIntVar(0, horizon, f"end{suffix}")
            interval = model.NewIntervalVar(start, duration, end, f"interval{suffix}")
            all_tasks[(j, m)] = (start, end, interval)
            starts[(j, m)] = start
            ends[(j, m)] = end
            intervals[(j, m)] = interval
    
    # Job precedence constraints
    for j in range(n_jobs):
        for k in range(len(jobs[j]) - 1):
            m1, d1 = jobs[j][k]
            m2, d2 = jobs[j][k + 1]
            model.Add(starts[(j, m2)] >= ends[(j, m1)])
    
    # Machine capacity constraints (no-overlap)
    machine_to_intervals = {}
    for j in range(n_jobs):
        for m, _ in jobs[j]:
            if m not in machine_to_intervals:
                machine_to_intervals[m] = []
            machine_to_intervals[m].append(intervals[(j, m)])
    
    for m, intervals_list in machine_to_intervals.items():
        model.AddNoOverlap(intervals_list)
    
    # Makespan variable
    makespan = model.NewIntVar(0, horizon, "makespan")
    for j in range(n_jobs):
        m_last, _ = jobs[j][-1]
        model.Add(makespan >= ends[(j, m_last)])
    
    # Objective: minimize makespan
    model.Minimize(makespan)
    
    return model, makespan, starts, ends


def solve_cp_instance(file_path, n_jobs, n_machines, jobs, p,
                      time_limit=300, verbose=True, 
                      optimum=None, quiet_filter=None):
    """Solve a single JSP instance using CP-SAT and return results."""
    
    logger.info(f"\n  [CP] Reading instance and building model from {file_path}")
    
    model, makespan_var, starts, ends = build_cp_model(n_jobs, n_machines, jobs, p)
    
    logger.info(f"  [CP] Solving with OR-Tools CP-SAT (time limit: {time_limit}s)...")
    
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = 8  # Use multiple cores
    
    if verbose:
        solver.parameters.log_search_progress = True
    
    start = time.time()
    status = solver.Solve(model)
    runtime = time.time() - start
    
    # Map OR-Tools status to readable format
    status_map = {
        cp_model.OPTIMAL: "Optimal",
        cp_model.FEASIBLE: "Feasible",
        cp_model.INFEASIBLE: "Infeasible",
        cp_model.MODEL_INVALID: "Model Invalid",
        cp_model.UNKNOWN: "Unknown"
    }
    status_str = status_map.get(status, "Unknown")
    
    makespan = solver.Value(makespan_var) if status in [cp_model.OPTIMAL, cp_model.FEASIBLE] else None
    
    # Extract schedule if solution found
    schedule = None
    if makespan is not None:
        schedule = []
        for (j, m), start_var in starts.items():
            start_time = solver.Value(start_var)
            duration = p[(j, m)]
            schedule.append({
                'job': j,
                'machine': m,
                'start': start_time,
                'duration': duration
            })
    
    # Calculate optimality gap
    optimality_gap = None
    status_symbol = "✓" if status in [cp_model.OPTIMAL, cp_model.FEASIBLE] else "✗"
    
    if optimum is not None and makespan is not None:
        optimality_gap = ((makespan - optimum) / optimum) * 100
        logger.info(f"  {status_symbol} [CP] Finished in {runtime:.2f}s | Status: {status_str} | Makespan: {makespan:.2f} | Optimum: {optimum:.2f} | Gap: {optimality_gap:.2f}%\n")
    else:
        logger.info(f"  {status_symbol} [CP] Finished in {runtime:.2f}s | Status: {status_str} | Makespan: {makespan if makespan else 'N/A'}\n")

    return {
        "instance": file_path,
        "solver": "CP",
        "status": status_str,
        "makespan": makespan,
        "time": runtime,
        "optimal": status == cp_model.OPTIMAL,
        "schedule": schedule,
        "optimum": optimum,
        "optimality_gap": optimality_gap
    }
