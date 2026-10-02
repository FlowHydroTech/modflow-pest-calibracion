"""Tests del Lambda Autoscaler (tareas 12.5, 12.6).

Verifica:
  - no se lanzan mas agentes que max_agents (Property 4 / req 8.4)
  - MasterHealth=0 se publica cuando el master no tiene logs recientes (8.6)
  - extract_models_requested parsea correctamente los patrones de PEST (8.2)
  - el autoscaler usa Batch API, nunca ECS (Property 4)
"""

import inspect

import pytest
from hypothesis import given, strategies as st

import lambdas.autoscaler.handler as autoscaler
from lambdas.autoscaler.handler import (
    extract_models_requested,
    run_autoscaler_cycle,
    AutoscalerResult,
)
from calibration_utils.batch import BatchJob


BASE_CONFIG = {
    "calibration_id": "CAL-20260115-001",
    "region": "us-east-1",
    "job_queue_agents": "pest-agent-queue",
    "job_definition_agent": "pest-agent-job-def",
    "log_group_master": "/batch/pest-master",
    "log_group_agents": "/batch/pest-agents",
    "max_agents": 300,
    "master_ip": "10.0.1.42",
}


def test_extract_models_requested_patterns():
    events = [
        {"message": "Running model 48 times ....."},
        {"message": "Calculating Jacobian matrix: running model 400 times ....."},
        {"message": "Parallelisation of lambda search: running model up to 37 times....."},
    ]
    assert extract_models_requested(events) == 400


def test_extract_models_requested_none():
    assert extract_models_requested([{"message": "no numbers here"}]) == 0


def test_master_unhealthy_when_no_logs(mocker):
    """Req 8.6: sin logs recientes -> MasterHealth=0 y no se escala."""
    mocker.patch.object(autoscaler.cw, "last_event_age_seconds", return_value=None)
    pub = mocker.patch.object(autoscaler.cw, "publish_metric")
    launch = mocker.patch.object(autoscaler.batch_utils, "submit_agent_jobs")

    result = run_autoscaler_cycle(BASE_CONFIG)

    assert result.master_healthy is False
    assert result.agents_launched == 0
    pub.assert_any_call("MasterHealth", 0, "CAL-20260115-001", region="us-east-1")
    launch.assert_not_called()


def test_master_stale_logs_unhealthy(mocker):
    """Logs mas viejos que 30 min -> no saludable."""
    mocker.patch.object(autoscaler.cw, "last_event_age_seconds", return_value=3600)
    mocker.patch.object(autoscaler.cw, "publish_metric")
    launch = mocker.patch.object(autoscaler.batch_utils, "submit_agent_jobs")

    result = run_autoscaler_cycle(BASE_CONFIG)
    assert result.master_healthy is False
    launch.assert_not_called()


def test_does_not_exceed_max_agents(mocker):
    """Property 4 / req 8.4: aunque PEST pida 500, no excede max_agents."""
    cfg = dict(BASE_CONFIG, max_agents=10)
    mocker.patch.object(autoscaler.cw, "last_event_age_seconds", return_value=60)
    mocker.patch.object(autoscaler.cw, "publish_metric")
    mocker.patch.object(
        autoscaler.cw, "fetch_recent_events",
        return_value=[{"message": "running model 500 times", "logStreamName": "s"}],
    )
    # 3 agentes activos
    mocker.patch.object(
        autoscaler.batch_utils, "get_running_jobs",
        return_value=[BatchJob(f"j{i}", f"agent-{i}", "RUNNING") for i in range(3)],
    )
    launch = mocker.patch.object(autoscaler.batch_utils, "submit_agent_jobs")
    mocker.patch.object(autoscaler, "_stop_completed_agents", return_value=0)

    result = run_autoscaler_cycle(cfg)
    # max 10 - 3 activos = 7 permitidos
    assert result.agents_launched == 7
    args, kwargs = launch.call_args
    assert args[2] == 7  # tercer posicional es el numero a lanzar


@given(
    models=st.integers(min_value=0, max_value=5000),
    active=st.integers(min_value=0, max_value=400),
    max_a=st.integers(min_value=1, max_value=400),
)
def test_property_never_exceeds_max_agents(models, active, max_a):
    """Property 4: launched + active nunca supera max_agents.

    Usa context managers de mock (no el fixture mocker) por compatibilidad con
    @given de hypothesis, que reutiliza fixtures function-scoped entre inputs.
    """
    from unittest.mock import patch

    cfg = dict(BASE_CONFIG, max_agents=max_a)
    jobs = [BatchJob(f"j{i}", f"a{i}", "RUNNING") for i in range(active)]
    events = [{"message": f"running model {models} times", "logStreamName": "s"}]

    with patch.object(autoscaler.cw, "last_event_age_seconds", return_value=60), \
         patch.object(autoscaler.cw, "publish_metric"), \
         patch.object(autoscaler.cw, "fetch_recent_events", return_value=events), \
         patch.object(autoscaler.batch_utils, "get_running_jobs", return_value=jobs), \
         patch.object(autoscaler.batch_utils, "submit_agent_jobs"), \
         patch.object(autoscaler, "_stop_completed_agents", return_value=0):
        result = run_autoscaler_cycle(cfg)

    # Invariante (req 8.4): el autoscaler nunca lanza agentes que lleven el
    # total por encima de max_agents. Si ya hay >= max activos, no lanza nada.
    assert result.agents_launched >= 0
    allowed = max(0, max_a - active)
    assert result.agents_launched <= allowed


def test_handler_uses_only_batch_api():
    """Property 4: el codigo del autoscaler no referencia ECS API."""
    src = inspect.getsource(autoscaler).lower()
    assert "list_tasks" not in src
    assert "stop_task" not in src
    assert "run_task" not in src
    assert 'client("ecs"' not in src