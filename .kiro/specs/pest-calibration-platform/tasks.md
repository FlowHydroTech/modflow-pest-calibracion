# Implementation Plan: PEST Calibration Platform

## Overview

Plan de implementación incremental en seis fases del PEST Calibration Platform. El Compute Plane (AWS Batch EC2) no cambia; estas tareas construyen únicamente el Control Plane encima de él. Las Fases 0 y 1 constituyen el MVP: corrigen riesgos activos y eliminan la dependencia de la conexión del operador. Las Fases 2–6 añaden observabilidad, quality monitoring y automatización completa de forma incremental.

Todas las tareas son de código: crear archivos, modificar scripts, implementar funciones o escribir tests. No se incluyen tareas de despliegue manual, documentación de usuario ni validaciones manuales.

---

## Tasks

## Fase 0 — Estabilización (MVP, Quick Wins)

Corrige los riesgos activos sin agregar nuevas funcionalidades. Todas las tareas de esta fase son obligatorias.

- [ ] 1. Corregir bug `$RETRY_CODE` → `$EXIT_CODE` en entrypoints de agente
  - Buscar todas las ocurrencias de `$RETRY_CODE` en archivos `entrypoint_agent.sh` dentro de `Calibracion_Modelo_PEST/` y reemplazar por `$EXIT_CODE`
  - Verificar que `EXIT_CODE=$?` se asigna inmediatamente después de la llamada al proceso agente en cada entrypoint modificado
  - Confirmar que la condición de retry evalúa `[ $EXIT_CODE -eq 80 ]` en todos los archivos corregidos
  - _Requisitos: 1.1, 1.2, 1.3, 1.4_

  - [ ] 1.1 Corregir entrypoints en `cmdic_linux_compile/app/entrypoint_agent.sh`
    - Reemplazar `$RETRY_CODE` por `$EXIT_CODE` y verificar asignación `EXIT_CODE=$?`
    - _Requisitos: 1.1, 1.2, 1.4_

  - [ ] 1.2 Corregir entrypoints en todos los subdirectorios de `sqm_reservas/`
    - Aplicar la misma corrección en `sqm_reservas/master/app/entrypoint_agent.sh`, `master - east2/app/entrypoint_agent.sh` y `master1/app/entrypoint_agent.sh`
    - _Requisitos: 1.1, 1.2, 1.4_

  - [ ] 1.3 Corregir entrypoints en `Estructura_Base/` y cualquier otro subdirectorio activo
    - Buscar con `grep -r 'RETRY_CODE'` todos los archivos restantes y aplicar la corrección
    - _Requisitos: 1.1, 1.2, 1.4_

- [ ] 2. Agregar shebang y `set -e` a entrypoints que los omiten
  - Verificar que `#!/bin/bash` sea la primera línea de cada `entrypoint_agent.sh`, `entrypoint_master.sh` y `entrypoint_autonomo.sh`
  - Agregar `set -e` (o checks explícitos de exit code) en los archivos que no lo tengan
  - _Requisitos: 1.5, 1.6_

  - [ ] 2.1 Auditar y corregir shebangs en todos los entrypoints activos
    - Recorrer todos los archivos `entrypoint_*.sh` y agregar `#!/bin/bash` si falta
    - _Requisitos: 1.5_

  - [ ]* 2.2 Escribir test de lint para verificar shebang y `set -e` en entrypoints
    - Agregar script `scripts/lint_entrypoints.sh` que falle si algún entrypoint carece de shebang o `set -e`
    - _Requisitos: 1.5, 1.6_

- [ ] 3. Configurar Terraform backend S3 + DynamoDB en el módulo talabre-linux
  - Crear archivo `backend.tf` en el módulo Terraform activo con el bloque `terraform { backend "s3" { ... } }`
  - Usar variables para `bucket`, `key`, `region` y `dynamodb_table` (no valores hardcodeados)
  - Habilitar `encrypt = true` en la configuración del backend
  - Crear los recursos S3 (con versionado) y DynamoDB (tabla de locks) en un módulo de bootstrap separado si no existen
  - _Requisitos: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [ ] 3.1 Crear `IaC_terraform/bootstrap/main.tf` con bucket S3 de state y tabla DynamoDB
    - Definir `aws_s3_bucket` con versioning habilitado, `aws_s3_bucket_server_side_encryption_configuration` y `aws_dynamodb_table` con `LockID` como hash key
    - _Requisitos: 2.1, 2.2, 2.3_

  - [ ] 3.2 Crear `backend.tf` en el módulo `talabre-linux` con backend S3 parametrizado
    - Usar `variable "tf_state_bucket"`, `variable "tf_state_key"` y `variable "tf_lock_table"` para que sea configurable por entorno
    - _Requisitos: 2.1, 2.4, 2.5_

- [ ] 4. Restringir IAM wildcard S3 al bucket específico de cada calibración
  - Localizar el recurso `aws_iam_role_policy "task_role_s3"` en `main.tf` del módulo talabre-linux
  - Reemplazar `arn:aws:s3:::*` y `arn:aws:s3:::*/*` por `arn:aws:s3:::${var.s3_bucket}` y `arn:aws:s3:::${var.s3_bucket}/*`
  - Revisar si existe permiso KMS Decrypt con `Resource = "*"` en módulos legacy gen1 y reemplazarlo por ARN específico o eliminar el permiso si no se usa
  - _Requisitos: 3.1, 3.2, 3.5_

  - [ ] 4.1 Restringir S3 IAM en `talabre-linux/main.tf`
    - Modificar el `Statement` de S3 para usar `arn:aws:s3:::${var.s3_bucket}` y `arn:aws:s3:::${var.s3_bucket}/*`
    - _Requisitos: 3.1, 3.2_

  - [ ] 4.2 Revisar y restringir IAM en módulos gen1 (KMS + S3 wildcard)
    - Localizar el permiso KMS Decrypt con wildcard y reemplazarlo por ARN de clave específica o eliminarlo si no hay cifrado activo
    - _Requisitos: 3.5_

