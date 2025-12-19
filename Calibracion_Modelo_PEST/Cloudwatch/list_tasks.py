import boto3

# Configuración
cluster_name = "mod-res-ensi-cluster-us-west-2"
task_family = "mod-res-ensi-task-agente-us-west-2"
region = "us-west-2"

# Cliente ECS
ecs = boto3.client('ecs', region_name=region)

# Listar todas las tareas running (con paginación)
task_arns = []
next_token = None

while True:
    if next_token:
        response = ecs.list_tasks(
            cluster=cluster_name,
            family=task_family,
            desiredStatus='RUNNING',
            nextToken=next_token
        )
    else:
        response = ecs.list_tasks(
            cluster=cluster_name,
            family=task_family,
            desiredStatus='RUNNING'
        )
    
    task_arns.extend(response['taskArns'])
    
    # Verificar si hay más páginas
    next_token = response.get('nextToken')
    if not next_token:
        break

print(f"Total de tareas RUNNING: {len(task_arns)}\n")

if task_arns:
    # Describir las tareas en lotes de 100 (límite de describe_tasks)
    all_tasks = []
    for i in range(0, len(task_arns), 100):
        batch = task_arns[i:i+100]
        tasks_details = ecs.describe_tasks(
            cluster=cluster_name,
            tasks=batch
        )
        all_tasks.extend(tasks_details['tasks'])
    
    # Mostrar información de cada tarea
    for i, task in enumerate(all_tasks, 1):
        print(f"=== Tarea {i} ===")
        print(f"Task ARN: {task['taskArn']}")
        print(f"Task ID: {task['taskArn'].split('/')[-1]}")
        print(f"Status: {task['lastStatus']}")
        print(f"Desired Status: {task['desiredStatus']}")
        print(f"Started At: {task.get('startedAt', 'N/A')}")
        print(f"Launch Type: {task['launchType']}")
        
        # Mostrar contenedores
        for container in task['containers']:
            print(f"  Container: {container['name']}")
            print(f"  Status: {container['lastStatus']}")
        
        print()
else:
    print("No hay tareas RUNNING en este momento.")

# Función para eliminar una tarea específica
def stop_task(task_arn):
    """
    Detiene (elimina) una tarea del cluster
    
    Args:
        task_arn: ARN completo de la tarea o solo el ID
    """
    try:
        response = ecs.stop_task(
            cluster=cluster_name,
            task=task_arn,
            reason='Stopped manually via script'
        )
        print(f"✓ Tarea detenida: {task_arn}")
        return response
    except Exception as e:
        print(f"✗ Error al detener tarea {task_arn}: {str(e)}")
        return None

# Ejemplo de uso:
# Para detener una tarea específica, descomenta y proporciona el Task ID o ARN:
# stop_task("TASK_ID_AQUI")

# Para detener TODAS las tareas (¡CUIDADO!), descomenta:
# for task_arn in task_arns:
#     stop_task(task_arn)
