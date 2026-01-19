import argparse
import time
import numpy as np
import requests


def _get_dbutils_secret(scope: str, key: str) -> str:
    try:
        dbutils  # noqa: F821
        return dbutils.secrets.get(scope, key)  # type: ignore # noqa: F821
    except Exception as e:
        raise RuntimeError(
            "dbutils.secrets is not available. Run this on a Databricks cluster."
        ) from e


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--endpoint", required=True)
    p.add_argument("--samples", type=int, default=50)
    p.add_argument("--secret_scope", required=True)
    p.add_argument("--secret_key", required=True)
    args = p.parse_args()

    host = "https://dbc-376f5995-7cc1.cloud.databricks.com"
    token = _get_dbutils_secret(args.secret_scope, args.secret_key)

    url = f"{host}/serving-endpoints/{args.endpoint}/invocations"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    payload = {
        "dataframe_split": {
            "columns": ["pressure", "flow", "radius"],
            "data": [[120.0, 4.2, 0.35]]
        }
    }

    lat_ms = []
    errors = 0

    for _ in range(args.samples):
        t0 = time.time()
        r = requests.post(url, json=payload, headers=headers, timeout=30)
        dt = (time.time() - t0) * 1000.0
        lat_ms.append(dt)
        if r.status_code != 200:
            errors += 1

    lat_ms = np.array(lat_ms, dtype=float)
    p95 = float(np.percentile(lat_ms, 95))
    p99 = float(np.percentile(lat_ms, 99))
    err_rate = float(errors) / float(args.samples)

    print(f"SLO PROBE: samples={args.samples} p95_ms={p95:.2f} p99_ms={p99:.2f} error_rate={err_rate:.3f}")

    # Tune thresholds for lab demo
    if err_rate > 0.02 or p99 > 2000:
        raise SystemExit("SLO FAILED")


if __name__ == "__main__":
    main()
