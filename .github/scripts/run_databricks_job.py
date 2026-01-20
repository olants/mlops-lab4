import argparse
import json
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

def run_cmd(cmd: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def sh_json(cmd: List[str]) -> Dict[str, Any]:
    p = run_cmd(cmd)
    if p.returncode != 0:
        print("COMMAND FAILED:", " ".join(cmd))
        if p.stdout.strip():
            print("STDOUT:\n", p.stdout)
        if p.stderr.strip():
            print("STDERR:\n", p.stderr)
        # Try best-effort parse of JSON from stdout/stderr
        for blob in (p.stdout, p.stderr):
            blob = (blob or "").strip()
            if blob.startswith("{") and blob.endswith("}"):
                try:
                    j = json.loads(blob)
                    print("PARSED ERROR JSON:\n", json.dumps(j, indent=2))
                except Exception:
                    pass
        sys.exit(p.returncode)

    out = p.stdout.strip()
    try:
        return json.loads(out) if out else {}
    except Exception:
        print("Expected JSON but got:\n", out)
        sys.exit(1)

def parse_jobs_list(data: Any) -> List[Dict[str, Any]]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("jobs"), list):
        return data["jobs"]
    return []

def job_name_of(j: Dict[str, Any]) -> str:
    return (j.get("settings") or {}).get("name") or j.get("name") or ""

def find_job_id_by_name(name: str) -> Optional[int]:
    data = sh_json(["databricks", "jobs", "list", "--output", "json"])
    jobs = parse_jobs_list(data)

    # exact
    for j in jobs:
        if job_name_of(j) == name:
            return int(j["job_id"])

    # contains
    n = name.lower()
    hits = [(job_name_of(j), int(j["job_id"])) for j in jobs if n in job_name_of(j).lower()]
    if len(hits) == 1:
        return hits[0][1]
    if len(hits) > 1:
        print("Multiple jobs matched; use job_id:")
        for jn, jid in hits[:20]:
            print(f"  - {jn} (job_id={jid})")
        return None

    print(f"Job not found: {name}")
    print("First jobs visible:")
    for j in jobs[:20]:
        print(f"  - {job_name_of(j)} -> {j.get('job_id')}")
    return None

def run_now(job_id: int) -> int:
    data = sh_json(["databricks", "jobs", "run-now", str(job_id), "--output", "json"])
    rid = data.get("run_id")
    if not rid:
        print("Unexpected run-now response:\n", json.dumps(data, indent=2))
        sys.exit(1)
    return int(rid)

def get_run(run_id: int) -> Dict[str, Any]:
    return sh_json(["databricks", "jobs", "get-run", str(run_id), "--output", "json"])

def wait_run(run_id: int) -> None:
    while True:
        r = get_run(run_id)
        state = r.get("state", {})
        life = state.get("life_cycle_state")
        result = state.get("result_state")
        msg = state.get("state_message", "")

        print(f"run_id={run_id} life={life} result={result} msg={msg[:200]}")

        if life in ("TERMINATED", "SKIPPED", "INTERNAL_ERROR"):
            if result == "SUCCESS":
                return

            # Print task-level info (super helpful)
            tasks = r.get("tasks") or []
            if tasks:
                print("TASK DETAILS:")
                print(json.dumps(tasks, indent=2)[:20000])

            raise SystemExit(f"Run failed: life={life} result={result} msg={msg}")

        time.sleep(15)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("job", help="Job name OR job_id")
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