- [ ] 5. Mover datos sensibles fuera del código versionado
  - Eliminar todos los valores hardcodeados de account ID (12 dígitos), VPC IDs (`vpc-*`), subnet IDs (`subnet-*`) y route table IDs (`rtb-*`) de los archivos `variables.tf`
  - Reemplazar account IDs en scripts Python/PowerShell/Bash por llamadas dinámicas a `aws sts get-caller-identity`
  - Crear `.gitignore` actualizado que excluya `terraform.tfvars`, `*.tfvars` (excepto `*.tfvars.example`)
  - _Requisitos: 4.1, 4.2, 4.3_

  - [ ] 5.1 Limpiar `variables.tf` de IDs de infraestructura hardcodeados
    - Reemplazar valores default de VPC ID, subnet ID y route table ID por `""` (vacío) o eliminar el default para forzar que el operador los provea en `terraform.tfvars`
    - _Requisitos: 4.1, 4.2_

  - [ ] 5.2 Reemplazar account ID hardcodeado en scripts operacionales
    - Actualizar scripts Python y Bash que usan account ID estático para derivarlo dinámicamente con `boto3.client('sts').get_caller_identity()['Account']` o `$(aws sts get-caller-identity --query Account --output text)`
    - _Requisitos: 4.3_

- [ ] 6. Crear `terraform.tfvars.example` con todas las variables requeridas
  - Crear el archivo en el directorio raíz del módulo activo (`talabre-linux/terraform.tfvars.example`) documentando cada variable sin valores reales
  - Incluir comentarios explicativos para cada variable (cómo obtener el valor, formato esperado)
  - Verificar que `terraform.tfvars` está en `.gitignore`
  - _Requisitos: 4.4_

  - [ ] 6.1 Crear `terraform.tfvars.example` en `talabre-linux/`
    - Documentar todas las variables necesarias con valores de ejemplo ficticios y comentarios
    - _Requisitos: 4.4_

- [ ] 7. Consolidar `pyproject.toml` con todas las dependencias necesarias
  - Crear o actualizar `pyproject.toml` en la raíz del repositorio como fuente única de dependencias Python
  - Agregar `boto3>=1.34.0,<2.0`, `pyyaml>=6.0,<7.0`, `python-hcl2>=4.3,<5.0`, `click>=8.1,<9.0`, `rich>=13.0,<14.0` como dependencias runtime
  - Agregar sección `[project.optional-dependencies]` con `test = ["pytest>=8.0,<9.0", "pytest-mock>=3.14,<4.0", "hypothesis>=6.100,<7.0", "moto[batch,cloudwatch,s3,logs]>=5.0,<6.0"]`
  - Identificar y marcar como redundantes los `requirements.txt` individuales que dupliquen estas dependencias
  - _Requisitos: 18.1, 18.2, 18.3, 18.4_

  - [ ] 7.1 Crear/actualizar `pyproject.toml` con dependencias runtime y de test
    - Incluir todas las dependencias del diseño con rangos de versión exactos
    - _Requisitos: 18.1, 18.2, 18.4_

  - [ ] 7.2 Añadir comentarios de deprecación a `requirements.txt` individuales
    - Agregar al inicio de cada `requirements.txt` existente un comentario indicando que `pyproject.toml` es la fuente autoritativa
    - _Requisitos: 18.3_

- [ ] 8. Checkpoint Fase 0 — Verificar correcciones críticas
  - Verificar que todos los entrypoints corregidos pasen el lint de shebang
  - Verificar que no hay referencias a `$RETRY_CODE` en el repositorio
  - Asegurarse de que todos los tests pasen; preguntar al usuario si surgen dudas.

---

## Fase 1 — Automatización IaC

Elimina la dependencia de la conexión del operador e implementa el núcleo del Control Plane. Todas las tareas de esta fase son obligatorias (MVP).

