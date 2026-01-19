import pandas as pd
import boto3
import time
from datetime import datetime, timedelta, timezone
import re
import hcl2
import json

# Configuración
find_logs = ["Running model", "Calculating Jacobian matrix", "Parallelisation of lambda search"]
find_model_start = "Running model"
find_model_end = "Model run complete"
agent_count_max = 998   #máximo número de agentes permitidos en la region us-west-2 de AWS. 1000 vcpu (2 master + 998 agentes) Fargate.
minutes_wait_between_checks = 12    # minutos entre cada verificación de logs cuando se requiere ajuste de agentes, se recomienda 5 o más minutos
                                    # por el tiempo de uptime de agentes, agentes sin log son apagados automáticamente por este script.
minutes_wait_between_checks_without_change = 3  # minutos entre cada verificación de logs cuando no requiere aumento de agentes.
date_filter = None      #fecha del último log del master, None para que tome la primera encontrada.
id_task_master = None      #fecha del último log del master, None para que tome la primera encontrada.

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
    # Busca un número después de "model" y antes de "time/times"
    match = re.search(r'model\s+(?:up\s+to\s+)?(\d+)\s+times?', message)
    if match:
        return int(match.group(1))
    return None

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
        print(f"Con prefijo: {prefix}")
        
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
            print(f"⚠ No se encontraron log streams con prefijo: {prefix}")
            return None
        
        # Retornar el stream con el lastEventTimestamp más reciente
        max_stream = max(log_streams, key=lambda x: x["lastEventTimestamp"] if x["lastEventTimestamp"] else datetime.min)
        
        print(f"✓ Stream más reciente encontrado:")
        print(f"  Nombre: {max_stream['logStreamName']}")
        print(f"  creationTime: {max_stream['creationTime']}")
        print(f"  Último evento: {max_stream['lastEventTimestamp']}")
        
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
        print(f"Con keywords: {keywords}")
        
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
            print(f"⚠ No se encontraron eventos con los keywords especificados")
            return None
        
        # Retornar el evento más reciente (el último)
        latest_event = max(matching_events, key=lambda x: x["timestamp"])
        
        print(f"✓ Último evento encontrado:")
        print(f"  Timestamp: {latest_event['timestamp']}")
        print(f"  Mensaje: {latest_event['message'][:100]}...")
        
        return latest_event
    
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

def clean_message(msg):
    """Elimina caracteres no permitidos en Excel (caracteres de control)."""
    if not msg:
        return msg
    # Eliminar caracteres de control excepto tab, newline, carriage return
    import unicodedata
    cleaned = "".join(
        ch if unicodedata.category(ch)[0] != "C" or ch in ("\t", "\n", "\r")
        else "" for ch in msg
    )
    return cleaned.strip()

#recuperar logs de cloudwatch
def fetch_events(log_group, start_ms=None, end_ms=None, region="us-west-2"):
    client = boto3.client("logs", region_name=region)
    paginator = client.get_paginator('filter_log_events')
    kwargs = {"logGroupName": log_group, "interleaved": True}
    if start_ms: kwargs["startTime"] = start_ms
    if end_ms: kwargs["endTime"] = end_ms

    rows = []
    for page in paginator.paginate(**kwargs):
        for ev in page.get("events", []):
            rows.append({
                "timestamp": datetime.fromtimestamp(ev["timestamp"]/1000, tz=timezone.utc).isoformat(),
                "ingestionTime": datetime.fromtimestamp(ev["ingestionTime"]/1000, tz=timezone.utc).isoformat(),
                #"timestamp": datetime.utcfromtimestamp(ev["timestamp"]/1000).isoformat() + "Z",
                #"ingestionTime": datetime.utcfromtimestamp(ev["ingestionTime"]/1000).isoformat() + "Z",
                "logStreamName": ev.get("logStreamName"),
                "eventId": ev.get("eventId"),
                "message": clean_message(ev.get("message"))
            })
    return rows

# Función para eliminar una tarea específica
def stop_task(task_arn, region="us-west-2", cluster_name=None):
    """
    Detiene (elimina) una tarea del cluster
    
    Args:
        task_arn: ARN completo de la tarea o solo el ID
    """
    try:
        ecs = boto3.client("ecs", region_name=region)
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

def parse_iso(s):
    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s, fmt)
            return int(dt.timestamp() * 1000)
        except Exception:
            pass
    raise ValueError("Formato de fecha inválido. Usa YYYY-MM-DD o YYYY-MM-DDTHH:MM:SS")

