variable "databricks_host" { type = string }
variable "databricks_token" { type = string }

# Your workspace paths (IMPORTANT: no /Workspace prefix for most APIs)
variable "train_notebook_path" {
  type    = string
  default = "/Users/olants@gmail.com/mlops-lab4/mlops-lab4"
}

variable "drift_py_path" {
  type    = string
  default = "/Users/olants@gmail.com/mlops-lab4/monitoring/drift_check.py"
}

variable "slo_py_path" {
  type    = string
  default = "/Users/olants@gmail.com/mlops-lab4/monitoring/slo_probe.py"
}

variable "registered_model_name" {
  type    = string
  default = "energy-lstm"
}

variable "serving_endpoint_name" {
  type    = string
  default = "energy-prod"
}

variable "spark_version" {
  type    = string
  default = "14.3.x-scala2.12"
}

variable "node_type_id" {
  type    = string
  default = "m5d.large"
}

# Schedules
variable "train_cron" { type = string default = "0 0 7 * * ?" }  # daily 07:00 UTC
variable "drift_cron" { type = string default = "0 0 8 * * ?" }  # daily 08:00 UTC
variable "slo_cron"   { type = string default = "0 0/30 * * * ?" } # every 30 min

# Blue/green model versions (set these when you want to rollout)
# Start with blue=latest prod you have, green=same; later set green to new version.
variable "blue_model_version"  { type = string default = "1" }
variable "green_model_version" { type = string default = "1" }
variable "blue_traffic_percent"  { type = number default = 100 }
variable "green_traffic_percent" { type = number default = 0 }

# Drift storage
variable "drift_s3_prefix" {
  type    = string
  default = "s3://lab3-databricks/drift"
}


variable "databricks_host" { type = string }
variable "databricks_token" { type = string }

variable "secret_scope_name" {
  type    = string
  default = "lab4"
}

variable "serving_token" {
  type      = string
  sensitive = true
}

# Paths (no /Workspace prefix)
variable "train_notebook_path" {
  type    = string
  default = "/Users/olants@gmail.com/mlops-lab4/mlops-lab4"
}

variable "drift_py_path" {
  type    = string
  default = "/Users/olants@gmail.com/mlops-lab4/monitoring/drift_check.py"
}

variable "slo_py_path" {
  type    = string
  default = "/Users/olants@gmail.com/mlops-lab4/monitoring/slo_probe.py"
}

variable "registered_model_name" { type = string default = "energy-lstm" }
variable "serving_endpoint_name" { type = string default = "energy-prod" }

variable "spark_version" { type = string default = "14.3.x-scala2.12" }
variable "node_type_id"   { type = string default = "m5d.large" }

variable "train_cron" { type = string default = "0 0 7 * * ?" }
variable "drift_cron" { type = string default = "0 0 8 * * ?" }
variable "slo_cron"   { type = string default = "0 0/30 * * * ?" }

variable "blue_model_version"  { type = string default = "1" }
variable "green_model_version" { type = string default = "1" }
variable "blue_traffic_percent"  { type = number default = 100 }
variable "green_traffic_percent" { type = number default = 0 }

variable "drift_s3_prefix" { type = string default = "s3://lab3-databricks/drift" }
