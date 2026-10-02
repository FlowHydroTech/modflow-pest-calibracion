"""Tests para calibration_utils.batch (tarea 11.4).

Verifica:
  - wait_for_master_ip retorna None al timeout sin bloquear ni lanzar (req 16.5)
  - el modulo usa Batch API, nunca ECS API (req 8.3, Property 4)
  - submit_agent_jobs(0) no lanza nada
"""

import inspect

import calibration_utils.batch as batch_mod
from calibration_utils.batch import submit_agent_jobs, wait_for_master_ip


def test_wait_for_master_ip_returns_none_on_timeout(mocker):
    """Req 16.5: al agotar timeout retorna None, no bloquea ni lanza."""
    fake_batch = mocker.Mock()
    # El job nunca llega a RUNNING
    fake_batch.describe_jobs.return_value = {"jobs": [{"status": "RUNNABLE"}]}
    fake_ec2 = mocker.Mock()

    mocker.patch.object(batch_mod, "_batch_client", return_value=fake_batch)
    mocker.patch("boto3.client", return_value=fake_ec2)
    mocker.patch("time.sleep", return_value=None)  # no esperar de verdad

    # timeout muy corto -> debe retornar None rapidamente
    result = wait_for_master_ip(job_id="job-123", timeout_s=0, poll_interval_s=0)
    assert result is None


def test_wait_for_master_ip_returns_ip_when_running(mocker):
    fake_batch = mocker.Mock()
    fake_batch.describe_jobs.return_value = {"jobs": [{"status": "RUNNING"}]}
    fake_ec2 = mocker.Mock()
    fake_ec2.describe_instances.return_value = {
        "Reservations": [
            {"Instances": [{"PrivateIpAddress": "10.0.1.42", "LaunchTime": 1}]}
        ]
    }
    mocker.patch.object(batch_mod, "_batch_client", return_value=fake_batch)
    mocker.patch("boto3.client", return_value=fake_ec2)
    mocker.patch("time.sleep", return_value=None)

    result = wait_for_master_ip(job_id="job-123", timeout_s=60, poll_interval_s=0)
    assert result == "10.0.1.42"


def test_submit_agent_jobs_zero_returns_empty(mocker):
    # No debe crear cliente ni llamar submit_job si n <= 0
    spy = mocker.patch.object(batch_mod, "_batch_client")
    assert submit_agent_jobs("queue", "jobdef", 0, "10.0.0.1") == []
    spy.assert_not_called()


def _strip_comments_and_docstrings(source: str) -> str:
    """Elimina docstrings y comentarios para analizar solo codigo ejecutable."""
    import ast

    tree = ast.parse(source)
    # Recolectar los nodos de docstring (expresiones string a nivel modulo/func/clase)
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            doc = ast.get_docstring(node, clean=False)
            if doc:
                docstrings.add(doc)
    lines = []
    for line in source.splitlines():
        # quitar comentarios de linea
        code = line.split("#", 1)[0]
        lines.append(code)
    code_only = "\n".join(lines)
    for doc in docstrings:
        code_only = code_only.replace(doc, "")
    return code_only


def test_module_never_calls_ecs():
    """Property 4: el codigo ejecutable de batch NO llama a la API de ECS.

    Se ignoran docstrings y comentarios (que mencionan ECS para explicar que
    NO se usa); se verifica solo el codigo real.
    """
    code = _strip_comments_and_docstrings(inspect.getsource(batch_mod)).lower()
    assert 'client("ecs"' not in code
    assert "client('ecs'" not in code
    assert "list_tasks" not in code
    assert "stop_task" not in code
    assert "run_task" not in code