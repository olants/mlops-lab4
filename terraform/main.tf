terraform {
  required_providers {
    databricks = {
      source  = "databricks/databricks"
      version = "~> 1.50"
    }
  }
}

provider "databricks" {
  host  = var.databricks_host
  token = var.databricks_token
}

# Pick a supported LTS runtime + node type automatically
data "databricks_spark_version" "lts" {
  long_term_support = true
}

data "databricks_node_type" "smallest" {
  local_disk = true
}

# Secret scope + secret for serving token
resource "databricks_secret_scope" "lab4" {
  name = var.secret_scope_name
}

resource "databricks_secret" "serving_token" {
  scope        = databricks_secret_scope.lab4.name
  key          = var.secret_key_name
  string_value = var.serving_token
}

# Cluster for jobs (NO_ISOLATION not allowed -> SINGLE_USER)
resource "databricks_cluster" "job_cluster" {
  cluster_name            = "lab4-job-cluster"
  spark_version           = data.databricks_spark_version.lts.id
  node_type_id            = data.databricks_node_type.smallest.id
  num_workers             = 1
  autotermination_minutes = 30

  data_security_mode = "SINGLE_USER"
  single_user_name   = var.single_user_name
}

# Training job (notebook)
resource "databricks_job" "train" {
  name = "lab4-train-pipeline"

  task {
    task_key = "train"

    notebook_task {
      notebook_path = var.train_notebook_path
    }

    existing_cluster_id = databricks_cluster.job_cluster.id
  }

  schedule {
    quartz_cron_expression = var.train_cron
    timezone_id            = "UTC"
    pause_status           = "UNPAUSED"
  }

  max_concurrent_runs = 1
}

# Drift job (python)
resource "databricks_job" "drift" {
  name = "lab4-drift-check"

  task {
    task_key = "drift"

    spark_python_task {
      python_file = var.drift_py_path
      parameters = [
        "--drift_s3_prefix", var.drift_s3_prefix,
        "--baseline_days", "7",
        "--features", "pressure,flow,radius"
      ]
    }

    existing_cluster_id = databricks_cluster.job_cluster.id

    library {
      pypi {
        package = "evidently==0.4.40"
      }
    }

    library {
      pypi {
        package = "pandas"
      }
    }

    library {
      pypi {
        package = "pyarrow"
      }
    }
  }

  schedule {
    quartz_cron_expression = var.drift_cron
    timezone_id            = "UTC"
    pause_status           = "UNPAUSED"
  }

  max_concurrent_runs = 1
}

# SLO probe job (python)
resource "databricks_job" "slo" {
  name = "lab4-slo-probe"

  task {
    task_key = "slo"

    spark_python_task {
      python_file = var.slo_py_path
      parameters = [
        "--endpoint", var.serving_endpoint_name,
        "--samples", "50",
        "--secret_scope", var.secret_scope_name,
        "--secret_key", var.secret_key_name
      ]
    }

    existing_cluster_id = databricks_cluster.job_cluster.id

    library {
      pypi {
        package = "requests"
      }
    }

    library {
      pypi {
        package = "numpy"
      }
    }
  }

  schedule {
    quartz_cron_expression = var.slo_cron
    timezone_id            = "UTC"
    pause_status           = "UNPAUSED"
  }

  max_concurrent_runs = 1
}

# Serving endpoint (created only when enable_serving=true)
resource "databricks_model_serving" "endpoint" {
  count = var.enable_serving ? 1 : 0

  name = var.serving_endpoint_name

  config {
    served_models {
      name                  = "blue"
      model_name            = var.registered_model_name
      model_version         = var.blue_model_version
      workload_size         = "Small"
      scale_to_zero_enabled = true
    }

    served_models {
      name                  = "green"
      model_name            = var.registered_model_name
      model_version         = var.green_model_version
      workload_size         = "Small"
      scale_to_zero_enabled = true
    }

    traffic_config {
      routes {
        served_model_name  = "blue"
        traffic_percentage = var.blue_traffic_percent
      }
      routes {
        served_model_name  = "green"
        traffic_percentage = var.green_traffic_percent
      }
    }
  }
}
