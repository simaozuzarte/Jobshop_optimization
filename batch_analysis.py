"""
Comprehensive batch test runner with results analysis
Generates representative results across JSPLIB families
"""
import subprocess
import csv
import json
import os
from datetime import datetime

test_instances = [
    ("ft06", 6, 6),
    ("ft10", 10, 10),
    ("abz5", 10, 10),
    ("la01", 10, 5),
    ("la10", 20, 5),
    ("ta01", 15, 15),
]

print("=" * 80)
print("JSP SOLVER - COMPREHENSIVE BATCH TEST")
print("=" * 80)
print(f"Test Date: {datetime.now().isoformat()}")
print(f"Instances: {len(test_instances)}")
print()

results = []

for instance_name, n_jobs, n_machines in test_instances:
    instance_path = f"JSPLIB/instances/{instance_name}"
    
    if not os.path.exists(instance_path):
        print(f"[SKIP] {instance_name} - file not found")
        continue
    
    print(f"[{instance_name}] Testing {n_jobs}x{n_machines} instance...", end=" ", flush=True)
    
    try:
        cmd = [
            "python", "jsp_solver.py",
            "-i", instance_path,
            "--solver", "both",
            "--time-limit", "120",
            "--quiet"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            print("OK")
            results.append({
                "instance": instance_name,
                "n_jobs": n_jobs,
                "n_machines": n_machines,
                "status": "completed"
            })
        else:
            print(f"ERROR (code {result.returncode})")
            
    except subprocess.TimeoutExpired:
        print("TIMEOUT")
    except Exception as e:
        print(f"EXCEPTION: {e}")

print()
print("=" * 80)
print(f"Completed: {len([r for r in results if r['status'] == 'completed'])}/{len(test_instances)}")
print("=" * 80)

# Save raw results
with open("output/test_batch_summary.json", "w") as f:
    json.dump(results, f, indent=2)

print("\nResults saved to output/test_batch_summary.json")
