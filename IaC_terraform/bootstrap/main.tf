# =======================================================================
# Bootstrap del backend remoto de Terraform (Fase 0 - F-01)
# Crea los recursos PERSISTENTES que almacenan el state de todas las
# calibraciones. Este modulo se aplica UNA SOLA VEZ por cuenta/region y
# NUNCA se destruye como parte del ciclo de vida de una calibracion.
#
# Uso inicial (una vez):
#   cd IaC_terraform/bootstrap
#   terraform init          # backend local solo para este bootstrap
#   terraform apply
#
# Despues, los modulos de calibracion usan el bucket y la tabla creados
# aqui como su backend "s3".
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

# Bucket S3 que almacena el state de Terraform (versionado + cifrado)
resource "aws_s3_bucket" "tf_state" {
  bucket = var.tf_state_bucket
  tags = {
    Name    = var.tf_state_bucket
    Purpose = "terraform-state"
    Owner   = "Modelamiento Numerico"
  }
}

resource "aws_s3_bucket_versioning" "tf_state" {
  bucket = aws_s3_bucket.tf_state.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tf_state" {
  bucket = aws_s3_bucket.tf_state.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Bloquear todo acceso publico al bucket de state
resource "aws_s3_bucket_public_access_block" "tf_state" {
  bucket                  = aws_s3_bucket.tf_state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Tabla DynamoDB para el locking del state
resource "aws_dynamodb_table" "tf_lock" {
  name         = var.tf_lock_table
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  tags = {
    Name    = var.tf_lock_table
    Purpose = "terraform-state-lock"
    Owner   = "Modelamiento Numerico"
  }
}