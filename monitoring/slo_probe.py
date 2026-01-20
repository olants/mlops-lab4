#!/usr/bin/env python3
import argparse
import json
import os
import random
import statistics
import time
from typing import List, Tuple

import boto3
import requests


def pct(p: float, xs: List[float]) -> float:
    """Percentile with simple nearest-rank method."""
    if not xs:
        return float("nan")
    xs = sorted(xs)
    k = int(round((p / 100.0) * (len(xs) - 1)))
    k = max(0, min(k, len(xs) - 1))
    return xs[k]


def make_sample() -> dict:
    # simple reasonable ranges; adjust if you want
    return {
        "pressure": float(random.uniform(80, 140)),
        "flow": float(random.uniform(2.0, 6.0)),
        "radius": float(random.uniform(0.2, 0.45)),
    }


def infer_serving_url(host: str, endpoint_name: str) -> str:
    # Databricks model serving invocations URL (classic)
    host = host.rstrip("/")
    return f"{host}/serving-endpoints/{endpoint_name}/invocations"


def call_endpoint(url: str, token: str, sample: dict, timeout_sec: int) -> Tuple[bool, float]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "dataframe_split": {
            "columns": ["pressure", "flow", "radius"],
            "data": [[sample["pressure"], sample["flow"], sample["radius"]]],
        }
    }

    t0 = time.perf_counter()
    try:
        r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=timeout_sec)
        latency_ms = (time.perf_counter() - t0) * 1000.0
        ok = (200 <= r.status_code < 300)
        return ok, latency_ms
    except Exception:
        latency_ms = (time.perf_counter() - t0) * 1000.0
        return False, latency_ms


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", required=True, help="Serving endpoint name (e.g. energy-prod)")
    ap.add_argument("--samples", type=int, default=50)
    ap.add_argument("--timeout_sec", type=int, default=2)

    ap.add_argument("--secret_scope", required=True)
    ap.add_argument("--secret_key", default="serving_token")

    ap.add_argument("--aws_region", default=os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1")
    ap.add_argument("--cw_namespace", default="Lab4/SLO")

    # SLO thresholds (optional; helps “fail the job” if violated)
    ap.add_argument("--p95_threshold_ms", type=float, default=1500.0)
    ap.add_argument("--error_rate_threshold_pct", type=float, default=5.0)

    args = ap.parse_args()

    # ---- Read Databricks token from Secrets ----
    # In a Databricks job, dbutils is available.
    try:
        token = dbutils.secrets.get(args.secret_scope, args.secret_key)  # type: ignore[name-defined]
    except Exception as e:
        raise RuntimeError(
            f"Cannot read Databricks secret scope='{args.secret_scope}' key='{args.secret_key}'. "
            f"Check Databricks -> Settings -> Secret scopes."
        ) from e

    host = os.environ.get("DATABRICKS_HOST", "").strip()
    if not host:
        raise RuntimeError("DATABRICKS_HOST env var is missing in the cluster/job environment.")

    url = infer_serving_url(host, args.endpoint)

    latencies: List[float] = []
    errors = 0

    for _ in range(args.samples):
        ok, latency_ms = call_endpoint(url, token, make_sample(), args.timeout_sec)
        latencies.append(latency_ms)
        if not ok:
            errors += 1

    p50_ms = pct(50, latencies)
    p95_ms = pct(95, latencies)
    p99_ms = pct(99, latencies)
    err_rate_pct = (errors / max(1, args.samples)) * 100.0

    print(json.dumps({
        "endpoint": args.endpoint,
        "samples": args.samples,
        "errors": errors,
        "error_rate_pct": err_rate_pct,
        "p50_ms": p50_ms,
        "p95_ms": p95_ms,
        "p99_ms": p99_ms,
    }, indent=2))

    # ---- Push to CloudWatch ----
    cw = boto3.client("cloudwatch", region_name=args.aws_region)
    cw.put_metric_data(
        Namespace=args.cw_namespace,
        MetricData=[
            {"MetricName": "LatencyP50Ms", "Value": float(p50_ms), "Unit": "Milliseconds"},
            {"MetricName": "LatencyP95Ms", "Value": float(p95_ms), "Unit": "Milliseconds"},
            {"MetricName": "LatencyP99Ms", "Value": float(p99_ms), "Unit": "Milliseconds"},
            {"MetricName": "ErrorRatePct", "Value": float(err_rate_pct), "Unit": "Percent"},
        ],
    )

    # ---- Optional: fail job when SLO violated (useful for alerting) ----
    violated = []
    if p95_ms > args.p95_threshold_ms:
        violated.append(f"p95_ms={p95_ms:.1f} > {args.p95_threshold_ms}")
    if err_rate_pct > args.error_rate_threshold_pct:
        violated.append(f"err_rate_pct={err_rate_pct:.2f} > {args.error_rate_threshold_pct}")

    if violated:
        raise SystemExit("SLO_VIOLATION: " + "; ".join(violated))


if __name__ == "__main__":
    main()
