import pandas as pd
import boto3
from datetime import datetime, timedelta
import re

# Configuración
region = "us-west-2"
project_name = "mod-res-ensi"
cluster_name = f"{project_name}-cluster-{region}"
service_name = f"{project_name}-master-service"
task_family_agent = f"{project_name}-task-agente-{region}"
log_group_master = f"/ecs/{project_name}-{region}-master"
log_group_agente = f"/ecs/{project_name}-{region}-agente"
log_stream_prefix_master = f"ecs/{project_name}-master"
log_stream_prefix_agente = f"ecs/{project_name}-agente"
find_logs = ["Running model", "Calculating Jacobian matrix", "Parallelisation of lambda search"]
hours_logs = 24  # Número de horas atrás para filtrar logs
max_agents = 998  # Número máximo de agentes permitidos en el clúster por región
log_file = "mod_res_ensi_west2_agente_logs20260105_0140.xlsx"
date_filter = "2026-01-05T02:38:39.758Z"
agent_count=1

#funcion para extraer el número de modelos a ejecutar
def extract_model_count(message):
    """
    Extrae el número de modelos a ejecutar de mensajes como:
    - 'Calculating Jacobian matrix: running model 400 times .....'
    - 'Parallelisation of lambda search: running model up to 37 times.....'
    
    Args:
        message: String del mensaje
    
    Returns:
        int con el número encontrado, o None
    """
    # Busca un número después de "model" y antes de "times"
    match = re.search(r'model\s+(?:up\s+to\s+)?(\d+)\s+times', message)
    if match:
        return int(match.group(1))
    return None

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

def get_logs_for_task(task_id, log_group, region="us-west-2", start_time=None, end_time=None):
    """
    Obtiene logs de CloudWatch para un TASK_ID específico.
    
    Args:
        task_id: ID de la tarea
        log_group: Nombre del log group (/ecs/mod-res-ensi-us-west-2-master)
        region: Región AWS
        start_time: Tiempo inicial en milisegundos (default: últimas 24 horas)
        end_time: Tiempo final en milisegundos (default: ahora)
    
    Returns:
        DataFrame con los logs
    """
    client = boto3.client("logs", region_name=region)
    
    # Configurar tiempos por defecto (últimas 24 horas)
    if not end_time:
        end_time = int(datetime.now().timestamp() * 1000)
    if not start_time:
        start_time = int((datetime.now() - timedelta(hours=24)).timestamp() * 1000)
    
    print(f"Buscando logs en: {log_group}")
    print(f"Para TASK_ID: {task_id}")
    print(f"Rango: {datetime.fromtimestamp(start_time/1000)} - {datetime.fromtimestamp(end_time/1000)}\n")
    
    try:
        rows = []
        paginator = client.get_paginator("filter_log_events")
        
        # El log stream sigue el patrón: /ecs/mod-res-ensi-us-west-2-master/mod-res-ensi-master/task_id
        log_stream_prefix = f"ecs/mod-res-ensi-master/{task_id}"
        
        page_iterator = paginator.paginate(
            logGroupName=log_group,
            logStreamNamePrefix=log_stream_prefix,
            startTime=start_time,
            endTime=end_time
        )
        
        for page in page_iterator:
            for event in page["events"]:
                rows.append({
                    "timestamp": datetime.fromtimestamp(event["timestamp"] / 1000),
                    "message": event["message"],
                    "logStreamName": event.get("logStreamName", "")
                })
        
        if not rows:
            print(f"⚠ No se encontraron logs para {log_stream_prefix}")
            return None
        
        df = pd.DataFrame(rows)
        df = df.sort_values("timestamp").reset_index(drop=True)
        
        print(f"✓ Se encontraron {len(df)} eventos de log\n")
        return df
        
    except Exception as e:
        print(f"Error al obtener logs: {e}")
        return None

def fetch_events(client, log_group, start_ms=None, end_ms=None):
    paginator = client.get_paginator('filter_log_events')
    kwargs = {"logGroupName": log_group, "interleaved": True}
    if start_ms: kwargs["startTime"] = start_ms
    if end_ms: kwargs["endTime"] = end_ms

    rows = []
    for page in paginator.paginate(**kwargs):
        for ev in page.get("events", []):
            rows.append({
                "timestamp": datetime.fromtimestamp(ev["timestamp"]/1000, tz=datetime.timezone.utc).isoformat(),
                "ingestionTime": datetime.fromtimestamp(ev["ingestionTime"]/1000, tz=datetime.timezone.utc).isoformat(),
                "logStreamName": ev.get("logStreamName"),
                "eventId": ev.get("eventId"),
                "message": ev.get("message")
            })
    return rows

