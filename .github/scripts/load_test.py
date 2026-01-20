import argparse, json, random, statistics, time, os
import requests

# NEW
import boto3

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

def cw_client(region: str):
    return boto3.client("cloudwatch", region_name=region)

def cw_flush(cw, namespace: str, dims: list, buffer: list):
    # PutMetricData: max 20 metrics per call; each MetricData can include one Value.
    # We batch by sending multiple MetricData entries, but still keep it <= 20.
    # So we flush in chunks of 20.
    while buffer:
        chunk = buffer[:20]
        buffer[:] = buffer[20:]
        cw.put_metric_data(Namespace=namespace, MetricData=chunk)

def run(url, duration, rps, timeout, mode,
        cw_namespace=None, cw_region=None, cw_endpoint_dim=None,
        cw_flush_every=10, cw_high_res=True):
    end = time.time() + duration
    lat = []
    ok = 0
    err = 0

    session = requests.Session()
    headers = {"Content-Type": "application/json"}

    # If calling Databricks model serving, you typically need Bearer token
    token = os.getenv("DATABRICKS_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    cw = None
    cw_buf = []
    dims = []
    if cw_namespace:
        cw = cw_client(cw_region or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1")
        # keep dimensions low-cardinality
        dims = [{"Name": "Endpoint", "Value": cw_endpoint_dim or "energy-prod"},
                {"Name": "Mode", "Value": mode}]
        storage_resolution = 1 if cw_high_res else 60

    def push_metrics(latency_ms: float, is_error: int):
        nonlocal cw_buf
        if not cw:
            return
        # One request = 3 datapoints: Requests, Errors, LatencyMs
        ts = time.time()
        cw_buf.append({
            "MetricName": "Requests",
            "Dimensions": dims,
            "Timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts)),
            "Value": 1.0,
            "Unit": "Count",
            "StorageResolution": storage_resolution,
        })
        cw_buf.append({
            "MetricName": "Errors",
            "Dimensions": dims,
            "Timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts)),
            "Value": float(is_error),
            "Unit": "Count",
            "StorageResolution": storage_resolution,
        })
        cw_buf.append({
            "MetricName": "LatencyMs",
            "Dimensions": dims,
            "Timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts)),
            "Value": float(latency_ms),
            "Unit": "Milliseconds",
            "StorageResolution": storage_resolution,
        })

        # Flush by request count (buffer size grows by 3 per request)
        if len(cw_buf) >= cw_flush_every * 3:
            cw_flush(cw, cw_namespace, dims, cw_buf)

    first_exc = None

    while time.time() < end:
        t0 = time.time()
        payload = SAMPLE_GOOD if mode == "normal" else (SAMPLE_BAD if random.random() < 0.7 else SAMPLE_GOOD)

        try:
            r = session.post(url, headers=headers, data=json.dumps(payload), timeout=timeout)
            dt = (time.time() - t0) * 1000.0
            lat.append(dt)

            if 200 <= r.status_code < 300:
                ok += 1
                push_metrics(dt, 0)
            else:
                err += 1
                push_metrics(dt, 1)
                if first_exc is None:
                    first_exc = f"status={r.status_code} body={r.text[:200]!r}"

        except Exception as e:
            err += 1
            if first_exc is None:
                first_exc = f"{type(e).__name__}: {e}"
            # no latency datapoint if we never got a response
            push_metrics(timeout * 1000.0, 1)

        sleep = max(0.0, (1.0 / rps) - (time.time() - t0))
        time.sleep(sleep)

    # final flush
    if cw and cw_buf:
        cw_flush(cw, cw_namespace, dims, cw_buf)

    total = ok + err
    p50 = percentile(lat, 50)
    p95 = percentile(lat, 95)
    p99 = percentile(lat, 99)
    avg = statistics.mean(lat) if lat else None
    err_rate = (err / total * 100.0) if total else 100.0

    res = {
        "total": total, "ok": ok, "err": err, "err_rate_pct": err_rate,
        "avg_ms": avg, "p50_ms": p50, "p95_ms": p95, "p99_ms": p99
    }
    if first_exc:
        res["debug_first_error"] = first_exc
    return res

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--duration", type=int, required=True)
    ap.add_argument("--rps", type=float, required=True)
    ap.add_argument("--timeout", type=float, required=True)
    ap.add_argument("--mode", choices=["normal", "failure"], required=True)
    ap.add_argument("--assert_recovery", action="store_true")

    # NEW: CloudWatch
    ap.add_argument("--cw_namespace", default="Lab4/Serving")
    ap.add_argument("--cw_region", default=os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1")
    ap.add_argument("--cw_endpoint_dim", default=os.getenv("SERVING_ENDPOINT_NAME") or "energy-prod")
    ap.add_argument("--cw_flush_every", type=int, default=10)
    ap.add_argument("--cw_high_res", action="store_true")

    args = ap.parse_args()

    res = run(
        args.url, args.duration, args.rps, args.timeout, args.mode,
        cw_namespace=args.cw_namespace,
        cw_region=args.cw_region,
        cw_endpoint_dim=args.cw_endpoint_dim,
        cw_flush_every=args.cw_flush_every,
        cw_high_res=args.cw_high_res,
    )
    print(json.dumps(res, indent=2))

    if args.assert_recovery:
        if res["err_rate_pct"] > 5.0:
            raise SystemExit(f"Recovery failed: error rate too high {res['err_rate_pct']:.2f}%")
        if res["p95_ms"] is not None and res["p95_ms"] > 2000:
            raise SystemExit(f"Recovery failed: p95 too high {res['p95_ms']:.0f}ms")
        print("Recovery OK")
