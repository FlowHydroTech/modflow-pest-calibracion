# =======================================================================
# Lambda ExtractPhiMetrics (Fase 3 - requisitos 11.1-11.6, 3.4)
# Extrae Phi de los logs del master, publica metricas en PEST/Calibration y
# clasifica el QualityState. IAM minimo (requisito 3.4): solo lectura de logs,
# PutMetricData en el namespace y publicacion al SNS de alertas.
# =======================================================================

variable "aws_region" {
  type    = string
  default = "us-east-1"
}
variable "project_name" { type = string }
variable "calibration_id" { type = string }
variable "log_group_master" { type = string }
variable "sns_topic_arn" { type = string }
variable "lambda_zip_path" {
  type        = string
  description = "Ruta al artefacto .zip del Lambda ExtractPhi"
}

resource "aws_iam_role" "extract_phi" {
  name = "${var.project_name}-extract-phi-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "extract_phi" {
  name = "extract-phi-min-privilege"
  role = aws_iam_role.extract_phi.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ReadMasterLogs"
        Effect   = "Allow"
        Action   = ["logs:FilterLogEvents", "logs:GetLogEvents", "logs:DescribeLogStreams"]
        Resource = "arn:aws:logs:${var.aws_region}:*:log-group:/batch/*"
      },
      {
        Sid      = "PublishMetrics"
        Effect   = "Allow"
        Action   = ["cloudwatch:PutMetricData"]
        Resource = "*"
        Condition = {
          StringEquals = { "cloudwatch:namespace" = "PEST/Calibration" }
        }
      },
      {
        Sid      = "PublishAlerts"
        Effect   = "Allow"
        Action   = ["sns:Publish"]
        Resource = var.sns_topic_arn
      },
      {
        Sid      = "LambdaLogging"
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:${var.aws_region}:*:log-group:/aws/lambda/${var.project_name}-extract-phi:*"
      }
    ]
  })
}

resource "aws_lambda_function" "extract_phi" {
  function_name    = "${var.project_name}-extract-phi"
  role             = aws_iam_role.extract_phi.arn
  handler          = "handler.handler"
  runtime          = "python3.12"
  timeout          = 120
  filename         = var.lambda_zip_path
  source_code_hash = filebase64sha256(var.lambda_zip_path)

  environment {
    variables = {
      CALIBRATION_ID   = var.calibration_id
      REGION           = var.aws_region
      LOG_GROUP_MASTER = var.log_group_master
      SNS_TOPIC_ARN    = var.sns_topic_arn
    }
  }
}

# Invocacion periodica (cada 5 min) para reevaluar Phi y calidad.
resource "aws_cloudwatch_event_rule" "extract_phi_schedule" {
  name                = "${var.project_name}-extract-phi-schedule"
  schedule_expression = "rate(5 minutes)"
}

resource "aws_cloudwatch_event_target" "extract_phi" {
  rule = aws_cloudwatch_event_rule.extract_phi_schedule.name
  arn  = aws_lambda_function.extract_phi.arn
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.extract_phi.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.extract_phi_schedule.arn
}

output "extract_phi_function_name" {
  value = aws_lambda_function.extract_phi.function_name
}