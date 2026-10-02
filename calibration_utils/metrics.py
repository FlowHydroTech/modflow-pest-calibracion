"""Publicacion de metricas custom de calibracion en CloudWatch.

Toda metrica se publica en el namespace PEST/Calibration e incluye
OBLIGATORIAMENTE la dimension CalibrationId con valor no vacio
(requisito 10.1, correctness property 7).

Metricas tipicas (requisito 10.2):
  MasterHealth, ActiveWorkers, CalibrationRuntime, PhiCurrent, PhiBest,
  CurrentIteration, CalibrationQualityState, FailedWorkers, CompletedRuns.
"""

from __future__ import annotations

import boto3

METRIC_NAMESPACE = "PEST/Calibration"


def _cw_client(region: str):
    return boto3.client("cloudwatch", region_name=region)


def publish_metric(
    name: str, value: float, calibration_id: str,
    unit: str = "None", region: str = "us-east-1",
) -> None:
    """Publica una metrica custom con la dimension CalibrationId obligatoria.

    Correctness property 7: si calibration_id es vacio o None, lanza ValueError
    y NO publica nada (garantiza que ninguna metrica queda sin la dimension).
    """
    if not calibration_id:
        raise ValueError("calibration_id es obligatorio para publicar una metrica")
    client = _cw_client(region)
    client.put_metric_data(
        Namespace=METRIC_NAMESPACE,
        MetricData=[
            {
                "MetricName": name,
                "Value": float(value),
                "Unit": unit,
                "Dimensions": [{"Name": "CalibrationId", "Value": calibration_id}],
            }
        ],
    )


def publish_metrics(
    metrics: dict[str, float], calibration_id: str, region: str = "us-east-1"
) -> None:
    """Publica varias metricas en una sola llamada, todas con CalibrationId."""
    if not calibration_id:
        raise ValueError("calibration_id es obligatorio para publicar metricas")
    client = _cw_client(region)
    client.put_metric_data(
        Namespace=METRIC_NAMESPACE,
        MetricData=[
            {
                "MetricName": name,
                "Value": float(value),
                "Dimensions": [{"Name": "CalibrationId", "Value": calibration_id}],
            }
            for name, value in metrics.items()
        ],
    )