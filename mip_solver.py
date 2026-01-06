"""
MIP Solver Module for Job Shop Scheduling Problem
Uses PuLP with CBC solver
"""

import time
import logging
from pulp import LpProblem, LpMinimize, LpBinary, LpVariable, LpStatus, PULP_CBC_CMD

logger = logging.getLogger(__name__)


def compute_time_bounds(n_jobs, n_machines, jobs, p):
    """Compute time bounds for the instance."""
    # Lower bound: maximum machine workload or maximum job length
    max_job_length = max(sum(duration for _, duration in jobs[j]) for j in range(n_jobs))
    max_machine_load = 0
    for m in range(n_machines):
        machine_load = sum(p[(j, m)] for j in range(n_jobs) if (j, m) in p)
        max_machine_load = max(max_machine_load, machine_load)
    
    lower_bound = max(max_job_length, max_machine_load)
    
    # Upper bound: sum of all processing times (trivial schedule)
    upper_bound = sum(p.values())
    
    # Big-M for disjunctive constraints
    big_M = upper_bound
    
    # Tighter Big-M: upper_bound - min_processing_time
    if p:
        min_processing = min(p.values())
        tighter_big_M = upper_bound - min_processing
    else:
        tighter_big_M = upper_bound
    
    return {
        'lower_bound': lower_bound,
        'upper_bound': upper_bound,
        'big_M': big_M,
        'tighter_big_M': tighter_big_M,
        'max_job_length': max_job_length,
        'max_machine_load': max_machine_load
    }


def build_mip_model(n_jobs, n_machines, jobs, p):
    """Build MIP model using PuLP."""
    prob = LpProblem("JSP_MIP", LpMinimize)

    # Compute bounds
    bounds = compute_time_bounds(n_jobs, n_machines, jobs, p)
    M = bounds['tighter_big_M']  # Use tighter bound

    # Start times with upper bound 
    horizon = bounds['upper_bound']
    S = {
        (j, m): LpVariable(f"S_{j}_{m}", lowBound=0, upBound=horizon)
        for j in range(n_jobs)
        for m, _ in jobs[j]
    }

    # Precompute jobs_on_m and M for all machines
    jobs_on_machine = {}  # jobs per machine
    for m in range(n_machines):
        jobs_on_m = [j for j in range(n_jobs) if any(machine == m for machine, _ in jobs[j])]
        jobs_on_machine[m] = jobs_on_m

    # Sequencing variables
    x = {}
    for m, jobs_on_m in jobs_on_machine.items():
        for i in jobs_on_m:
            for j in jobs_on_m:
                if i < j:
                    x[(i, j, m)] = LpVariable(f"x_{i}_{j}_{m}", cat=LpBinary)

    # Makespan
    C_max = LpVariable("C_max", lowBound=bounds['lower_bound'], upBound=horizon)
    prob += C_max

    # Job precedence constraints
    for j in range(n_jobs):
        for k in range(len(jobs[j]) - 1):
            m1, d1 = jobs[j][k]
            m2, _ = jobs[j][k + 1]
            prob += S[(j, m2)] >= S[(j, m1)] + d1

    # Machine capacity constraints
    for m, jobs_on_m in jobs_on_machine.items():
        for i in jobs_on_m:
            for k in jobs_on_m:
                if i < k:
                    prob += S[(i, m)] + p[(i, m)] <= S[(k, m)] + M * (1 - x[(i, k, m)])
                    prob += S[(k, m)] + p[(k, m)] <= S[(i, m)] + M * x[(i, k, m)]

    # Makespan definition
    for j in range(n_jobs):
        m_last, d_last = jobs[j][-1]
        prob += C_max >= S[(j, m_last)] + d_last

    return prob, C_max, S, x, bounds


def solve_mip_instance(file_path, n_jobs, n_machines, jobs, p, 
                       time_limit=300, gap=0.1, verbose=True, 
                       optimum=None, quiet_filter=None):
    """Solve a single JSP instance using MIP and return results."""
    
    
    prob, C_max, S, x, bounds = build_mip_model(n_jobs, n_machines, jobs, p)

    # Count constraints and variables for progress info
    n_vars = len(prob.variables())
    n_constraints = len(prob.constraints)
    logger.info(f"Model: {n_vars} variables, {n_constraints} constraints")
    logger.info(f"\n  [MIP] Reading instance and building model from {file_path}")
    logger.debug(f"  [MIP] Time bounds: LB={bounds['lower_bound']}, UB={bounds['upper_bound']}, Big-M={bounds['big_M']}")
    logger.info(f"  [MIP] Solving with CBC (time limit: {time_limit}s, gap: {gap*100:.1f}%)...")

    solver = PULP_CBC_CMD(msg=verbose, timeLimit=time_limit, gapRel=gap)

    start = time.time()
    prob.solve(solver)
    runtime = time.time() - start

    status = LpStatus[prob.status]
    makespan = C_max.varValue if status in ["Optimal", "Feasible"] else None

    # If we have a known optimum, check if the makespan actually equals the optimum
    if optimum is not None and makespan is not None:
        epsilon = 1e-6
        if abs(makespan - optimum) > epsilon:
            # Makespan differs from known optimum, so not truly optimal
            status = "Feasible"

    # Extract schedule if solution found
    schedule = []
    for (j, m), var in S.items():
        if var.varValue is not None:
            duration = p[(j, m)]
            schedule.append({
                'job': j,
                'machine': m,
                'start': var.varValue,
                'duration': duration
            })

    # Calculate optimality gap
    optimality_gap = None
    status_symbol = "✓" if status in ["Optimal", "Feasible"] else "✗"
    
    if optimum is not None and makespan is not None:
        optimality_gap = ((makespan - optimum) / optimum) * 100
        logger.info(f"  {status_symbol} [MIP] Finished in {runtime:.2f}s | Status: {status} | Makespan: {makespan:.2f} | Optimum: {optimum:.2f} | Gap: {optimality_gap:.2f}%\n")
    else:
        logger.info(f"  {status_symbol} [MIP] Finished in {runtime:.2f}s | Status: {status} | Makespan: {makespan}\n")

    return {
        "instance": file_path,
        "solver": "MIP",
        "status": status,
        "makespan": makespan,
        "time": runtime,
        "optimal": status == "Optimal",
        "schedule": schedule,
        "optimum": optimum,
        "optimality_gap": optimality_gap
    }
