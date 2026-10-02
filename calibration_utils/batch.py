"""Gestion de jobs PEST en AWS Batch.

IMPORTANTE (correctness property 4): este modulo usa EXCLUSIVAMENTE la API de
AWS Batch (batch:SubmitJob, batch:ListJobs, batch:TerminateJob,
batch:DescribeJobs). NO debe invocar NUNCA la API de ECS (ecs:ListTasks,
ecs:StopTask, ecs:RunTask). El bug historico de auto_scaling_tasks.py mezclaba
ambas APIs; aqui se corrige centralizando en Batch.

Requisitos cubiertos: 8.3, 16.2, 16.5.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import boto3

# Estados de un job Batch que se consideran "activos".
ACTIVE_STATUSES = ("SUBMITTED", "PENDING", "RUNNABLE", "STARTING", "RUNNING")


@dataclass
class BatchJob:
    """Representa un job Batch con los campos relevantes para el autoscaler."""

    job_id: str
    job_name: str
    status: str
    task_arn: str = ""      # container.taskArn, cuando el job esta RUNNING
    container_instance_arn: str = ""


def _batch_client(region: str):
    return boto3.client("batch", region_name=region)


def submit_master_job(
    job_queue: str, job_definition: str, env_vars: dict | None = None,
    job_name: str = "pest-master", region: str = "us-east-1",
) -> str:
    """Lanza el job master y retorna su jobId.

    Requisito 16.2. Usa batch:SubmitJob.
    """
    client = _batch_client(region)
    kwargs = {
        "jobName": job_name,
        "jobQueue": job_queue,
        "jobDefinition": job_definition,
    }
    if env_vars:
        kwargs["containerOverrides"] = {
            "environment": [{"name": k, "value": str(v)} for k, v in env_vars.items()]
        }
    response = client.submit_job(**kwargs)
    return response["jobId"]


def submit_agent_jobs(
    job_queue: str, job_definition: str, n: int, master_ip: str,
    region: str = "us-east-1", throttle_s: float = 0.1,
) -> list[str]:
    """Lanza N agentes apuntando a master_ip. Retorna la lista de jobIds.

    Requisito 16.2. Cada agente recibe MASTER_HOST=master_ip como override.
    """
    if n <= 0:
        return []
    client = _batch_client(region)
    job_ids: list[str] = []
    for i in range(n):
        response = client.submit_job(
            jobName=f"pest-agent-{i + 1:03d}",
            jobQueue=job_queue,
            jobDefinition=job_definition,
            containerOverrides={
                "environment": [{"name": "MASTER_HOST", "value": master_ip}]
            },
        )
        job_ids.append(response["jobId"])
        if throttle_s:
            time.sleep(throttle_s)
    return job_ids


def get_running_jobs(job_queue: str, region: str = "us-east-1") -> list[BatchJob]:
    """Lista los jobs en estado RUNNING de la cola. Usa batch:ListJobs.

    Requisitos 8.3, 16.2. NO usa ECS API.
    """
    client = _batch_client(region)
    jobs: list[BatchJob] = []
    paginator = client.get_paginator("list_jobs")
    for page in paginator.paginate(jobQueue=job_queue, jobStatus="RUNNING"):
        for summary in page.get("jobSummaryList", []):
            jobs.append(
                BatchJob(
                    job_id=summary["jobId"],
                    job_name=summary.get("jobName", ""),
                    status=summary.get("status", "RUNNING"),
                )
            )
    return jobs


def list_active_jobs(job_queue: str, region: str = "us-east-1") -> list[BatchJob]:
    """Lista todos los jobs activos (cualquier estado no terminal) de la cola."""
    client = _batch_client(region)
    jobs: list[BatchJob] = []
    paginator = client.get_paginator("list_jobs")
    for status in ACTIVE_STATUSES:
        for page in paginator.paginate(jobQueue=job_queue, jobStatus=status):
            for summary in page.get("jobSummaryList", []):
                jobs.append(
                    BatchJob(
                        job_id=summary["jobId"],
                        job_name=summary.get("jobName", ""),
                        status=summary.get("status", status),
                    )
                )
    return jobs


def terminate_job(job_id: str, reason: str, region: str = "us-east-1") -> None:
    """Termina un job Batch. Usa batch:TerminateJob (NO ecs:StopTask).

    Requisitos 8.3, 16.2.
    """
    client = _batch_client(region)
    client.terminate_job(jobId=job_id, reason=reason)


def wait_for_master_ip(
    job_id: str, timeout_s: int = 600, poll_interval_s: int = 10,
    region: str = "us-east-1",
) -> str | None:
    """Espera a que el master este RUNNING y retorna su IP privada.

    Sondea batch:DescribeJobs hasta que el job este RUNNING; luego obtiene la
    IP privada de la instancia EC2 subyacente (tag Role=Master) via EC2.

    Requisito 16.5: si se agota timeout_s, retorna None SIN bloquear ni lanzar
    excepcion.
    """
    batch = _batch_client(region)
    ec2 = boto3.client("ec2", region_name=region)
    start = time.monotonic()

    while time.monotonic() - start < timeout_s:
        resp = batch.describe_jobs(jobs=[job_id])
        jobs = resp.get("jobs", [])
        if jobs and jobs[0].get("status") == "RUNNING":
            ip = _master_private_ip(ec2)
            if ip:
                return ip
        time.sleep(poll_interval_s)

    return None


def _master_private_ip(ec2_client) -> str | None:
    """Obtiene la IP privada de la instancia EC2 master mas reciente (running)."""
    resp = ec2_client.describe_instances(
        Filters=[
            {"Name": "tag:Role", "Values": ["Master"]},
            {"Name": "instance-state-name", "Values": ["running"]},
        ]
    )
    instances = [
        inst
        for reservation in resp.get("Reservations", [])
        for inst in reservation.get("Instances", [])
    ]
    if not instances:
        return None
    latest = max(instances, key=lambda x: x.get("LaunchTime"))
    return latest.get("PrivateIpAddress")