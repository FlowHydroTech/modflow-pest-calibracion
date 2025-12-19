import pandas as pd
import boto3

# Configuración
cluster_name = "mod-res-ensi-cluster-us-west-2"
task_family = "mod-res-ensi-task-agente-stop-us-west-2"
region = "us-west-2"
fecha_filtro = pd.to_datetime('2025-12-18T15:07:03.326Z') #fecha filtro inicial para logs de agentes
log_file = "mod_res_ensi_agente_logs20251218_1232.xlsx"

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

# Leer el archivo Excel
df = pd.read_excel(log_file)

# Mostrar los primeros 5 registros
print(df.head())

# Información adicional del DataFrame
print(f"\nTotal de registros: {len(df)}")
print(f"\nColumnas: {list(df.columns)}")
df['timestamp'] = pd.to_datetime(df['timestamp'], format='ISO8601')
print(f"\ndtype: {df.dtypes}")

# Filtrar por timestamp y mensaje
df_iniciado = df[(df['timestamp'] > fecha_filtro) & (df['message'].str.contains('Running model', na=False))]
print(f"Iniciados: {df_iniciado['logStreamName'].count()}")

# Extraer el último valor del split por '/'
task_ids_iniciados = df_iniciado['logStreamName'].str.split('/').str[-1].tolist()

print(f"\nTotal de task IDs únicos en logs: {len(set(task_ids_iniciados))}")
#print(f"Primeros 5 task IDs: {task_ids_iniciados[:5]}")


df_completado = df[(df['timestamp'] > fecha_filtro) & (df['message'].str.contains('Model run complete.', na=False))]
print(f"Completados: {df_completado['logStreamName'].count()}")

# Extraer el último valor del split por '/'
task_ids_completados = df_completado['logStreamName'].str.split('/').str[-1].tolist()


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
    k=0
    j=0
    for i, task in enumerate(all_tasks, 1):
        # print(f"=== Tarea {i} ===")
        # print(f"Task ARN: {task['taskArn']}")
        # print(f"Task: {task['taskArn'].split('/')[-1]}")
        # print(f"Task ID: {task['taskArn'].split('/')[-1]}")
        if task['taskArn'].split('/')[-1] in task_ids_iniciados:
            k+=1
            if task['taskArn'].split('/')[-1] not in task_ids_completados:
                # encontrada pero no completada
                print(f"⚠ {task['taskArn'].split('/')[-1]} está INICIADA pero NO completada")
                #stop_task(task['taskArn'])
            else:
                # encontrada y completada
                print(f"✓ {task['taskArn'].split('/')[-1]} está completada")
                #stop_task(task['taskArn'])
            #print(f"✓ {task['taskArn'].split('/')[-1]} está en la lista")
        else:
            #no encontrada, se elimina la tarea
            j+=1
            #stop_task(task['taskArn'])
            #print(f"✗ {task['taskArn'].split('/')[-1]} NO está en la lista")
        # print(f"Status: {task['lastStatus']}")
        # print(f"Desired Status: {task['desiredStatus']}")
        # print(f"Started At: {task.get('startedAt', 'N/A')}")
        # print(f"Launch Type: {task['launchType']}")
        
        # # Mostrar contenedores
        # for container in task['containers']:
        #     print(f"  Container: {container['name']}")
        #     print(f"  Status: {container['lastStatus']}")
        
        # print()
    print(f"\nTotal de tareas encontradas en logs: {k}")
    print(f"Total de tareas NO encontradas en logs: {j}\n")
else:
    print("No hay tareas RUNNING en este momento.")

