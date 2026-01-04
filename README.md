# PROJ_SAAD - Job Shop Scheduling Problem Solver

A Mixed Integer Programming (MIP) solver for the **Job Shop Scheduling Problem (JSP)** using Python and PuLP. This project minimizes the makespan (total completion time) for scheduling jobs across multiple machines.

<br>

## 📋 Table of Contents

- [Overview](#overview)
- [Problem Description](#problem-description)
- [Project Structure](#project-structure)
- [Installation](#installation)
- [Usage](#usage)
- [Instance Format](#instance-format)
- [Mathematical Model](#mathematical-model)
- [Benchmark Instances](#benchmark-instances)
- [TODOs](#todos)
- [References](#references)

<br>

## 🎯 Overview

This project implements a **MIP-based solver** for the classic Job Shop Scheduling Problem using the [PuLP](https://coin-or.github.io/pulp/) library with the CBC solver. It reads benchmark instances from the JSPLIB library and finds optimal or near-optimal schedules.

<br>

## 📝 Problem Description

The **Job Shop Scheduling Problem (JSP)** is a combinatorial optimization problem where:

- There are **n jobs** to be processed on **m machines**
- Each job consists of a sequence of operations that must be performed in a specific order
- Each operation requires a specific machine for a given duration
- Each machine can process only one operation at a time
- The goal is to **minimize the makespan** (the time when all jobs are completed)

<br>

## 📁 Project Structure

```
PROJ_SAAD/
├── README.md                 # This file
├── jsp_solver.py             # Main MIP solver (currently test.py)
└── JSPLIB/                   # Benchmark instance library
    ├── instances.json        # Metadata for all instances (optimum values, bounds)
    ├── README.md             # JSPLIB documentation
    ├── instances/            # Instance files (130+ benchmarks)
    │   ├── abz5-9            # Adams, Balas, Zawack instances
    │   ├── ft06, ft10, ft20  # Fisher-Thompson instances
    │   ├── la01-40           # Lawrence instances
    │   ├── orb01-10          # Applegate-Cook instances
    │   ├── swv01-20          # Storer et al. instances
    │   ├── ta01-80           # Taillard instances
    │   └── yn1-4             # Yamada-Nakano instances
    └── script/               # Helper scripts for loading instances
```
<br>

## ⚙️ Installation

### Prerequisites

- **Python 3.12 or lower** (Required for OR-Tools compatibility. OR-Tools does not support Python 3.13+)
- pip package manager

### Install Dependencies

```bash
pip install pulp
pip install ortools
```

<br>

## 🚀 Usage

### Quick Start

The solver uses **command-line arguments** to specify which instances to solve and how to configure the solver. You must provide either `-i` (specific files) or `-p` (pattern matching).

### Basic Commands

```bash
# Solve a single instance
python jsp_solver.py -i JSPLIB/instances/abz5

# Solve multiple specific instances
python jsp_solver.py -i JSPLIB/instances/abz5 JSPLIB/instances/ft06 JSPLIB/instances/la01

# Solve all instances matching a pattern (use quotes)
python jsp_solver.py -p "JSPLIB/instances/la*"

# Solve ALL instances (warning: 130+ files, takes hours!)
python jsp_solver.py -p "JSPLIB/instances/*"
```

### Advanced Options

```bash
# Adjust time limit per instance (in seconds)
python jsp_solver.py -i JSPLIB/instances/abz5 -t 60

# Set tighter optimality gap (5% instead of default 10%)
python jsp_solver.py -i JSPLIB/instances/abz5 -g 0.05

# Show detailed solver output during optimization
python jsp_solver.py -i JSPLIB/instances/abz5 --verbose

# Minimal output mode (only final results)
python jsp_solver.py -i JSPLIB/instances/abz5 --quiet

# Combine multiple options
python jsp_solver.py -p "JSPLIB/instances/ft*" -t 120 -g 0.05 --verbose
```

### Command-Line Arguments

| Argument | Short | Description | Default |
|----------|-------|-------------|---------|
| `--instances` | `-i` | List of instance file paths | Required* |
| `--pattern` | `-p` | Glob pattern to match files (e.g., `"la*"`) | Required* |
| `--time-limit` | `-t` | Max seconds per instance | 300 |
| `--gap` | `-g` | MIP gap tolerance (0.1 = 10%) | 0.1 |
| `--verbose` | `-v` | Show CBC solver output | False |
| `--quiet` | `-q` | Suppress progress messages | False |
| `--help` | `-h` | Display help message | - |

\* Either `-i` or `-p` is required (mutually exclusive)

### How It Works

1. **Reading**: The solver reads JSPLIB instance files and parses job/machine data
2. **Model Building**: Constructs a Mixed Integer Programming model with:
   - Decision variables for start times and job sequencing
   - Constraints for job precedence and machine capacity
   - Objective to minimize makespan
3. **Solving**: Calls the CBC solver with specified time/gap limits
4. **Reporting**: Outputs status, makespan, and runtime

### Output Format

#### Standard Mode (default)
Shows progress for each instance with real-time updates:

```
Solving 2 instance(s)...
Settings: time_limit=300s, gap=10.0%
------------------------------------------------------------

[1/2] Solving: JSPLIB/instances/abz5
  → Reading instance and building model...
  → Model: 150 variables, 300 constraints
  → Solving with CBC (time limit: 300s, gap: 10.0%)...
  ✓ Finished in 45.23s
  Result: {'instance': 'JSPLIB/instances/abz5', 'status': 'Optimal', 'makespan': 1234.0, 'time': 45.23}

[2/2] Solving: JSPLIB/instances/ft06
  → Reading instance and building model...
  → Model: 42 variables, 84 constraints
  → Solving with CBC (time limit: 300s, gap: 10.0%)...
  ✓ Finished in 2.15s
  Result: {'instance': 'JSPLIB/instances/ft06', 'status': 'Optimal', 'makespan': 55.0, 'time': 2.15}

============================================================
SUMMARY
============================================================
Solved: 2/2
Total time: 47.38s
```

#### Quiet Mode (`--quiet`)
Only prints final results (one per line):

```
{'instance': 'JSPLIB/instances/abz5', 'status': 'Optimal', 'makespan': 1234.0, 'time': 45.23}
{'instance': 'JSPLIB/instances/ft06', 'status': 'Optimal', 'makespan': 55.0, 'time': 2.15}
```

#### Verbose Mode (`--verbose`)
Shows CBC solver log with search tree progress, cuts, and branching decisions.

### Result Fields

Each result dictionary contains:
- **`instance`**: Path to the instance file
- **`status`**: Solver status (Optimal, Feasible, Infeasible, Not Solved, Undefined)
- **`makespan`**: Objective value (total completion time), or `None` if unsolved
- **`time`**: Wall-clock time in seconds

### Interrupting Execution

Press **Ctrl+C** to gracefully stop execution. The solver will:
- Display how many instances were completed
- Show total elapsed time
- Report partial results

```
^C
⚠ Interrupted by user (Ctrl+C)
Completed 3/10 instance(s) in 145.67s
Solved before interruption: 2/3
```

<br>

## 📄 Instance Format

Instance files follow the JSPLIB standard format:

```
<number_of_jobs> <number_of_machines>
<machine_0> <duration_0> <machine_1> <duration_1> ...  # Job 0
<machine_0> <duration_0> <machine_1> <duration_1> ...  # Job 1
...
```

**Example** (3 jobs, 3 machines):
```
3 3
0 3 1 2 2 2    # Job 0: M0(3) → M1(2) → M2(2)
0 2 2 1 1 4    # Job 1: M0(2) → M2(1) → M1(4)
1 4 2 3 0 1    # Job 2: M1(4) → M2(3) → M0(1)
```

<br>

## 🔢 Mathematical Model

### Decision Variables

- $S_{j,m}$ : Start time of job $j$ on machine $m$
- $x_{i,j,m}$ : Binary variable (1 if job $i$ precedes job $j$ on machine $m$)
- $C_{max}$ : Makespan (objective to minimize)

### Objective Function

$$\min C_{max}$$

### Constraints

1. **Job Precedence**: Operations within a job must follow their prescribed order
   $$S_{j,m_2} \geq S_{j,m_1} + p_{j,m_1}$$

2. **Machine Capacity**: No two jobs can use the same machine simultaneously
   $$S_{i,m} + p_{i,m} \leq S_{j,m} + M(1 - x_{i,j,m})$$
   $$S_{j,m} + p_{j,m} \leq S_{i,m} + M \cdot x_{i,j,m}$$

3. **Makespan Definition**: 
   $$C_{max} \geq S_{j,m_{last}} + p_{j,m_{last}} \quad \forall j$$

<br>

## 📊 Benchmark Instances

The JSPLIB library includes **130+ benchmark instances** from the literature:

| Series | Count | Size Range | Source |
|--------|-------|------------|--------|
| ABZ    | 5     | 10×10 to 20×15 | Adams et al. (1988) |
| FT     | 3     | 6×6 to 20×5 | Fisher & Thompson (1963) |
| LA     | 40    | 10×5 to 30×10 | Lawrence (1984) |
| ORB    | 10    | 10×10 | Applegate & Cook (1991) |
| SWV    | 20    | 20×10 to 50×10 | Storer et al. (1992) |
| TA     | 80    | 15×15 to 100×20 | Taillard (1993) |
| YN     | 4     | 20×20 | Yamada & Nakano (1992) |

Check `JSPLIB/instances.json` for known optimum values and bounds.

<br>

## ✅ TODOs

- [x] **Rename `test.py` → `jsp_solver.py`** - More descriptive name
- [x] **Add command-line argument parsing** - Use `argparse` to specify instances, time limits, etc.
- [ ] **Improve Big-M calculation** - Currently hardcoded as 10000; should be computed dynamically
- [ ] **Add solution validation** - Verify that the solution respects all constraints
- [x] **Export schedule visualization** - Generate Gantt charts for the solution

### Medium Priority
- [ ] **Add logging module** - Replace `print()` with proper logging
- [ ] **Load optimum values from `instances.json`** - Compare solver results with known optima
- [ ] **Calculate optimality gap** - Report `(found - optimum) / optimum × 100%`
- [x] **Save results to CSV/JSON** - Export batch results for analysis
- [ ] **Add solution extraction** - Output the actual schedule (start times per operation)

### Low Priority / Enhancements
- [ ] **Implement warm-start** - Use heuristic solutions (e.g., SPT, LPT) as initial solution
- [ ] **Add alternative solvers** - Support Gurobi, CPLEX, or HiGHS
- [ ] **Implement valid inequalities** - Add cuts to strengthen the formulation
- [ ] **Add unit tests** - Test parsing, model building, and solving
- [ ] **Create configuration file** - YAML/JSON config for solver parameters
- [ ] **Add progress callback** - Report intermediate solutions during solving
- [ ] **Parallelize solving** - Solve multiple instances concurrently

<br>

## 📚 References

1. Adams, J., Balas, E., Zawack, D. (1988). "The shifting bottleneck procedure for job shop scheduling." *Management Science*, 34(3), 391-401.
2. Muth, J.F., Thompson, G.L. (1963). *Industrial Scheduling*. Prentice-Hall.
3. Lawrence, S. (1984). "Resource constrained project scheduling." Carnegie-Mellon University.
4. Applegate, D., Cook, W. (1991). "A computational study of job-shop scheduling." *ORSA Journal on Computing*, 3(2), 149-156.
5. Taillard, E. (1993). "Benchmarks for basic scheduling problems." *European Journal of Operational Research*, 64(2), 278-285.

<br>

## 👤 Authors

Daniel Dória Pinto - up202108808@up.pt
Leonor Filipe - up202204354@up.pt  
Simão Zuzarte Bernardo - up202502529@up.pt
