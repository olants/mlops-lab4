import argparse
import os
from datetime import datetime

import pandas as pd

from evidently.report import Report
from evidently.metric_preset import DataDriftPreset


def _spark_read_parquet_any(spark, path: str):
    try:
        return spark.read.parquet(path)
    except Exception:
        return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--drift_s3_prefix", required=True)
    p.add_argument("--baseline_days", type=int, default=7)
    p.add_argument("--features", default="pressure,flow,radius")
    args = p.parse_args()

    features = [x.strip() for x in args.features.split(",") if x.strip()]
    drift_prefix = args.drift_s3_prefix.rstrip("/")

    # Try to read "processed" parquet (your lab path)
    default_data = "s3://lab3-databricks/processed/energy_sample_parquet"

    try:
        spark  # noqa: F821
        sdf = _spark_read_parquet_any(spark, default_data)  # type: ignore # noqa: F821
        if sdf is None:
            print(f"No parquet readable at {default_data}. Skipping drift check.")
            return
        df = sdf.select(*features).toPandas()
    except Exception as e:
        print(f"Spark not available or read failed: {e}. Skipping drift check.")
        return

    # Basic split (since sample data may not have timestamps):
    # baseline = first 70%, current = last 30%
    if len(df) < 50:
        print("Not enough rows for drift check. Need at least ~50. Skipping.")
        return

    df = df.dropna()
    cut = int(len(df) * 0.7)
    ref = df.iloc[:cut].copy()
    cur = df.iloc[cut:].copy()

    report = Report(metrics=[DataDriftPreset()])
    report.run(reference_data=ref, current_data=cur)

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    local_html = f"/tmp/drift_report_{ts}.html"
    report.save_html(local_html)

    # Write to DBFS then you can copy to S3 if needed
    dbfs_path = f"/dbfs/tmp/drift_report_{ts}.html"
    os.makedirs("/dbfs/tmp", exist_ok=True)

    with open(local_html, "r", encoding="utf-8") as src, open(dbfs_path, "w", encoding="utf-8") as dst:
        dst.write(src.read())

    print(f"Drift report saved: dbfs:/tmp/drift_report_{ts}.html")
    print(f"(Configured drift prefix: {drift_prefix})")


if __name__ == "__main__":
    main()
