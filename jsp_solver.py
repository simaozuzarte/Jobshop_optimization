import time
import argparse
import os
import glob
import sys
import json
import csv
import logging
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# Install on terminal: python -m pip install pulp
from pulp import LpProblem, LpMinimize, LpBinary, lpSum, PULP_CBC_CMD, LpVariable, LpStatus

#CP_SAT Solver from Or-Tools
from ortools.sat.python import cp_model

#For pretty table output
from tabulate import tabulate

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Create a custom logger that respects quiet mode
class QuietFilter(logging.Filter):
    def __init__(self, quiet=False):
        self.quiet = quiet
    
    def filter(self, record):
        return not self.quiet

quiet_filter = QuietFilter()

def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Job Shop Scheduling Problem (JSP) MIP Solver",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python jsp_solver.py -i JSPLIB/instances/abz5
  python jsp_solver.py -i JSPLIB/instances/abz5 JSPLIB/instances/ft06
  python jsp_solver.py -p "JSPLIB/instances/la*" --time-limit 60
  python jsp_solver.py -p "JSPLIB/instances/ft*" --gap 0.05 --verbose
  python jsp_solver.py -i JSPLIB/instances/ft06 --solver both --compare
        """
    )
    
    # Instance selection (mutually exclusive group)
    instance_group = parser.add_mutually_exclusive_group(required=True)
    instance_group.add_argument(
        "-i", "--instances",
        nargs="+",
        help="One or more instance file paths to solve"
    )
    instance_group.add_argument(
        "-p", "--pattern",
        type=str,
        help="Glob pattern to match instance files (e.g., 'JSPLIB/instances/la*')"
    )
    
    # Solver selection
    parser.add_argument(
        "-s", "--solver",
        choices=["mip", "cp", "both"],
        default="both",
        help="Solver to use: mip (MIP), cp (CP-SAT), or both (default: both)"
    )

     # Comparison and output
    parser.add_argument(
        "-c", "--compare",
        action="store_true",
        help="Generate comparison table when using both solvers"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output file for results (CSV format)"
    )

    # Solver parameters
    parser.add_argument(
        "-t", "--time-limit",
        type=int,
        default=300,
        help="Time limit in seconds for each instance (default: 300)"
    )
    parser.add_argument(
        "-g", "--gap",
        type=float,
        default=0.1,
        help="Relative MIP gap tolerance (default: 0.1 = 10%%)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show solver output during optimization"
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress all output except final results"
    )

    # Export CSV 
    parser.add_argument(
        "--export-csv",
        type=str, 
        help="Export results to CSV file")

    #Export JSON
    parser.add_argument(
        "--export-json", 
        type=str, 
        help="Export results to JSON file")

    # Gantt chart 
    parser.add_argument(
        "--gantt", 
        action="store_true", 
        help="Generate Gantt chart visualizations")
    
    

    return parser.parse_args()

#Function to read JSPLIB instance files
def read_jsplib_instance(file_path):
    jobs = []
    p = {}

    with open(file_path, "r") as file:
        lines = [l.strip() for l in file if l.strip() and not l.startswith("#")]

    n_jobs, n_machines = map(int, lines[0].split())
    job_lines = lines[1:]

    for j, line in enumerate(job_lines):
        numbers = list(map(int, line.split()))
        job_pairs = []

        for i in range(0, len(numbers), 2):
            m = numbers[i]-1 #Convert to 0-based index
            d = numbers[i+1]
            job_pairs.append((m, d))
            p[(j, m)] = d

        jobs.append(job_pairs)

    return n_jobs, n_machines, jobs, p

def load_optimum_values(jsplib_dir="JSPLIB"):
    """Load optimum values and bounds from instances.json."""
    optimum_data = {}
    instances_json_path = os.path.join(jsplib_dir, "instances.json")
    
    if not os.path.exists(instances_json_path):
        logger.warning(f"instances.json not found at {instances_json_path}")
        return optimum_data
    
    try:
        with open(instances_json_path, 'r') as f:
            data = json.load(f)
        
        for instance_info in data:
            name = instance_info.get('name')
            optimum = instance_info.get('optimum')
            bounds = instance_info.get('bounds')
            
            optimum_data[name] = {
                'optimum': optimum,
                'bounds': bounds
            }
        
        logger.debug(f"Loaded optimum values for {len(optimum_data)} instances")
        return optimum_data
    except Exception as e:
        logger.error(f"Error loading instances.json: {e}")
        return optimum_data

def get_instance_optimum(file_path, optimum_data):
    """Get optimum value for an instance by extracting its name from file path."""
    instance_name = os.path.splitext(os.path.basename(file_path))[0]
    return optimum_data.get(instance_name, {})

def validate_schedule(schedule, n_jobs, n_machines, jobs, p):
    """Validate that a schedule respects all constraints.
    
    Returns:
        tuple: (is_valid, violations_list)
    """
    violations = []
    
    if not schedule:
        return True, []
    
    # Create a dictionary for quick lookup: (job, machine) -> (start, duration, end)
    schedule_dict = {}
    for op in schedule:
        j, m = op['job'], op['machine']
        schedule_dict[(j, m)] = {
            'start': op['start'],
            'duration': op['duration'],
            'end': op['start'] + op['duration']
        }
    
    # Check 1: All operations are present
    all_ops = set()
    for j in range(n_jobs):
        for m, _ in jobs[j]:
            all_ops.add((j, m))
    
    schedule_ops = set((op['job'], op['machine']) for op in schedule)
    missing_ops = all_ops - schedule_ops
    if missing_ops:
        violations.append(f"Missing operations: {missing_ops}")
    
    extra_ops = schedule_ops - all_ops
    if extra_ops:
        violations.append(f"Extra/invalid operations: {extra_ops}")
    
    # Check 2: Job precedence constraints
    for j in range(n_jobs):
        for k in range(len(jobs[j]) - 1):
            m1, d1 = jobs[j][k]
            m2, _ = jobs[j][k + 1]
            
            if (j, m1) in schedule_dict and (j, m2) in schedule_dict:
                end1 = schedule_dict[(j, m1)]['end']
                start2 = schedule_dict[(j, m2)]['start']
                
                if start2 < end1:
                    violations.append(
                        f"Job precedence violated: Job {j}, "
                        f"Operation on M{m1} ends at {end1}, "
                        f"but operation on M{m2} starts at {start2}"
                    )
    
    # Check 3: Machine capacity constraints (no overlapping operations)
    for m in range(n_machines):
        # Get all operations on this machine
        machine_ops = [(op['job'], op['start'], op['start'] + op['duration']) 
                       for op in schedule if op['machine'] == m]
        
        # Sort by start time
        machine_ops.sort(key=lambda x: x[1])
        
        # Check for overlaps
        for i in range(len(machine_ops)):
            for j in range(i + 1, len(machine_ops)):
                job_i, start_i, end_i = machine_ops[i]
                job_j, start_j, end_j = machine_ops[j]
                
                # Check if intervals overlap (accounting for floating point)
                eps = 1e-6
                if start_i + eps < end_j and start_j + eps < end_i:
                    violations.append(
                        f"Machine capacity violated: Machine {m}, "
                        f"Job {job_i}[{start_i:.2f}, {end_i:.2f}] overlaps with "
                        f"Job {job_j}[{start_j:.2f}, {end_j:.2f}]"
                    )
    
    # Check 4: Start times and durations are non-negative
    for op in schedule:
        if op['start'] < -1e-6:
            violations.append(f"Negative start time: {op['start']} for Job {op['job']} on M{op['machine']}")
        if op['duration'] < 0:
            violations.append(f"Negative duration: {op['duration']} for Job {op['job']} on M{op['machine']}")
    
    is_valid = len(violations) == 0
    return is_valid, violations

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
    big_M = upper_bound  # Conservative but valid
    
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

#Function to build MIP model using PuLP
def build_mip_model(n_jobs, n_machines, jobs, p):
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
    C_max = LpVariable("C_max", lowBound=bounds['lower_bound'],upBound=horizon)
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


#Function to build CP-SAT model using OR-Tools
def build_cp_model(n_jobs, n_machines, jobs, p):
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



# Function to solve a single instance
def solve_mip_instance(file_path, time_limit=300, gap=0.1, verbose=True, quiet=False, optimum_data=None):
    """Solve a single JSP instance and return results."""
    if optimum_data is None:
        optimum_data = {}
    
    quiet_filter.quiet = quiet
    logger.addFilter(quiet_filter)
    
    try:
        logger.info(f"[MIP] Reading instance and building model from {file_path}")
        
        n_jobs, n_machines, jobs, p = read_jsplib_instance(file_path)
        prob, C_max, S, x, bounds = build_mip_model(n_jobs, n_machines, jobs, p)

        # Count constraints and variables for progress info
        n_vars = len(prob.variables())
        n_constraints = len(prob.constraints)
        logger.info(f"[MIP] Model: {n_vars} variables, {n_constraints} constraints")
        logger.debug(f"[MIP] Time bounds: LB={bounds['lower_bound']}, UB={bounds['upper_bound']}, Big-M={bounds['big_M']}")
        logger.info(f"[MIP] Solving with CBC (time limit: {time_limit}s, gap: {gap*100:.1f}%)...")

        solver = PULP_CBC_CMD(msg=verbose, timeLimit=time_limit, gapRel=gap)

        start = time.time()
        prob.solve(solver)
        runtime = time.time() - start

        status = LpStatus[prob.status]
        makespan = C_max.varValue if status in ["Optimal", "Feasible"] else None

        # Extract schedule if solution found
        schedule = []
        for (j, m), var in S.items():
            if var.varValue is not None:
                duration = p[(j, m)]  # Get duration from p dictionary
                schedule.append({
                    'job': j,
                    'machine': m,
                    'start': var.varValue,
                    'duration': duration
                })

        # Validate schedule
        is_valid = True
        validation_info = None
        if schedule:
            is_valid, violations = validate_schedule(schedule, n_jobs, n_machines, jobs, p)
            if not is_valid:
                logger.warning(f"[MIP] Schedule validation failed with {len(violations)} violations")
                validation_info = violations
            else:
                logger.debug("[MIP] Schedule validation passed")
        
        # Calculate optimality gap
        instance_info = get_instance_optimum(file_path, optimum_data)
        optimum = instance_info.get('optimum')
        optimality_gap = None
        
        if optimum is not None and makespan is not None:
            optimality_gap = ((makespan - optimum) / optimum) * 100
            logger.info(f"[MIP] Status: {status} | Makespan: {makespan} | Optimum: {optimum} | Gap: {optimality_gap:.2f}% | Time: {runtime:.2f}s")
        else:
            logger.info(f"[MIP] Status: {status} | Makespan: {makespan} | Time: {runtime:.2f}s")

        return {
            "instance": file_path,
            "solver": "MIP",
            "status": status,
            "makespan": makespan,
            "time": runtime,
            "optimal": status == "Optimal",
            "schedule": schedule,
            "optimum": optimum,
            "optimality_gap": optimality_gap,
            "schedule_valid": is_valid,
            "validation_violations": validation_info
        }
    finally:
        logger.removeFilter(quiet_filter)

def solve_cp_instance(file_path, time_limit=300, verbose=True, quiet=False, optimum_data=None):
    """Solve a single JSP instance using CP-SAT and return results."""
    if optimum_data is None:
        optimum_data = {}
    
    quiet_filter.quiet = quiet
    logger.addFilter(quiet_filter)
    
    try:
        logger.info(f"[CP] Reading instance and building model from {file_path}")
        
        n_jobs, n_machines, jobs, p = read_jsplib_instance(file_path)
        model, makespan_var, starts, ends = build_cp_model(n_jobs, n_machines, jobs, p)
        
        logger.info(f"[CP] Solving with OR-Tools CP-SAT (time limit: {time_limit}s)...")
        
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
                duration = p[(j, m)]  # Get duration from p dictionary
                schedule.append({
                    'job': j,
                    'machine': m,
                    'start': start_time,
                    'duration': duration
                })
        
        # Validate schedule
        is_valid = True
        validation_info = None
        if schedule:
            is_valid, violations = validate_schedule(schedule, n_jobs, n_machines, jobs, p)
            if not is_valid:
                logger.warning(f"[CP] Schedule validation failed with {len(violations)} violations")
                validation_info = violations
            else:
                logger.debug("[CP] Schedule validation passed")
        
        # Calculate optimality gap
        instance_info = get_instance_optimum(file_path, optimum_data)
        optimum = instance_info.get('optimum')
        optimality_gap = None
        
        if optimum is not None and makespan is not None:
            optimality_gap = ((makespan - optimum) / optimum) * 100
            status_symbol = "✓" if status in [cp_model.OPTIMAL, cp_model.FEASIBLE] else "✗"
            logger.info(f"{status_symbol} [CP] Finished in {runtime:.2f}s - Makespan: {makespan} - Optimum: {optimum} - Gap: {optimality_gap:.2f}% - Status: {status_str}")
        else:
            status_symbol = "✓" if status in [cp_model.OPTIMAL, cp_model.FEASIBLE] else "✗"
            logger.info(f"{status_symbol} [CP] Finished in {runtime:.2f}s - Makespan: {makespan if makespan else 'N/A'} - Status: {status_str}")
        
        return {
            "instance": file_path,
            "solver": "CP",
            "status": status_str,
            "makespan": makespan,
            "time": runtime,
            "optimal": status == cp_model.OPTIMAL,
            "schedule": schedule,
            "optimum": optimum,
            "optimality_gap": optimality_gap,
            "schedule_valid": is_valid,
            "validation_violations": validation_info
        }
    finally:
        logger.removeFilter(quiet_filter)

def compare_solvers(results_mip, results_cp):
    """Compare results from MIP and CP solvers."""
    comparison = []
    
    for mip_res, cp_res in zip(results_mip, results_cp):
        instance_name = os.path.basename(mip_res["instance"])
        
        # Calculate percentage difference in makespan
        makespan_diff = None
        if mip_res["makespan"] is not None and cp_res["makespan"] is not None:
            makespan_diff = abs(mip_res["makespan"] - cp_res["makespan"]) / max(mip_res["makespan"], cp_res["makespan"]) * 100
        
        # Determine which solver is better
        better_solver = None
        if mip_res["makespan"] is not None and cp_res["makespan"] is not None:
            if mip_res["makespan"] < cp_res["makespan"]:
                better_solver = "MIP"
            elif cp_res["makespan"] < mip_res["makespan"]:
                better_solver = "CP"
            else:
                better_solver = "Equal"
        
        comparison.append({
            "Instance": instance_name,
            "MIP Status": mip_res["status"],
            "MIP Makespan": mip_res["makespan"],
            "MIP Gap %": f"{mip_res['optimality_gap']:.2f}" if mip_res.get('optimality_gap') is not None else "N/A",
            "MIP Time (s)": f"{mip_res['time']:.2f}",
            "CP Status": cp_res["status"],
            "CP Makespan": cp_res["makespan"],
            "CP Gap %": f"{cp_res['optimality_gap']:.2f}" if cp_res.get('optimality_gap') is not None else "N/A",
            "CP Time (s)": f"{cp_res['time']:.2f}",
            "Makespan Diff %": f"{makespan_diff:.2f}" if makespan_diff is not None else "N/A",
            "Better Solver": better_solver if better_solver else "N/A"
        })
    
    return comparison


def print_comparison_table(comparison_data):
    """Print a formatted comparison table."""
    if not comparison_data:
        logger.info("No comparison data available.")
        return
    
    headers = ["Instance", "MIP Status", "MIP Makespan", "MIP Gap %", "MIP Time (s)", 
               "CP Status", "CP Makespan", "CP Gap %", "CP Time (s)", "Makespan Diff %", "Better Solver"]
    
    # Convert to list of lists for tabulate
    table_data = []
    for row in comparison_data:
        table_data.append([
            row["Instance"],
            row["MIP Status"],
            row["MIP Makespan"] if row["MIP Makespan"] is not None else "N/A",
            row["MIP Gap %"],
            row["MIP Time (s)"],
            row["CP Status"],
            row["CP Makespan"] if row["CP Makespan"] is not None else "N/A",
            row["CP Gap %"],
            row["CP Time (s)"],
            row["Makespan Diff %"],
            row["Better Solver"]
        ])
    
    logger.info("\n" + "=" * 140)
    logger.info("SOLVER COMPARISON TABLE")
    logger.info("=" * 140)
    logger.info("\n" + tabulate(table_data, headers=headers, tablefmt="grid"))
    
    # Summary statistics
    mip_solved = sum(1 for row in comparison_data if row["MIP Makespan"] is not None)
    cp_solved = sum(1 for row in comparison_data if row["CP Makespan"] is not None)
    mip_better = sum(1 for row in comparison_data if row["Better Solver"] == "MIP")
    cp_better = sum(1 for row in comparison_data if row["Better Solver"] == "CP")
    
    logger.info(f"\nComparison Summary:")
    logger.info(f"  Instances solved by MIP: {mip_solved}/{len(comparison_data)}")
    logger.info(f"  Instances solved by CP:  {cp_solved}/{len(comparison_data)}")
    logger.info(f"  MIP better makespan:     {mip_better}")
    logger.info(f"  CP better makespan:      {cp_better}")
    logger.info(f"  Equal makespan:          {len(comparison_data) - mip_better - cp_better}")


def export_results(results, output_file, comparison_data=None):
    """Export results to CSV file."""
    import csv
    
    with open(output_file, 'w', newline='') as csvfile:
        fieldnames = ["instance", "solver", "status", "makespan", "time", "optimal"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for result in results:
            # Create a copy with only the fields we want to export
            export_row = {k: v for k, v in result.items() if k in fieldnames}
            writer.writerow(export_row)
    
    print(f"\nResults exported to {output_file}")
    
    # Export comparison data if available
    if comparison_data:
        comp_file = output_file.replace('.csv', '_comparison.csv')
        with open(comp_file, 'w', newline='') as csvfile:
            if comparison_data:
                writer = csv.DictWriter(csvfile, fieldnames=comparison_data[0].keys())
                writer.writeheader()
                writer.writerows(comparison_data)
        print(f"Comparison data exported to {comp_file}")


def export_results_csv(results, filename="results.csv"):
    """Export results to CSV file."""
    if not results:
        return
    
    with open(filename, 'w', newline='') as csvfile:
        fieldnames = ['instance', 'solver', 'status', 'makespan', 'optimum', 'optimality_gap', 'time', 'optimal', 'schedule_valid', 'timestamp']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for result in results:
            row = {
                'instance': os.path.basename(result.get('instance', '')),
                'solver': result.get('solver', ''),
                'status': result.get('status', ''),
                'makespan': result.get('makespan', ''),
                'optimum': result.get('optimum', ''),
                'optimality_gap': result.get('optimality_gap', ''),
                'time': result.get('time', ''),
                'optimal': result.get('optimal', False),
                'schedule_valid': result.get('schedule_valid', ''),
                'timestamp': datetime.now().isoformat()
            }
            writer.writerow(row)
    
    logger.info(f"  ✓ Results exported to {filename}")


def export_results_json(results, filename="results.json"):
    """Export results to JSON file."""
    if not results:
        return
    
    export_data = {
        'timestamp': datetime.now().isoformat(),
        'total_instances': len(results),
        'results': results
    }
    
    with open(filename, 'w') as jsonfile:
        json.dump(export_data, jsonfile, indent=2, default=str)
    
    logger.info(f"  ✓ Results exported to {filename}")


def extract_schedule_from_mip(prob, n_jobs, jobs):
    """Extract schedule from MIP solution."""
    schedule = []
    for j in range(n_jobs):
        for m, duration in jobs[j]:
            var_name = f"S_{j}_{m}"
            var = prob.variablesDict().get(var_name)
            if var and var.varValue is not None:
                schedule.append({
                    'job': j,
                    'machine': m,
                    'start': var.varValue,
                    'duration': duration,
                    'end': var.varValue + duration
                })
    return schedule


def extract_schedule_from_cp(solver, starts, jobs):
    """Extract schedule from CP solution."""
    schedule = []
    for (j, m), start_var in starts.items():
        duration = next((d for (machine, d) in jobs[j] if machine == m), 0)
        schedule.append({
            'job': j,
            'machine': m,
            'start': solver.Value(start_var),
            'duration': duration,
            'end': solver.Value(start_var) + duration
        })
    return schedule


def plot_gantt_chart(schedule, n_machines, makespan, instance_name, solver_name, output_dir="output"):
    """Generate and save Gantt chart visualization."""
    if not schedule:
        return
    
    # Create output directory structure: output/{instance_name}/
    instance_output_dir = os.path.join(output_dir, instance_name)
    os.makedirs(instance_output_dir, exist_ok=True)
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Extract unique job numbers from schedule
    unique_jobs = sorted(set(s['job'] for s in schedule))
    colors = plt.cm.tab20(np.linspace(0, 1, len(unique_jobs)))
    
    # Plot each operation
    for op in schedule:
        j = op['job']
        m = op['machine']
        start_time = op['start']
        duration = op['duration']
        
        # Create rectangle for the operation
        rect = mpatches.Rectangle(
            (start_time, m - 0.4), 
            duration, 
            0.8,
            facecolor=colors[j % len(colors)],
            edgecolor='black',
            alpha=0.8,
            label=f'Job {j}'
        )
        ax.add_patch(rect)
        
        # Add text label
        ax.text(start_time + duration/2, m, 
                f'J{j}', 
                ha='center', va='center',
                fontsize=8, color='white', fontweight='bold')
    
    # Set up plot
    ax.set_xlabel('Time', fontsize=12)
    ax.set_ylabel('Machine', fontsize=12)
    ax.set_title(f'Gantt Chart - {instance_name} ({solver_name})\nMakespan: {makespan}', fontsize=14)
    
    # Set limits and ticks
    ax.set_xlim(0, makespan * 1.1)
    ax.set_ylim(-0.5, n_machines - 0.5)
    ax.set_yticks(range(n_machines))
    ax.grid(True, alpha=0.3, linestyle='--')
    
    # Create legend
    legend_patches = [mpatches.Patch(color=colors[j % len(colors)], 
                                     label=f'Job {j}', 
                                     alpha=0.8) for j in unique_jobs]
    ax.legend(handles=legend_patches, bbox_to_anchor=(1.05, 1), loc='upper left')
    
    # Adjust layout and save
    plt.tight_layout()
    filename = f"gantt_{instance_name}_{solver_name}.png"
    filepath = os.path.join(instance_output_dir, filename)
    plt.savefig(filepath, dpi=150, bbox_inches='tight')
    plt.close()
    
    logger.info(f"  ✓ Gantt chart saved to {filepath}")


def main():
    """Main entry point for the JSP solver."""
    args = parse_arguments()
    
    # Configure logging based on quiet flag
    if args.quiet:
        logger.setLevel(logging.WARNING)
    else:
        logger.setLevel(logging.INFO)
    
    # Load optimum values from instances.json
    optimum_data = load_optimum_values()
    
    # Get list of instances to solve
    if args.instances:
        instances = args.instances
    else:
        instances = sorted(glob.glob(args.pattern))
        if not instances:
            logger.error(f"Error: No files match pattern '{args.pattern}'")
            return
    
    # Validate instance files exist
    for inst in instances:
        if not os.path.isfile(inst):
            logger.error(f"Error: Instance file not found: {inst}")
            return
    
    logger.info(f"Solving {len(instances)} instance(s)...")
    logger.info(f"Settings: solver={args.solver}, time_limit={args.time_limit}s, gap={args.gap*100:.1f}%")
    logger.info("-" * 80)
    
    all_results = []
    mip_results = []
    cp_results = []
    start_total = time.time()
    
    try:
        # Solve each instance with selected solver(s)
        for idx, inst in enumerate(instances, 1):
            logger.info(f"\n[{idx}/{len(instances)}] Solving: {inst}")
            
            # Solve with MIP if requested
            if args.solver in ["mip", "both"]:
                mip_res = solve_mip_instance(
                    inst,
                    time_limit=args.time_limit,
                    gap=args.gap,
                    verbose=args.verbose,
                    quiet=args.quiet,
                    optimum_data=optimum_data
                )
                mip_results.append(mip_res)
                all_results.append(mip_res)
                

            # Solve with CP if requested
            if args.solver in ["cp", "both"]:
                cp_res = solve_cp_instance(
                    inst,
                    time_limit=args.time_limit,
                    verbose=args.verbose,
                    quiet=args.quiet,
                    optimum_data=optimum_data
                )
                cp_results.append(cp_res)
                all_results.append(cp_res)

        
        # Generate comparison if both solvers were used
        comparison_data = None
        if args.solver == "both" and args.compare:
            comparison_data = compare_solvers(mip_results, cp_results)
            print_comparison_table(comparison_data)
        
                # Generate Gantt charts if requested
        if args.gantt:
            for result in all_results:
                if result.get("schedule") and result.get("makespan"):
                    instance_name = os.path.basename(result["instance"]).replace('.', '_')
                    # Need to get n_machines for the instance
                    n_jobs, n_machines, jobs, p = read_jsplib_instance(result["instance"])
                    plot_gantt_chart(
                        result["schedule"],
                        n_machines,
                        result["makespan"],
                        instance_name,
                        result["solver"],
                        output_dir="output"
                    )
        
        # Export results if requested
        if args.export_csv:
            export_results_csv(all_results, args.export_csv)
        
        if args.export_json:
            export_results_json(all_results, args.export_json)

        # Print summary
        total_elapsed = time.time() - start_total
        
        if args.solver == "both":
            logger.info("\n" + "=" * 80)
            logger.info("SOLVER SUMMARY")
            logger.info("=" * 80)
            
            mip_solved = sum(1 for r in mip_results if r["makespan"] is not None)
            cp_solved = sum(1 for r in cp_results if r["makespan"] is not None)
            mip_optimal = sum(1 for r in mip_results if r["optimal"])
            cp_optimal = sum(1 for r in cp_results if r["optimal"])
            
            logger.info(f"MIP Solver: {mip_solved}/{len(instances)} solved, {mip_optimal} optimal")
            logger.info(f"CP Solver:  {cp_solved}/{len(instances)} solved, {cp_optimal} optimal")
        else:
            solved = sum(1 for r in all_results if r["makespan"] is not None)
            optimal = sum(1 for r in all_results if r["optimal"])
            logger.info(f"\nSolved: {solved}/{len(instances)} instances, {optimal} optimal")
        
        logger.info(f"Total time: {total_elapsed:.2f}s")
        
        # Export results if requested
        if args.output:
            export_results(all_results, args.output, comparison_data)
        
    except KeyboardInterrupt:
        total_elapsed = time.time() - start_total
        logger.warning(f"\n\n⚠ Interrupted by user (Ctrl+C)")
        logger.warning(f"Completed {len(all_results)} instance(s) in {total_elapsed:.2f}s")
        
        if all_results:
            solved = sum(1 for r in all_results if r["makespan"] is not None)
            logger.warning(f"Solved before interruption: {solved}")
        
        sys.exit(1)


if __name__ == "__main__":
    main()