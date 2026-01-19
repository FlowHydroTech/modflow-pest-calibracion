#!/usr/bin/env python3
"""
Script para auditar recursos AWS existentes y generar código Terraform.
Útil para leer infraestructura creada manualmente o en otra región.
"""

import boto3
import json
from datetime import datetime

def get_aws_session(region):
    """Crear sesión AWS."""
    return boto3.Session(region_name=region)

def audit_security_groups(ec2_client, project_name):
    """Auditar security groups."""
    print(f"\n{'='*60}")
    print(f"SECURITY GROUPS en {ec2_client.meta.region_name}")
    print(f"{'='*60}")
    
    try:
        response = ec2_client.describe_security_groups()
        sgs = [sg for sg in response['SecurityGroups'] 
               if project_name in sg.get('GroupName', '')]
        
        for sg in sgs:
            print(f"\nGrupo: {sg['GroupName']} ({sg['GroupId']})")
            print(f"  VPC: {sg['VpcId']}")
            print(f"  Tags: {sg.get('Tags', [])}")
            
            # Ingress rules
            if sg['IpPermissions']:
                print(f"  Ingress Rules:")
                for rule in sg['IpPermissions']:
                    print(f"    - Puerto {rule.get('FromPort')}-{rule.get('ToPort')} ({rule.get('IpProtocol')})")
            
            # Egress rules
            if sg['IpPermissionsEgress']:
                print(f"  Egress Rules:")
                for rule in sg['IpPermissionsEgress']:
                    print(f"    - Puerto {rule.get('FromPort')}-{rule.get('ToPort')} ({rule.get('IpProtocol')})")
        
        return sgs
    except Exception as e:
        print(f"Error al auditar SGs: {e}")
        return []

def audit_vpc_endpoints(ec2_client, project_name):
    """Auditar VPC endpoints."""
    print(f"\n{'='*60}")
    print(f"VPC ENDPOINTS en {ec2_client.meta.region_name}")
    print(f"{'='*60}")
    
    try:
        response = ec2_client.describe_vpc_endpoints()
        endpoints = [ep for ep in response['VpcEndpoints']]
        
        for ep in endpoints:
            tags = {tag['Key']: tag['Value'] for tag in ep.get('Tags', [])}
            if 'Project' in str(tags):
                print(f"\nEndpoint: {ep['VpcEndpointId']}")
                print(f"  Service: {ep['ServiceName']}")
                print(f"  Type: {ep['VpcEndpointType']}")
                print(f"  State: {ep['State']}")
                print(f"  VPC: {ep['VpcId']}")
                print(f"  Tags: {tags}")
        
        return endpoints
    except Exception as e:
        print(f"Error al auditar endpoints: {e}")
        return []

def audit_ecs_resources(ecs_client, project_name, region):
    """Auditar recursos ECS."""
    print(f"\n{'='*60}")
    print(f"ECS RESOURCES en {region}")
    print(f"{'='*60}")
    
    try:
        # Clusters
        clusters_response = ecs_client.list_clusters()
        print(f"\nClusters: {clusters_response['clusterArns']}")
        
        for cluster_arn in clusters_response.get('clusterArns', []):
            cluster_name = cluster_arn.split('/')[-1]
            
            # Services
            services_response = ecs_client.list_services(cluster=cluster_arn)
            print(f"\n  Services en {cluster_name}:")
            for service_arn in services_response.get('serviceArns', []):
                service_name = service_arn.split('/')[-1]
                print(f"    - {service_name}")
            
            # Task definitions
            task_defs = ecs_client.list_task_definitions()
            print(f"\n  Task Definitions:")
            for td_arn in task_defs.get('taskDefinitionArns', []):
                td_name = td_arn.split('/')[-1]
                if project_name in td_name:
                    print(f"    - {td_name}")
    
    except Exception as e:
        print(f"Error al auditar ECS: {e}")

def audit_iam_roles(iam_client, project_name):
    """Auditar roles IAM."""
    print(f"\n{'='*60}")
    print(f"IAM ROLES")
    print(f"{'='*60}")
    
    try:
        response = iam_client.list_roles()
        roles = [r for r in response['Roles'] 
                if project_name in r['RoleName']]
        
        for role in roles:
            print(f"\nRole: {role['RoleName']}")
            print(f"  Arn: {role['Arn']}")
            
            # Attached policies
            policies = iam_client.list_attached_role_policies(
                RoleName=role['RoleName']
            )
            print(f"  Attached Policies:")
            for policy in policies['AttachedPolicies']:
                print(f"    - {policy['PolicyName']}")
    
    except Exception as e:
        print(f"Error al auditar roles: {e}")