def get_log_streams_by_prefix(log_group, prefix, region="us-west-2"):
    """
    Obtiene el log stream más reciente de un log group que comienza con un prefijo específico.
    
    Args:
        log_group: Nombre del log group (/ecs/mod-res-ensi-us-west-2-master)
        prefix: Prefijo del log stream (ecs/mod-res-ensi-master)
        region: Región AWS (default: us-west-2)
    
    Returns:
        Diccionario con el log stream que tiene el lastEventTimestamp más reciente, o None
    """
    client = boto3.client("logs", region_name=region)
    
    log_streams = []
    next_token = None
    
    try:
        print(f"Buscando log streams en: {log_group}")
        print(f"Con prefijo: {prefix}\n")
        
        while True:
            kwargs = {
                "logGroupName": log_group,
                "logStreamNamePrefix": prefix
            }
            if next_token:
                kwargs["nextToken"] = next_token
            
            response = client.describe_log_streams(**kwargs)
            
            for stream in response.get("logStreams", []):
                log_streams.append({
                    "logStreamName": stream["logStreamName"],
                    "creationTime": datetime.fromtimestamp(stream["creationTime"] / 1000),
                    "lastEventTimestamp": datetime.fromtimestamp(stream.get("lastEventTimestamp", 0) / 1000) if stream.get("lastEventTimestamp") else None,
                    "storedBytes": stream.get("storedBytes", 0)
                })
            
            next_token = response.get("nextToken")
            if not next_token:
                break
        
        if not log_streams:
            print(f"⚠ No se encontraron log streams con prefijo: {prefix}\n")
            return None
        
        # Retornar el stream con el lastEventTimestamp más reciente
        max_stream = max(log_streams, key=lambda x: x["lastEventTimestamp"] if x["lastEventTimestamp"] else datetime.min)
        
        print(f"✓ Stream más reciente encontrado:")
        print(f"  Nombre: {max_stream['logStreamName']}")
        print(f"  creationTime: {max_stream['creationTime']}")
        print(f"  Último evento: {max_stream['lastEventTimestamp']}\n")
        
        return max_stream
    
    except Exception as e:
        print(f"✗ Error al obtener log streams: {e}")
        return None

def get_latest_log_event(log_group, log_stream_name, keywords, region="us-west-2"):
    """
    Obtiene el último evento de log que contiene alguno de los keywords especificados.
    
    Args:
        log_group: Nombre del log group (/ecs/mod-res-ensi-us-west-2-master)
        log_stream_name: Nombre del log stream
        keywords: Lista de strings para buscar (ej: ["Running model", "Calculating Jacobian matrix", "Parallelisation of lambda search"])
        region: Región AWS (default: us-west-2)
    
    Returns:
        Diccionario con el último evento encontrado, o None
    """
    client = boto3.client("logs", region_name=region)
    
    try:
        print(f"Buscando eventos en: {log_stream_name}")
        print(f"Con keywords: {keywords}\n")
        
        matching_events = []
        next_token = None
        
        while True:
            kwargs = {
                "logGroupName": log_group,
                "logStreamName": log_stream_name,
                "startFromHead": True  # Comenzar desde el inicio del log stream
            }
            if next_token:
                kwargs["nextToken"] = next_token
            
            response = client.get_log_events(**kwargs)

            # Si no hay eventos, salir del bucle
            if not response.get('events'):
                break
            
            for event in response.get("events", []):
                message = event.get("message", "")
                # Verificar si el mensaje contiene alguno de los keywords
                if any(keyword in message for keyword in keywords):
                    matching_events.append({
                        "timestamp": datetime.fromtimestamp(event["timestamp"] / 1000),
                        "message": message
                    })
            
            next_token = response.get("nextForwardToken")
            if not next_token or next_token == response.get("nextBackwardToken"):
                break
        
        if not matching_events:
            print(f"⚠ No se encontraron eventos con los keywords especificados\n")
            return None
        
        # Retornar el evento más reciente (el último)
        latest_event = max(matching_events, key=lambda x: x["timestamp"])
        
        print(f"✓ Último evento encontrado:")
        print(f"  Timestamp: {latest_event['timestamp']}")
        print(f"  Mensaje: {latest_event['message'][:100]}...\n")
        
        return latest_event
    
    except Exception as e:
        print(f"✗ Error al obtener eventos de log: {e}")
        return None

