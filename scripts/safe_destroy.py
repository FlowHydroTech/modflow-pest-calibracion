"""safe_destroy: destruccion segura de la infraestructura de una calibracion.

Verifica que los resultados esten en S3 ANTES de ejecutar `terraform destroy`,
para no perder resultados si el operador olvida respaldar (F-10).

Correctness property 3: safe_destroy nunca ejecuta `terraform destroy` cuando
s3_results_exist() es False, salvo que force=True.

Requisitos: 9.1-9.8.

Uso:
  python -m scripts.safe_destroy --calibration-id CAL-20260115-001 \
      --terraform-module IaC_terraform/ModeloPest/talabre-linux/us-east-1 \
      --s3-bucket acct-pest-talabre-east-1 [--force]
"""

from __future__ import annotations

import argparse
import subprocess
from dataclasses import dataclass, field

import boto3

from calibration_utils import batch as batch_utils
from calibration_utils import is_valid_calibration_id


@dataclass
class DestroyResult:
    success: bool
    reason: str = ""
    orphans: list[str] = field(default_factory=list)


def s3_results_exist(bucket: str, calibration_id: str, region: str = "us-east-1") -> bool:
    """True si existe al menos un objeto bajo calibrations/{id}/modelo/.

    Requisito 9.1.
    """
    s3 = boto3.client("s3", region_name=region)
    prefix = f"calibrations/{calibration_id}/modelo/"
    resp = s3.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=1)
    return resp.get("KeyCount", 0) > 0


def export_cloudwatch_logs(log_group: str, bucket: str, prefix: str, region: str = "us-east-1") -> None:
    """Exporta un log group a S3 via create_export_task (requisito 9.2)."""
    import time

    logs = boto3.client("logs", region_name=region)
    logs.create_export_task(
        logGroupName=log_group,
        fromTime=0,
        to=int(time.time() * 1000),
        destination=bucket,
        destinationPrefix=prefix,
    )


def stop_all_jobs(job_queue: str, reason: str, region: str = "us-east-1") -> int:
    """Detiene todos los jobs activos de una cola. Usa Batch API (req 9.4)."""
    jobs = batch_utils.list_active_jobs(job_queue, region=region)
    for job in jobs:
        batch_utils.terminate_job(job.job_id, reason=reason, region=region)
    return len(jobs)


def verify_no_orphan_resources(calibration_id: str, job_queues: list[str], region: str = "us-east-1") -> list[str]:
    """Verifica que no queden jobs activos de esta calibracion (req 9.7)."""
    orphans: list[str] = []
    for queue in job_queues:
        for job in batch_utils.list_active_jobs(queue, region=region):
            orphans.append(f"{queue}:{job.job_id}")
    return orphans


def _terraform_destroy(terraform_module: str) -> None:
    subprocess.run(
        ["terraform", "destroy", "-auto-approve", "-no-color"],
        cwd=terraform_module,
        check=True,
    )


def _notify(topic_arn: str | None, subject: str, message: str, region: str = "us-east-1") -> None:
    if not topic_arn:
        print(f"[ALERTA] {subject}: {message}")
        return
    sns = boto3.client("sns", region_name=region)
    sns.publish(TopicArn=topic_arn, Subject=subject[:100], Message=message)


def safe_destroy(
    calibration_id: str,
    terraform_module: str,
    s3_bucket: str,
    force: bool = False,
    region: str = "us-east-1",
    job_queues: list[str] | None = None,
    log_group_master: str | None = None,
    log_group_agents: str | None = None,
    sns_topic_arn: str | None = None,
) -> DestroyResult:
    """Destruye la infraestructura de una calibracion de forma segura.

    Secuencia:
      1. Verificar resultados en S3 (abortar si no hay y no force).
      2. Exportar logs a S3.
      3. (El manifest se genera en Fase 5, tarea 27.3.)
      4. Detener jobs Batch activos.
      5. terraform destroy.
      6. Verificar que no queden recursos huerfanos.
    """
    if not is_valid_calibration_id(calibration_id):
        return DestroyResult(success=False, reason="INVALID_CALIBRATION_ID")

    job_queues = job_queues or []

    # 1. Guardia de resultados (correctness property 3)
    results_exist = s3_results_exist(s3_bucket, calibration_id, region=region)
    if not results_exist and not force:
        print(
            "ERROR: no se encontraron resultados en "
            f"s3://{s3_bucket}/calibrations/{calibration_id}/modelo/ . "
            "Abortando destroy. Use --force para destruir de todas formas "
            "(riesgo de perdida de datos)."
        )
        return DestroyResult(success=False, reason="NO_RESULTS_IN_S3")

    if not results_exist and force:
        print("ADVERTENCIA: --force activo y sin resultados en S3. Los resultados pueden perderse.")

    # 2. Exportar logs
    if log_group_master:
        try:
            export_cloudwatch_logs(log_group_master, s3_bucket, f"calibrations/{calibration_id}/logs/master/", region)
        except Exception as exc:  # noqa: BLE001 - best effort
            print(f"ADVERTENCIA: no se pudieron exportar logs del master: {exc}")
    if log_group_agents:
        try:
            export_cloudwatch_logs(log_group_agents, s3_bucket, f"calibrations/{calibration_id}/logs/agents/", region)
        except Exception as exc:  # noqa: BLE001
            print(f"ADVERTENCIA: no se pudieron exportar logs de agentes: {exc}")

    # 4. Detener jobs
    for queue in job_queues:
        stop_all_jobs(queue, reason="safe_destroy initiated", region=region)

    # 5. terraform destroy
    try:
        _terraform_destroy(terraform_module)
    except subprocess.CalledProcessError as exc:
        orphans = verify_no_orphan_resources(calibration_id, job_queues, region)
        _notify(
            sns_topic_arn,
            f"CRITICAL: terraform destroy fallido ({calibration_id})",
            f"terraform destroy fallo: {exc}. Recursos a limpiar manualmente: {orphans}",
            region,
        )
        return DestroyResult(success=False, reason="TERRAFORM_DESTROY_FAILED", orphans=orphans)

    # 6. Verificar huerfanos
    orphans = verify_no_orphan_resources(calibration_id, job_queues, region)
    if orphans:
        _notify(
            sns_topic_arn,
            f"WARNING: recursos huerfanos post-destroy ({calibration_id})",
            f"Recursos aun activos: {orphans}",
            region,
        )
    return DestroyResult(success=True, orphans=orphans)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Destruccion segura de infraestructura de calibracion")
    parser.add_argument("--calibration-id", required=True)
    parser.add_argument("--terraform-module", required=True)
    parser.add_argument("--s3-bucket", required=True)
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--job-queue", action="append", default=[], dest="job_queues")
    parser.add_argument("--log-group-master")
    parser.add_argument("--log-group-agents")
    parser.add_argument("--sns-topic-arn")
    args = parser.parse_args(argv)

    result = safe_destroy(
        calibration_id=args.calibration_id,
        terraform_module=args.terraform_module,
        s3_bucket=args.s3_bucket,
        force=args.force,
        region=args.region,
        job_queues=args.job_queues,
        log_group_master=args.log_group_master,
        log_group_agents=args.log_group_agents,
        sns_topic_arn=args.sns_topic_arn,
    )
    print(result)
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())