def generate_terraform_skeleton(project_name, region, output_file="audit_resources.tf"):
    """Generar esqueleto .tf para importar recursos."""
    
    skeleton = f"""# Archivo generado automáticamente: {datetime.now().isoformat()}
# Edita este archivo y usa: terraform import <resource_type> <resource_id>

# SECURITY GROUPS
# terraform import aws_security_group.ecs_master_sg sg-XXXXX
resource "aws_security_group" "ecs_master_sg" {{
  name        = "{project_name}-master-sg-{region}"
  description = "Master PEST security group"
  vpc_id      = var.vpc_id
  
  tags = local.default_tags
}}

# terraform import aws_security_group.ecs_tasks_sg sg-XXXXX
resource "aws_security_group" "ecs_tasks_sg" {{
  name        = "{project_name}-tasks-sg-{region}"
  description = "ECS tasks security group"
  vpc_id      = var.vpc_id
  
  tags = local.default_tags
}}

# VPC ENDPOINTS
# terraform import aws_vpc_endpoint.ecr_api vpce-XXXXX
resource "aws_vpc_endpoint" "ecr_api" {{
  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.{region}.ecr.api"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = var.private_subnet_ids
  security_group_ids  = [aws_security_group.vpc_endpoints_sg.id]
  private_dns_enabled = true
  
  tags = local.default_tags
}}

# terraform import aws_vpc_endpoint.ecr_dkr vpce-XXXXX
resource "aws_vpc_endpoint" "ecr_dkr" {{
  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.{region}.ecr.dkr"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = var.private_subnet_ids
  security_group_ids  = [aws_security_group.vpc_endpoints_sg.id]
  private_dns_enabled = true
  
  tags = local.default_tags
}}

# ECS CLUSTER
# terraform import aws_ecs_cluster.cluster-pest-talabre {project_name}-cluster-{region}
resource "aws_ecs_cluster" "cluster-pest-talabre" {{
  name = "{project_name}-cluster-{region}"
  
  tags = local.default_tags
}}

# IAM ROLES (usar terraform import para establecer referencias)
# terraform import aws_iam_role.task_role {project_name}-ecsTaskS3WriteRole-{region}
resource "aws_iam_role" "task_role" {{
  name = "{project_name}-ecsTaskS3WriteRole-{region}"
  
  tags = local.default_tags
}}

# NOTAS:
# 1. Obtén los IDs de recursos con AWS CLI:
#    aws ec2 describe-security-groups --region {region} --query 'SecurityGroups[?contains(GroupName, `{project_name}`)].GroupId'
#    aws ec2 describe-vpc-endpoints --region {region} --query 'VpcEndpoints[*].[VpcEndpointId,ServiceName]'
#
# 2. Usa terraform import para cada recurso:
#    terraform import aws_security_group.ecs_master_sg <group-id>
#
# 3. Terraform leerá el estado actual y lo registrará en terraform.tfstate
#
# 4. Verifica con: terraform plan (no debería mostrar cambios)
"""
    
    with open(output_file, 'w') as f:
        f.write(skeleton)
    
    print(f"\n✓ Esqueleto generado: {output_file}")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Auditar recursos AWS y generar código Terraform"
    )
    parser.add_argument("--region", default="us-east-2", help="Región AWS")
    parser.add_argument("--project", required=True, help="Nombre del proyecto (para filtrar recursos)")
    parser.add_argument("--output", default="audit_resources.tf", help="Archivo .tf de salida")
    
    args = parser.parse_args()
    
    print(f"Auditando recursos en {args.region} para proyecto {args.project}...\n")
    
    # Crear clientes
    session = get_aws_session(args.region)
    ec2 = session.client('ec2')
    ecs = session.client('ecs')
    iam = session.client('iam')
    
    # Auditar recursos
    audit_security_groups(ec2, args.project)
    audit_vpc_endpoints(ec2, args.project)
    audit_ecs_resources(ecs, args.project, args.region)
    audit_iam_roles(iam, args.project)
    
    # Generar esqueleto
    generate_terraform_skeleton(args.project, args.region, args.output)
    
    print("\nPróximos pasos:")
    print(f"1. Obtén los IDs de recursos con AWS CLI")
    print(f"2. Reemplaza los placeholders en {args.output}")
    print(f"3. Ejecuta: terraform import <resource_type> <resource_id>")
    print(f"4. Verifica con: terraform plan")

if __name__ == "__main__":
    main()
