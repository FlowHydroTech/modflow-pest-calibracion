# Archivo generado automáticamente: 2025-12-24T01:25:12.588608
# Edita este archivo y usa: terraform import <resource_type> <resource_id>

# SECURITY GROUPS
# terraform import aws_security_group.ecs_master_sg sg-XXXXX
resource "aws_security_group" "ecs_master_sg" {
  name        = "mod-res-ensi-master-sg-us-east-2"
  description = "Master PEST security group"
  vpc_id      = var.vpc_id
  
  tags = local.default_tags
}

# terraform import aws_security_group.ecs_tasks_sg sg-XXXXX
resource "aws_security_group" "ecs_tasks_sg" {
  name        = "mod-res-ensi-tasks-sg-us-east-2"
  description = "ECS tasks security group"
  vpc_id      = var.vpc_id
  
  tags = local.default_tags
}

# VPC ENDPOINTS
# terraform import aws_vpc_endpoint.ecr_api vpce-XXXXX
resource "aws_vpc_endpoint" "ecr_api" {
  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.us-east-2.ecr.api"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = var.private_subnet_ids
  security_group_ids  = [aws_security_group.vpc_endpoints_sg.id]
  private_dns_enabled = true
  
  tags = local.default_tags
}

# terraform import aws_vpc_endpoint.ecr_dkr vpce-XXXXX
resource "aws_vpc_endpoint" "ecr_dkr" {
  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.us-east-2.ecr.dkr"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = var.private_subnet_ids
  security_group_ids  = [aws_security_group.vpc_endpoints_sg.id]
  private_dns_enabled = true
  
  tags = local.default_tags
}

# ECS CLUSTER
# terraform import aws_ecs_cluster.cluster-pest-talabre mod-res-ensi-cluster-us-east-2
resource "aws_ecs_cluster" "cluster-pest-talabre" {
  name = "mod-res-ensi-cluster-us-east-2"
  
  tags = local.default_tags
}

# IAM ROLES (usar terraform import para establecer referencias)
# terraform import aws_iam_role.task_role mod-res-ensi-ecsTaskS3WriteRole-us-east-2
resource "aws_iam_role" "task_role" {
  name = "mod-res-ensi-ecsTaskS3WriteRole-us-east-2"
  
  tags = local.default_tags
}

# NOTAS:
# 1. Obtén los IDs de recursos con AWS CLI:
#    aws ec2 describe-security-groups --region us-east-2 --query 'SecurityGroups[?contains(GroupName, `mod-res-ensi`)].GroupId'
#    aws ec2 describe-vpc-endpoints --region us-east-2 --query 'VpcEndpoints[*].[VpcEndpointId,ServiceName]'
#
# 2. Usa terraform import para cada recurso:
#    terraform import aws_security_group.ecs_master_sg <group-id>
#
# 3. Terraform leerá el estado actual y lo registrará en terraform.tfstate
#
# 4. Verifica con: terraform plan (no debería mostrar cambios)
