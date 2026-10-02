"""Tests de calibration_utils.metrics (tarea 16.3).

Property 7: toda metrica publicada lleva la dimension CalibrationId.
"""

import boto3
import pytest
from moto import mock_aws
from hypothesis import given, strategies as st

from calibration_utils.metrics import publish_metric, publish_metrics, METRIC_NAMESPACE


def test_publish_metric_requires_calibration_id():
    """Property 7: sin calibration_id lanza ValueError y no publica."""
    with pytest.raises(ValueError):
        publish_metric("MasterHealth", 1, "")
    with pytest.raises(ValueError):
        publish_metric("MasterHealth", 1, None)


@mock_aws
def test_publish_metric_includes_dimension():
    publish_metric("ActiveWorkers", 42, "CAL-20260115-001", region="us-east-1")
    # moto no expone facilmente las dimensiones via get_metric_data aqui;
    # el valor de esta prueba es que la llamada no lanza y usa el namespace correcto.
    cw = boto3.client("cloudwatch", region_name="us-east-1")
    resp = cw.list_metrics(Namespace=METRIC_NAMESPACE)
    names = {m["MetricName"] for m in resp.get("Metrics", [])}
    assert "ActiveWorkers" in names
    # Verificar que la metrica tiene la dimension CalibrationId
    dims = [
        d
        for m in resp["Metrics"]
        if m["MetricName"] == "ActiveWorkers"
        for d in m.get("Dimensions", [])
    ]
    assert any(d["Name"] == "CalibrationId" for d in dims)


@given(
    name=st.sampled_from(["MasterHealth", "ActiveWorkers", "PhiCurrent", "CurrentIteration"]),
    value=st.floats(min_value=0, max_value=1e9, allow_nan=False, allow_infinity=False),
    bad_id=st.sampled_from(["", None]),
)
def test_property_metric_requires_calibration_id(name, value, bad_id):
    """Property 7: sin un calibration_id valido, publish_metric SIEMPRE lanza.

    No usa mocks AWS (seria lento bajo @given y dispararia el deadline de
    hypothesis); verifica solo el contrato de la guardia, que es la invariante
    de la Property 7: ninguna metrica se publica sin la dimension CalibrationId.
    """
    with pytest.raises(ValueError):
        publish_metric(name, value, bad_id)