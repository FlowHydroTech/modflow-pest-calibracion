"""Tests del Quality Engine (tareas 22.2-22.4).

Property 1: CONVERGED requiere mensaje PEST explicito.
Property 2: STAGNATED nunca detiene la calibracion (solo clasifica).
"""

import pytest
from hypothesis import given, strategies as st

from calibration_utils.quality import (
    QualityState,
    QualityConfig,
    classify_calibration_quality,
    relative_improvement,
    detect_convergence_message,
)

CFG = QualityConfig(stagnation_window_iterations=5, stagnation_threshold=0.001, improvement_threshold=0.01)


# --------------------------------------------------------------------------
# 22.2 - Unitarios
# --------------------------------------------------------------------------

def test_empty_history_unknown():
    assert classify_calibration_quality([], False, CFG) == QualityState.UNKNOWN


def test_single_element_unknown():
    assert classify_calibration_quality([1000.0], False, CFG) == QualityState.UNKNOWN


def test_improving():
    # Reducciones > 1% por iteracion
    phi = [1000.0, 800.0, 600.0, 400.0]
    assert classify_calibration_quality(phi, False, CFG) == QualityState.IMPROVING


def test_slow_improvement():
    # Reduccion entre 0.1% y 1%
    phi = [1000.0, 996.0, 992.0, 988.0]  # ~0.4% por paso
    assert classify_calibration_quality(phi, False, CFG) == QualityState.SLOW_IMPROVEMENT


def test_stagnated():
    # Phi practicamente constante
    phi = [1000.0, 1000.0, 1000.0, 1000.0, 1000.0, 1000.0]
    assert classify_calibration_quality(phi, False, CFG) == QualityState.STAGNATED


def test_converged_requires_message():
    # Aunque el Phi caiga drasticamente, sin mensaje NO es CONVERGED
    phi = [9000.0, 100.0, 1.0]
    assert classify_calibration_quality(phi, False, CFG) != QualityState.CONVERGED
    # Con mensaje explicito, SI es CONVERGED
    assert classify_calibration_quality(phi, True, CFG) == QualityState.CONVERGED


def test_stagnated_does_not_raise():
    """Property 2: STAGNATED no lanza excepcion."""
    phi = [1000.0] * 10
    result = classify_calibration_quality(phi, False, CFG)  # no debe lanzar
    assert result == QualityState.STAGNATED


def test_relative_improvement():
    assert relative_improvement(1000.0, 900.0) == pytest.approx(0.1)
    assert relative_improvement(0.0, 100.0) is None  # phi_prev <= 0


def test_detect_convergence_message():
    assert detect_convergence_message("Optimisation complete: RELPARSTP") is True
    assert detect_convergence_message("PHIREDSTP criterion met") is True
    assert detect_convergence_message("Running model 48 times") is False


# --------------------------------------------------------------------------
# 22.3 - Property 1: CONVERGED nunca sin mensaje PEST
# --------------------------------------------------------------------------

@given(st.lists(st.floats(min_value=0.01, max_value=1e6, allow_nan=False, allow_infinity=False), min_size=0, max_size=50))
def test_property_converged_requires_message(phi_history):
    """Property 1: para cualquier phi_history, sin mensaje nunca es CONVERGED."""
    result = classify_calibration_quality(phi_history, False, CFG)
    assert result != QualityState.CONVERGED


@given(st.lists(st.floats(min_value=0.01, max_value=1e6, allow_nan=False, allow_infinity=False), min_size=0, max_size=50))
def test_property_message_always_converged(phi_history):
    """Con mensaje explicito, SIEMPRE es CONVERGED (sin importar el Phi)."""
    result = classify_calibration_quality(phi_history, True, CFG)
    assert result == QualityState.CONVERGED


# --------------------------------------------------------------------------
# 22.4 - Property 2: la clasificacion es pura (nunca lanza, nunca efectos)
# --------------------------------------------------------------------------

@given(
    st.lists(st.floats(min_value=0.01, max_value=1e6, allow_nan=False, allow_infinity=False), min_size=0, max_size=50),
    st.booleans(),
)
def test_property_classify_is_pure_and_total(phi_history, conv):
    """Property 2: classify siempre retorna un QualityState valido, nunca lanza."""
    result = classify_calibration_quality(phi_history, conv, CFG)
    assert result in QualityState