output "tf_state_bucket" {
  description = "Bucket S3 creado para el state de Terraform"
  value       = aws_s3_bucket.tf_state.id
}

output "tf_lock_table" {
  description = "Tabla DynamoDB creada para el locking del state"
  value       = aws_dynamodb_table.tf_lock.name
}