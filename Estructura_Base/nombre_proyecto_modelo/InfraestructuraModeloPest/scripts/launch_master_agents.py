#!/usr/bin/env python3
"""
Script para lanzar master y agentes PEST con soporte para agregar agentes a un master existente.

Uso:
  python launch_master_agents.py <num_agentes> [--master-only]

Ejemplos:
  python launch_master_agents.py 5          # Lanza master + 5 agentes (o agrega 5 a master existente)
  python launch_master_agents.py 3 --master-only  # Solo lanza el master, sin agentes
  python launch_master_agents.py 10         # Agrega 10 agentes al master existente
  python launch_master_agents.py 5 --jco    # Lanza master con ACTIVATE_JCO=1 + 5 agentes
"""

import boto3
import time
import sys
import json
from datetime import datetime
from botocore.exceptions import ClientError

# -----------------------------------------------------------------------
# Configuración — actualizar con los outputs de terraform apply
# -----------------------------------------------------------------------
AWS_REGION              = "us-west-2"
PROJECT_NAME            = "pest-cmdic-linux-ensi"
MASTER_JOB_QUEUE        = f"{PROJECT_NAME}-master-queue"
AGENT_JOB_QUEUE         = f"{PROJECT_NAME}-agent-queue"
MASTER_JOB_DEFINITION   = f"{PROJECT_NAME}-master-job-def"
AGENT_JOB_DEFINITION    = f"{PROJECT_NAME}-agent-job-def"

# Clientes AWS
batch_client = boto3.client("batch", region_name=AWS_REGION)
ecs_client = boto3.client("ecs", region_name=AWS_REGION)
ec2_client = boto3.client("ec2", region_name=AWS_REGION)