def start_task(count_agents, cluster_name, task_definition, subnets_id, security_group_id, launch_type="FARGATE", region="us-west-2"):
    # Crear cliente ECS
    ecs_client = boto3.client('ecs', region_name=region)
    batch_size = 10  # Lanzar 10 tareas a la vez
    
    # Ejecutar tareas en lotes de 10
    for i in range(0, count_agents, batch_size):
        tasks_to_launch = min(batch_size, count_agents - i)
        while True:
            response = ecs_client.run_task(
                cluster=cluster_name,
                launchType=launch_type,
                count=tasks_to_launch,
                enableExecuteCommand=True,
                networkConfiguration={
                    'awsvpcConfiguration': {
                        'subnets': subnets_id,
                        'securityGroups': [security_group_id],
                        'assignPublicIp': 'DISABLED'
                    }
                },
                taskDefinition=task_definition
            )

            try:
                print(f"{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} Tareas {i+1} a {i+tasks_to_launch} ejecutadas")
                time.sleep(0.5)  # Pequeña pausa entre lotes
                break  # Salir del bucle si se ejecutó correctamente
            except Exception as e:
                print(f"{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} Error al ejecutar tareas {i+1} a {i+tasks_to_launch}: {str(e)}")
                print(f"{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} reintentando en 30 segundos...")
                time.sleep(30)

    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} Todos los {count_agents} agentes han sido enviados.")

def validate_stop_tasks(task_ids, df_count_running, region, cluster_name):
    tasks_to_stop_list = []
    task_running_count = 0
    for task_id in task_ids:
        if task_id in df_count_running['task_id'].values:
            stop_task_flag = df_count_running[df_count_running['task_id'] == task_id]['stop_task'].values[0]
            if stop_task_flag:
                print(f"⚠ {task_id} - Modelo Ejecutado (stop_task=True) → DETENER")
                stop_task(task_id, region=region, cluster_name=cluster_name)
                tasks_to_stop_list.append(task_id)
            else:
                print(f"→ {task_id} - Aún procesando modelo (stop_task=False)")
                task_running_count += 1
        else:
            print(f"✗ {task_id} - NO encontrado en los logs (agente sin proceso) → DETENER")
            stop_task(task_id, region=region, cluster_name=cluster_name)
            tasks_to_stop_list.append(task_id)
    
    print(f"Tareas detenidas: {len(tasks_to_stop_list)}")
    print(f"Tareas aún en ejecución: {task_running_count}")

