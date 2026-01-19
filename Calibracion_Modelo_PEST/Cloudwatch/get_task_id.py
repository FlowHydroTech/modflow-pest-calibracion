#!/usr/bin/env python3
import boto3
import sys

def get_task_id(cluster_name, service_name, region="us-west-2"):
    """
    Obtiene el TASK_ID del servicio ECS especificado.
    
    Args:
        cluster_name: Nombre del cluster ECS
        service_name: Nombre del servicio ECS
        region: Región AWS (default: us-west-2)
    
    Returns:
        TASK_ID extraído del ARN
    """
    client = boto3.client("ecs", region_name=region)
    
    try:
        # Listar tasks del servicio
        response = client.list_tasks(
            cluster=cluster_name,
            serviceName=service_name,
            desiredStatus="RUNNING"
        )
        
        if not response["taskArns"]:
            print(f"Error: No hay tasks ejecutándose en {service_name}")
            return None
        
        # Extraer el TASK_ID del ARN (último elemento después del /)
        task_arn = response["taskArns"][0]
        task_id = task_arn.split("/")[-1]
        
        print(f"TASK_ARN: {task_arn}")
        print(f"TASK_ID: {task_id}")
        
        return task_id
        
    except Exception as e:
        print(f"Error al obtener TASK_ID: {e}")
        return None

if __name__ == "__main__":
    cluster = "mod-res-ensi-cluster-us-west-2"
    service = "mod-res-ensi-master-service"
    region = "us-west-2"
    
    task_id = get_task_id(cluster, service, region)
    
    if task_id:
        print(f"\n✓ TASK_ID obtenido: {task_id}")
        sys.exit(0)
    else:
        print("\n✗ No se pudo obtener el TASK_ID")
        sys.exit(1)
