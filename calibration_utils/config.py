"""CalibrationConfig: contrato de configuracion de una calibracion PEST.

Define el modelo de datos `CalibrationConfig`, su carga desde YAML
(`load_calibration_config`), su validacion local sin llamadas a AWS
(`validate_calibration_config`), su serializacion de vuelta a YAML
(`serialize_calibration_config`) y la generacion de identificadores
(`generate_calibration_id`).

Requisitos cubiertos: 5.1-5.3, 6.1-6.7, 12.1-12.4.
Correctness properties: 5 (formato CalibrationId), 6 (validacion de
constraints), 9 (round-trip del parser).
"""

from __future__ import annotations

import os
import re
import dataclasses
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

import yaml

# Formato canonico de un CalibrationId: CAL-YYYYMMDD-NNN
CALIBRATION_ID_PATTERN = re.compile(r"^CAL-\d{8}-\d{3}$")

# Rango valido de puertos TCP para el proceso master PEST.
_MIN_PORT = 1024
_MAX_PORT = 65535


@dataclass
class CalibrationConfig:
    """Configuracion completa de una calibracion, cargada desde calibration.yaml.

    Los campos sin valor por defecto son obligatorios y deben proveerse en el
    YAML. Los demas tienen defaults razonables alineados con el diseno.
    """

    # --- metadata ---
    name: str                       # requerido
    # --- model ---
    pst_file: str                   # requerido
    # --- infrastructure ---
    terraform_module: str           # requerido
    s3_bucket: str                  # requerido
    ecr_image: str                  # requerido

    # metadata opcional
    id: str = ""                    # auto-generado si vacio: CAL-YYYYMMDD-NNN
    description: str = ""
    model_version: str = ""

    # pest
    executable_master: str = "./pest_hp"
    executable_agent: str = "./agent_hp"
    port: int = 4004
    command_master: str = "/h"
    command_agent: str = "/h"

    # compute
    region: str = "us-east-1"
    master_instance_types: list[str] = field(
        default_factory=lambda: ["r6a.xlarge", "r6i.xlarge"]
    )
    agent_instance_types: list[str] = field(
        default_factory=lambda: ["c7a.medium"]
    )
    initial_agents: int = 50
    max_agents: int = 300
    use_spot: bool = True

    # infrastructure opcional
    ttl_hours: int = 72

    # monitoring
    log_retention_days: int = 90
    alert_email: str = ""

    # quality (condicionado a OQ-07/OQ-08)
    stagnation_window_iterations: int = 5
    stagnation_threshold: float = 0.001
    improvement_threshold: float = 0.01

    # alerts
    notify_on_stagnated: bool = True
    notify_on_converged: bool = True
    notify_on_failed: bool = True
    notify_on_completed: bool = True


@dataclass
class ValidationResult:
    """Resultado de validar una CalibrationConfig.

    `valid` es True solo si no hay errores. `errors` mapea nombre de campo
    (o "<file>" para errores de contexto) al motivo del rechazo.
    """

    valid: bool
    errors: dict[str, str] = field(default_factory=dict)

    def add_error(self, field_name: str, reason: str) -> None:
        self.errors[field_name] = reason
        self.valid = False


# Campos obligatorios (sin default) del contrato.
_REQUIRED_FIELDS = ("name", "pst_file", "terraform_module", "s3_bucket", "ecr_image")

# Conjunto de nombres de campo validos del dataclass, para rechazar claves
# desconocidas en el YAML de forma controlada.
_VALID_FIELDS = {f.name for f in dataclasses.fields(CalibrationConfig)}


