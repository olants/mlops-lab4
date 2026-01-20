resource "aws_cloudwatch_dashboard" "lab4" {
  dashboard_name = "lab4-serving"
  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        x = 0; y = 0; width = 12; height = 6
        properties = {
          region = var.aws_region
          title  = "Latency (p95/p99/avg) - Lab4/Serving"
          period = 60
          stat   = "p95"
          metrics = [
            [ "Lab4/Serving", "LatencyMs", "Endpoint", var.serving_endpoint_name, "Mode", "normal", { "stat": "p95" } ],
            [ ".", "LatencyMs", ".", ".", ".", ".", { "stat": "p99" } ],
            [ ".", "LatencyMs", ".", ".", ".", ".", { "stat": "Average" } ]
          ]
        }
      },
      {
        type = "metric"
        x = 12; y = 0; width = 12; height = 6
        properties = {
          region = var.aws_region
          title  = "Requests & Errors + ErrorRate% (metric math)"
          period = 60
          metrics = [
            [ "Lab4/Serving", "Requests", "Endpoint", var.serving_endpoint_name, "Mode", "normal", { "stat": "Sum", "id": "req" } ],
            [ ".", "Errors",   ".", ".", ".", ".", { "stat": "Sum", "id": "err" } ],
            [ { "expression": "100 * err / MAX([req,1])", "label": "ErrorRatePct", "id": "erate", "yAxis": "right" } ]
          ]
        }
      }
    ]
  })
}
