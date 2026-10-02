"""Lambda ExtractPhiMetrics: extrae Phi de los logs del master y clasifica calidad.

Lee los logs del master PEST_HP, extrae el objective function (Phi) y el numero
de iteracion usando los patrones del estado del arte (doc 23), publica las
metricas en PEST/Calibration y clasifica el QualityState. Si detecta STAGNATED,
envia una alerta WARNING por SNS (sin detener la calibracion, Property 2).

Requisitos: 11.1, 11.2, 11.3, 11.4, 11.6, 3.4.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

import boto3

from calibration_utils import cloudwatch as cw
from calibration_utils import metrics as metrics_mod
from calibration_utils.quality import (
    QualityState,
    QualityConfig,
    classify_calibration_quality,
    detect_convergence_message,
)

# Patrones de Phi para PEST_HP (del estado del arte, doc 23).
_RX_ITERATION = re.compile(r"OPTIMISATION ITERATION NO\.\s*:\s*(\d+)", re.IGNORECASE)
_RX_STARTING_PHI = re.compile(r"[Ss]tarting phi for this iteration\s*:\s*([0-9.Ee+-]+)")
_RX_LOWEST_PHI = re.compile(r"[Ll]owest phi this iteration\s*:\s*([0-9.Ee+-]+)")
_RX_FINAL_PHI = re.compile(r"[Ff]inal phi\s*:\s*([0-9.Ee+-]+)")


@dataclass
class PhiReading:
    iteration: int | None = None
    phi: float | None = None


@dataclass
class PhiExtractionResult:
    readings: int = 0
    phi_current: float | None = None
    phi_best: float | None = None
    current_iteration: int | None = None
    quality_state: int = 0
    converged: bool = False
    phi_history: list[float] = field(default_factory=list)


def extract_phi_from_events(events: list[dict]) -> list[PhiReading]:
    """Extrae lecturas de Phi e iteracion de una lista de eventos de log.

    Prioriza "lowest phi this iteration" (Phi al final de la iteracion); si no
    aparece, usa "starting phi" o "final phi". Cada iteracion produce una lectura.
    """
    readings: list[PhiReading] = []
    current_iter: int | None = None
    for ev in events:
        msg = ev.get("message", "")

        m_iter = _RX_ITERATION.search(msg)
        if m_iter:
            current_iter = int(m_iter.group(1))

        phi_value: float | None = None
        for rx in (_RX_LOWEST_PHI, _RX_FINAL_PHI, _RX_STARTING_PHI):
            m = rx.search(msg)
            if m:
                try:
                    phi_value = float(m.group(1))
                except ValueError:
                    phi_value = None
                break

        if phi_value is not None:
            readings.append(PhiReading(iteration=current_iter, phi=phi_value))

    return readings


def process_master_logs(config: dict) -> PhiExtractionResult:
    """Lee los logs del master, extrae Phi, publica metricas y clasifica calidad."""
    calibration_id = config["calibration_id"]
    region = config.get("region", "us-east-1")
    log_group_master = config["log_group_master"]
    sns_topic_arn = config.get("sns_topic_arn")
    quality_cfg = QualityConfig(
        stagnation_window_iterations=int(config.get("stagnation_window_iterations", 5)),
        stagnation_threshold=float(config.get("stagnation_threshold", 0.001)),
        improvement_threshold=float(config.get("improvement_threshold", 0.01)),
    )

    # Leer una ventana amplia para reconstruir la historia de Phi.
    events = cw.fetch_recent_events(log_group_master, minutes=int(config.get("window_minutes", 1440)), region=region)

    readings = extract_phi_from_events(events)
    phi_history = [r.phi for r in readings if r.phi is not None]

    result = PhiExtractionResult(readings=len(readings), phi_history=phi_history)

    if phi_history:
        result.phi_current = phi_history[-1]
        result.phi_best = min(phi_history)
        result.current_iteration = readings[-1].iteration
        metrics_mod.publish_metric("PhiCurrent", result.phi_current, calibration_id, region=region)
        metrics_mod.publish_metric("PhiBest", result.phi_best, calibration_id, region=region)
        if result.current_iteration is not None:
            metrics_mod.publish_metric("CurrentIteration", result.current_iteration, calibration_id, region=region)

    # Deteccion de convergencia desde el texto completo de los logs recientes.
    full_text = "\n".join(ev.get("message", "") for ev in events)
    converged = detect_convergence_message(full_text)
    result.converged = converged

    state = classify_calibration_quality(phi_history, converged, quality_cfg)
    result.quality_state = int(state)
    metrics_mod.publish_metric("CalibrationQualityState", int(state), calibration_id, region=region)

    # Requisito 11.6 / Property 2: STAGNATED genera alerta WARNING, NO detiene.
    if state == QualityState.STAGNATED and sns_topic_arn:
        _publish_warning(
            sns_topic_arn,
            calibration_id,
            f"Calibracion {calibration_id} STAGNATED: Phi sin mejora significativa "
            f"en la ventana de {quality_cfg.stagnation_window_iterations} iteraciones. "
            "Revision cientifica recomendada. La calibracion NO fue detenida.",
            region,
        )

    return result


def _publish_warning(topic_arn: str, calibration_id: str, message: str, region: str) -> None:
    sns = boto3.client("sns", region_name=region)
    sns.publish(
        TopicArn=topic_arn,
        Subject=f"WARNING: {calibration_id} STAGNATED"[:100],
        Message=message,
    )


def handler(event, context):
    """Entry point. Invocado por subscription filter de CloudWatch Logs o EventBridge."""
    config = _resolve_config(event or {})
    result = process_master_logs(config)
    return {
        "readings": result.readings,
        "phi_current": result.phi_current,
        "phi_best": result.phi_best,
        "current_iteration": result.current_iteration,
        "quality_state": result.quality_state,
        "converged": result.converged,
    }


def _resolve_config(event: dict) -> dict:
    def pick(key, default=None):
        return event.get(key) or os.environ.get(key.upper(), default)

    return {
        "calibration_id": pick("calibration_id"),
        "region": pick("region", "us-east-1"),
        "log_group_master": pick("log_group_master"),
        "sns_topic_arn": pick("sns_topic_arn"),
        "stagnation_window_iterations": pick("stagnation_window_iterations", "5"),
        "stagnation_threshold": pick("stagnation_threshold", "0.001"),
        "improvement_threshold": pick("improvement_threshold", "0.01"),
        "window_minutes": pick("window_minutes", "1440"),
    }