- [ ] 9. Implementar `calibration_utils/config.py`: CalibrationConfig + parser/validator
  - Crear el directorio `calibration_utils/` con `__init__.py`
  - Implementar el dataclass `CalibrationConfig` con todos los campos del diseño y sus valores por defecto
  - Implementar `load_calibration_config(path: str) -> CalibrationConfig` usando PyYAML
  - Implementar `validate_calibration_config(config: CalibrationConfig) -> ValidationResult` con todas las reglas de validación (sin llamadas a AWS)
  - Implementar `generate_calibration_id() -> str` con formato `CAL-YYYYMMDD-NNN` y contador secuencial basado en S3
  - _Requisitos: 5.1, 5.2, 5.3, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 12.1, 12.2_

  - [ ] 9.1 Crear `calibration_utils/__init__.py` y estructura de paquete
    - Inicializar el paquete con imports públicos de las funciones principales
    - _Requisitos: 16.3_

  - [ ] 9.2 Implementar `CalibrationConfig` dataclass en `calibration_utils/config.py`
    - Definir todos los campos con tipos y valores por defecto según el diseño
    - _Requisitos: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [ ] 9.3 Implementar `load_calibration_config` y `validate_calibration_config`
    - Parser YAML que retorna `CalibrationConfig` y validador que retorna `ValidationResult` con mensajes descriptivos por campo fallido
    - _Requisitos: 6.6, 6.7, 12.1, 12.2_

  - [ ] 9.4 Implementar `generate_calibration_id` con formato `CAL-YYYYMMDD-NNN`
    - Usar fecha UTC + contador secuencial; garantizar unicidad para múltiples IDs en el mismo día
    - _Requisitos: 5.1, 5.2, 5.3_

  - [ ]* 9.5 Escribir tests unitarios para `CalibrationConfig` y el validador
    - Probar campos faltantes, `initial_agents > max_agents`, `port` fuera de rango, `ttl_hours <= 0`
    - _Requisitos: 6.2, 6.3, 6.4, 6.6_

  - [ ]* 9.6 Escribir property test: configuraciones con `initial_agents > max_agents` siempre fallan validación
    - Usar `hypothesis` para generar configuraciones inválidas; verificar que `valid=False` siempre
    - **Property 6: CalibrationConfig validation rejects constraint violations**
    - **Validates: Requirements 6.2, 6.3, 6.4**

  - [ ]* 9.7 Escribir property test de round-trip YAML para `CalibrationConfig`
    - Serializar a YAML y parsear de vuelta; verificar equivalencia de todos los campos
    - **Property 9: Config Parser round-trip preserves CalibrationConfig**
    - **Validates: Requirements 12.3, 12.4**

  - [ ]* 9.8 Escribir property test: todos los CalibrationIds generados cumplen formato `^CAL-\d{8}-\d{3}$`
    - Generar N IDs y verificar que todos coinciden con el patrón regex
    - **Property 5: CalibrationId format is enforced across all components**
    - **Validates: Requirements 5.1, 5.3**

- [ ] 10. Implementar `Config_Serializer`: serialización YAML de `CalibrationConfig`
  - Agregar función `serialize_calibration_config(config: CalibrationConfig) -> str` en `calibration_utils/config.py`
  - Garantizar que el YAML generado es parseable de vuelta a un objeto equivalente
  - _Requisitos: 12.3, 12.4_

  - [ ] 10.1 Implementar `serialize_calibration_config` en `calibration_utils/config.py`
    - Serializar el dataclass a YAML preservando tipos y valores por defecto
    - _Requisitos: 12.3_

- [ ] 11. Implementar `calibration_utils/batch.py`: gestión de jobs AWS Batch
  - Implementar `submit_master_job(job_queue, job_def, env_vars) -> str`
  - Implementar `wait_for_master_ip(job_id, timeout_s=600) -> str | None` (retorna `None` si timeout sin bloquear)
  - Implementar `submit_agent_jobs(job_queue, job_def, n, master_ip) -> list[str]`
  - Implementar `get_running_jobs(job_queue) -> list[BatchJob]` usando `batch:ListJobs` (NO ECS API)
  - Implementar `terminate_job(job_id, reason) -> None` usando `batch:TerminateJob`
  - _Requisitos: 8.3, 16.2, 16.5_

  - [ ] 11.1 Implementar `submit_master_job` y `submit_agent_jobs` en `calibration_utils/batch.py`
    - Usar `boto3.client('batch').submit_job()` con parámetros del diseño
    - _Requisitos: 16.2_

  - [ ] 11.2 Implementar `wait_for_master_ip` con timeout configurable
    - Sondear `batch:DescribeJobs` hasta que el job esté en RUNNING y tenga IP via EC2 tags; retornar `None` si se agota `timeout_s`
    - _Requisitos: 16.5_

  - [ ] 11.3 Implementar `get_running_jobs` y `terminate_job` usando exclusivamente Batch API
    - Prohibir cualquier llamada a ECS; documentar explícitamente en el módulo que solo se usa Batch API
    - _Requisitos: 8.3, 16.2_

  - [ ]* 11.4 Escribir tests unitarios para `batch.py` con `moto`
    - Verificar que `wait_for_master_ip` retorna `None` al timeout, que `get_running_jobs` nunca llama ECS
    - _Requisitos: 8.3, 16.5_

- [ ] 12. Implementar Lambda Autoscaler con EventBridge scheduled rule
  - Crear directorio `lambdas/autoscaler/` con `handler.py`, `requirements.txt` y `template.yaml` (SAM o Terraform)
  - Implementar `handler(event, context) -> AutoscalerResult` con el algoritmo del diseño
  - Implementar `extract_models_requested(log_group, calibration_id) -> int` leyendo patrones de logs
  - Implementar verificación de salud del master (sin logs > 30 min → publicar `MasterHealth=0`)
  - Implementar lanzamiento de agentes con límite `max_agents`
  - Implementar terminación de agentes que completaron vía `batch:TerminateJob`
  - Crear regla EventBridge (o Terraform `aws_cloudwatch_event_rule`) con schedule `rate(10 minutes)`
  - Definir IAM Role con permisos mínimos: `batch:ListJobs`, `batch:SubmitJob`, `batch:TerminateJob`, `cloudwatch:PutMetricData`, `logs:GetLogEvents`
  - _Requisitos: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8_

  - [ ] 12.1 Crear estructura `lambdas/autoscaler/` con `handler.py` base
    - Implementar el esqueleto del handler con parseo de `event` y retorno de `AutoscalerResult`
    - _Requisitos: 8.1, 8.7_

  - [ ] 12.2 Implementar `extract_models_requested` leyendo logs de CloudWatch
    - Buscar patrones `"Running model X times"` y `"Calculating Jacobian matrix: running model X times"` en los últimos 15 minutos; retornar el máximo X
    - _Requisitos: 8.2_

  - [ ] 12.3 Implementar ciclo completo de autoscaling (verificar master, ajustar agentes)
    - Integrar verificación de salud, conteo de agentes activos vía Batch API, lanzamiento de nuevos agentes y terminación de completados
    - _Requisitos: 8.3, 8.4, 8.5, 8.6, 8.8_

  - [ ] 12.4 Crear módulo Terraform `lambdas/autoscaler/infra.tf` con Lambda + EventBridge + IAM Role
    - Definir `aws_lambda_function`, `aws_cloudwatch_event_rule`, `aws_cloudwatch_event_target` y `aws_iam_role` con permisos mínimos
    - _Requisitos: 3.3, 8.1_

  - [ ]* 12.5 Escribir tests unitarios para el handler del Autoscaler con `moto`
    - Verificar que no se lanzan más agentes que `max_agents`, que se usa Batch API exclusivamente, que `MasterHealth=0` se publica cuando no hay logs
    - _Requisitos: 8.3, 8.4, 8.6_

  - [ ]* 12.6 Escribir property test: autoscaler nunca excede `max_agents`
    - **Property 4: Autoscaler uses only the Batch API for job management**
    - **Validates: Requirements 8.3**

