import time
import argparse
import os
import glob
import sys
# Install on terminal: python -m pip install pulp
from pulp import LpProblem, LpMinimize, LpBinary, lpSum, PULP_CBC_CMD, LpVariable, LpStatus


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
            m = numbers[i]-1
            d = numbers[i+1]
            job_pairs.append((m, d))
            p[(j, m)] = d

        jobs.append(job_pairs)

    return n_jobs, n_machines, jobs, p

#Function to build MIP model
def build_mip_model(n_jobs, n_machines, jobs, p):
    prob = LpProblem("JSP_MIP", LpMinimize)

    # Start times
    S = {
        (j, m): LpVariable(f"S_{j}_{m}", lowBound=0)
        for j in range(n_jobs)
        for m, _ in jobs[j]
    }
    M = 10000

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
    C_max = LpVariable("C_max", lowBound=0)
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

    return prob, C_max



# Function to solve a single instance
def solve_instance(file_path, time_limit=300, gap=0.1, verbose=True, quiet=False):
    """Solve a single JSP instance and return results."""
    if not quiet:
        print(f"  → Reading instance and building model...", flush=True)
    
    n_jobs, n_machines, jobs, p = read_jsplib_instance(file_path)
    prob, C_max = build_mip_model(n_jobs, n_machines, jobs, p)

    if not quiet:
        # Count constraints and variables for progress info
        n_vars = len(prob.variables())
        n_constraints = len(prob.constraints)
        print(f"  → Model: {n_vars} variables, {n_constraints} constraints", flush=True)
        print(f"  → Solving with CBC (time limit: {time_limit}s, gap: {gap*100:.1f}%)...", flush=True)

    solver = PULP_CBC_CMD(msg=verbose, timeLimit=time_limit, gapRel=gap)

    start = time.time()
    prob.solve(solver)
    runtime = time.time() - start

    status = LpStatus[prob.status]
    makespan = C_max.varValue if status in ["Optimal", "Feasible"] else None

    if not quiet:
        print(f"  ✓ Finished in {runtime:.2f}s", flush=True)

    return {
        "instance": file_path,
        "status": status,
        "makespan": makespan,
        "time": runtime
    }


def main():
    """Main entry point for the JSP solver."""
    args = parse_arguments()
    
    # Get list of instances to solve
    if args.instances:
        instances = args.instances
    else:
        instances = sorted(glob.glob(args.pattern))
        if not instances:
            print(f"Error: No files match pattern '{args.pattern}'")
            return
    
    # Validate instance files exist
    for inst in instances:
        if not os.path.isfile(inst):
            print(f"Error: Instance file not found: {inst}")
            return
    
    if not args.quiet:
        print(f"Solving {len(instances)} instance(s)...")
        print(f"Settings: time_limit={args.time_limit}s, gap={args.gap*100:.1f}%")
        print("-" * 60)
    
    results = []
    start_total = time.time()
    
    try:
        # Solve each instance and store results
        for idx, inst in enumerate(instances, 1):
            if not args.quiet:
                print(f"\n[{idx}/{len(instances)}] Solving: {inst}")
            
            res = solve_instance(
                inst,
                time_limit=args.time_limit,
                gap=args.gap,
                verbose=args.verbose,
                quiet=args.quiet
            )
            results.append(res)
            
            if not args.quiet:
                print(f"  Result: {res}")
            else:
                print(res)
        
        # Print summary
        if not args.quiet and len(instances) > 1:
            total_elapsed = time.time() - start_total
            print("\n" + "=" * 60)
            print("SUMMARY")
            print("=" * 60)
            solved = sum(1 for r in results if r["status"] in ["Optimal", "Feasible"])
            print(f"Solved: {solved}/{len(results)}")
            print(f"Total time: {total_elapsed:.2f}s")
            
    except KeyboardInterrupt:
        total_elapsed = time.time() - start_total
        print(f"\n\n⚠ Interrupted by user (Ctrl+C)")
        print(f"Completed {len(results)}/{len(instances)} instance(s) in {total_elapsed:.2f}s")
        
        if results:
            solved = sum(1 for r in results if r["status"] in ["Optimal", "Feasible"])
            print(f"Solved before interruption: {solved}/{len(results)}")
        
        sys.exit(1)


if __name__ == "__main__":
    main()
