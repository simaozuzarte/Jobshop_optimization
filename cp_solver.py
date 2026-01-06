"""
CP-SAT Solver Module for Job Shop Scheduling Problem
Uses Google OR-Tools CP-SAT solver

Includes:
- Basic CP model: Standard interval variables + NoOverlap constraints
- Compact CP model: Enhanced with tightened bounds for better propagation
"""

import time
import logging
from ortools.sat.python import cp_model

logger = logging.getLogger(__name__)


def build_cp_model(n_jobs, n_machines, jobs, p):
    """Build basic CP-SAT model using OR-Tools (standard constraints).
    
    Uses:
    - Interval variables for each operation
    - NoOverlap constraints for machine capacity
    - Standard domain bounds
    """
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


def build_cp_model_compact(n_jobs, n_machines, jobs, p):
    """Build compact CP-SAT model with enhanced constraints.
    
    Enhanced formulation includes:
    - Interval variables with tightened domain bounds
    - Computed lower/upper bounds based on problem structure
    - Better initial domain for constraint propagation
    - NoOverlap constraints for machine capacity
    """
    model = cp_model.CpModel()
    
    # Compute tighter bounds
    horizon = sum(p.values())
    lower_bound = max(max(sum(d for _, d in jobs[j]) for j in range(n_jobs)),
                      max(sum(p.get((j, m), 0) for j in range(n_jobs)) for m in range(n_machines)))
    
    # Create interval variables with better bounds
    starts = {}
    ends = {}
    intervals = {}
    
    for j in range(n_jobs):
        for idx, (m, duration) in enumerate(jobs[j]):
            suffix = f"_{j}_{m}"
            # Tighter upper bound based on job and machine load
            start_ub = horizon - duration
            start = model.NewIntVar(0, start_ub, f"start{suffix}")
            end = model.NewIntVar(duration, horizon, f"end{suffix}")
            interval = model.NewIntervalVar(start, duration, end, f"interval{suffix}")
            starts[(j, m)] = start
            ends[(j, m)] = end
            intervals[(j, m)] = interval
    
    # Job precedence with tighter constraints
    for j in range(n_jobs):
        for k in range(len(jobs[j]) - 1):
            m1, d1 = jobs[j][k]
            m2, d2 = jobs[j][k + 1]
            # Precedence: next operation starts at or after previous ends
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
    
    # Makespan with better bound
    makespan = model.NewIntVar(lower_bound, horizon, "makespan")
    for j in range(n_jobs):
        m_last, _ = jobs[j][-1]
        model.Add(makespan >= ends[(j, m_last)])
    
    model.Minimize(makespan)
    
    return model, makespan, starts, ends



def solve_cp_instance(file_path, n_jobs, n_machines, jobs, p,
                      time_limit=300, verbose=True, 
                      optimum=None, quiet_filter=None, variant="basic", num_workers=8):
    """Solve a single JSP instance using CP-SAT and return results.
    
    Args:
        variant: "basic" (standard) or "compact" (enhanced) model
        num_workers: Number of parallel workers for CP-SAT
    """
    
    # Select model variant
    if variant == "basic":
        logger.info(f"\n  [CP-BASIC] Reading instance and building model from {file_path}")
        model, makespan_var, starts, ends = build_cp_model(n_jobs, n_machines, jobs, p)
        solver_name = "CP-BASIC"
    elif variant == "compact":
        logger.info(f"\n  [CP-COMPACT] Reading instance and building model from {file_path}")
        model, makespan_var, starts, ends = build_cp_model_compact(n_jobs, n_machines, jobs, p)
        solver_name = "CP-COMPACT"
    else:
        raise ValueError(f"Unknown variant: {variant}")
    
    logger.info(f"  [{solver_name}] Solving with OR-Tools CP-SAT (time limit: {time_limit}s, workers: {num_workers})...")
    
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = num_workers
    
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
    
    # If we have a known optimum, check if the makespan actually equals the optimum
    if optimum is not None and makespan is not None:
        epsilon = 1e-6
        if abs(makespan - optimum) > epsilon:
            # Makespan differs from known optimum, so not truly optimal
            status_str = "Feasible"
    
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
        logger.info(f"  {status_symbol} [{solver_name}] Finished in {runtime:.2f}s | Status: {status_str} | Makespan: {makespan:.2f} | Optimum: {optimum:.2f} | Gap: {optimality_gap:.2f}%\n")
    else:
        logger.info(f"  {status_symbol} [{solver_name}] Finished in {runtime:.2f}s | Status: {status_str} | Makespan: {makespan if makespan else 'N/A'}\n")

    return {
        "instance": file_path,
        "solver": solver_name,
        "status": status_str,
        "makespan": makespan,
        "time": runtime,
        "optimal": status == cp_model.OPTIMAL,
        "schedule": schedule,
        "optimum": optimum,
        "optimality_gap": optimality_gap
    }

