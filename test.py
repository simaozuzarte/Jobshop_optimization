#install on terminal python -m pip install pulp
from pulp import LpProblem, LpMinimize, LpBinary, lpSum, PULP_CBC_CMD, LpVariable

#data definition
jobs = []
p={}
file_path = "abz5.txt"
with open (file_path, "r") as file:
    lines = [l.strip() for l in file if not l.startswith("#")]
    
    # first line: dimensions
    n_jobs, n_machines = map(int, lines[0].split())
    
    # Remaining lines: jobs
    job_lines = lines[1:]
    
    
    #for each job a line 
    for j, line in enumerate(job_lines):
        #dividing the line in int number
        numbers = list(map(int, line.split()))
        
        #creating pair lists (machine, duration)
        job_pairs = []
        for i in range(0, len(numbers), 2) :
            machine = numbers[i]
            duration = numbers[i+1]
            job_pairs.append((machine,duration))

            #save on a dictionary
            p[(j, machine)] = duration
        
        jobs.append(job_pairs)

print(p)


#Creating the model 

#type of problem
prob = LpProblem("", LpMinimize)

#2 a)
#initial time variables S[j,m]
S = {}
for j in range(n_jobs):
    for machine,duration in jobs[j]:
        S[(j, machine)] = LpVariable(f"S_{j}_{machine}", lowBound = 0, cat = 'Continuous')

#2 b)
x = {}
M = 10000
for m in range(n_machines):
    jobs_on_m = [j for j in range(n_jobs) if any (machine==m for machine,_ in jobs[j])]
    for i in jobs_on_m:
        for j in jobs_on_m:
            if i < j:
                x[(i,j,m)] = LpVariable(f"x_{i}_{j}_{m}", cat = LpBinary)

#3 Objective function: minimize makespan
C_max = LpVariable("C_max", lowBound = 0, cat='Continuous')
prob += C_max

#4 Restrictions

#a) Precedence within each job

for j in range (n_jobs):
    job_seq = jobs[j]
    for k in range(len(job_seq)-1):
        m_curr, p_curr = job_seq[k]
        m_next, _ = job_seq[k+1]
        prob += S[(j, m_next)] >= S[(j, m_curr)]+ p_curr

#b) Job Sequence in each machine
for m in range(n_machines):
    jobs_on_m = [j for j in range(n_jobs) if any(machine==m for machine,_ in jobs[j])]
    for i in jobs_on_m:
        for j in jobs_on_m:
            if i < j:
                p_i_m = p[(i,m)]
                p_j_m = p[(j,m)]
                prob += S[(i,m)] + p_i_m <= S[(j,m)] + M*(1-x[(i,j,m)])
                prob += S[(j,m)] + p_j_m <= S[(i,m)] + M*(x[(i,j,m)])

#c) Makespan
for j in range(n_jobs):
    last_machine, last_duration = jobs[j][-1]
    prob += C_max >= S[(j, last_machine)] + last_duration

#5 Solve model
solver = PULP_CBC_CMD(msg=1, timeLimit=300)
prob.solve(solver)

#6 Show Results
print("Status:", prob.status)
print("Makespan:", C_max.varValue)

for j in range(n_jobs):
    for m,d in jobs[j]:
        print(f"Job {j}, Machine {m}, Start: {S[(j,m)].varValue}, Duration: {d}")
            

