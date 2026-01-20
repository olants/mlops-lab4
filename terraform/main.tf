terraform {
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}
provider "aws" { region = var.aws_region }

locals {
  namespace = "Lab4/SLO"
  metric_p95 = "LatencyP95Ms"
  metric_err = "ErrorRatePct"
}

library {
  pypi {
    package = "evidently==0.4.40"
  }
}

resource "aws_cloudwatch_dashboard" "lab4" {
  dashboard_name = "lab4-mlops-dashboard"
  dashboard_body = jsonencode({
    widgets = [
      {
        type="metric", x=0, y=0, width=12, height=6,
        properties={
          title="Latency p95 (ms)", region=var.aws_region, stat="Average", period=60,
          metrics=[[local.namespace, local.metric_p95]]
        }
      },
      {
        type="metric", x=12, y=0, width=12, height=6,
        properties={
          title="Error rate (%)", region=var.aws_region, stat="Average", period=60,
          metrics=[[local.namespace, local.metric_err]]
        }
      }
    ]
  })
}

resource "aws_cloudwatch_metric_alarm" "latency_p95_high" {
  alarm_name          = "lab4-latency-p95-high"
  alarm_description   = "Lab4 SLO: p95 latency too high"
  namespace           = local.namespace
  metric_name         = local.metric_p95
  statistic           = "Average"
  period              = 60
  evaluation_periods  = 5
  datapoints_to_alarm = 3
  threshold           = 2000
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
}

resource "aws_cloudwatch_metric_alarm" "error_rate_high" {
  alarm_name          = "lab4-error-rate-high"
  alarm_description   = "Lab4 SLO: error rate too high"
  namespace           = local.namespace
  metric_name         = local.metric_err
  statistic           = "Average"
  period              = 60
  evaluation_periods  = 5
  datapoints_to_alarm = 3
  threshold           = 5
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
}
