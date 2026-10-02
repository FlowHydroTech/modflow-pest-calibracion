variable "aws_region" {
  description = "Region donde se crean el bucket de state y la tabla de locks"
  type        = string
  default     = "us-east-1"
}

variable "tf_state_bucket" {
  description = "Nombre del bucket S3 para el state de Terraform (debe ser globalmente unico)"
  type        = string
}

variable "tf_lock_table" {
  description = "Nombre de la tabla DynamoDB para el locking del state"
  type        = string
  default     = "terraform-state-lock"
}