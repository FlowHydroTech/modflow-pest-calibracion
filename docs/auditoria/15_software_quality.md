# Software Quality Assessment

---

## Evaluación General

| Aspecto | Estado | Observación |
|---------|--------|-------------|
| Estructura de proyecto | ❌ Inexistente | Scripts sueltos, sin módulos |
| Type hints | ⚠️ Parcial | Presentes en scripts recientes, ausentes en legacy |
| Manejo de errores | ⚠️ Parcial | `ClientError` capturado en Batch scripts; ausente en scripts legacy |
| Retries | ⚠️ Parcial | Implementado en `submit_agents()` para throttling. Incompleto en otros |
| Logging | ⚠️ Básico | `print()` con timestamp. No usa módulo `logging` |
| Tests | ❌ Ausentes | Sin pytest, sin directorio tests/ |
| Linting/Formatting | ❌ Ausente | Sin ruff, black, flake8 configurado |
| Separación responsabilidades | ❌ Baja | `auto_scaling_tasks.py` mezcla: Terraform, CloudWatch, ECS, Batch, escalado |
| Documentación | ⚠️ Parcial | Docstrings en funciones críticas. Comentarios inline útiles |
| Configuración centralizada | ❌ Ausente | Valores hardcodeados en múltiples scripts |
| Módulos reutilizables | ❌ Ausentes | Lógica duplicada entre scripts |
| CI/CD | ❌ Ausente | Sin pipeline de integración continua |
| Packaging | ⚠️ Parcial | `pyproject.toml` existe pero no describe el proyecto real |

---

## Bug Crítico Activo

### entrypoint_agent.sh — Variable `$RETRY_CODE` no definida

```bash
# Línea ~85 de entrypoint_agent.sh — BUG ACTIVO:
if [ $RETRY_CODE -eq 80 ] || echo "wine: failed to map the shared user data" \
    2>&1 | grep -q "c0000018"; then

# La variable $RETRY_CODE nunca se define en el script.
# La variable definida más arriba es $EXIT_CODE.
# Esto hace que la condición falle silenciosamente en bash
# (variable no definida = string vacío = no numérico = comparación falla).
```

**Impacto:** El retry ante el error Wine `c0000018` nunca se ejecuta.

---

## Código Muerto Identificado

| Archivo | Razón |
|---------|-------|
| `IaC_terraform/Arquitectura_regional/activar_agentes_pest.py` | Usa `ecs.run_task()` (API ECS). Corresponde a arquitectura gen1 obsoleta |
| `IaC_terraform/Arquitectura_regional/desactivar_agentes_pest.py` | Similar al anterior |
| `Calibracion_Modelo_PEST/Talabre/docker_test/` | docker-compose de testing local, no parte del flujo productivo |
| `Calibracion_Modelo_PEST/sqm_reservas/master1/` | Variante legacy no documentada |
| `Calibracion_Modelo_PEST/sqm_reservas/master - east2/` | Variante legacy no documentada |
| Código comentado en `auto_scaling_tasks.py` | Sección `start_task()` que llama `ecs.run_task()` (API obsoleta) |
| `null_resource "run_agent_once"` en Terraform gen1 | Sustituido por `launch_master_agents.py` pero aún en código |

---

## Análisis de Responsabilidades en auto_scaling_tasks.py

Este archivo mezcla demasiadas responsabilidades:

```
auto_scaling_tasks.py
├── read_terraform_variables()      ← Parseo de archivos TF
├── read_terraform_state()          ← Lectura de state file
├── get_log_streams_by_prefix()     ← CloudWatch Logs
├── get_latest_log_event()          ← CloudWatch Logs
├── extract_model_count()           ← Parsing de mensajes PEST
├── get_all_ecs_tasks()             ← API ECS (¡en stack Batch!)
├── fetch_events()                  ← CloudWatch Logs
├── stop_task()                     ← API ECS stop_task
├── build_task_to_job_map()         ← API Batch
├── summarize_agent_task_status()   ← Análisis de datos
├── validate_stop_tasks()           ← Orquestación de parada
└── main()                          ← Loop principal
```

**Debería separarse en módulos:**
- `calibration_utils/cloudwatch.py` → lectura de logs y métricas
- `calibration_utils/batch.py` → gestión de jobs
- `calibration_utils/terraform.py` → lectura de variables/state
- `calibration_utils/pest_parser.py` → parsing de mensajes PEST
- `autoscaler.py` → lógica de escalado (usa los módulos anteriores)

---

## Duplicación de Código

| Función | Aparece en |
|---------|-----------|
| `fetch_events()` | `auto_scaling_tasks.py` + `Cloudwatch/getLog.py` |
| `parse_iso()` | `auto_scaling_tasks.py` + `Cloudwatch/getLog.py` |
| `clean_message()` | `auto_scaling_tasks.py` + `Cloudwatch/getLog.py` |
| `read_terraform_variables()` | `auto_scaling_tasks.py` + `Arquitectura_regional/activar_agentes_pest.py` |
| `get_log_streams_by_prefix()` | `auto_scaling_tasks.py` + `Cloudwatch/get_log_streams.py` |

---

## Problemas en Scripts Shell

| Script | Problema |
|--------|---------|
| `entrypoint_master.sh` | Sin shebang (`#!/bin/bash`), sin `set -e` |
| `entrypoint_autonomo.sh` | Sin shebang, sin `set -e` |
| `entrypoint_agent.sh` | Tiene shebang y `set -e` ✅ pero bug en `$RETRY_CODE` |
| `ensibatch.sh` | Shebang en línea 14 (no al inicio), lógica mezclada |
| `ensibatch_timeout.sh` | Correcto ✅ — shebang al inicio, `set -uo pipefail` |

---

## Desincronización de Dependencias

```toml
# pyproject.toml (dependencies):
"mkdocs>=1.6.1"        ← solo para documentación, no para scripts
"openpyxl>=3.1.5"
"pandas>=3.0.5"         ← versión diferente a requirements.txt
"python-hcl2>=8.1.2"   ← versión diferente a requirements.txt
```

```
# requirements.txt:
boto3>=1.34           ← AUSENTE en pyproject.toml
pandas>=2.0
python-hcl2>=4.0
pyyaml>=6.0           ← AUSENTE en pyproject.toml
openpyxl>=3.1
```

---

## Recomendaciones de Calidad

| Prioridad | Acción | Esfuerzo |
|-----------|--------|---------|
| 1 | Corregir bug `$RETRY_CODE` → `$EXIT_CODE` | XS |
| 2 | Agregar shebang + `set -e` a entrypoints sin ellos | XS |
| 3 | Mover shebang al inicio de `ensibatch.sh` | XS |
| 4 | Unificar dependencias en `pyproject.toml` | XS |
| 5 | Crear módulo `calibration_utils/` con funciones compartidas | S |
| 6 | Agregar pytest con tests unitarios para funciones críticas | M |
| 7 | Configurar `ruff` para linting básico | XS |
| 8 | Parametrizar scripts hardcodeados (`auto_scaling_tasks.py`) | S |
| 9 | Separar `auto_scaling_tasks.py` en módulos | M |
| 10 | Deprecar código muerto (scripts ECS legacy) | S |
