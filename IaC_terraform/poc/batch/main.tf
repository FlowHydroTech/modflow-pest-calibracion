# =======================================================================
# Batch POC minimo: valida el circuito Batch + CloudWatch + Quality Engine
# con una instancia pequena (t3.small On-Demand) y la imagen dummy sin Wine.
# Modo autonomo: un solo job master que simula la calibracion (sin agentes),
# suficiente para validar logs -> metricas -> clasificacion de calidad.
# Lee los datos de red del state remoto del modulo poc/network.
# =======================================================================

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  backend "s3" {
    encrypt = true
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}
variable "project_name" {
  type    = string
  default = "pest-poc"
}
variable "ecr_image" {
  type        = string
  description = "URI con tag de la imagen dummy en ECR"
}
variable "instance_types" {
  type    = list(string)
  default = ["c7i-flex.large"]
}
variable "max_vcpus" {
  type    = number
  default = 2
}

# --- Leer la red POC desde su state remoto ---
data "terraform_remote_state" "network" {
  backend = "s3"
  config = {
    bucket         = "803037204233-pest-terraform-state"
    key            = "pest-poc/network/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "terraform-state-lock"
  }
}

locals {
  tags       = { Project = var.project_name, Purpose = "POC", Owner = "FlowHydro" }
  vpc_id     = data.terraform_remote_state.network.outputs.vpc_id
  subnet_ids = data.terraform_remote_state.network.outputs.private_subnet_ids
}

# --- CloudWatch Log Group del master (retencion corta para POC) ---
resource "aws_cloudwatch_log_group" "master" {
  name              = "/batch/${var.project_name}-master"
  retention_in_days = 7
  tags              = local.tags
}

# --- IAM: Job (task) role con S3 restringido al bucket de resultados POC ---
resource "aws_iam_role" "job" {
  name = "${var.project_name}-job-role"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
  tags = local.tags
}

resource "aws_iam_role_policy" "job_s3" {
  name = "s3-results"
  role = aws_iam_role.job.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:PutObject", "s3:GetObject", "s3:ListBucket"]
      Resource = [
        "arn:aws:s3:::803037204233-pest-poc-results",
        "arn:aws:s3:::803037204233-pest-poc-results/*"
      ]
    }]
  })
}

resource "aws_iam_role_policy" "job_logs" {
  name = "cloudwatch-logs"
  role = aws_iam_role.job.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
      Resource = "arn:aws:logs:${var.aws_region}:*:log-group:/batch/*"
    }]
  })
}

# --- IAM: Batch service role ---
resource "aws_iam_role" "batch_service" {
  name = "${var.project_name}-batch-service-role"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "batch.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
  tags = local.tags
}

resource "aws_iam_role_policy_attachment" "batch_service" {
  role       = aws_iam_role.batch_service.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBatchServiceRole"
}

# --- IAM: EC2 instance role para las instancias Batch ---
resource "aws_iam_role" "instance" {
  name = "${var.project_name}-instance-role"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "ec2.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
  tags = local.tags
}

resource "aws_iam_role_policy_attachment" "instance_ecs" {
  role       = aws_iam_role.instance.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceforEC2Role"
}

resource "aws_iam_role_policy_attachment" "instance_ssm" {
  role       = aws_iam_role.instance.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "instance" {
  name = "${var.project_name}-instance-profile"
  role = aws_iam_role.instance.name
  tags = local.tags
}

# --- SG de las instancias Batch (egress only; alcanzan endpoints) ---
resource "aws_security_group" "batch" {
  name        = "${var.project_name}-batch-sg"
  description = "Batch POC instances - egress only"
  vpc_id      = local.vpc_id
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = local.tags
}

# --- Compute Environment On-Demand (instancia pequena) ---
resource "aws_batch_compute_environment" "poc" {
  compute_environment_name = "${var.project_name}-ce"
  type         = "MANAGED"
  state        = "ENABLED"
  service_role = aws_iam_role.batch_service.arn

  compute_resources {
    type                = "EC2"
    allocation_strategy = "BEST_FIT_PROGRESSIVE"
    instance_type       = var.instance_types
    min_vcpus           = 0
    max_vcpus           = var.max_vcpus
    instance_role       = aws_iam_instance_profile.instance.arn
    subnets             = local.subnet_ids
    security_group_ids  = [aws_security_group.batch.id]
    tags                = local.tags
  }
  tags       = local.tags
  depends_on = [aws_iam_role_policy_attachment.batch_service]
}

resource "aws_batch_job_queue" "poc" {
  name     = "${var.project_name}-queue"
  state    = "ENABLED"
  priority = 1
  compute_environment_order {
    order               = 1
    compute_environment = aws_batch_compute_environment.poc.arn
  }
  tags = local.tags
}

# --- Job Definition autonomo (dummy) ---
resource "aws_batch_job_definition" "poc" {
  name = "${var.project_name}-job-def"
  type = "container"
  container_properties = jsonencode({
    image   = var.ecr_image
    command = ["/bin/bash", "/app/entrypoint_autonomo.sh"]
    resourceRequirements = [
      { type = "VCPU", value = "1" },
      { type = "MEMORY", value = "1800" }
    ]
    jobRoleArn = aws_iam_role.job.arn
    environment = [
      { name = "NOMBRE_MODELO_PEST", value = "dummy.pst" },
      { name = "BUCKET_NAME", value = "803037204233-pest-poc-results" },
      { name = "AWS_REGION", value = var.aws_region }
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.master.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "master"
      }
    }
  })
  retry_strategy { attempts = 1 }
  tags = local.tags
}

# --- Bucket de resultados POC ---
resource "aws_s3_bucket" "results" {
  bucket = "803037204233-pest-poc-results"
  tags   = local.tags
}

output "job_queue"       { value = aws_batch_job_queue.poc.name }
output "job_definition"  { value = aws_batch_job_definition.poc.name }
output "log_group_master" { value = aws_cloudwatch_log_group.master.name }
output "results_bucket"  { value = aws_s3_bucket.results.id }