def load_calibration_config(path: str) -> CalibrationConfig:
    """Carga y parsea un calibration.yaml en un CalibrationConfig.

    Precondiciones:
      - `path` existe y es un YAML valido.
    Postcondiciones:
      - Retorna un CalibrationConfig con los campos poblados.
    Lanza:
      - FileNotFoundError si el archivo no existe.
      - ValueError si el YAML es invalido, no es un mapa, faltan campos
        obligatorios o contiene claves desconocidas.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"calibration.yaml no encontrado: {path}")

    with open(path, "r", encoding="utf-8") as fh:
        try:
            data = yaml.safe_load(fh)
        except yaml.YAMLError as exc:
            raise ValueError(f"YAML invalido en {path}: {exc}") from exc

    return _config_from_dict(data)


def _config_from_dict(data: object) -> CalibrationConfig:
    """Construye un CalibrationConfig desde un dict ya parseado."""
    if data is None or not isinstance(data, dict):
        raise ValueError(
            "calibration.yaml debe contener un mapa de clave-valor en el nivel raiz"
        )

    unknown = set(data.keys()) - _VALID_FIELDS
    if unknown:
        raise ValueError(f"Campos desconocidos en calibration.yaml: {sorted(unknown)}")

    missing = [f for f in _REQUIRED_FIELDS if not data.get(f)]
    if missing:
        raise ValueError(f"Faltan campos obligatorios en calibration.yaml: {missing}")

    return CalibrationConfig(**data)


def validate_calibration_config(
    config: CalibrationConfig, model_context_path: str | None = None
) -> ValidationResult:
    """Valida una CalibrationConfig localmente, sin llamadas a AWS.

    Reglas (requisitos 6.1-6.7):
      - pst_file debe existir dentro de model_context_path (si se provee).
      - initial_agents <= max_agents.
      - port en rango 1024-65535.
      - ttl_hours > 0.
      - s3_bucket, terraform_module, ecr_image no vacios.

    Postcondiciones:
      - No realiza ninguna llamada de red / AWS.
      - Retorna ValidationResult con un mensaje por cada campo fallido.
    """
    result = ValidationResult(valid=True)

    for name in _REQUIRED_FIELDS:
        value = getattr(config, name, "")
        if value is None or (isinstance(value, str) and value.strip() == ""):
            result.add_error(name, "campo obligatorio vacio o ausente")

    if config.initial_agents > config.max_agents:
        result.add_error(
            "initial_agents",
            f"initial_agents ({config.initial_agents}) no puede ser mayor que "
            f"max_agents ({config.max_agents})",
        )

    if not (_MIN_PORT <= config.port <= _MAX_PORT):
        result.add_error(
            "port", f"port ({config.port}) fuera del rango {_MIN_PORT}-{_MAX_PORT}"
        )

    if config.ttl_hours <= 0:
        result.add_error("ttl_hours", f"ttl_hours ({config.ttl_hours}) debe ser > 0")

    if config.initial_agents < 0:
        result.add_error("initial_agents", "initial_agents no puede ser negativo")

    # pst_file debe existir dentro del contexto del modelo, si se indica.
    if model_context_path and config.pst_file:
        pst_path = os.path.join(model_context_path, config.pst_file)
        if not os.path.isfile(pst_path):
            result.add_error(
                "pst_file", f"no existe dentro del contexto del modelo: {pst_path}"
            )

    return result


def serialize_calibration_config(config: CalibrationConfig) -> str:
    """Serializa una CalibrationConfig a una cadena YAML.

    Propiedad de round-trip (correctness property 9): parsear el YAML
    resultante produce un CalibrationConfig equivalente al original.
    """
    data = asdict(config)
    return yaml.safe_dump(data, sort_keys=True, allow_unicode=True, default_flow_style=False)


def parse_calibration_config(yaml_text: str) -> CalibrationConfig:
    """Parsea una cadena YAML en un CalibrationConfig (contraparte de serialize)."""
    data = yaml.safe_load(yaml_text)
    return _config_from_dict(data)


def generate_calibration_id(existing_ids: list[str] | None = None, now: datetime | None = None) -> str:
    """Genera un CalibrationId unico con formato CAL-YYYYMMDD-NNN.

    `YYYYMMDD` es la fecha UTC actual; `NNN` es un contador secuencial de 3
    digitos. `existing_ids` permite calcular el siguiente secuencial del dia
    (en produccion se obtiene listando el prefijo S3 de calibraciones).

    Propiedad (correctness property 5): el id retornado siempre matchea
    `^CAL-\\d{8}-\\d{3}$`. Dos ids generados el mismo dia con el historial
    correcto tienen sufijos distintos.
    """
    current = now or datetime.now(timezone.utc)
    date_part = current.strftime("%Y%m%d")
    prefix = f"CAL-{date_part}-"

    max_seq = 0
    for existing in existing_ids or []:
        if existing.startswith(prefix) and CALIBRATION_ID_PATTERN.match(existing):
            seq = int(existing[-3:])
            if seq > max_seq:
                max_seq = seq

    next_seq = max_seq + 1
    if next_seq > 999:
        raise ValueError(f"Se agotaron los secuenciales para la fecha {date_part}")

    return f"{prefix}{next_seq:03d}"


def is_valid_calibration_id(value: str) -> bool:
    """True si `value` cumple el formato canonico CAL-YYYYMMDD-NNN."""
    return bool(CALIBRATION_ID_PATTERN.match(value))