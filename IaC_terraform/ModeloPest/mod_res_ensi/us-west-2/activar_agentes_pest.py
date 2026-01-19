import boto3
import time
from datetime import datetime
import hcl2
import json

#leer recursos desde el estado de terraform
def read_terraform_state(state_file="terraform.tfstate"):
    """Lee el archivo tfstate y extrae recursos e IDs"""
    with open(state_file, 'r') as f:
        state = json.load(f)
    
    resources = {}
    for resource in state.get("resources", []):
        for instance in resource.get("instances", []):
            key = f"{resource['type']}.{resource['name']}"
            resources[key] = instance.get("attributes", {})
    
    return resources

#extraer variables de terraform
def read_terraform_variables(file_path):
    """
    Lee las variables de Terraform desde un archivo variables.tf
    Args:
        file_path: Ruta al archivo variables.tf
    Returns:
        Diccionario con las variables y sus valores por defecto
    """
    with open(file_path, 'r') as f:
        tf_dict = hcl2.load(f)
    
    variables = {}
    
    # hcl2.load() devuelve la estructura: {"variable": [{"nombre_var": {...}}]}
    if "variable" in tf_dict:
        var_list = tf_dict["variable"]
        if isinstance(var_list, list):
            # Si es una lista, iterar sobre cada elemento
            for var_item in var_list:
                if isinstance(var_item, dict):
                    for var_name, var_config in var_item.items():
                        if isinstance(var_config, dict) and "default" in var_config:
                            variables[var_name] = var_config["default"]
        elif isinstance(var_list, dict):
            # Si es un dict directo, iterar sobre items
            for var_name, var_config in var_list.items():
                if isinstance(var_config, dict) and "default" in var_config:
                    variables[var_name] = var_config["default"]
    
    return variables

# Parámetros configurables
cantidad_nuevos_agentes = 37  # Número de agentes a activar


#leer variables de terraform
tf_vars = read_terraform_variables('variables.tf')
#recuperar variables desde el archivo variables.tf
nombre_proyecto = tf_vars.get('project_name')
region_name = tf_vars.get('aws_region', "us-west-2")
private_subnet_ids = tf_vars.get('private_subnet_ids')
#recuperar recursos desde el estado de terraform
state = read_terraform_state()
security_group_id = state.get("aws_security_group.ecs_tasks_sg", {}).get("id")
master_host = 'master.' + nombre_proyecto + '.local'
pest_port = 4004
cluster_name = nombre_proyecto + '-cluster-' + region_name
task_definition = nombre_proyecto + '-task-agente-' + region_name
launch_type = 'FARGATE'  # Cambia a 'EC2' si no usas Fargate

#extraer variables de terraform

# Crear cliente ECS
ecs_client = boto3.client('ecs', region_name=region_name)  # Cambia a tu región

# Ejecutar tareas
for i in range(1, cantidad_nuevos_agentes+1):
    while True:
        response = ecs_client.run_task(
            cluster=cluster_name,
            launchType=launch_type,
            count=1,
            enableExecuteCommand=True,
            networkConfiguration={
                'awsvpcConfiguration': {
                    'subnets': private_subnet_ids,
                    'securityGroups': [security_group_id],
                    'assignPublicIp': 'DISABLED'
                }
            },
            taskDefinition=task_definition
        )

        try:
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} Tarea {i} ejecutada, ARN: {response['tasks'][0]['taskArn']}")
            time.sleep(0.05)  # Evita golpear el API con demasiadas peticiones por segundo
            break  # Salir del bucle si la tarea se ejecutó correctamente
        except Exception as e:
            print(f"{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} Error al ejecutar la tarea {i}: {response['failures'][0]['reason']}")
            print(f"{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} reintentando en 30 segundos...")
            # Espera para evitar sobrecargar el API de ECS
            time.sleep(30)  # Espera 30 segundos antes de reintentar

print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} Las {i} tareas han sido enviadas.")