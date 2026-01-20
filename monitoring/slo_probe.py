#!/usr/bin/env python3
import argparse
import json
import os
import random
import statistics
import time
from typing import List, Tuple

import numpy as np
import requests
import boto3


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--endpoint", required=True, help="Databricks serving endpoint name, e.g. energy-prod")
    p.add_argument("--samples", type=int, default=50, help="Number of requests to send")
    p.add_argument("--timeout_sec", type=float, default=2.0, help="HTTP timeout per request")
    p.add_argument("--secret_scope", default="", help="If running inside Databricks, scope for token secret")
    p.add_argument("--secret_key", default="", help="If running inside Databricks, key for token secret")
    p.add_argument("--cloudwatch_namespace", default="Lab4/SLO")
    p.add_argument("--region", default=os.getenv("AWS_REGION", "us-east-1"))

    # SLO thresholds (edit to your lab requirements)
    p.add_argument("--slo_p95_ms", type=float, default=500.0)
    p.add_argument("--slo_p99_ms", type=float, default=1000.0)
    p.add_argument("--slo_error_pct", type=float, default=5.0)

    return p.parse_args()


def get_databricks_token(args) -> str:
    # Prefer env var (works in GitHub Actions too)
    tok = os.getenv("DATABRICKS_TOKEN")
    if tok:
        return tok

    # If running inside Databricks: read secret
    if args.secret_scope and args.secret_key:
        try:
            # dbutils exists only inside Databricks notebooks/jobs
            tok = dbutils.secrets.get(args.secret_scope, args.secret_key)  # type: ignore  # noqa: F821
            return tok
        except Exception as e:
            raise RuntimeError(f"Failed to read token from dbutils.secrets: {e}")

    raise RuntimeError("No Databricks token found. Set DATABRICKS_TOKEN env var or provide secret_scope/secret_key.")


def build_url(endpoint_name: str) -> str:
    host = os.getenv("DATABRICKS_HOST", "").rstrip("/")
    if not host:
        raise RuntimeError("DATABRICKS_HOST env var is missing")
    return f"{host}/serving-endpoints/{endpoint_name}/invocations"


def make_payload() -> dict:
    # Generate a plausible sample (adjust ranges if you want)
    pressure = random.uniform(80, 140)
    flow = random.uniform(2.0, 6.0)
    radius = random.uniform(0.2, 0.5)

    return {
        "dataframe_split": {
            "columns": ["pressure", "flow", "radius"],
            "data": [[pressure, flow, radius]],
        }
    }


def pctl(values: List[float], q: float) -> float:
    # numpy percentile is easiest and robust
    if not values:
        return float("nan")
    return float(np.percentile(np.array(values, dtype=float), q))


def call_endpoint(url: str, token: str, timeout_sec: float) -> Tuple[bool, float]:
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = make_payload()

    t0 = time.perf_counter()
    try:
        r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=timeout_sec)
        dt_ms = (time.perf_counter() - t0) * 1000.0
        if r.status_code >= 200 and r.status_code < 300:
            return True, dt_ms
        return False, dt_ms
    except Exception:
        dt_ms = (time.perf_counter() - t0) * 1000.0
        return False, dt_ms


def put_cloudwatch(namespace: str, region: str, p95_ms: float, p99_ms: float, err_rate_pct: float):
    cw = boto3.client("cloudwatch", region_name=region)
    cw.put_metric_data(
        Namespace=namespace,
        MetricData=[
            {"MetricName": "LatencyP95Ms", "Value": p95_ms, "Unit": "Milliseconds"},
            {"MetricName": "LatencyP99Ms", "Value": p99_ms, "Unit": "Milliseconds"},
            {"MetricName": "ErrorRatePct", "Value": err_rate_pct, "Unit": "Percent"},
        ],
    )


def main():
    args = parse_args()
    token = get_databricks_token(args)
    url = build_url(args.endpoint)

    ok_count = 0
    latencies: List[float] = []

    for _ in range(args.samples):
        ok, dt_ms = call_endpoint(url, token, args.timeout_sec)
        latencies.append(dt_ms)
        if ok:
            ok_count += 1

    total = len(latencies)
    err_count = total - ok_count
    err_rate_pct = (err_count / total * 100.0) if total else 100.0

    p95_ms = pctl(latencies, 95)
    p99_ms = pctl(latencies, 99)

    print(f"Endpoint: {args.endpoint}")
    print(f"Samples: {total}, OK: {ok_count}, Errors: {err_count}, ErrorRatePct: {err_rate_pct:.2f}")
    print(f"Latency ms: p95={p95_ms:.1f}, p99={p99_ms:.1f}, mean={statistics.mean(latencies):.1f}")

    # Publish metrics
    put_cloudwatch(args.cloudwatch_namespace, args.region, p95_ms, p99_ms, err_rate_pct)
    print(f"Published CloudWatch metrics to {args.cloudwatch_namespace} in {args.region}")

    # Enforce SLO (fail job if violated)
    violated = []
    if p95_ms > args.slo_p95_ms:
        violated.append(f"p95_ms {p95_ms:.1f} > {args.slo_p95_ms}")
    if p99_ms > args.slo_p99_ms:
        violated.append(f"p99_ms {p99_ms:.1f} > {args.slo_p99_ms}")
    if err_rate_pct > args.slo_error_pct:
        violated.append(f"err_rate_pct {err_rate_pct:.2f} > {args.slo_error_pct}")

    if violated:
        raise SystemExit("SLO VIOLATION: " + "; ".join(violated))


if __name__ == "__main__":
    main()
