import argparse, json, os, subprocess, sys, time

def sh(cmd):
    return subprocess.check_output(cmd, text=True)

def find_job_id(job_name: str) -> int:
    jobs = json.loads(sh(["databricks", "jobs", "list", "--output", "json"]))
    for j in jobs:
        if j.get("settings", {}).get("name") == job_name:
            return int(j["job_id"])
    raise SystemExit(f"Job not found: {job_name}")

def run_now(job_id: int) -> int:
    out = sh(["databricks", "jobs", "run-now", str(job_id), "--output", "json"])
    data = json.loads(out)
    return int(data["run_id"])

def wait_run(run_id: int) -> None:
    while True:
        r = json.loads(sh(["databricks", "runs", "get", str(run_id), "--output", "json"]))
        state = r.get("state", {})
        life = state.get("life_cycle_state")
        result = state.get("result_state")
        msg = state.get("state_message", "")
        print(f"run_id={run_id} life={life} result={result} msg={msg[:120]}")
        if life in ("TERMINATED", "SKIPPED", "INTERNAL_ERROR"):
            if result == "SUCCESS":
                return
            raise SystemExit(f"Run failed: {result} {msg}")
        time.sleep(15)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("job_name")
    ap.add_argument("--wait", action="store_true")
    args = ap.parse_args()

    job_id = find_job_id(args.job_name)
    run_id = run_now(job_id)
    print(f"Triggered {args.job_name} job_id={job_id} run_id={run_id}")

    if args.wait:
        wait_run(run_id)
        print("SUCCESS")
