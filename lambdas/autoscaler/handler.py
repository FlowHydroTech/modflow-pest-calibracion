"""Lambda Autoscaler de agentes PEST.

Reemplaza el loop `while True` de auto_scaling_tasks.py que corria en la laptop
del operador (F-03). Esta funcion es invocada por una regla EventBridge cada N
minutos (default 10) y es independiente de cualquier maquina del operador.

Algoritmo (del design.md):
  1. Verificar salud del master (sin logs > 30 min -> MasterHealth=0, no escalar).
  2. Extraer numero de modelos solicitados de los logs recientes del master.
  3. Contar agentes RUNNING via Batch API (NUNCA ECS).
  4. Lanzar agentes faltantes sin exceder max_agents.
  5. Terminar agentes que completaron su corrida.

Requisitos: 8.1-8.8. Correctness property 4 (solo Batch API).
"""

from __future__ import annotations

import re
import os
from dataclasses import dataclass, asdict

from calibration_utils import batch as batch_utils
from calibration_utils import cloudwatch as cw

# Patron para extraer el numero de modelos solicitados por PEST (ya validado
# en auto_scaling_tasks.py): "Running model 48 times", "running model up to 37 times".
_MODELS_PATTERN = re.compile(r"model\s+(?:up\s+to\s+)?(\d+)\s+times?", re.IGNORECASE)

# Mensajes que indican que un agente completo su corrida.
_AGENT_DONE_MARKERS = ("Model run complete", "MODEL TIMEOUT")

# Umbral de inactividad del master (segundos) para declararlo no saludable.
MASTER_STALE_SECONDS = 30 * 60


@dataclass
class AutoscalerResult:
    agents_launched: int
    agents_stopped: int
    master_healthy: bool
    models_needed: int = 0
    active_agents: int = 0


def extract_models_requested(events: list[dict]) -> int:
    """Retorna el maximo numero de modelos solicitados en los eventos dados.

    Requisito 8.2. Si no hay coincidencias, retorna 0 (no lanzar agentes).
    """
    max_models = 0
    for ev in events:
        for match in _MODELS_PATTERN.finditer(ev.get("message", "")):
            value = int(match.group(1))
            if value > max_models:
                max_models = value
    return max_models


def _agent_completed(message: str) -> bool:
    return any(marker in message for marker in _AGENT_DONE_MARKERS)


def run_autoscaler_cycle(config: dict) -> AutoscalerResult:
    """Ejecuta un ciclo de autoscaling. `config` provee los parametros del evento.

    Claves esperadas en config:
      calibration_id, region, job_queue_agents, job_definition_agent,
      log_group_master, log_group_agents, max_agents, master_ip.
    """
    calibration_id = config["calibration_id"]
    region = config.get("region", "us-east-1")
    log_group_master = config["log_group_master"]
    job_queue_agents = config["job_queue_agents"]
    max_agents = int(config["max_agents"])
    master_ip = config.get("master_ip", "")

    # 1. Salud del master
    age = cw.last_event_age_seconds(log_group_master, region=region)
    if age is None or age > MASTER_STALE_SECONDS:
        cw.publish_metric("MasterHealth", 0, calibration_id, region=region)
        return AutoscalerResult(
            agents_launched=0, agents_stopped=0, master_healthy=False
        )
    cw.publish_metric("MasterHealth", 1, calibration_id, region=region)

    # 2. Modelos solicitados (logs de los ultimos 15 min)
    master_events = cw.fetch_recent_events(log_group_master, minutes=15, region=region)
    models_needed = extract_models_requested(master_events)

    # 3. Agentes RUNNING via Batch API
    active = batch_utils.get_running_jobs(job_queue_agents, region=region)
    active_count = len(active)
    cw.publish_metric("ActiveWorkers", active_count, calibration_id, region=region)

    # 4. Lanzar faltantes sin exceder max_agents
    launched = 0
    if models_needed > active_count:
        gap = models_needed - active_count
        allowed = max_agents - active_count
        to_launch = max(0, min(gap, allowed))
        if to_launch > 0 and master_ip:
            batch_utils.submit_agent_jobs(
                job_queue_agents,
                config["job_definition_agent"],
                to_launch,
                master_ip,
                region=region,
            )
            launched = to_launch

    # 5. Terminar agentes que completaron
    stopped = _stop_completed_agents(active, config, region)

    return AutoscalerResult(
        agents_launched=launched,
        agents_stopped=stopped,
        master_healthy=True,
        models_needed=models_needed,
        active_agents=active_count,
    )


def _stop_completed_agents(active_agents, config: dict, region: str) -> int:
    """Termina los agentes cuyo log indica que completaron su corrida."""
    log_group_agents = config.get("log_group_agents")
    if not log_group_agents:
        return 0
    events = cw.fetch_recent_events(log_group_agents, minutes=30, region=region)
    completed_streams = {
        ev["logStreamName"]
        for ev in events
        if _agent_completed(ev.get("message", ""))
    }
    if not completed_streams:
        return 0

    stopped = 0
    for job in active_agents:
        # El taskId suele ser el ultimo segmento del logStreamName.
        if any(job.job_id in s or s.endswith(job.job_name) for s in completed_streams):
            batch_utils.terminate_job(
                job.job_id, reason="Model run complete - autoscaler", region=region
            )
            stopped += 1
    return stopped


def handler(event, context):
    """Entry point de la Lambda. Invocado por EventBridge cada N minutos.

    Toma la configuracion de `event` (o variables de entorno como fallback) y
    ejecuta un ciclo. Requisito 8.7: parametrizado, sirve a cualquier proyecto.
    """
    config = _resolve_config(event or {})
    result = run_autoscaler_cycle(config)
    return asdict(result)


def _resolve_config(event: dict) -> dict:
    """Resuelve la configuracion desde el event, con fallback a env vars."""
    def pick(key, default=None):
        return event.get(key) or os.environ.get(key.upper(), default)

    return {
        "calibration_id": pick("calibration_id"),
        "region": pick("region", "us-east-1"),
        "job_queue_agents": pick("job_queue_agents"),
        "job_definition_agent": pick("job_definition_agent"),
        "log_group_master": pick("log_group_master"),
        "log_group_agents": pick("log_group_agents"),
        "max_agents": pick("max_agents", "300"),
        "master_ip": pick("master_ip", ""),
    }