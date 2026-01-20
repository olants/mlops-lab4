import argparse
import json
import os
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

def sh(cmd: List[str]) -> str:
    return subprocess.check_output(cmd, text=True)

def parse_jobs_list(raw: str) -> List[Dict[str, Any]]:
    """
    Handles both:
      - JSON array: [ {job}, ... ]
      - JSON object: { "jobs": [ {job}, ... ] }
    """
    data = json.loads(raw)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("jobs"), list):
        return data["jobs"]
    # fallback: unknown shape
    return []

def job_name_of(j: Dict[str, Any]) -> str:
    return (j.get("settings") or {}).get("name") or j.get("name") or ""

def find_job_id_by_name(name: str) -> Optional[int]:
    raw = sh(["databricks", "jobs", "list", "--output", "json"])
    jobs = parse_jobs_list(raw)

    # 1) exact match
    for j in jobs:
        if job_name_of(j) == name:
            return int(j.get("job_id") or j.get("job_id", 0))

    # 2) case-insensitive "contains"
    n = name.lower()
    candidates = []
    for j in jobs:
        jn = job_name_of(j)
        if n in jn.lower():
            candidates.append((jn, int(j.get("job_id"))))

    if len(candidates) == 1:
        return candidates[0][1]

    if len(candidates) > 1:
        print("Multiple jobs matched. Please use JOB_ID for stability or pick exact name:")
        for jn, jid in candidates[:20]:
            print(f"  - {jn} (job_id={jid})")
        return None

    # nothing found
    print(f"Job not found: {name}")
    print("Here are the first jobs I can see (name -> job_id):")
    for j in jobs[:20]:
        jn = job_name_of(j)
        jid = j.get("job_id")
        print(f"  - {jn} -> {jid}")
    return None

def run_now(job_id: int) -> int:
    out = sh(["databricks", "jobs", "run-now", str(job_id), "--output", "json"])
    data = json.loads(out)
    if "run_id" not in data:
        raise SystemExit(f"Unexpected run-now response: {data}")
    return int(data["run_id"])

def wait_run(run_id: int) -> None:
    while True:
        out = sh(["databricks", "runs", "get", str(run_id), "--output", "json"])
        r = json.loads(out)
        state = r.get("state", {})
        life = state.get("life_cycle_state")
        result = state.get("result_state")
        msg = state.get("state_message", "")

        print(f"run_id={run_id} life={life} result={result} msg={msg[:160]}")

        if life in ("TERMINATED", "SKIPPED", "INTERNAL_ERROR"):
            if result == "SUCCESS":
                return
            raise SystemExit(f"Run failed: result={result} msg={msg}")

        time.sleep(15)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("job", help="Job name OR job_id")
    ap.add_argument("--wait", action="store_true")
    args = ap.parse_args()

    # Allow passing numeric job_id directly
    job_id: Optional[int] = None
    if args.job.isdigit():
        job_id = int(args.job)
    else:
        job_id = find_job_id_by_name(args.job)

    if not job_id:
        sys.exit(1)

    run_id = run_now(job_id)
    print(f"Triggered job_id={job_id} run_id={run_id}")

    if args.wait:
        wait_run(run_id)
        print("SUCCESS")