- [ ] 13. Implementar `scripts/safe_destroy.py` con verificación S3
  - Implementar `safe_destroy(calibration_id, terraform_module, s3_bucket, force=False) -> DestroyResult`
  - Implementar `s3_results_exist(bucket, calibration_id) -> bool`
  - Implementar exportación de logs CloudWatch a S3 antes del destroy
  - Implementar parada de todos los Batch jobs activos antes del destroy
  - Implementar `verify_no_orphan_resources(project_name, region) -> OrphanCheckResult`
  - Manejar fallo de `terraform destroy`: enviar alerta SNS con lista de recursos, retornar `DestroyResult(success=False)`
  - _Requisitos: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8_

  - [ ] 13.1 Implementar `s3_results_exist` y la guardia principal de `safe_destroy`
    - Verificar prefijo S3 antes de cualquier acción; retornar `DestroyResult(success=False, reason="NO_RESULTS_IN_S3")` si no hay resultados y `force=False`
    - _Requisitos: 9.1_

  - [ ] 13.2 Implementar exportación de logs y parada de Batch jobs
    - Exportar logs del master y agentes a S3; detener todos los jobs activos con `batch:TerminateJob`
    - _Requisitos: 9.2, 9.4_

  - [ ] 13.3 Implementar `terraform destroy` con manejo de errores y verificación de huérfanos
    - Ejecutar `terraform destroy` via subprocess; en fallo, enviar SNS con recursos a limpiar manualmente; verificar recursos huérfanos post-destroy
    - _Requisitos: 9.5, 9.6, 9.7_

  - [ ]* 13.4 Escribir tests unitarios para `safe_destroy` con `moto`
    - Verificar que `terraform destroy` nunca se llama cuando `s3_results_exist()` es `False` y `force=False`; verificar que con `force=True` procede aunque S3 esté vacío
    - _Requisitos: 9.1, 9.8_

  - [ ]* 13.5 Escribir property test: `safe_destroy` con `force=False` y S3 vacío siempre retorna `success=False`
    - **Property 3: safe_destroy preserves results before destroying infrastructure**
    - **Validates: Requirements 9.1**

- [ ] 14. Deprecar y archivar archivos legacy ECS Fargate
  - Crear directorio `_legacy/` en la raíz del repositorio
  - Mover `IaC_terraform/Arquitectura_regional/`, `IaC_terraform/ModeloPest/unica_region_EC2/` e `IaC_terraform/ModeloPest/Multiple_Region/` a `_legacy/`
  - Mover scripts que llaman ECS API (`ecs:RunTask`, `ecs:StopTask`, `ecs:ListTasks`) a `_legacy/`
  - Agregar `README_LEGACY.md` en `_legacy/` explicando por qué están archivados
  - _Requisitos: 17.1, 17.2, 17.3, 17.4_

  - [ ] 14.1 Crear `_legacy/` y mover módulos Terraform ECS Fargate
    - Mover los tres directorios de módulos legacy a `_legacy/IaC_terraform/`
    - _Requisitos: 17.1_

  - [ ] 14.2 Mover scripts ECS API a `_legacy/scripts/` y agregar `README_LEGACY.md`
    - Mover `activar_agentes_pest.py` y cualquier script que llame ECS API; agregar README explicando la migración a Batch gen2
    - _Requisitos: 17.2, 17.4_

- [ ] 15. Checkpoint Fase 1 — Verificar núcleo del Control Plane
  - Ejecutar todos los tests unitarios y de propiedades de `calibration_utils/` y lambdas
  - Verificar que no hay imports de ECS API en código activo (fuera de `_legacy/`)
  - Asegurarse de que todos los tests pasen; preguntar al usuario si surgen dudas.

---

## Fase 2 — Observabilidad

Añade métricas en tiempo real, alarmas y retención de logs para detectar fallos sin conexión manual.

- [ ] 16. Implementar publicación de métricas CloudWatch en `calibration_utils/`
  - Agregar función `publish_metric(name, value, calibration_id, unit="None")` en un módulo `calibration_utils/metrics.py`
  - Garantizar que toda llamada a `cloudwatch:PutMetricData` incluye la dimensión `CalibrationId` con valor no vacío
  - Publicar `MasterHealth`, `ActiveWorkers` y `CalibrationRuntime` desde el Lambda Autoscaler
  - _Requisitos: 10.1, 10.2_

  - [ ] 16.1 Crear `calibration_utils/metrics.py` con `publish_metric`
    - Implementar wrapper de `cloudwatch:PutMetricData` que fuerza la dimensión `CalibrationId`
    - _Requisitos: 10.1_

  - [ ] 16.2 Integrar publicación de métricas en el Lambda Autoscaler
    - Llamar a `publish_metric` para `MasterHealth`, `ActiveWorkers` al final de cada ciclo
    - _Requisitos: 10.2, 8.8_

  - [ ]* 16.3 Escribir property test: todas las métricas publicadas llevan dimensión `CalibrationId`
    - **Property 7: All published metrics carry the CalibrationId dimension**
    - **Validates: Requirements 10.1**

