import argparse
import json
import time
from datetime import datetime, timedelta, timezone

import pandas as pd

from evidently.report import Report
from evidently.metric_preset import DataDriftPreset


def _utc_now():
    return datetime.now(timezone.utc)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--drift_s3_prefix", required=True)
    p.add_argument("--baseline_days", type=int, default=7)
    p.add_argument("--features", default="pressure,flow")
    args = p.parse_args()

    features = [x.strip() for x in args.features.split(",") if x.strip()]

    # TODO: Replace these with how YOU load “current” and “baseline” data.
    # Minimal course-friendly approach:
    # - baseline: last 7 days from processed dataset
    # - current: last 1 day
    #
    # If you only have sample.csv for now, you can use random splits as “baseline/current”
    # and later replace with real time-based slices.
    #
    # Example placeholders:
    processed_path = "s3://lab3-databricks/processed/energy_sample_parquet"
    df = pd.read_parquet(processed_path)

    # Fake time slicing (if no timestamp column exists):
    # baseline = first 80%, current = last 20%
    cut = int(len(df) * 0.8)
    ref = df.iloc[:cut][features].copy()
    cur = df.iloc[cut:][features].copy()

    report = Report(metrics=[DataDriftPreset()])
    report.run(reference_data=ref, current_data=cur)

    ts = _utc_now().strftime("%Y%m%dT%H%M%SZ")
    out_prefix = f"{args.drift_s3_prefix.rstrip('/')}/{ts}"

    # Save HTML + JSON to S3 via pandas-compatible filesystem (Databricks has this)
    html_path = f"{out_prefix}/evidently_report.html"
    json_path = f"{out_prefix}/evidently_report.json"

    report.save_html(html_path)
    report.save_json(json_path)

    # Extract a simple drift score for alerting (share_of_drifted_columns)
    report_dict = report.as_dict()
    # Evidently schema can differ; keep it safe:
    drift_score = None
    try:
        # Search for DataDriftTable / share of drifted columns
        for m in report_dict.get("metrics", []):
            if m.get("metric") == "DataDriftTable":
                drift_score = m.get("result", {}).get("share_of_drifted_columns")
                break
    except Exception:
        drift_score = None

    score_obj = {
        "timestamp": ts,
        "features": features,
        "drift_score": drift_score,
        "report_prefix": out_prefix,
    }

    score_path = f"{out_prefix}/drift_score.json"
    pd.Series([json.dumps(score_obj)]).to_csv(score_path, index=False, header=False)

    print("Drift report:", out_prefix)
    print("Drift score:", drift_score)


if __name__ == "__main__":
    main()
