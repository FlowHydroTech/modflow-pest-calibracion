"""Tests para calibration_utils.config.

Cubre tareas 9.5-9.8 y 10.1:
  - unitarios de CalibrationConfig y el validador (9.5)
  - property: constraints invalidos siempre fallan validacion (9.6, Property 6)
  - property: round-trip YAML (9.7, Property 9)
  - property: formato de CalibrationId (9.8, Property 5)
"""

from datetime import datetime, timezone

import pytest
from hypothesis import given, strategies as st

from calibration_utils.config import (
    CalibrationConfig,
    validate_calibration_config,
    serialize_calibration_config,
    parse_calibration_config,
    generate_calibration_id,
    is_valid_calibration_id,
    CALIBRATION_ID_PATTERN,
)


def make_config(**overrides) -> CalibrationConfig:
    """Crea un CalibrationConfig valido base, con overrides opcionales."""
    base = dict(
        name="talabre-pwadj",
        pst_file="talabre_pwadj_ddn.pst",
        terraform_module="IaC_terraform/ModeloPest/talabre-linux/us-east-1",
        s3_bucket="acct-pest-talabre-east-1",
        ecr_image="acct.dkr.ecr.us-east-1.amazonaws.com/pest-talabre-linux:abc1234",
    )
    base.update(overrides)
    return CalibrationConfig(**base)


# --------------------------------------------------------------------------
# 9.5 - Tests unitarios del validador
# --------------------------------------------------------------------------

def test_valid_config_passes():
    result = validate_calibration_config(make_config())
    assert result.valid is True
    assert result.errors == {}


def test_initial_agents_greater_than_max_fails():
    result = validate_calibration_config(make_config(initial_agents=400, max_agents=300))
    assert result.valid is False
    assert "initial_agents" in result.errors


def test_port_out_of_range_fails():
    assert validate_calibration_config(make_config(port=80)).valid is False
    assert validate_calibration_config(make_config(port=70000)).valid is False


def test_ttl_hours_non_positive_fails():
    assert validate_calibration_config(make_config(ttl_hours=0)).valid is False
    assert validate_calibration_config(make_config(ttl_hours=-5)).valid is False


def test_empty_required_field_fails():
    result = validate_calibration_config(make_config(s3_bucket=""))
    assert result.valid is False
    assert "s3_bucket" in result.errors


def test_missing_pst_in_context_fails(tmp_path):
    # Contexto sin el pst_file -> debe fallar
    result = validate_calibration_config(
        make_config(pst_file="no_existe.pst"), model_context_path=str(tmp_path)
    )
    assert result.valid is False
    assert "pst_file" in result.errors


def test_present_pst_in_context_passes(tmp_path):
    (tmp_path / "modelo.pst").write_text("dummy", encoding="utf-8")
    result = validate_calibration_config(
        make_config(pst_file="modelo.pst"), model_context_path=str(tmp_path)
    )
    assert result.valid is True


# --------------------------------------------------------------------------
# 9.6 - Property 6: constraints invalidos SIEMPRE fallan validacion
# --------------------------------------------------------------------------

@given(
    initial=st.integers(min_value=1, max_value=10000),
    extra=st.integers(min_value=1, max_value=10000),
)
def test_property_initial_gt_max_always_invalid(initial, extra):
    """Property 6: initial_agents > max_agents siempre produce valid=False."""
    cfg = make_config(initial_agents=initial + extra, max_agents=initial)
    assert validate_calibration_config(cfg).valid is False


@given(port=st.integers().filter(lambda p: p < 1024 or p > 65535))
def test_property_port_out_of_range_always_invalid(port):
    """Property 6: cualquier port fuera de rango produce valid=False."""
    assert validate_calibration_config(make_config(port=port)).valid is False


# --------------------------------------------------------------------------
# 9.7 - Property 9: round-trip YAML preserva el CalibrationConfig
# --------------------------------------------------------------------------

@given(
    name=st.text(min_size=1, max_size=40).filter(lambda s: s.strip() != ""),
    initial=st.integers(min_value=0, max_value=300),
    max_a=st.integers(min_value=300, max_value=2000),
    port=st.integers(min_value=1024, max_value=65535),
    ttl=st.integers(min_value=1, max_value=720),
    spot=st.booleans(),
)
def test_property_config_roundtrip(name, initial, max_a, port, ttl, spot):
    """Property 9: parse(serialize(cfg)) == cfg para configuraciones validas."""
    original = make_config(
        name=name, initial_agents=initial, max_agents=max_a,
        port=port, ttl_hours=ttl, use_spot=spot,
    )
    restored = parse_calibration_config(serialize_calibration_config(original))
    assert restored == original


# --------------------------------------------------------------------------
# 9.8 - Property 5: formato de CalibrationId
# --------------------------------------------------------------------------

@given(st.integers(min_value=0, max_value=900))
def test_property_generated_id_matches_format(n_existing):
    """Property 5: todo id generado matchea ^CAL-\\d{8}-\\d{3}$."""
    fixed_now = datetime(2026, 1, 15, tzinfo=timezone.utc)
    existing = [f"CAL-20260115-{i:03d}" for i in range(1, n_existing + 1)]
    new_id = generate_calibration_id(existing_ids=existing, now=fixed_now)
    assert CALIBRATION_ID_PATTERN.match(new_id)
    assert is_valid_calibration_id(new_id)


def test_sequential_ids_same_day_are_unique():
    fixed_now = datetime(2026, 1, 15, tzinfo=timezone.utc)
    first = generate_calibration_id(existing_ids=[], now=fixed_now)
    second = generate_calibration_id(existing_ids=[first], now=fixed_now)
    assert first == "CAL-20260115-001"
    assert second == "CAL-20260115-002"
    assert first != second


def test_invalid_calibration_ids_rejected():
    for bad in ["cal-20260115-001", "CAL-2026015-001", "CAL-20260115-01", "CAL-20260115-0001", "foo"]:
        assert is_valid_calibration_id(bad) is False