- [ ] 17. Configurar CloudWatch Alarms + SNS topic para alertas críticas
  - Crear módulo Terraform `infra/observability.tf` con: SNS topic `pest-alerts`, alarma sobre `MasterHealth` (valor 0 por 2 períodos de 5 min), alarma de TTL de infraestructura activa
  - Configurar suscripción email al SNS topic usando `alert_email` del `CalibrationConfig`
  - _Requisitos: 10.4, 10.5, 10.6_

  - [ ] 17.1 Crear `infra/observability.tf` con SNS topic y alarma de `MasterHealth`
    - Definir `aws_sns_topic`, `aws_sns_topic_subscription` (email), `aws_cloudwatch_metric_alarm` para `MasterHealth`
    - _Requisitos: 10.4, 10.5_

  - [ ] 17.2 Agregar alarma de TTL de infraestructura activa
    - Definir `aws_cloudwatch_metric_alarm` sobre `CalibrationRuntime` que dispara cuando supera `ttl_hours * 3600` segundos
    - _Requisitos: 10.6_

- [ ] 18. Configurar retención de 90 días en log groups del master
  - Agregar `aws_cloudwatch_log_group` con `retention_in_days = 90` en el módulo Terraform activo para los log groups `/batch/{id}-master` y `/batch/{id}-agents`
  - _Requisitos: 10.3_

  - [ ] 18.1 Agregar configuración de retención de logs en `talabre-linux/main.tf`
    - Crear o actualizar `aws_cloudwatch_log_group` para master y agentes con `retention_in_days = 90`
    - _Requisitos: 10.3_

- [ ] 19. Crear script de validación del formato de logs Phi del master (OQ-03)
  - Crear `scripts/validate_phi_log_format.py` que descarga los últimos N eventos del log group del master y prueba los patrones candidatos: `r'Phi\s*=\s*([\d\.]+)'`, `r'Objective function value:\s*([\d\.]+)'`, `r'Current phi\s*=\s*([\d\.]+)'`
  - Imprimir el patrón que genera más matches y los primeros 5 ejemplos de cada uno
  - Este script es un prerequisito para la Fase 3 — su output confirma OQ-03
  - _Requisitos: 11.1_

  - [ ] 19.1 Crear `scripts/validate_phi_log_format.py`
    - Script que toma `--log-group` y `--calibration-id` como argumentos CLI, descarga eventos y prueba los patrones candidatos de Phi
    - _Requisitos: 11.1_

- [ ] 20. Checkpoint Fase 2 — Verificar observabilidad
  - Ejecutar todos los tests de `calibration_utils/metrics.py`
  - Verificar que no hay llamadas a `cloudwatch:PutMetricData` sin dimensión `CalibrationId`
  - Asegurarse de que todos los tests pasen; preguntar al usuario si surgen dudas.

---

## Fase 3 — Quality Engine

Condicionado a OQ-03 (formato de logs Phi confirmado). Implementa la extracción de Phi y clasificación de calidad.

- [ ] 21. Implementar Lambda ExtractPhiMetrics
  - Crear `lambdas/extract_phi/handler.py` con el handler disparado por CloudWatch Logs subscription filter
  - Implementar `extract_phi_from_events(events, phi_pattern) -> list[PhiReading]` usando el patrón regex confirmado vía OQ-03
  - Publicar métricas `PhiCurrent`, `PhiBest`, `CurrentIteration` con dimensión `CalibrationId`
  - Definir IAM Role con permisos mínimos: `logs:FilterLogEvents`, `logs:GetLogEvents`, `cloudwatch:PutMetricData`
  - _Requisitos: 11.1, 11.2, 11.3, 3.4_

  - [ ] 21.1 Crear estructura `lambdas/extract_phi/` con `handler.py`
    - Implementar esqueleto del handler con parseo del evento de CloudWatch Logs
    - _Requisitos: 11.1_

  - [ ] 21.2 Implementar `extract_phi_from_events` con el patrón regex confirmado (OQ-03)
    - Parsear eventos de log para extraer valor de Phi y número de iteración
    - _Requisitos: 11.1, 11.3_

  - [ ] 21.3 Implementar publicación de `PhiCurrent`, `PhiBest`, `CurrentIteration`
    - Mantener el mínimo histórico para `PhiBest`; publicar las tres métricas con dimensión `CalibrationId`
    - _Requisitos: 11.1, 11.2, 11.3_

  - [ ] 21.4 Crear módulo Terraform para Lambda ExtractPhi + IAM Role
    - Definir Lambda, subscription filter del log group del master y IAM Role con permisos mínimos
    - _Requisitos: 3.4_

  - [ ]* 21.5 Escribir tests unitarios para `extract_phi_from_events`
    - Probar con líneas de log reales y edge cases (línea sin Phi, múltiples valores en el mismo evento)
    - _Requisitos: 11.1_