def get_all_log_events(log_group, log_stream_name, start_time=None, region="us-west-2"):
    """
    Obtiene todos los eventos de log de un log stream desde un tiempo específico.
    
    Args:
        log_group: Nombre del log group (/ecs/mod-res-ensi-us-west-2-master)
        log_stream_name: Nombre del log stream
        start_time: Datetime desde el cual obtener los eventos (default: desde el inicio)
        region: Región AWS (default: us-west-2)
    
    Returns:
        DataFrame con todos los eventos de log ordenados por timestamp
    """
    client = boto3.client("logs", region_name=region)
    
    try:
        print(f"Recuperando todos los eventos de: {log_stream_name}")
        if start_time:
            print(f"Desde: {start_time}\n")
        else:
            print()
        
        events = []
        next_token = None
        
        while True:
            kwargs = {
                "logGroupName": log_group,
                "logStreamName": log_stream_name,
                "startFromHead": True  # Comenzar desde el inicio del log stream
            }
            if next_token:
                kwargs["nextToken"] = next_token
            
            response = client.get_log_events(**kwargs)
            
            # Si no hay eventos, salir del bucle
            if not response.get('events'):
                break
            
            for event in response.get("events", []):
                event_timestamp = datetime.fromtimestamp(event["timestamp"] / 1000)
                
                # Si start_time está especificado, filtrar eventos posteriores
                if start_time:
                    if event_timestamp >= start_time:
                        events.append({
                            "timestamp": event_timestamp,
                            "message": event.get("message", "")
                        })
                else:
                    events.append({
                        "timestamp": event_timestamp,
                        "message": event.get("message", "")
                    })
            
            next_token = response.get("nextForwardToken")
            # Salir si no hay más tokens
            if not next_token:
                break
        
        if not events:
            print(f"⚠ No se encontraron eventos en el log stream\n")
            return None
        
        # Crear DataFrame y ordenar por timestamp
        df = pd.DataFrame(events)
        df = df.sort_values("timestamp").reset_index(drop=True)
        
        print(f"✓ Se obtuvieron {len(df)} eventos de log")
        print(f"  Primero: {df['timestamp'].iloc[0]}")
        print(f"  Último: {df['timestamp'].iloc[-1]}\n")
        
        return df
    
    except Exception as e:
        print(f"✗ Error al obtener eventos de log: {e}")
        return None

def get_all_ecs_tasks(cluster_name, family, desired_status="RUNNING", region="us-west-2"):
    """
    Obtiene todas las tareas ECS de un clúster y familia específicos.
    
    Args:
        cluster_name: Nombre del clúster ECS
        family: Familia de tareas ECS
        desired_status: Estado deseado de las tareas (default: "RUNNING")
        region: Región AWS (default: us-west-2)
    """
    ecs = boto3.client("ecs", region_name=region)
    task_arns = []
    next_token = None

    while True:
        kwargs = {
            "cluster": cluster_name,
            "family": family,
            "desiredStatus": desired_status
        }
        if next_token:
            kwargs["nextToken"] = next_token

        response = ecs.list_tasks(**kwargs)
        task_arns.extend(response.get("taskArns", []))
        next_token = response.get("nextToken")

        if not next_token:
            break

    return task_arns

if __name__ == "__main__":
    # automatizar el aumento y disminución de agentes según logs.

    #Obtener el stream más reciente del master
    # max_stream = get_log_streams_by_prefix(
    #     log_group=log_group_master,
    #     prefix=log_stream_prefix_master,
    #     region=region
    # )

    # # 2. Obtener el último evento con los keywords
    # if max_stream:
    #     keywords = find_logs
    #     latest_event = get_latest_log_event(
    #         log_group=log_group_master,
    #         log_stream_name=max_stream["logStreamName"],
    #         keywords=keywords,
    #         region=region
    #     )
    
    # if latest_event:
    #     print(f"Timestamp: {latest_event['timestamp']}")
    #     print(f"Mensaje: {latest_event['message']}")

    #     agent_count_new = int(extract_model_count(latest_event['message']))  # 400
    #     date_filter = latest_event['timestamp']
    #     print(f"\nagent_count_new:{agent_count_new}. date_filter: {date_filter}\n")

    #     if agent_count_new == agent_count:
    #         print(f"\nNo se requieren nuevos agentes. Actualmente hay {agent_count} agentes.")
    #     elif agent_count_new > agent_count:
    #         print(f"\nAumentar el número de agentes requeridos desde {agent_count} a {agent_count_new}.")
    #     else:
    #         print(f"\nDisminuir el número de agentes requeridos desde {agent_count} a {agent_count_new}.")
    #     # recuperar tareas de agente del cluster
    #     agent_tasks = get_all_ecs_tasks(cluster_name, task_family_agent, desired_status="RUNNING", region=region)
    #     count_tasks = len(agent_tasks)
    #     print(f"Total de tareas de agente RUNNING: {count_tasks}")
        
    # exit()

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
    df_iniciado = df[(df['timestamp'] > date_filter) & (df['message'].str.contains('Running model', na=False))]
    print(f"Iniciados: {df_iniciado['logStreamName'].count()}")

    # Extraer el último valor del split por '/'
    task_ids_iniciados = df_iniciado['logStreamName'].str.split('/').str[-1].tolist()

    print(f"\nTotal de task IDs únicos en logs: {len(set(task_ids_iniciados))}")
    #print(f"Primeros 5 task IDs: {task_ids_iniciados[:5]}")


    df_completado = df[(df['timestamp'] > date_filter) & (df['message'].str.contains('Model run complete.', na=False))]
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
                family=task_family_agent,
                desiredStatus='RUNNING',
                nextToken=next_token
            )
        else:
            response = ecs.list_tasks(
                cluster=cluster_name,
                family=task_family_agent,
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

