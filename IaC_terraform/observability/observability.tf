# =======================================================================
# Observabilidad: SNS + CloudWatch Alarms (Fase 2 - requisitos 10.4-10.6)
# Alarmas sobre las metricas custom del namespace PEST/Calibration que publica
# el Lambda Autoscaler. Todas las alarmas notifican a un SNS topic suscrito al
# email del operador.
# =======================================================================

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}
variable "project_name" { type = string }
variable "calibration_id" { type = string }
variable "alert_email" {
  type        = string
  description = "Email para recibir alertas (no versionar valores reales)"
}
variable "ttl_hours" {
  type    = number
  default = 72
}

# --- SNS topic de alertas ---
resource "aws_sns_topic" "pest_alerts" {
  name = "${var.project_name}-alerts"
  tags = {
    Project       = var.project_name
    CalibrationId = var.calibration_id
  }
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.pest_alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# --- Alarma CRITICAL: master no saludable (requisitos 10.4, 10.5) ---
# MasterHealth=0 durante 2 periodos consecutivos de 5 min.
resource "aws_cloudwatch_metric_alarm" "master_health" {
  alarm_name          = "${var.project_name}-master-unhealthy"
  alarm_description   = "El master PEST no reporta salud (MasterHealth=0) por 10 min"
  namespace           = "PEST/Calibration"
  metric_name         = "MasterHealth"
  statistic           = "Minimum"
  comparison_operator = "LessThanThreshold"
  threshold           = 1
  period              = 300
  evaluation_periods  = 2
  treat_missing_data  = "breaching"

  dimensions = {
    CalibrationId = var.calibration_id
  }

  alarm_actions = [aws_sns_topic.pest_alerts.arn]
  ok_actions    = [aws_sns_topic.pest_alerts.arn]
  tags = {
    CalibrationId = var.calibration_id
    Severity      = "CRITICAL"
  }
}

# --- Alarma WARNING: TTL de infraestructura excedido (requisito 10.6) ---
# CalibrationRuntime (segundos) supera ttl_hours * 3600.
resource "aws_cloudwatch_metric_alarm" "infra_ttl" {
  alarm_name          = "${var.project_name}-infra-ttl-exceeded"
  alarm_description   = "La calibracion lleva activa mas de ${var.ttl_hours} horas"
  namespace           = "PEST/Calibration"
  metric_name         = "CalibrationRuntime"
  statistic           = "Maximum"
  comparison_operator = "GreaterThanThreshold"
  threshold           = var.ttl_hours * 3600
  period              = 300
  evaluation_periods  = 1
  treat_missing_data  = "notBreaching"

  dimensions = {
    CalibrationId = var.calibration_id
  }

  alarm_actions = [aws_sns_topic.pest_alerts.arn]
  tags = {
    CalibrationId = var.calibration_id
    Severity      = "WARNING"
  }
}

output "sns_topic_arn" {
  value = aws_sns_topic.pest_alerts.arn
}