- [ ] 22. Implementar clasificador `QualityState` (Quality Engine)
  - Crear `calibration_utils/quality.py` con `classify_calibration_quality(phi_history, convergence_msg_detected, config) -> QualityState`
  - Implementar ventana deslizante con `stagnation_window_iterations` configurables
  - Garantizar que `CONVERGED` solo se retorna cuando `convergence_msg_detected=True`
  - Garantizar que `STAGNATED` no lanza excepción ni detiene la calibración
  - Retornar `QualityState.UNKNOWN` cuando `phi_history` tiene menos de 2 elementos
  - _Requisitos: 11.4, 11.5, 11.6, 11.7, 11.8_

  - [ ] 22.1 Implementar `classify_calibration_quality` en `calibration_utils/quality.py`
    - Implementar el algoritmo de ventana deslizante del diseño con los cuatro estados
    - _Requisitos: 11.4, 11.5, 11.7, 11.8_

  - [ ]* 22.2 Escribir tests unitarios para el clasificador
    - Probar: lista vacía → UNKNOWN, 1 elemento → UNKNOWN, convergencia numérica sin mensaje → no CONVERGED, STAGNATED no lanza excepción
    - _Requisitos: 11.5, 11.6, 11.8_

  - [ ]* 22.3 Escribir property test: CONVERGED nunca sin mensaje PEST
    - Para cualquier `phi_history` y `convergence_msg_detected=False`, el resultado nunca es `CONVERGED`
    - **Property 1: CONVERGED requires an explicit PEST message**
    - **Validates: Requirements 11.5**

  - [ ]* 22.4 Escribir property test: STAGNATED nunca detiene la calibración
    - Para cualquier estado STAGNATED, verificar que no se llama a `batch:TerminateJob` ni se modifica el `ExecutionState`
    - **Property 2: STAGNATED never stops the calibration automatically**
    - **Validates: Requirements 11.6**

- [ ] 23. Configurar alerta SNS WARNING para `QualityState.STAGNATED`
  - Integrar el clasificador en el Lambda ExtractPhi: cuando el estado sea STAGNATED, publicar alerta WARNING via SNS
  - Verificar que el Lambda no llama a `batch:TerminateJob` cuando detecta STAGNATED
  - Publicar métrica `CalibrationQualityState` (0–4 según enum) con dimensión `CalibrationId`
  - _Requisitos: 11.4, 11.6_

  - [ ] 23.1 Integrar clasificador de calidad en `lambdas/extract_phi/handler.py`
    - Llamar a `classify_calibration_quality` después de extraer el Phi y publicar `CalibrationQualityState`; enviar SNS WARNING si STAGNATED
    - _Requisitos: 11.4, 11.6_

- [ ] 24. Checkpoint Fase 3 — Verificar Quality Engine
  - Ejecutar todos los property tests del clasificador y tests del Lambda ExtractPhi
  - Asegurarse de que todos los tests pasen; preguntar al usuario si surgen dudas.

---

## Fase 4 — Dashboard

Añade visibilidad centralizada en CloudWatch.

- [ ] 25. Crear CloudWatch Dashboard con widgets de Phi, infraestructura y logs
  - Agregar `aws_cloudwatch_dashboard` en `infra/observability.tf` con los siguientes widgets:
    - Widget de línea: `PhiCurrent` y `PhiBest` por iteración (evolución de la función objetivo)
    - Widget de número: `CalibrationQualityState` (estado actual)
    - Widget de número: `ActiveWorkers` y `MasterHealth`
    - Widget de número: `CalibrationRuntime` (segundos)
    - Widget de logs: últimas 50 líneas del log group del master
  - Parametrizar el dashboard con `CalibrationId` como variable
  - _Requisitos: 10.1, 10.2_

  - [ ] 25.1 Definir `aws_cloudwatch_dashboard` en `infra/observability.tf`
    - Crear el JSON de configuración del dashboard con los cinco tipos de widget especificados
    - _Requisitos: 10.1, 10.2_

- [ ] 26. Checkpoint Fase 4 — Verificar dashboard
  - Revisar que el JSON del dashboard es válido (sin deploy requerido en esta tarea)
  - Asegurarse de que no hay errores de sintaxis Terraform; preguntar al usuario si surgen dudas.

---

## Fase 5 — Reproducibilidad

Genera trazabilidad científica completa con manifests inmutables y tags de imagen por commit.

- [ ] 27. Implementar `calibration_utils/manifest.py`: CalibrationManifest + guardado en S3
  - Implementar el dataclass `CalibrationManifest` con todos los campos del diseño
  - Implementar `generate_manifest(calibration_id, config, metrics) -> CalibrationManifest`
  - Implementar `save_manifest_to_s3(manifest, bucket) -> str` que guarda en `s3://{bucket}/calibrations/{id}/manifest.json`
  - Garantizar que `docker_image_digest` nunca contiene `:latest` — validar en la función de generación
  - Calcular `phi_reduction_pct = (phi_initial - phi_final) / phi_initial * 100` cuando ambos valores estén disponibles
  - _Requisitos: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6_

  - [ ] 27.1 Implementar `CalibrationManifest` dataclass en `calibration_utils/manifest.py`
    - Definir todos los campos de reproducibilidad y métricas científicas del diseño
    - _Requisitos: 13.2, 13.5_

  - [ ] 27.2 Implementar `generate_manifest` y `save_manifest_to_s3`
    - Calcular `configuration_hash` como SHA256 del YAML, `phi_reduction_pct` cuando sea posible; guardar JSON en S3
    - _Requisitos: 13.1, 13.4, 13.6_

  - [ ] 27.3 Integrar `save_manifest_to_s3` en `safe_destroy.py` (paso 3 del algoritmo)
    - Llamar a `generate_manifest` y `save_manifest_to_s3` antes de invocar `terraform destroy`
    - _Requisitos: 9.3, 13.1_

  - [ ]* 27.4 Escribir property test: ningún manifest usa `:latest` como digest
    - Para cualquier `CalibrationManifest` generado, `docker_image_digest` no contiene `:latest` y coincide con `sha256:[a-f0-9]{64}`
    - **Property 8: CalibrationManifest never uses :latest as image reference**
    - **Validates: Requirements 13.3**