if __name__ == "__main__":
    # automatizar el aumento y disminución de agentes según logs.
    while True:
        print("\n=== Verificando necesidad de ajuste de agentes ECS ===\n")
        print(f"Timestamp actual: {datetime.now().strftime('%Y%m%d %H:%M:%S')}\n")
        minutes_sleep = minutes_wait_between_checks_without_change
        #recuperar variables de terraform
        tf_vars = read_terraform_variables('variables.tf')
        region = tf_vars.get('aws_region', "us-west-2")
        private_subnet_ids = tf_vars.get('private_subnet_ids')
        project_name = tf_vars.get('project_name')
        #recuperar recursos desde el estado de terraform
        state = read_terraform_state()
        ecs_tasks_sg_id = state.get("aws_security_group.ecs_tasks_sg", {}).get("id")
        print(f"Región AWS desde Terraform: {region}")
        print(f"Proyecto desde Terraform: {project_name}")
        #print(f"private_subnet_ids desde Terraform: {private_subnet_ids} con type: {type(private_subnet_ids)}")
        print(f"sg_id desde Terraform: {ecs_tasks_sg_id}")
        log_group_master = f"/ecs/{project_name}-{region}-master"
        log_stream_prefix_master = f"ecs/{project_name}-master"
        log_group_agente = f"/ecs/{project_name}-{region}-agente"
        cluster_name = f"{project_name}-cluster-{region}"
        task_family_agent = f"{project_name}-task-agente-{region}"

        #Obtener el stream más reciente del master
        max_stream = get_log_streams_by_prefix(
            log_group=log_group_master,
            prefix=log_stream_prefix_master,
            region=region
        )

        # 2. Obtener el último evento con los keywords
        if max_stream:
            if not id_task_master:
                id_task_master = max_stream["logStreamName"].split('/')[-1]
            else:
                if id_task_master != max_stream["logStreamName"].split('/')[-1]:
                    print(f"⚠ Cambio detectado en el log stream del master: {id_task_master} → {max_stream['logStreamName'].split('/')[-1]}. Se detiene el proceso de autoescalado.")
                    exit()
            keywords = find_logs
            latest_event = get_latest_log_event(
                log_group=log_group_master,
                log_stream_name=max_stream["logStreamName"],
                keywords=keywords,
                region=region
            )
        
        if latest_event:
            agent_count = int(extract_model_count(latest_event['message']))  # cantidad de agentes requeridos segun log master.
            date_filter_new = latest_event['timestamp']
            if not date_filter:
                date_filter = date_filter_new
            #print(f"fecha: {date_filter}, type: {type(date_filter)}")
            print(f"Agentes necesarios según log master:{agent_count} con fecha de log: {date_filter}")

            # recuperar tareas de agente del cluster
            ecs_list_agents_running = get_all_ecs_tasks(cluster_name, task_family_agent, desired_status="RUNNING", region=region)
            agents_running = len(ecs_list_agents_running)
            # Extraer solo el ID después del último /
            task_ids = [arn.split('/')[-1] for arn in ecs_list_agents_running]
            #print(f"ecs_list_agents_running: {task_ids}")
            print(f"Total de tareas de agente RUNNING: {agents_running}")

            #recuperar logs de agentes desde la fecha del último log del master
            start_ms = parse_iso(date_filter.strftime("%Y-%m-%dT%H:%M:%S"))
            end_ms = None
            rows = fetch_events(log_group_agente, start_ms=start_ms, end_ms=end_ms, region=region)

            # Validar variable rows (si es 0 es porque no hay logs nuevos en agentes desde la fecha del master) 
            # Se debe ajustar nuevamente la cantidad de agentes.
            if rows:
                df_agent_logs = pd.DataFrame(rows)
                df_agent_logs['timestamp'] = pd.to_datetime(df_agent_logs['timestamp'], format='ISO8601')
                df_agent_logs['task_id'] = df_agent_logs['logStreamName'].str.split('/').str[-1]
                # Contar "Running model" por task_id
                count_running = df_agent_logs[df_agent_logs['message'].str.contains(find_model_start, na=False)].groupby('task_id').size()

                # Contar "Model run complete" por task_id
                count_ending = df_agent_logs[df_agent_logs['message'].str.contains(find_model_end, na=False)].groupby('task_id').size()

                # Crear DataFrame nuevo con los conteos
                df_count_running = count_running.reset_index(name='count_running')
                
                # Agregar columna count_ending al df
                df_count_running = df_count_running.merge(count_ending.reset_index(name='count_ending'), on='task_id', how='left')
                df_count_running['count_ending'] = df_count_running['count_ending'].fillna(0).astype(int)
                
                # Agregar columna stop_task (True si count_running == count_ending)
                df_count_running['stop_task'] = df_count_running['count_running'] == df_count_running['count_ending']

                #verificar si cambió la necesidad de agentes
                print(f"date_filter_new: {date_filter_new}. date_filter: {date_filter}")
                #print(f"agent_count: {agent_count}. agent_count: {agent_count}")
                if date_filter_new > date_filter:
                    #si cambió, actualizar el valor
                    date_filter = date_filter_new

                    #validar si es necesario aumentar o disminuir agentes
                    if agents_running < agent_count:
                        print(f"Se requieren más agentes. Actualmente hay {agents_running} agentes, se necesitan {agent_count} agentes.")
                        #aumentar agentes
                        tasks_to_start = agent_count - agents_running
                        if tasks_to_start + agents_running > agent_count_max:
                            tasks_to_start = agent_count - agents_running
                            print(f"⚠ Se alcanzó el máximo número de agentes permitidos en la región ({agent_count}). Solo se iniciarán {tasks_to_start} agentes adicionales.")
                        print(f"Iniciando {tasks_to_start} tareas de agente adicionales...")

                        start_task(
                            count_agents=tasks_to_start,
                            cluster_name=cluster_name,
                            task_definition=task_family_agent,
                            subnets_id=private_subnet_ids,  
                            security_group_id=ecs_tasks_sg_id,  # Reemplaza con tu grupo de seguridad  (SG for ECS tasks)
                            launch_type="FARGATE",
                            region=region
                        )
                        minutes_sleep = minutes_wait_between_checks

                    else:
                        # si son menos o iguales se verifica log de agentes en busca de agentes sin tareas o finalizadas.
                        print(f"Sin cambio en cantidad de agentes, se verifica log de agentes en busca de agentes sin tareas o modelo completado para detenerlos.")
                        # Verificar que task_ids existan en df_count_running
                        print("=== Verificación de task_ids en df_count_running ===")
                        validate_stop_tasks(task_ids, df_count_running, region, cluster_name)
                        
                else:
                    # sin cambios menos o iguales se verifica log de agentes en busca de agentes sin tareas o finalizadas.
                    print(f"Sin cambio en cantidad de agentes, se verifica log de agentes en busca de agentes sin tareas o modelo completado para detenerlos.")
                    print("=== Verificación de task_ids en df_count_running ===")
                    validate_stop_tasks(task_ids, df_count_running, region, cluster_name)
            else:
                print("⚠ No se encontraron logs nuevos en los agentes desde la fecha del último log del master.")
                #crear cantidad de agentes según log del master.
                print (f"Creando {agent_count} agentes según log del master...")
                start_task(
                            count_agents=agent_count,
                            cluster_name=cluster_name,
                            task_definition=task_family_agent,
                            subnets_id=private_subnet_ids,  
                            security_group_id=ecs_tasks_sg_id,  # Reemplaza con tu grupo de seguridad  (SG for ECS tasks)
                            launch_type="FARGATE",
                            region=region
                        )
        else:
            print("⚠ No se pudo obtener el último evento del log master. No se realizarán ajustes.")
        print(f"Timestamp actual: {datetime.now().strftime('%Y%m%d %H:%M:%S')}\n")
        print(f"=== Esperando {minutes_sleep} minutos para la siguiente verificación... ===")
        time.sleep(minutes_sleep*60) 