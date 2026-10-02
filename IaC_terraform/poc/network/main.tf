# =======================================================================
# Red POC: VPC dedicada minima con subredes privadas y VPC Endpoints.
# SIN NAT Gateway (sin costo fijo). Los contenedores alcanzan ECR/S3/Logs/
# Batch via endpoints. Refleja la arquitectura objetivo (subredes privadas
# sin IP publica) a escala minima para validar el circuito end-to-end.
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
    # bucket, key, region, dynamodb_table via -backend-config=backend.hcl
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
variable "vpc_cidr" {
  type    = string
  default = "10.42.0.0/16"
}
variable "azs" {
  type    = list(string)
  default = ["us-east-1a", "us-east-1b"]
}
variable "private_subnet_cidrs" {
  type    = list(string)
  default = ["10.42.1.0/24", "10.42.2.0/24"]
}

locals {
  tags = {
    Project = var.project_name
    Purpose = "POC"
    Owner   = "FlowHydro"
  }
}

resource "aws_vpc" "poc" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = merge(local.tags, { Name = "${var.project_name}-vpc" })
}

resource "aws_subnet" "private" {
  count             = length(var.private_subnet_cidrs)
  vpc_id            = aws_vpc.poc.id
  cidr_block        = var.private_subnet_cidrs[count.index]
  availability_zone = var.azs[count.index]
  tags              = merge(local.tags, { Name = "${var.project_name}-private-${count.index}" })
}

# Route table privada (sin ruta a Internet: todo va por endpoints)
resource "aws_route_table" "private" {
  vpc_id = aws_vpc.poc.id
  tags   = merge(local.tags, { Name = "${var.project_name}-rt-private" })
}

resource "aws_route_table_association" "private" {
  count          = length(aws_subnet.private)
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}

# --- Security group para los VPC Endpoints (HTTPS desde la VPC) ---
resource "aws_security_group" "endpoints" {
  name        = "${var.project_name}-endpoints-sg"
  description = "HTTPS desde la VPC hacia los VPC Endpoints"
  vpc_id      = aws_vpc.poc.id

  ingress {
    description = "HTTPS desde la VPC"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = merge(local.tags, { Name = "${var.project_name}-endpoints-sg" })
}

# --- Gateway endpoint para S3 (sin costo) ---
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.poc.id
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.private.id]
  tags              = merge(local.tags, { Name = "${var.project_name}-s3-endpoint" })
}

# --- Interface endpoints necesarios para Batch EC2 + pull ECR + logs ---
locals {
  interface_services = [
    "ecr.api",
    "ecr.dkr",
    "logs",
    "ecs",          # Batch usa el agente ECS en las instancias EC2
    "ecs-agent",
    "ecs-telemetry",
    "ssm",
    "ssmmessages",
    "ec2messages",
  ]
}

resource "aws_vpc_endpoint" "interface" {
  for_each            = toset(local.interface_services)
  vpc_id              = aws_vpc.poc.id
  service_name        = "com.amazonaws.${var.aws_region}.${each.value}"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.endpoints.id]
  private_dns_enabled = true
  tags                = merge(local.tags, { Name = "${var.project_name}-${each.value}-endpoint" })
}

output "vpc_id" {
  value = aws_vpc.poc.id
}
output "private_subnet_ids" {
  value = aws_subnet.private[*].id
}
output "private_route_table_id" {
  value = aws_route_table.private.id
}
output "vpc_cidr" {
  value = aws_vpc.poc.cidr_block
}