- [ ] 28. Actualizar build scripts para usar commit SHA como image tag
  - Modificar el script de build Docker (o agregar `scripts/build_and_push.sh`) para:
    - Obtener el commit SHA con `git rev-parse HEAD`
    - Etiquetar la imagen con `{ecr_repo}:{git_sha[:8]}`
    - Advertir si hay cambios no commiteados antes de construir
    - No publicar imágenes únicamente con tag `:latest`
  - _Requisitos: 14.1, 14.2, 14.4_

  - [ ] 28.1 Crear `scripts/build_and_push.sh` con lógica de SHA tagging
    - Obtener SHA, construir imagen, advertir si hay uncommitted changes, pushear con tag de SHA
    - _Requisitos: 14.1, 14.2, 14.4_

  - [ ] 28.2 Actualizar `Dockerfile` activo: migrar `ubuntu:25.04` → `ubuntu:24.04 LTS`
    - Cambiar la imagen base en todos los Dockerfiles activos (fuera de `_legacy/`) de `ubuntu:25.04` a `ubuntu:24.04`
    - Verificar que el build no se rompe con la nueva base
    - _Requisitos: 14.1_

- [ ] 29. Checkpoint Fase 5 — Verificar reproducibilidad
  - Ejecutar tests de `calibration_utils/manifest.py` y verificar que ningún manifest usa `:latest`
  - Asegurarse de que todos los tests pasen; preguntar al usuario si surgen dudas.

---

## Fase 6 — Automatización Completa

Completa el Control Plane con utilidades compartidas, state machine de ciclo de vida y CLI de operador.

- [ ] 30. Implementar `calibration_utils/cloudwatch.py`
  - Implementar `fetch_recent_events(log_group, minutes=15) -> list[LogEvent]`
  - Implementar `parse_iso_timestamp(ts: str) -> datetime`
  - Implementar `clean_message(msg: str) -> str`
  - Reemplazar las implementaciones duplicadas en `auto_scaling_tasks.py` y `getLog.py` por imports de este módulo
  - _Requisitos: 16.1_

  - [ ] 30.1 Crear `calibration_utils/cloudwatch.py` con las tres funciones
    - Implementar `fetch_recent_events` usando `cloudwatch_logs:FilterLogEvents` con filtro de tiempo
    - _Requisitos: 16.1_

  - [ ] 30.2 Refactorizar `auto_scaling_tasks.py` para usar `calibration_utils/cloudwatch.py`
    - Eliminar código duplicado de lectura de logs; importar desde `calibration_utils.cloudwatch`
    - _Requisitos: 16.1_

- [ ] 31. Implementar `calibration_utils/terraform.py`
  - Implementar `read_terraform_outputs(module_path) -> dict` reemplazando los múltiples parsers `hcl2` duplicados
  - Implementar `run_terraform_apply(module_path, vars) -> TerraformResult`
  - Implementar `run_terraform_destroy(module_path) -> TerraformResult`
  - Refactorizar `safe_destroy.py` y `auto_scaling_tasks.py` para usar este módulo
  - _Requisitos: 16.4_

  - [ ] 31.1 Crear `calibration_utils/terraform.py` con las tres funciones
    - Usar `subprocess` para invocar Terraform y parsear outputs con `python-hcl2`
    - _Requisitos: 16.4_

  - [ ] 31.2 Refactorizar `safe_destroy.py` y `activar_agentes_pest.py` para usar `calibration_utils/terraform.py`
    - Eliminar parsers `hcl2` duplicados; importar desde `calibration_utils.terraform`
    - _Requisitos: 16.4_

- [ ] 32. Implementar `ExecutionState` machine completa
  - Crear `calibration_utils/state.py` con el enum `ExecutionState` y las transiciones válidas
  - Implementar función `transition(current: ExecutionState, event: str) -> ExecutionState` que valida transiciones
  - Persistir el estado en S3 (`calibrations/{id}/state.json`) para que sobreviva a desconexiones del operador
  - Implementar que en estado FAILED solo se acepte la transición a CANCELLING
  - _Requisitos: 7.1, 7.2, 7.3, 7.4, 7.5_

  - [ ] 32.1 Crear `calibration_utils/state.py` con `ExecutionState` enum y función `transition`
    - Definir todos los estados del diseño y la tabla de transiciones válidas
    - _Requisitos: 7.1, 7.2, 7.3, 7.4_

  - [ ] 32.2 Implementar persistencia de `ExecutionState` en S3
    - Guardar y leer `calibrations/{id}/state.json` para durabilidad entre invocaciones Lambda
    - _Requisitos: 7.5_

  - [ ]* 32.3 Escribir tests unitarios para la state machine
    - Probar secuencia happy path, transiciones inválidas desde FAILED, persistencia en S3 con `moto`
    - _Requisitos: 7.2, 7.3, 7.4_

