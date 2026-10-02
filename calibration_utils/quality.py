"""Quality Engine: clasificacion del estado cientifico de una calibracion.

Distingue el EXECUTION STATE (ciclo de vida operacional) del QUALITY STATE
(progreso cientifico segun la evolucion de Phi). Este modulo implementa solo el
Quality State.

Correctness properties:
  - Property 1: CONVERGED se retorna si y solo si convergence_msg_detected=True
    (nunca se infiere de umbrales numericos).
  - Property 2: STAGNATED solo se clasifica; nunca detiene la calibracion ni
    lanza excepcion (es responsabilidad del llamador generar la alerta).

Requisitos: 11.4, 11.5, 11.6, 11.7, 11.8.

Referencia cientifica: docs/auditoria/10_calibration_quality.md y
docs/auditoria/23_phi_log_format_research.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class QualityState(IntEnum):
    """Estado de calidad de una calibracion. El valor entero se publica como
    metrica CloudWatch (CalibrationQualityState)."""

    UNKNOWN = 0
    IMPROVING = 1
    SLOW_IMPROVEMENT = 2
    STAGNATED = 3
    CONVERGED = 4


@dataclass
class QualityConfig:
    """Umbrales de clasificacion. Configurables (condicionado a OQ-07/OQ-08);
    los defaults son el punto de partida fundamentado, no definitivos."""

    stagnation_window_iterations: int = 5
    stagnation_threshold: float = 0.001   # < 0.1% mejora relativa media -> estancado
    improvement_threshold: float = 0.01   # > 1% mejora relativa media -> mejorando

    @classmethod
    def from_calibration_config(cls, config) -> "QualityConfig":
        """Construye una QualityConfig desde una CalibrationConfig."""
        return cls(
            stagnation_window_iterations=getattr(config, "stagnation_window_iterations", 5),
            stagnation_threshold=getattr(config, "stagnation_threshold", 0.001),
            improvement_threshold=getattr(config, "improvement_threshold", 0.01),
        )


def relative_improvement(phi_prev: float, phi_curr: float) -> float | None:
    """Mejora relativa de una iteracion: (phi_prev - phi_curr) / phi_prev.

    Retorna None si phi_prev <= 0 (no se puede calcular mejora relativa).
    Positivo = Phi bajo (mejoro); negativo = Phi subio (empeoro).
    """
    if phi_prev <= 0:
        return None
    return (phi_prev - phi_curr) / phi_prev


def classify_calibration_quality(
    phi_history: list[float],
    convergence_msg_detected: bool,
    config: QualityConfig | None = None,
) -> QualityState:
    """Clasifica el estado de calidad de una calibracion.

    Args:
      phi_history: Phi por iteracion, en orden cronologico.
      convergence_msg_detected: True si el log del master contiene un mensaje
        explicito de convergencia de PEST (RELPARSTP/PHIREDSTP/"optimisation
        complete"). Es la UNICA fuente para CONVERGED.
      config: umbrales; usa defaults si no se provee.

    Returns:
      QualityState.

    Precondiciones: config.improvement_threshold > config.stagnation_threshold > 0.
    Postcondiciones:
      - CONVERGED <=> convergence_msg_detected (Property 1).
      - Nunca lanza excepcion ni modifica estado externo (Property 2).
      - phi_history con < 2 elementos -> UNKNOWN (requisito 11.8).
    """
    cfg = config or QualityConfig()

    # Property 1: CONVERGED SOLO desde mensaje explicito de PEST.
    if convergence_msg_detected:
        return QualityState.CONVERGED

    # Requisito 11.8: datos insuficientes.
    if phi_history is None or len(phi_history) < 2:
        return QualityState.UNKNOWN

    # Ventana deslizante: ultimas N iteraciones (requisito 11.7).
    window = max(2, cfg.stagnation_window_iterations)
    recent = phi_history[-(window + 1):] if len(phi_history) > window else phi_history

    improvements: list[float] = []
    for i in range(1, len(recent)):
        imp = relative_improvement(recent[i - 1], recent[i])
        if imp is not None:
            improvements.append(imp)

    if not improvements:
        return QualityState.UNKNOWN

    sliding_mean = sum(improvements) / len(improvements)

    # Clasificacion por umbrales (requisito 11.4).
    if sliding_mean > cfg.improvement_threshold:
        return QualityState.IMPROVING
    if sliding_mean > cfg.stagnation_threshold:
        return QualityState.SLOW_IMPROVEMENT
    # Property 2: STAGNATED solo se clasifica; el llamador decide la alerta.
    return QualityState.STAGNATED


# Palabras clave de convergencia de PEST_HP (del estado del arte, doc 23).
PEST_CONVERGENCE_KEYWORDS = (
    "RELPARSTP",
    "PHIREDSTP",
    "NOPTMAX",
    "optimisation complete",
    "optimization complete",
)


def detect_convergence_message(log_text: str) -> bool:
    """True si el texto de log contiene una palabra clave de convergencia PEST."""
    lowered = log_text.lower()
    return any(kw.lower() in lowered for kw in PEST_CONVERGENCE_KEYWORDS)