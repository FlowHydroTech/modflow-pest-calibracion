"""Utilidades de CloudWatch Logs y Metrics para el Control Plane PEST.

Centraliza la lectura de eventos de log y la publicacion de metricas custom,
eliminando la duplicacion historica entre auto_scaling_tasks.py y getLog.py
(F-21). La version completa de este modulo se consolida en la Fase 6 (tarea 30);
aqui se incluye lo que necesita el Lambda Autoscaler (Fase 1-2).

Metric namespace: PEST/Calibration. Toda metrica lleva la dimension
CalibrationId (requisito 10.1, correctness property 7).
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import boto3

METRIC_NAMESPACE = "PEST/Calibration"


def _logs_client(region: str):
    return boto3.client("logs", region_name=region)



def fetch_recent_events(
    log_group: str, minutes: int = 15, region: str = "us-east-1"
) -> list[dict]:
    """Devuelve los eventos del log group en los ultimos `minutes` minutos.

    Cada evento es un dict con 'timestamp' (datetime UTC), 'message' (str) y
    'logStreamName'. Usa logs:FilterLogEvents.
    """
    client = _logs_client(region)
    start_ms = int((time.time() - minutes * 60) * 1000)
    events: list[dict] = []
    paginator = client.get_paginator("filter_log_events")
    for page in paginator.paginate(
        logGroupName=log_group, startTime=start_ms, interleaved=True
    ):
        for ev in page.get("events", []):
            events.append(
                {
                    "timestamp": datetime.fromtimestamp(
                        ev["timestamp"] / 1000, tz=timezone.utc
                    ),
                    "message": ev.get("message", ""),
                    "logStreamName": ev.get("logStreamName", ""),
                }
            )
    return events


def last_event_age_seconds(
    log_group: str, region: str = "us-east-1"
) -> float | None:
    """Edad en segundos del ultimo evento del log group.

    Retorna None si el log group no tiene eventos. Usado para la salud del
    master (sin logs > 30 min -> MasterHealth=0).
    """
    client = _logs_client(region)
    resp = client.describe_log_streams(
        logGroupName=log_group,
        orderBy="LastEventTime",
        descending=True,
        limit=1,
    )
    streams = resp.get("logStreams", [])
    if not streams:
        return None
    last_ts = streams[0].get("lastEventTimestamp")
    if not last_ts:
        return None
    now_ms = time.time() * 1000
    return (now_ms - last_ts) / 1000.0


# publish_metric vive en calibration_utils/metrics.py (fuente unica, tarea 16.1).
# Se re-exporta aqui por compatibilidad con los imports existentes.
from calibration_utils.metrics import publish_metric  # noqa: E402,F401