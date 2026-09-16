#!/usr/bin/env python3
"""
Detiene el master y todos los agentes PEST en ejecución.

Uso:
  python stop_master_agents.py           # Detiene master + todos los agentes
  python stop_master_agents.py --agents  # Solo detiene agentes, deja el master
  python stop_master_agents.py --master  # Solo detiene el master
"""

import boto3
import time
import sys
from datetime import datetime
from botocore.exceptions import ClientError

# -----------------------------------------------------------------------
# Configuración
# -----------------------------------------------------------------------
AWS_REGION           = "us-east-1"
PROJECT_NAME         = "pest-talabre-linux"
MASTER_JOB_QUEUE     = f"{PROJECT_NAME}-master-queue"
AGENT_JOB_QUEUE      = f"{PROJECT_NAME}-agent-queue"
ACTIVE_STATUSES      = ["SUBMITTED", "PENDING", "RUNNABLE", "STARTING", "RUNNING"]

batch_client = boto3.client("batch", region_name=AWS_REGION)


def ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def list_active_jobs(queue: str) -> list[dict]:
    """Lista todos los jobs activos en un queue."""
    jobs = []
    try:
        paginator = batch_client.get_paginator("list_jobs")
        for status in ACTIVE_STATUSES:
            for page in paginator.paginate(jobQueue=queue, jobStatus=status):
                jobs.extend(page.get("jobSummaryList", []))
    except ClientError as e:
        print(f"  Error listando jobs de {queue}: {e}")
    return jobs


def terminate_jobs(jobs: list[dict], reason: str = "Detenido manualmente") -> int:
    """Termina una lista de jobs. Retorna la cantidad de jobs terminados."""
    terminated = 0
    for job in jobs:
        job_id   = job["jobId"]
        job_name = job.get("jobName", "")
        status   = job.get("status", "")
        try:
            batch_client.terminate_job(jobId=job_id, reason=reason)
            print(f"  ✓ Terminado [{status}] {job_name} ({job_id[:8]}…)")
            terminated += 1
            time.sleep(0.1)
        except ClientError as e:
            print(f"  ✗ Error terminando {job_id[:8]}…: {e}")
    return terminated


def main():
    only_agents = "--agents" in sys.argv
    only_master = "--master" in sys.argv

    print(f"\n{'='*70}")
    print(f"Stop PEST Master-Agents")
    print(f"Región: {AWS_REGION} | Proyecto: {PROJECT_NAME}")
    print(f"{'='*70}\n")

    total = 0

    # Detener agentes
    if not only_master:
        print(f"{ts()} Buscando agentes activos en '{AGENT_JOB_QUEUE}'...")
        agent_jobs = list_active_jobs(AGENT_JOB_QUEUE)
        if agent_jobs:
            print(f"  Encontrados {len(agent_jobs)} agentes. Deteniendo...")
            total += terminate_jobs(agent_jobs)
        else:
            print(f"  No hay agentes activos.")

    # Detener master
    if not only_agents:
        print(f"\n{ts()} Buscando master activo en '{MASTER_JOB_QUEUE}'...")
        master_jobs = list_active_jobs(MASTER_JOB_QUEUE)
        if master_jobs:
            print(f"  Encontrados {len(master_jobs)} jobs de master. Deteniendo...")
            total += terminate_jobs(master_jobs)
        else:
            print(f"  No hay master activo.")

    print(f"\n{'='*70}")
    print(f"{ts()} {total} jobs detenidos.")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
