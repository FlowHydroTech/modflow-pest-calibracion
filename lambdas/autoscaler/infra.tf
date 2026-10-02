# =======================================================================
# Lambda Autoscaler de agentes PEST (Fase 1 - F-03, F-07)
# Reemplaza el loop manual de auto_scaling_tasks.py por una Lambda invocada
# por EventBridge cada N minutos, independiente de la laptop del operador.
#
# IAM con minimo privilegio (requisito 3.3): solo batch:ListJobs, SubmitJob,
# TerminateJob, DescribeJobs; cloudwatch:PutMetricData; logs lectura; ec2 describe
# (para obtener la IP del master).
# =======================================================================

variable "aws_region" {
  type    = string
  default = "us-east-1"
}
variable "project_name" { type = string }
variable "calibration_id" { type = string }
variable "job_queue_agents" { type = string }
variable "job_definition_agent" { type = string }
variable "log_group_master" { type = string }
variable "log_group_agents" { type = string }
variable "max_agents" {
  type    = number
  default = 300
}
variable "schedule_expression" {
  type    = string
  default = "rate(10 minutes)"
}
variable "lambda_zip_path" {
  type        = string
  description = "Ruta al artefacto .zip del Lambda"
}

# --- IAM Role de ejecucion con minimo privilegio ---
resource "aws_iam_role" "autoscaler" {
  name = "${var.project_name}-autoscaler-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "autoscaler" {
  name = "autoscaler-min-privilege"
  role = aws_iam_role.autoscaler.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "BatchJobManagement"
        Effect = "Allow"
        Action = [
          "batch:ListJobs",
          "batch:SubmitJob",
          "batch:TerminateJob",
          "batch:DescribeJobs"
        ]
        Resource = "*"
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
        Sid    = "ReadLogs"
        Effect = "Allow"
        Action = [
          "logs:FilterLogEvents",
          "logs:GetLogEvents",
          "logs:DescribeLogStreams"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:*:log-group:/batch/*"
      },
      {
        Sid      = "DescribeMasterInstance"
        Effect   = "Allow"
        Action   = ["ec2:DescribeInstances"]
        Resource = "*"
      },
      {
        Sid      = "LambdaBasicLogging"
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:${var.aws_region}:*:log-group:/aws/lambda/${var.project_name}-autoscaler:*"
      }
    ]
  })
}

# --- Lambda ---
resource "aws_lambda_function" "autoscaler" {
  function_name    = "${var.project_name}-autoscaler"
  role             = aws_iam_role.autoscaler.arn
  handler          = "handler.handler"
  runtime          = "python3.12"
  timeout          = 120
  filename         = var.lambda_zip_path
  source_code_hash = filebase64sha256(var.lambda_zip_path)

  environment {
    variables = {
      CALIBRATION_ID       = var.calibration_id
      REGION               = var.aws_region
      JOB_QUEUE_AGENTS     = var.job_queue_agents
      JOB_DEFINITION_AGENT = var.job_definition_agent
      LOG_GROUP_MASTER     = var.log_group_master
      LOG_GROUP_AGENTS     = var.log_group_agents
      MAX_AGENTS           = tostring(var.max_agents)
    }
  }
}

# --- EventBridge: invocacion periodica ---
resource "aws_cloudwatch_event_rule" "autoscaler_schedule" {
  name                = "${var.project_name}-autoscaler-schedule"
  schedule_expression = var.schedule_expression
}

resource "aws_cloudwatch_event_target" "autoscaler" {
  rule = aws_cloudwatch_event_rule.autoscaler_schedule.name
  arn  = aws_lambda_function.autoscaler.arn
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.autoscaler.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.autoscaler_schedule.arn
}

output "autoscaler_function_name" {
  value = aws_lambda_function.autoscaler.function_name
}