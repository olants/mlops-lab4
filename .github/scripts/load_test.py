import argparse, json, random, statistics, time
import requests

SAMPLE_GOOD = {
  "dataframe_split": {
    "columns": ["pressure", "flow", "radius"],
    "data": [[120.0, 4.2, 0.35]]
  }
}

SAMPLE_BAD = {
  "dataframe_split": {
    "columns": ["pressure", "flow"],   # missing radius -> should fail
    "data": [[120.0, 4.2]]
  }
}

def percentile(xs, p):
    if not xs: return None
    xs = sorted(xs)
    k = int(round((p/100) * (len(xs)-1)))
    return xs[k]

def run(url, duration, rps, timeout, mode):
    end = time.time() + duration
    lat = []
    ok = 0
    err = 0

    session = requests.Session()
    headers = {"Content-Type": "application/json"}

    while time.time() < end:
        t0 = time.time()

        payload = SAMPLE_GOOD if mode == "normal" else (SAMPLE_BAD if random.random() < 0.7 else SAMPLE_GOOD)

        try:
            r = session.post(url, headers=headers, data=json.dumps(payload), timeout=timeout)
            dt = (time.time() - t0) * 1000.0
            lat.append(dt)
            if 200 <= r.status_code < 300:
                ok += 1
            else:
                err += 1
        except Exception:
            err += 1

        # pace to RPS
        sleep = max(0.0, (1.0 / rps) - (time.time() - t0))
        time.sleep(sleep)

    total = ok + err
    p50 = percentile(lat, 50)
    p95 = percentile(lat, 95)
    p99 = percentile(lat, 99)
    avg = statistics.mean(lat) if lat else None
    err_rate = (err / total * 100.0) if total else 100.0

    return {
        "total": total, "ok": ok, "err": err, "err_rate_pct": err_rate,
        "avg_ms": avg, "p50_ms": p50, "p95_ms": p95, "p99_ms": p99
    }

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--duration", type=int, required=True)
    ap.add_argument("--rps", type=float, required=True)
    ap.add_argument("--timeout", type=float, required=True)
    ap.add_argument("--mode", choices=["normal", "failure"], required=True)
    ap.add_argument("--assert_recovery", action="store_true")
    args = ap.parse_args()

    res = run(args.url, args.duration, args.rps, args.timeout, args.mode)
    print(json.dumps(res, indent=2))

    # Recovery gate (tune thresholds to your lab SLOs)
    if args.assert_recovery:
        if res["err_rate_pct"] > 5.0:
            raise SystemExit(f"Recovery failed: error rate too high {res['err_rate_pct']:.2f}%")
        if res["p95_ms"] is not None and res["p95_ms"] > 2000:
            raise SystemExit(f"Recovery failed: p95 too high {res['p95_ms']:.0f}ms")
        print("Recovery OK")
