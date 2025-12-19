import boto3
from datetime import datetime
import pandas as pd

# Configuración
log_group = '/ecs/mod-res-ensi-us-west-2-agente'
region = 'us-west-2'

# Fecha filtro
fecha_filtro = datetime.fromisoformat('2025-12-14T08:12:02.651Z'.replace('Z', '+00:00'))
timestamp_filtro = int(fecha_filtro.timestamp() * 1000)  # CloudWatch usa milisegundos

# Cliente CloudWatch Logs
logs = boto3.client('logs', region_name=region)

# Obtener todos los log streams (con paginación)
log_streams = []
next_token = None

while True:
    if next_token:
        response = logs.describe_log_streams(
            logGroupName=log_group,
            orderBy='LastEventTime',
            descending=True,
            nextToken=next_token
        )
    else:
        response = logs.describe_log_streams(
            logGroupName=log_group,
            orderBy='LastEventTime',
            descending=True
        )
    
    log_streams.extend(response['logStreams'])
    
    next_token = response.get('nextToken')
    if not next_token:
        break

print(f"Total de log streams: {len(log_streams)}\n")

# Filtrar streams con última actividad después de la fecha filtro
log_streams_filtrados = [
    stream for stream in log_streams 
    if stream.get('lastEventTimestamp', 0) > timestamp_filtro
]

print(f"Log streams filtrados (después de {fecha_filtro}): {len(log_streams_filtrados)}\n")

# Extraer solo los nombres de los log streams filtrados
for i, stream in enumerate(log_streams_filtrados[:10], 1):  # Mostrar primeros 10
    stream_name = stream['logStreamName']
    last_event = datetime.fromtimestamp(stream.get('lastEventTimestamp', 0) / 1000)
    first_event = datetime.fromtimestamp(stream.get('firstEventTimestamp', 0) / 1000)
    
    print(f"{i}. {stream_name}")
    print(f"   Last Event: {last_event}")
    print(f"   First Event: {first_event}")
    print()

# Guardar todos los stream names filtrados en una lista
stream_names = [stream['logStreamName'] for stream in log_streams_filtrados]

print(f"\nPrimeros 5 stream names filtrados:")
for name in stream_names[:5]:
    print(f"  - {name}")

# Crear DataFrame con los stream names
df_streams = pd.DataFrame({'logStreamName': stream_names})

# Agregar columnas adicionales útiles
df_streams['task_id'] = df_streams['logStreamName'].str.split('/').str[-1]
df_streams['container'] = df_streams['logStreamName'].str.split('/').str[1]

print(f"\n=== DataFrame de Log Streams ===")
print(df_streams.head())
print(f"\nShape: {df_streams.shape}")
print(f"\nColumnas: {list(df_streams.columns)}")
