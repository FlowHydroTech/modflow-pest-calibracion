"""Tests de la Lambda ExtractPhi (tareas 21.5, 23).

Verifica extraccion de Phi/iteracion con los patrones del estado del arte,
publicacion de metricas con CalibrationId, y la alerta STAGNATED sin detener.
"""

import lambdas.extract_phi.handler as ep
from lambdas.extract_phi.handler import extract_phi_from_events, process_master_logs


def _ev(msg):
    return {"message": msg, "logStreamName": "master/default/abc"}


def test_extract_iteration_and_phi():
    events = [
        _ev("OPTIMISATION ITERATION NO.        : 1"),
        _ev("Starting phi for this iteration                     :   8432.5"),
        _ev("Lowest phi this iteration                           :   6234.8"),
        _ev("OPTIMISATION ITERATION NO.        : 2"),
        _ev("Lowest phi this iteration                           :   3891.2"),
    ]
    readings = extract_phi_from_events(events)
    # Dos iteraciones con "lowest phi" + el "starting phi" de la primera
    phis = [r.phi for r in readings]
    assert 6234.8 in phis
    assert 3891.2 in phis
    # La ultima lectura corresponde a la iteracion 2
    assert readings[-1].iteration == 2
    assert readings[-1].phi == 3891.2


def test_extract_final_phi():
    events = [_ev("Final phi                                           :   312.7")]
    readings = extract_phi_from_events(events)
    assert len(readings) == 1
    assert readings[0].phi == 312.7


def test_extract_scientific_notation():
    events = [_ev("Lowest phi this iteration : 1.2345E+03")]
    readings = extract_phi_from_events(events)
    assert readings[0].phi == 1234.5


def test_no_phi_lines():
    events = [_ev("Running model 48 times ....."), _ev("Model run complete.")]
    assert extract_phi_from_events(events) == []


def test_process_publishes_metrics_and_classifies(mocker):
    """Flujo completo: publica PhiCurrent/Best/Iteration/QualityState."""
    events = [
        _ev("OPTIMISATION ITERATION NO.        : 1"),
        _ev("Lowest phi this iteration : 1000.0"),
        _ev("OPTIMISATION ITERATION NO.        : 2"),
        _ev("Lowest phi this iteration : 500.0"),
    ]
    mocker.patch.object(ep.cw, "fetch_recent_events", return_value=events)
    pub = mocker.patch.object(ep.metrics_mod, "publish_metric")

    result = process_master_logs({
        "calibration_id": "CAL-20260115-001",
        "region": "us-east-1",
        "log_group_master": "/batch/pest-master",
    })

    assert result.phi_current == 500.0
    assert result.phi_best == 500.0
    assert result.current_iteration == 2
    # Se publicaron las metricas de Phi + QualityState, todas con CalibrationId
    published = [c.args[0] for c in pub.call_args_list]
    assert "PhiCurrent" in published
    assert "PhiBest" in published
    assert "CalibrationQualityState" in published
    for c in pub.call_args_list:
        assert c.args[2] == "CAL-20260115-001"  # calibration_id siempre presente


def test_stagnated_sends_warning_not_terminate(mocker):
    """Req 11.6 / Property 2: STAGNATED envia SNS WARNING y NO termina jobs."""
    events = [
        _ev("OPTIMISATION ITERATION NO. : 1"), _ev("Lowest phi this iteration : 1000.0"),
        _ev("OPTIMISATION ITERATION NO. : 2"), _ev("Lowest phi this iteration : 1000.0"),
        _ev("OPTIMISATION ITERATION NO. : 3"), _ev("Lowest phi this iteration : 1000.0"),
        _ev("OPTIMISATION ITERATION NO. : 4"), _ev("Lowest phi this iteration : 1000.0"),
        _ev("OPTIMISATION ITERATION NO. : 5"), _ev("Lowest phi this iteration : 1000.0"),
        _ev("OPTIMISATION ITERATION NO. : 6"), _ev("Lowest phi this iteration : 1000.0"),
    ]
    mocker.patch.object(ep.cw, "fetch_recent_events", return_value=events)
    mocker.patch.object(ep.metrics_mod, "publish_metric")
    warn = mocker.patch.object(ep, "_publish_warning")

    result = process_master_logs({
        "calibration_id": "CAL-20260115-001",
        "region": "us-east-1",
        "log_group_master": "/batch/pest-master",
        "sns_topic_arn": "arn:aws:sns:us-east-1:803037204233:pest-alerts",
    })

    from calibration_utils.quality import QualityState
    assert result.quality_state == int(QualityState.STAGNATED)
    warn.assert_called_once()
    # No existe ninguna llamada a terminate_job en este modulo (Property 2)
    import inspect
    assert "terminate_job" not in inspect.getsource(ep)


def test_convergence_message_detected(mocker):
    events = [
        _ev("Lowest phi this iteration : 100.0"),
        _ev("Optimisation complete: the 5 lowest phi's are within RELPARSTP"),
    ]
    mocker.patch.object(ep.cw, "fetch_recent_events", return_value=events)
    mocker.patch.object(ep.metrics_mod, "publish_metric")

    result = process_master_logs({
        "calibration_id": "CAL-20260115-001",
        "region": "us-east-1",
        "log_group_master": "/batch/pest-master",
    })
    from calibration_utils.quality import QualityState
    assert result.converged is True
    assert result.quality_state == int(QualityState.CONVERGED)