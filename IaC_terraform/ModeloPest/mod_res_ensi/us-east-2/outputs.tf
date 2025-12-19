output "central_private_ip" {
  value       = aws_instance.central.private_ip
  description = "IP privada fija del nodo central EC2."
}

output "central_security_group_id" {
  value       = aws_security_group.central_sg.id
  description = "SG del nodo central."
}

output "ecr_central_repo_east2" {
  value       = var.ecr_image_central
  description = "Repo ECR central (us-east-2)."
}

output "ecr_host_repo_east2" {
  value       = var.ecr_image_host_east2
  description = "Repo ECR host (us-east-2)."
}

output "s3_results_bucket_name" {
  value       = data.aws_s3_bucket.results.bucket
  description = "Nombre del bucket S3 para resultados."
}