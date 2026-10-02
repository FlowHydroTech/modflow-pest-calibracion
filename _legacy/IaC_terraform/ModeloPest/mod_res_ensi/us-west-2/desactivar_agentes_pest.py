import boto3
import time
from datetime import datetime
import hcl2

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


# Parámetros básicos
#leer variables de terraform
tf_vars = read_terraform_variables('variables.tf')
nombre_proyecto = tf_vars.get('nombre_proyecto', 'mod-res-ensi')
region_name = tf_vars.get('region', 'us-west-2')
cluster_name = nombre_proyecto + '-cluster-' + region_name
task_family_agente = nombre_proyecto + '-task-agente-' + region_name
# Crear cliente ECS
ecs_client = boto3.client('ecs', region_name=region_name)  # Cambia a tu región

# Función para eliminar una tarea específica
def stop_task(task_arn):
    """
    Detiene (elimina) una tarea del cluster
    
    Args:
        task_arn: ARN completo de la tarea o solo el ID
    """
    try:
        response = ecs_client.stop_task(
            cluster=cluster_name,
            task=task_arn,
            reason='Stopped manually via script'
        )
        print(f"✓ Tarea detenida: {task_arn}")
        return response
    except Exception as e:
        print(f"✗ Error al detener tarea {task_arn}: {str(e)}")
        return None
    

# Listar todas las tareas running (con paginación)
task_arns = []
next_token = None

while True:
    if next_token:
        response = ecs_client.list_tasks(
            cluster=cluster_name,
            family=task_family_agente,
            desiredStatus='RUNNING',
            nextToken=next_token
        )
    else:
        response = ecs_client.list_tasks(
            cluster=cluster_name,
            family=task_family_agente,
            desiredStatus='RUNNING'
        )
    
    task_arns.extend(response['taskArns'])
    
    # Verificar si hay más páginas
    next_token = response.get('nextToken')
    if not next_token:
        break

print(f"Total de tareas (agentes) RUNNING: {len(task_arns)}\n")

if task_arns:
    # Describir las tareas en lotes de 100 (límite de describe_tasks)
    all_tasks = []
    for i in range(0, len(task_arns), 100):
        batch = task_arns[i:i+100]
        tasks_details = ecs_client.describe_tasks(
            cluster=cluster_name,
            tasks=batch
        )
        all_tasks.extend(tasks_details['tasks'])
    
    # Detener cada tarea
    for i, task in enumerate(all_tasks, 1):
        #print(f"=== Deteniendo Tarea {i} {task['taskArn']} ===")
        stop_task(task['taskArn'])