
import time
#install on terminal python -m pip install pulp
from pulp import LpProblem, LpMinimize, LpBinary, lpSum, PULP_CBC_CMD, LpVariable, LpStatus

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



#Function to solve a single instance
def solve_instance(file_path):
    n_jobs, n_machines, jobs, p = read_jsplib_instance(file_path)
    prob, C_max = build_mip_model(n_jobs, n_machines, jobs, p)

    solver = PULP_CBC_CMD(msg=True, timeLimit=300, gapRel=0.1)  # increase time limit

    start = time.time()
    prob.solve(solver)
    runtime = time.time() - start

    status = LpStatus[prob.status]
    makespan = C_max.varValue if status in ["Optimal", "Feasible"] else None

    return {
        "instance": file_path,
        "status": status,
        "makespan": makespan,
        "time": runtime
    }


#Loop to solve multiple instances
instances = [
    "JSPLIB/instances/abz5",
    
    
]

results = []

#Solve each instance and store results
for inst in instances:
    res = solve_instance(inst)
    results.append(res)
    print(res)
