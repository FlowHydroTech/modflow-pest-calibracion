#!/usr/bin/env python3
import boto3
import pandas as pd
import sys
from datetime import datetime, timedelta
import argparse

def get_task_id(cluster_name, service_name, region="us-west-2"):
    """
    Obtiene el TASK_ID del servicio ECS especificado.
    """
    client = boto3.client("ecs", region_name=region)
    
    try:
        response = client.list_tasks(
            cluster=cluster_name,
            serviceName=service_name,
            desiredStatus="RUNNING"
        )
        
        if not response["taskArns"]:
            print(f"Error: No hay tasks ejecutándose en {service_name}")
            return None
        
        task_arn = response["taskArns"][0]
        task_id = task_arn.split("/")[-1]
        
        print(f"TASK_ARN: {task_arn}")
        print(f"TASK_ID: {task_id}\n")
        
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


def display_logs(df, max_rows=50):
    """
    Muestra los logs en la consola.
    """
    if df is None or df.empty:
        return
    
    print("=" * 120)
    print(f"ÚLTIMOS {min(len(df), max_rows)} EVENTOS:")
    print("=" * 120)
    
    # Mostrar últimos N registros
    for idx, row in df.tail(max_rows).iterrows():
        print(f"\n[{row['timestamp']}]")
        print(f"{row['message']}")
    
    print("\n" + "=" * 120)


def export_logs(df, output_file, format="csv"):
    """
    Exporta los logs a un archivo (CSV o Excel).
    """
    try:
        if format.lower() == "excel":
            df.to_excel(output_file, index=False, engine="openpyxl")
        else:
            df.to_csv(output_file, index=False, encoding="utf-8")
        
        print(f"✓ Logs exportados a: {output_file}")
        return True
    except Exception as e:
        print(f"✗ Error al exportar logs: {e}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Obtiene logs de CloudWatch para un TASK_ID del servicio ECS"
    )
    parser.add_argument(
        "--cluster",
        default="mod-res-ensi-cluster-us-west-2",
        help="Nombre del cluster ECS"
    )
    parser.add_argument(
        "--service",
        default="mod-res-ensi-master-service",
        help="Nombre del servicio ECS"
    )
    parser.add_argument(
        "--log-group",
        default="/ecs/mod-res-ensi-us-west-2-master",
        help="Nombre del log group en CloudWatch"
    )
    parser.add_argument(
        "--region",
        default="us-west-2",
        help="Región AWS"
    )
    parser.add_argument(
        "--task-id",
        default=None,
        help="TASK_ID específico (si no se proporciona, se obtiene del servicio running)"
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help="Horas hacia atrás para buscar logs (default: 24)"
    )
    parser.add_argument(
        "--output",
        default="task_logs.csv",
        help="Archivo de salida (default: task_logs.csv)"
    )
    parser.add_argument(
        "--format",
        choices=["csv", "excel"],
        default="csv",
        help="Formato de salida"
    )
    parser.add_argument(
        "--display",
        action="store_true",
        help="Mostrar los logs en la consola"
    )
    
    args = parser.parse_args()
    
    # Obtener TASK_ID
    if args.task_id:
        task_id = args.task_id
        print(f"Usando TASK_ID especificado: {task_id}\n")
    else:
        task_id = get_task_id(args.cluster, args.service, args.region)
        if not task_id:
            sys.exit(1)
    
    # Calcular tiempos
    end_time = int(datetime.now().timestamp() * 1000)
    start_time = int((datetime.now() - timedelta(hours=args.hours)).timestamp() * 1000)
    
    # Obtener logs
    df = get_logs_for_task(task_id, args.log_group, args.region, start_time, end_time)
    
    if df is not None:
        # Mostrar en consola si se solicita
        if args.display:
            display_logs(df)
        
        # Exportar a archivo
        if args.output:
            export_logs(df, args.output, args.format)
        
        # Mostrar resumen
        print(f"\nResumen:")
        print(f"  Total de eventos: {len(df)}")
        print(f"  Primer evento: {df['timestamp'].min()}")
        print(f"  Último evento: {df['timestamp'].max()}")
    else:
        print("No se pudieron obtener los logs")
        sys.exit(1)
