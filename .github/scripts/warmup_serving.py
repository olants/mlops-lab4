import os, json, time, argparse
import requests

PAYLOAD = {
  "dataframe_split": {
    "columns": ["pressure", "flow", "radius"],
    "data": [[120.0, 4.2, 0.35]]
  }
}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--tries", type=int, default=8)
    ap.add_argument("--timeout", type=float, default=60)
    args = ap.parse_args()

    token = os.getenv("DATABRICKS_TOKEN")
    if not token:
        raise SystemExit("Missing DATABRICKS_TOKEN")

    headers = {"Content-Type":"application/json", "Authorization": f"Bearer {token}"}

    for i in range(1, args.tries + 1):
        try:
            r = requests.post(args.url, headers=headers, data=json.dumps(PAYLOAD), timeout=args.timeout)
            if 200 <= r.status_code < 300:
                print(f"Warm-up OK on try {i}")
                raise SystemExit(0)
            else:
                print(f"Warm-up got status={r.status_code}, body={(r.text or '')[:200]!r}")
        except Exception as e:
            print(f"Warm-up exception on try {i}: {type(e).__name__}: {e}")
        time.sleep(5)

    raise SystemExit("Warm-up failed: endpoint did not respond successfully")
