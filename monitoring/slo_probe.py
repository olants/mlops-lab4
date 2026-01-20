import boto3
cw = boto3.client("cloudwatch", region_name="us-east-1")
cw.put_metric_data(
  Namespace="Lab4/SLO",
  MetricData=[
    {"MetricName":"LatencyP95Ms","Value":p95_ms,"Unit":"Milliseconds"},
    {"MetricName":"ErrorRatePct","Value":err_rate_pct,"Unit":"Percent"},
  ]
)