- [ ] 33. Implementar CLI Python: `calibrate start`, `status`, `stop`, `list`
  - Crear `calibrate/cli.py` con `click` como framework CLI
  - Implementar `calibrate start <config_path>`: validar config, generar `CalibrationId` antes de cualquier llamada AWS, imprimir ID + link al dashboard, iniciar workflow
  - Implementar `calibrate status <calibration_id>`: consultar `ExecutionState`, `QualityState` y último Phi desde CloudWatch
  - Implementar `calibrate stop <calibration_id> [--destroy]`: detener jobs Batch; con `--destroy`, invocar `safe_destroy`
  - Implementar `calibrate list [--last N]`: listar últimas N calibraciones desde manifests en S3
  - Usar cadena de credenciales AWS estándar (env vars, `~/.aws/credentials`, EC2 role) — nunca almacenar credenciales
  - _Requisitos: 15.1, 15.2, 15.3, 15.4, 15.5, 15.6, 15.7_

  - [ ] 33.1 Crear `calibrate/cli.py` con esqueleto `click` y `calibrate start`
    - Implementar `cmd_start` con validación local, generación de `CalibrationId` y print antes de AWS calls
    - _Requisitos: 15.1, 15.2, 15.3_

  - [ ] 33.2 Implementar `calibrate status` y `calibrate list`
    - Consultar `ExecutionState` y métricas CloudWatch para `status`; leer manifests S3 para `list`
    - _Requisitos: 15.4, 15.6_

  - [ ] 33.3 Implementar `calibrate stop [--destroy]`
    - Detener jobs Batch; con `--destroy` invocar `safe_destroy` con el `CalibrationId`
    - _Requisitos: 15.5_

  - [ ]* 33.4 Escribir tests unitarios para los comandos CLI con `pytest` y `moto`
    - Probar: config path inexistente → exit code no-cero sin llamadas AWS; `calibrate list` con manifests en S3
    - _Requisitos: 15.2, 15.3_

- [ ] 34. Agregar infraestructura de tests: `tests/` con pytest y hypothesis
  - Crear directorio `tests/` con `conftest.py`, fixtures de `moto` y configuración de `pytest`
  - Crear `pytest.ini` o sección `[tool.pytest.ini_options]` en `pyproject.toml`
  - Verificar que todos los tests de las fases anteriores corren con `pytest tests/ --run` sin errores
  - _Requisitos: 19.1, 19.2_

  - [ ] 34.1 Crear `tests/conftest.py` con fixtures comunes de `moto`
    - Definir fixtures `mock_s3`, `mock_batch`, `mock_cloudwatch`, `mock_logs` reutilizables
    - _Requisitos: 19.1_

  - [ ] 34.2 Crear archivos de tests agrupados por módulo
    - Crear `tests/test_config.py`, `tests/test_batch.py`, `tests/test_quality.py`, `tests/test_safe_destroy.py`, `tests/test_cli.py` con todos los tests escritos en las fases anteriores
    - _Requisitos: 19.2_

  - [ ] 34.3 Actualizar `README.md` raíz para indicar arquitectura activa (Batch gen2) y archivar ECS gen1
    - Documentar que AWS Batch EC2 es la arquitectura activa y que `_legacy/` contiene módulos archivados
    - _Requisitos: 17.2_

- [ ] 35. Checkpoint final — Todos los tests en verde
  - Ejecutar suite completa: `pytest tests/ -v`
  - Verificar que no hay referencias a ECS API fuera de `_legacy/`
  - Verificar que no hay `$RETRY_CODE` en el repositorio
  - Verificar que ningún manifest generado usa `:latest`
  - Asegurarse de que todos los tests pasen; preguntar al usuario si surgen dudas.

---

## Notes

- Tareas marcadas con `*` son opcionales y pueden omitirse para un MVP más rápido; representan tests de propiedad o tests de integración
- Las Fases 0 y 1 son obligatorias y constituyen el MVP completo
- Las Fases 2–6 son incrementales; cada fase agrega valor sin romper lo anterior
- El Compute Plane (AWS Batch EC2, entrypoints, imágenes Docker) no se reemplaza — solo se construye orquestación encima
- OQ-03 (formato de logs Phi) debe resolverse con `scripts/validate_phi_log_format.py` (tarea 19.1) antes de implementar la Fase 3
- Cada tarea de property test referencia explícitamente la Property del design.md que verifica
- Los checkpoints al final de cada fase no son de despliegue: son de ejecución de tests y revisión de invariantes en el código

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.3", "2.1", "5.1", "5.2", "6.1", "7.1"] },
    { "id": 1, "tasks": ["2.2", "3.1", "4.1", "4.2", "7.2"] },
    { "id": 2, "tasks": ["3.2", "9.1", "14.1", "14.2"] },
    { "id": 3, "tasks": ["9.2", "9.3", "9.4", "11.1", "11.2", "11.3", "13.1"] },
    { "id": 4, "tasks": ["9.5", "9.6", "9.7", "9.8", "10.1", "11.4", "12.1", "13.2"] },
    { "id": 5, "tasks": ["12.2", "12.3", "13.3", "16.1"] },
    { "id": 6, "tasks": ["12.4", "12.5", "12.6", "13.4", "13.5", "16.2", "17.1", "18.1"] },
    { "id": 7, "tasks": ["16.3", "17.2", "19.1"] },
    { "id": 8, "tasks": ["21.1", "22.1", "28.1"] },
    { "id": 9, "tasks": ["21.2", "21.3", "22.2", "22.3", "22.4", "28.2"] },
    { "id": 10, "tasks": ["21.4", "21.5", "23.1", "25.1"] },
    { "id": 11, "tasks": ["27.1", "30.1", "31.1", "32.1"] },
    { "id": 12, "tasks": ["27.2", "27.3", "27.4", "30.2", "31.2", "32.2"] },
    { "id": 13, "tasks": ["32.3", "33.1"] },
    { "id": 14, "tasks": ["33.2", "33.3", "34.1"] },
    { "id": 15, "tasks": ["33.4", "34.2", "34.3"] }
  ]
}
```
