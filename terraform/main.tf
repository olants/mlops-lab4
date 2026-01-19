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

# ----------------- Secrets -----------------
resource "databricks_secret_scope" "lab4" {
  name = var.secret_scope_name
}

resource "databricks_secret" "serving_token" {
  scope        = databricks_secret_scope.lab4.name
  key          = var.secret_key_name
  string_value = var.serving_token
}

# ----------------- Serverless Job Environment -----------------
# This makes Jobs compatible with "Only serverless compute is supported".
resource "databricks_job_environment" "serverless" {
  name = "lab4-serverless-env"

  environment {
    # Use serverless compute
    spec {
      client = "1"
    }
  }
}

# ----------------- TRAIN JOB -----------------
resource "databricks_job" "train" {
  name = "lab4-train-pipeline"

  task {
    task_key = "train"

    notebook_task {
      notebook_path = var.train_notebook_path
    }

    # ✅ Serverless-only workspace fix
    environment_key = databricks_job_environment.serverless.key
  }

  schedule {
    quartz_cron_expression = var.train_cron
    timezone_id            = "UTC"
    pause_status           = "UNPAUSED"
  }

  max_concurrent_runs = 1
}

# ----------------- DRIFT JOB -----------------
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

    library {
      pypi { package = "evidently==0.4.40" }
    }
    library {
      pypi { package = "pandas" }
    }
    library {
      pypi { package = "pyarrow" }
    }

    # ✅ Serverless-only workspace fix
    environment_key = databricks_job_environment.serverless.key
  }

  schedule {
    quartz_cron_expression = var.drift_cron
    timezone_id            = "UTC"
    pause_status           = "UNPAUSED"
  }

  max_concurrent_runs = 1
}

# ----------------- SLO JOB -----------------
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

    library {
      pypi { package = "requests" }
    }
    library {
      pypi { package = "numpy" }
    }

    # ✅ Serverless-only workspace fix
    environment_key = databricks_job_environment.serverless.key
  }

  schedule {
    quartz_cron_expression = var.slo_cron
    timezone_id            = "UTC"
    pause_status           = "UNPAUSED"
  }

  max_concurrent_runs = 1
}

# ----------------- SERVING (Phase 2) -----------------
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
