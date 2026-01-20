import argparse
import json
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

def sh(cmd: List[str]) -> str:
    return subprocess.check_output(cmd, text=True)

def parse_jobs_list(raw: str) -> List[Dict[str, Any]]:
    data = json.loads(raw)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("jobs"), list):
        return data["jobs"]
    return []

def job_name_of(j: Dict[str, Any]) -> str:
    return (j.get("settings") or {}).get("name") or j.get("name") or ""

def find_job_id_by_name(name: str) -> Optional[int]:
    raw = sh(["databricks", "jobs", "list", "--output", "json"])
    jobs = parse_jobs_list(raw)

    # exact match
    for j in jobs:
        if job_name_of(j) == name:
            return int(j["job_id"])

    # contains match
    n = name.lower()
    hits = [(job_name_of(j), int(j["job_id"])) for j in jobs if n in job_name_of(j).lower()]

    if len(hits) == 1:
        return hits[0][1]

    if len(hits) > 1:
        print("Multiple jobs matched. Use job_id for stability:")
        for jn, jid in hits[:20]:
            print(f"  - {jn} (job_id={jid})")
        return None

    print(f"Job not found: {name}")
    print("First jobs visible (name -> job_id):")
    for j in jobs[:20]:
        print(f"  - {job_name_of(j)} -> {j.get('job_id')}")
    return None

def run_now(job_id: int) -> int:
    out = sh(["databricks", "jobs", "run-now", str(job_id), "--output", "json"])
    data = json.loads(out)
    return int(data["run_id"])

def get_run(run_id: int) -> Dict[str, Any]:
    # NEW CLI: jobs get-run
    out = sh(["databricks", "jobs", "get-run", str(run_id), "--output", "json"])
    return json.loads(out)

def wait_run(run_id: int) -> None:
    while True:
        r = get_run(run_id)
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
    ap.add_argument("job", help="Job name OR job_id (digits)")
    ap.add_argument("--wait", action="store_true")
    args = ap.parse_args()

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
