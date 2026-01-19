variable "databricks_host" {
  type = string
}

variable "databricks_token" {
  type      = string
  sensitive = true
}

variable "serving_token" {
  type      = string
  sensitive = true
}

variable "secret_scope_name" {
  type    = string
  default = "lab4-mlops"
}

variable "secret_key_name" {
  type    = string
  default = "serving_token"
}

variable "single_user_name" {
  type    = string
  default = "olants@gmail.com"
}

variable "train_notebook_path" {
  type = string
}

variable "drift_py_path" {
  type = string
}

variable "slo_py_path" {
  type = string
}

variable "registered_model_name" {
  type    = string
  default = "energy-lstm"
}

variable "serving_endpoint_name" {
  type    = string
  default = "energy-prod"
}

variable "train_cron" {
  type    = string
  default = "0 0 7 * * ?"
}

variable "drift_cron" {
  type    = string
  default = "0 0 8 * * ?"
}

variable "slo_cron" {
  type    = string
  default = "0 0/30 * * * ?"
}

variable "enable_serving" {
  type    = bool
  default = false
}

variable "blue_model_version" {
  type    = string
  default = "1"
}

variable "green_model_version" {
  type    = string
  default = "1"
}

variable "blue_traffic_percent" {
  type    = number
  default = 100
}

variable "green_traffic_percent" {
  type    = number
  default = 0
}

variable "drift_s3_prefix" {
  type    = string
  default = "s3://lab3-databricks/drift"
}
