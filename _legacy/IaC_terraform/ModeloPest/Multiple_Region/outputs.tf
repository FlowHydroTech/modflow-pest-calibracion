output "central_private_ip" {
  value       = aws_instance.central.private_ip
  description = "IP privada fija del nodo central EC2."
}

output "central_security_group_id" {
  value       = aws_security_group.central_sg.id
  description = "SG del nodo central."
}

output "ecr_central_repo_west2" {
  value       = aws_ecr_repository.central_west2.repository_url
  description = "Repo ECR central (us-west-2)."
}

output "ecr_host_repo_west2" {
  value       = aws_ecr_repository.host_west2.repository_url
  description = "Repo ECR host (us-west-2)."
}

output "ecr_host_repo_east1" {
  value       = aws_ecr_repository.host_east1.repository_url
  description = "Repo ECR host (us-east-1)."
}

output "ecr_host_repo_east2" {
  value       = aws_ecr_repository.host_east2.repository_url
  description = "Repo ECR host (us-east-2)."
}
output "s3_results_bucket_name" {
  value       = aws_s3_bucket.results_bucket.bucket
  description = "Nombre del bucket S3 para resultados."
}