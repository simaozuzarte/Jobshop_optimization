# SAAD Project - Job Shop Scheduling Problem Solver

A hybrid solver for the **Job Shop Scheduling Problem (JSP)** using Python, implementing both Mixed Integer Programming (MIP) and Constraint Programming (CP) approaches. This project minimizes the makespan (total completion time) for scheduling jobs across multiple machines.


## Table of Contents

- [Overview](#overview)
- [Problem Description](#problem-description)
- [Project Structure](#project-structure)
- [Installation](#installation)
- [Usage](#usage)
- [Instance Format](#instance-format)
- [Mathematical Model](#mathematical-model)
- [Benchmark Instances](#benchmark-instances)
- [TODOs](#todos)
- [Authors](#authors)


## Overview

This project implements **dual solvers** for the classic Job Shop Scheduling Problem:

1. **MIP Solver**: Uses the [PuLP](https://coin-or.github.io/pulp/) library with the CBC (COIN-OR) solver
2. **CP-SAT Solver**: Uses Google's [OR-Tools](https://developers.google.com/optimization) CP-SAT solver

The solvers read benchmark instances from the JSPLIB library and find optimal or near-optimal schedules. Results from both approaches can be compared to identify strengths/weaknesses of each method.


## Problem Description

The **Job Shop Scheduling Problem (JSP)** is a combinatorial optimization problem where:

- There are **n jobs** to be processed on **m machines**
- Each job consists of a sequence of operations that must be performed in a specific order
- Each operation requires a specific machine for a given duration
- Each machine can process only one operation at a time
- The goal is to **minimize the makespan** (the time when all jobs are completed)


## Project Structure

```
PROJ_SAAD/
├── README.md                 # This file
├── jsp_solver.py             # Main dual solver (MIP + CP-SAT)
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

## Installation

### Pre-requisites

- **Python 3.12 or lower** (Required for OR-Tools compatibility. OR-Tools does not support Python 3.13+)
- pip package manager

### Install Dependencies

```bash
pip install pulp matplotlib tabulate numpy
pip install --no-cache-dir "ortools==9.8.3296"
```

This installs:
- **PuLP**: MIP modeling and optimization interface
- **OR-Tools**: CP-SAT solver and utilities
- **Matplotlib & NumPy**: Gantt chart visualization
- **Tabulate**: Pretty-printed tables


## Usage

### Quick Start

The solver uses **command-line arguments** to specify which instances to solve and how to configure the solver. You must provide either `-i` (specific files) or `-p` (pattern matching).

### Basic Commands

```bash
# Solve a single instance with both solvers
python jsp_solver.py -i JSPLIB/instances/abz5

# Solve multiple specific instances
python jsp_solver.py -i JSPLIB/instances/abz5 JSPLIB/instances/ft06 JSPLIB/instances/la01

# Solve all instances matching a pattern (use quotes)
python jsp_solver.py -p "JSPLIB/instances/la*"

# Solve with only MIP solver
python jsp_solver.py -p "JSPLIB/instances/ft*" --solver mip

# Solve with only CP-SAT solver
python jsp_solver.py -p "JSPLIB/instances/ft*" --solver cp

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

# Generate comparison table when using both solvers
python jsp_solver.py -p "JSPLIB/instances/ft*" --compare

# Generate Gantt charts for solutions
python jsp_solver.py -i JSPLIB/instances/abz5 --gantt

# Export results to CSV
python jsp_solver.py -p "JSPLIB/instances/la*" --export-csv results.csv

# Export results to JSON
python jsp_solver.py -p "JSPLIB/instances/la*" --export-json results.json

# Combine multiple options
python jsp_solver.py -p "JSPLIB/instances/ft*" -t 120 -g 0.05 --solver both --compare --gantt
```

### Command-Line Arguments

| Argument | Short | Description | Default |
|----------|-------|-------------|---------|
| `--instances` | `-i` | List of instance file paths | Required* |
| `--pattern` | `-p` | Glob pattern to match files (e.g., `"la*"`) | Required* |
| `--solver` | `-s` | Solver to use: `mip`, `cp`, or `both` | `both` |
| `--time-limit` | `-t` | Max seconds per instance | 300 |
| `--gap` | `-g` | MIP gap tolerance (0.1 = 10%) | 0.1 |
| `--compare` | `-c` | Generate comparison table (requires `--solver both`) | False |
| `--gantt` | - | Generate Gantt chart visualizations | False |
| `--export-csv` | - | Export results to CSV file | - |
| `--export-json` | - | Export results to JSON file | - |
| `--verbose` | `-v` | Show detailed solver output | False |
| `--quiet` | `-q` | Suppress progress messages | False |
| `--help` | `-h` | Display help message | - |

\* Either `-i` or `-p` is required (mutually exclusive)

### How It Works

1. **Reading**: The solver reads JSPLIB instance files and parses job/machine data
2. **Model Building**: Constructs a model (MIP or CP-SAT) with:
   - Decision variables for start times and job sequencing
   - Constraints for job precedence and machine capacity
   - Objective to minimize makespan
3. **Solving**: Calls the selected solver (CBC for MIP, OR-Tools CP-SAT for CP) with specified time/gap limits
4. **Reporting**: Outputs status, makespan, runtime, and optional visualizations/exports

### Output Format

#### Default Mode (both solvers)
Shows progress for each instance with individual solver outputs:

```
Solving 2 instance(s)...
Settings: solver=both, time_limit=300s, gap=10.0%
--------------------------------------------------------------------------------

[1/2] Solving: JSPLIB/instances/abz5
Model: 150 variables, 300 constraints

  [MIP] Reading instance and building model from JSPLIB/instances/abz5
  [MIP] Solving with CBC (time limit: 300s, gap: 10.0%)...
  ✓ [MIP] Finished in 45.23s | Status: Optimal | Makespan: 1234.00 | Optimum: 1234.00 | Gap: 0.00%

  [CP] Reading instance and building model from JSPLIB/instances/abz5
  [CP] Solving with OR-Tools CP-SAT (time limit: 300s)...
  ✓ [CP] Finished in 23.45s | Status: Optimal | Makespan: 1234.00 | Optimum: 1234.00 | Gap: 0.00%

[2/2] Solving: JSPLIB/instances/ft06
Model: 112 variables, 186 constraints

  [MIP] Reading instance and building model from JSPLIB/instances/ft06
  [MIP] Solving with CBC (time limit: 300s, gap: 10.0%)...
  ✓ [MIP] Finished in 2.15s | Status: Optimal | Makespan: 55.00 | Optimum: 55.00 | Gap: 0.00%

  [CP] Reading instance and building model from JSPLIB/instances/ft06
  [CP] Solving with OR-Tools CP-SAT (time limit: 300s)...
  ✓ [CP] Finished in 1.82s | Status: Optimal | Makespan: 55.00 | Optimum: 55.00 | Gap: 0.00%

================================================================================
SOLVER SUMMARY
================================================================================
MIP Solver: 2/2 solved, 2 optimal
CP Solver:  2/2 solved, 2 optimal
Total time: 73.65s
```

#### With Comparison Table (`--compare`)
Displays a detailed comparison between MIP and CP-SAT solvers with optimality gaps:

```
| Instance | MIP Status | MIP Makespan | MIP Gap % | MIP Time (s) | CP Status | CP Makespan | CP Gap % | CP Time (s) | Makespan Diff % | Better Solver |
|----------|-----------|--------------|-----------|-------------|----------|------------|---------|------------|-----------------|---------------|
| abz5     | Optimal    | 1234         | 0.00      | 45.23       | Optimal  | 1234       | 0.00    | 23.45      | 0.00            | Equal         |
| ft06     | Optimal    | 55           | 0.00      | 2.15        | Optimal  | 55         | 0.00    | 1.82       | 0.00            | Equal         |
```

#### MIP-Only Mode (`--solver mip`)
Shows only MIP solver progress and results.

#### CP-Only Mode (`--solver cp`)
Shows only CP-SAT solver progress and results.

#### Quiet Mode (`--quiet`)
Suppresses all progress output, showing only the final summary.

#### Verbose Mode (`--verbose`)
Shows detailed solver logs including search tree progress, cuts, and branching decisions.

### Result Fields

Each result record contains:
- **`instance`**: Path to the instance file
- **`solver`**: Solver used (`MIP` or `CP`)
- **`status`**: Solver status (Optimal, Feasible, Infeasible, Unknown)
- **`makespan`**: Objective value (total completion time), or `None` if unsolved
- **`time`**: Wall-clock time in seconds
- **`optimal`**: Boolean indicating if solution is proven optimal
- **`optimum`**: Known optimum value from instances.json (if available)
- **`optimality_gap`**: Gap from optimum: `(found - optimum) / optimum × 100%` (if optimum is known)
- **`schedule`**: List of operations with start times and durations (if solved)
- **`schedule_valid`**: Boolean indicating if schedule passed validation
- **`validation_violations`**: List of constraint violations (if validation failed)

### Output Files

When using export options:

#### CSV Export (`--export-csv results.csv`)
Exports results in tabular format with columns: instance, solver, status, makespan, optimum, optimality_gap, time, optimal, schedule_valid

#### JSON Export (`--export-json results.json`)
Exports full results including complete schedule details in JSON format

#### Gantt Charts (`--gantt`)
Generates PNG visualizations of the schedule for each solved instance, saved to `output/` directory

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


## Instance Format

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


## Mathematical Model

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


## Benchmark Instances

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


## ✅ TODOs

- [x] **Rename `test.py` → `jsp_solver.py`** - More descriptive name
- [x] **Add command-line argument parsing** - Use `argparse` to specify instances, time limits, etc.
- [x] **Improve Big-M calculation** - Currently hardcoded as 10000; should be computed dynamically
- [x] **Add solution validation** - Verify that the solution respects all constraints
- [x] **Export schedule visualization** - Generate Gantt charts for the solution

### Medium Priority
- [x] **Add logging module** - Replace `print()` with proper logging
- [x] **Load optimum values from `instances.json`** - Compare solver results with known optima
- [x] **Calculate optimality gap** - Report `(found - optimum) / optimum × 100%`
- [x] **Save results to CSV/JSON** - Export batch results for analysis
- [x] **Add solution extraction** - Output the actual schedule (start times per operation)

### Low Priority / Enhancements
- [ ] **Implement warm-start** - Use heuristic solutions (e.g., SPT, LPT) as initial solution
- [ ] **Add alternative solvers** - Support Gurobi, CPLEX, or HiGHS
- [ ] **Implement valid inequalities** - Add cuts to strengthen the formulation
- [ ] **Add unit tests** - Test parsing, model building, and solving
- [ ] **Create configuration file** - YAML/JSON config for solver parameters
- [ ] **Add progress callback** - Report intermediate solutions during solving
- [ ] **Parallelize solving** - Solve multiple instances concurrently


## Authors

- Daniel Dória Pinto - up202108808@up.pt
- Leonor Filipe - up202204354@up.pt  
- Simão Zuzarte Bernardo - up202502529@up.pt