def ts() -> str:
    """Timestamp para logs."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def find_master_job() -> dict | None:
    """Busca un master PEST en ejecución o pendiente.
    
    Retorna:
        dict con keys 'jobId', 'jobName', 'status', 'containerProperties' si existe
        None si no hay master
    """
    print(f"{ts()} Buscando master PEST en ejecución...")
    
    try:
        # Listar todos los jobs del master queue
        response = batch_client.list_jobs(
            jobQueue=MASTER_JOB_QUEUE
        )
        
        # Filtrar por status RUNNING, RUNNABLE, SUBMITTED
        for job_summary in response.get("jobSummaryList", []):
            status = job_summary.get("status")
            job_name = job_summary.get("jobName", "")
            
            if status in ("RUNNING", "RUNNABLE", "SUBMITTED") and "master" in job_name.lower():
                print(f"  Master encontrado: {job_summary['jobId']} ({status})")
                
                # Obtener detalles completos del job
                detail_response = batch_client.describe_jobs(jobs=[job_summary["jobId"]])
                return detail_response["jobs"][0]
        
        print(f"  No hay master en ejecucion")
        return None
    
    except ClientError as e:
        print(f"  Error buscando master: {e}")
        return None


def get_master_ip(master_job: dict) -> str | None:
    """Obtiene la IP privada del master desde la instancia EC2 asociada.
    
    Busca la instancia EC2 más reciente con tag Role=Master en estado running.
    """
    print(f"{ts()} Obteniendo IP privada del master...")
    
    try:
        # Buscar instancia EC2 con tag Role=Master en estado running
        response = ec2_client.describe_instances(
            Filters=[
                {"Name": "tag:Role", "Values": ["Master"]},
                {"Name": "instance-state-name", "Values": ["running"]}
            ]
        )
        
        instances = []
        for reservation in response.get("Reservations", []):
            for instance in reservation.get("Instances", []):
                instances.append(instance)
        
        if not instances:
            print(f"  No se encontraron instancias EC2 con tag Role=Master en running")
            return None
        
        # Usar la más reciente (launch time más nueva)
        latest = max(instances, key=lambda x: x.get("LaunchTime", ""))
        private_ip = latest.get("PrivateIpAddress")
        instance_id = latest.get("InstanceId")
        
        if private_ip:
            print(f"  IP del master: {private_ip} (instance: {instance_id})")
            return private_ip
        
        print(f"  ✗ Instancia sin PrivateIpAddress")
        return None
    
    except ClientError as e:
        print(f"  Error obteniendo IP: {e}")
        return None


def submit_master(activate_jco: bool = False) -> str | None:
    """Lanza el job master y retorna su job ID."""
    print(f"{ts()} Lanzando master PEST (ACTIVATE_JCO={'1' if activate_jco else '0'})...")
    
    kwargs = dict(
        jobName=f"{PROJECT_NAME}-master",
        jobQueue=MASTER_JOB_QUEUE,
        jobDefinition=MASTER_JOB_DEFINITION,
    )
    if activate_jco:
        kwargs["containerOverrides"] = {
            "environment": [
                {"name": "ACTIVATE_JCO", "value": "1"}
            ]
        }
    
    try:
        response = batch_client.submit_job(**kwargs)
        job_id = response["jobId"]
        print(f"  Master lanzado: {job_id}")
        return job_id
    
    except ClientError as e:
        print(f"  Error lanzando master: {e}")
        return None


def wait_for_master_ip(timeout_s: int = 300, job_id: str | None = None) -> str | None:
    """Espera a que el master obtenga IP privada (está running).
    
    Si job_id se proporciona, usa ese ID directamente; si no, busca el master en el queue.
    """
    print(f"{ts()} Esperando que el master esté en RUNNING (timeout {timeout_s}s)...")
    
    start = time.time()
    while time.time() - start < timeout_s:
        # Si tenemos job_id, usarlo directamente
        if job_id:
            try:
                response = batch_client.describe_jobs(jobs=[job_id])
                master = response["jobs"][0] if response["jobs"] else None
            except ClientError as e:
                print(f"  Error describiendo job {job_id}: {e}")
                time.sleep(5)
                continue
        else:
            master = find_master_job()
        
        if master is None:
            print(f"  [{ts()}] Master aún no visible...")
            time.sleep(5)
            continue
        
        status = master.get("status")
        print(f"  [{status}] {ts()}")
        
        if status == "RUNNING":
            # La tarea está corriendo, pero la IP se registra después de que el contenedor inicia
            # Esperar un poco más para que Wine inicie y la instancia esté lista
            print(f"  Esperando 10s más para que la instancia esté lista...")
            time.sleep(10)
            ip = get_master_ip(master)
            if ip:
                return ip
        
        time.sleep(5)
    
    print(f"  Timeout esperando IP del master")
    return None


def submit_agents(master_ip: str, num_agents: int) -> list[str]:
    """Lanza N agentes apuntando al master_ip."""
    print(f"{ts()} Lanzando {num_agents} agentes apuntando a {master_ip}...")
    
    job_ids = []
    for i in range(num_agents):
        while True:
            try:
                response = batch_client.submit_job(
                    jobName=f"{PROJECT_NAME}-agent-{i+1:03d}",
                    jobQueue=AGENT_JOB_QUEUE,
                    jobDefinition=AGENT_JOB_DEFINITION,
                    containerOverrides={
                        "environment": [
                            {"name": "MASTER_HOST", "value": master_ip}
                        ]
                    }
                )
                job_id = response["jobId"]
                job_ids.append(job_id)
                print(f"  Agente {i+1}/{num_agents} lanzado: {job_id}")
                time.sleep(0.1)  # ~10 jobs/s para evitar throttling
                break
            
            except ClientError as e:
                code = e.response["Error"]["Code"]
                if code in ("ThrottlingException", "RequestLimitExceeded"):
                    print(f"  Throttling en agente {i+1}, reintentando en 15s...")
                    time.sleep(15)
                else:
                    print(f"  Error lanzando agente {i+1}: {e}")
                    break
    
    return job_ids


def main():
    """Orquestación principal."""
    
    # Parsear argumentos
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    try:
        num_agentes = int(sys.argv[1])
    except ValueError:
        print(f"Error: <num_agentes> debe ser un número entero")
        sys.exit(1)
    
    master_only  = "--master-only" in sys.argv
    activate_jco = "--jco" in sys.argv
    
    print(f"\n{'='*70}")
    print(f"Orquestador PEST Master-Agent v1.0")
    print(f"Region: {AWS_REGION} | Proyecto: {PROJECT_NAME}")
    print(f"Master JobQueue: {MASTER_JOB_QUEUE}")
    print(f"Agent JobQueue:  {AGENT_JOB_QUEUE}")
    print(f"ACTIVATE_JCO:    {'1 (--jco activo)' if activate_jco else '0'}")
    print(f"{'='*70}\n")
    
    # Paso 1: Buscar master existente o lanzar uno nuevo
    master_job = find_master_job()
    if master_job:
        print(f"{ts()} Master existente detectado (status: {master_job['status']})")
        master_status = master_job["status"]
        
        if master_status not in ("RUNNING", "RUNNABLE"):
            print(f"{ts()} El master no esta en RUNNING (status: {master_status})")
            sys.exit(1)
        
        master_ip = get_master_ip(master_job)
        if not master_ip:
            print(f"{ts()} No se pudo obtener IP del master existente")
            sys.exit(1)
    else:
        print(f"{ts()} Master no encontrado, lanzando uno nuevo...")
        job_id = submit_master(activate_jco=activate_jco)
        if not job_id:
            sys.exit(1)
        
        master_ip = wait_for_master_ip(job_id=job_id)
        if not master_ip:
            print(f"{ts()} No se pudo obtener IP del master lanzado")
            sys.exit(1)
    
    print(f"\n{ts()} Master IP: {master_ip}")
    
    # Paso 2: Lanzar agentes (a menos que --master-only)
    if master_only:
        print(f"\n{ts()} [--master-only] Solo master lanzado, sin agentes")
    else:
        if num_agentes > 0:
            agent_ids = submit_agents(master_ip, num_agentes)
            print(f"\n{ts()} {len(agent_ids)} agentes lanzados")
            print(f"\nJob IDs:")
            for jid in agent_ids:
                print(f"  {jid}")
    
    print(f"\n{'='*70}")
    print(f"{ts()} Orquestacion completada")
    print(f"Master disponible en: {master_ip}:{4004}")
    print(f"Ver logs en CloudWatch: /batch/{PROJECT_NAME}")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
