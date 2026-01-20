variable "aws_region" { type = string default = "us-east-1" }
variable "serving_endpoint_name" { type = string default = "energy-prod" }

provider "aws" {
  region = var.aws_region
}
