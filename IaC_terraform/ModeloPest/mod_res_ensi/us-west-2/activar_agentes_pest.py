import boto3
import time
from datetime import datetime

# Parámetros básicos
nombre_proyecto = 'mod-res-ensi'
region_name = 'us-west-2'
ejecutable_agente = 'agent_hp.exe'
nombre_modelo_pest_a_ejecutar = 'mod_res_ensi.pst'
master_host = 'master.' + nombre_proyecto + '.local'
pest_port = 4004
cluster_name = nombre_proyecto + '-cluster-' + region_name
task_definition = nombre_proyecto + '-task-agente-' + region_name
launch_type = 'FARGATE'  # Cambia a 'EC2' si no usas Fargate
subnet_id = 'subnet-00f3021ecee723128'  # Reemplaza con tu subnet real
security_group_id = 'sg-052558493715a971c'  # Reemplaza con tu grupo de seguridad  (SG for ECS tasks)
cantidad_nuevos_agentes = 1  # Número de agentes a activar
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
                    'subnets': [subnet_id],
                    'securityGroups': [security_group_id],
                    'assignPublicIp': 'DISABLED'
                }
            },
            taskDefinition=task_definition
        )

        try:
            print(f"{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} Tarea {i} ejecutada, ARN: {response['tasks'][0]['taskArn']}")
            time.sleep(0.1)  # Evita golpear el API con demasiadas peticiones por segundo
            break  # Salir del bucle si la tarea se ejecutó correctamente
        except Exception as e:
            print(f"{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} Error al ejecutar la tarea {i}: {response['failures'][0]['reason']}")
            print(f"{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} reintentando en 30 segundos...")
            # Espera para evitar sobrecargar el API de ECS
            time.sleep(30)  # Espera 30 segundos antes de reintentar

print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} Las {i} tareas han sido enviadas.")