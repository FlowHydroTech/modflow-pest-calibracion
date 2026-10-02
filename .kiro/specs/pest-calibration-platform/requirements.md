# Requirements Document

## Introduction

El **PEST Calibration Platform** es la evolución del sistema actual de calibración de modelos MODFLOW/PEST sobre AWS. El sistema actual requiere ~8 pasos manuales por calibración, depende de la laptop del operador para el autoscaler, no registra trazabilidad científica y tiene vulnerabilidades de seguridad activas (bug de retry, state Terraform local, IAM con wildcard S3, credenciales hardcodeadas). Este documento especifica los requisitos derivados del diseño aprobado, organizados por las seis fases del roadmap.

El **MVP** comprende las Fases 0 y 1: corregir los riesgos activos y eliminar la dependencia de la conexión continua del operador sin agregar servicios innecesarios. Las fases posteriores agregan observabilidad, quality monitoring y automatización completa de forma incremental.

**Hallazgos de auditoría que originan estos requisitos:** F-01 (sin backend Terraform remoto), F-02 (bug $RETRY_CODE), F-03 (autoscaler local), F-04/F-05 (datos sensibles en código), F-07 (autoscaler hardcodeado), F-08 (S3 wildcard en IAM), F-10 (no hay verificación de backup antes de destroy), F-16 (sin métricas de Phi).

**Preguntas abiertas condicionantes:**
- **OQ-03:** El formato exacto de las líneas de Phi en los logs del master debe validarse con logs reales antes de implementar los requisitos de extracción (Fases 2–3).
- **OQ-07:** La duración típica de calibraciones debe validarse antes de fijar el valor por defecto de `ttl_hours`.
- **OQ-08:** El valor de `stagnation_window_iterations` debe calibrarse con histórico de calibraciones reales antes de activar alertas STAGNATED en producción.

---

## Glossary

- **PEST**: Software de calibración paramétrica (Parameter ESTimation). Minimiza la función objetivo Phi ajustando parámetros del modelo numérico.
- **PEST_HP**: Variante de PEST que usa paralelización vía TCP/IP entre un proceso master y múltiples agentes.
- **Master**: Proceso `pest_hp` que coordina la calibración, ejecuta el algoritmo de Levenberg-Marquardt y distribuye corridas del modelo a los agentes.
- **Agent / Agente**: Proceso `agent_hp` que recibe instrucciones del master, ejecuta el modelo numérico (MODFLOW), y devuelve resultados.
- **Phi (Φ)**: Función objetivo de PEST. Suma ponderada de residuales al cuadrado entre observaciones de campo y valores simulados. PEST minimiza Phi iterativamente.
- **CalibrationId**: Identificador único de una calibración con formato `CAL-YYYYMMDD-NNN`.
- **Calibration_Platform**: El sistema en su conjunto, incluyendo Control Plane y Compute Plane.
- **Control_Plane**: Capa de orquestación, monitoreo y ciclo de vida de infraestructura (nuevos componentes).
- **Compute_Plane**: Capa de ejecución real (AWS Batch EC2 con PEST y MODFLOW — sin cambios respecto al sistema actual).
- **Lambda_Autoscaler**: Función Lambda que reemplaza el loop `while True` de `auto_scaling_tasks.py`.
- **Lambda_ExtractPhi**: Función Lambda que extrae el Phi de los logs del master y lo publica como Custom Metric.
- **Safe_Destroy**: Script Python que verifica la existencia de resultados en S3 antes de ejecutar `terraform destroy`.
- **CLI**: Interfaz de línea de comandos (`calibrate`) que sirve como punto de entrada único para los operadores.
- **CalibrationConfig**: Estructura de datos que representa la configuración de una calibración, cargada desde `calibration.yaml`.
- **CalibrationManifest**: Registro inmutable generado al finalizar una calibración, con toda la información necesaria para reproducirla.
- **ExecutionState**: Estado del ciclo de vida de ejecución de una calibración (ej. RUNNING, COMPLETED, FAILED).
- **QualityState**: Estado del progreso científico de una calibración basado en la evolución de Phi (ej. IMPROVING, STAGNATED, CONVERGED).
- **Agent_Entrypoint**: Script `entrypoint_agent.sh` que lanza el proceso agente dentro del contenedor Docker.
- **Terraform_Backend**: Configuración de almacenamiento remoto del state de Terraform (S3 + DynamoDB lock).
- **Calibration_Utils**: Biblioteca Python compartida que elimina la duplicación de lógica entre scripts.
- **Wine**: Capa de compatibilidad que permite ejecutar `pest_hp.exe` (binario Windows) en contenedores Linux de AWS Batch.

---

## Requirements

---

### Requirement 1: Corrección del Bug de Retry en el Agente (Fase 0 — F-02)

**User Story:** Como operador de calibración, quiero que los agentes reintenten automáticamente cuando Wine falla con el error conocido `c0000018`, para que las calibraciones no se interrumpan innecesariamente por un error intermitente de Wine en AWS.

#### Acceptance Criteria

1. THE Agent_Entrypoint SHALL capture the exit code of the agent process into the variable `$EXIT_CODE` immediately after the process terminates.
2. WHEN the agent process exits with `$EXIT_CODE` equal to 80, THE Agent_Entrypoint SHALL retry the agent execution at least once before reporting a failure to AWS Batch.
3. WHEN the Wine runtime emits the error string `c0000018` to stderr, THE Agent_Entrypoint SHALL treat that condition as equivalent to exit code 80 and trigger the retry mechanism.
4. THE Agent_Entrypoint SHALL NOT use the variable name `$RETRY_CODE` anywhere in the retry condition logic, as that variable is never defined.
5. THE Agent_Entrypoint SHALL begin with the `#!/bin/bash` shebang line as the first line of the file.
6. THE Agent_Entrypoint SHALL include `set -e` or explicit exit code checks so that errors in non-retry commands cause the script to exit with a non-zero code.

---

### Requirement 2: Terraform Backend Remoto (Fase 0 — F-01)

**User Story:** Como miembro del equipo de infraestructura, quiero que el estado de Terraform se almacene en S3 con locking por DynamoDB, para que ningún miembro del equipo pierda control sobre la infraestructura si se pierde un archivo local, y para que sea posible ejecutar `terraform destroy` desde cualquier máquina.

#### Acceptance Criteria

1. THE Terraform_Backend SHALL be configured in all active Terraform modules (talabre-linux and any future calibration module) using an S3 bucket with versioning enabled.
2. THE Terraform_Backend SHALL use a DynamoDB table for state locking to prevent concurrent state writes.
3. THE Terraform_Backend S3 bucket SHALL have server-side encryption enabled (`encrypt = true`).
4. THE Terraform_Backend configuration SHALL use variables for the bucket name, key path, and DynamoDB table name, so they can be overridden per environment without modifying the code.
5. THE Calibration_Platform SHALL NOT store any `terraform.tfstate` file in the local filesystem of the operator's machine after applying the backend configuration.
6. IF the DynamoDB lock is held by another process, THEN THE Terraform CLI SHALL return an error indicating the state is locked, preventing simultaneous destructive operations.

---

### Requirement 3: IAM de Mínimo Privilegio para Tasks de Batch (Fase 0 — F-08)

**User Story:** Como responsable de seguridad, quiero que los contenedores de AWS Batch solo puedan acceder al bucket S3 específico de cada calibración, para que un contenedor comprometido no pueda leer ni modificar buckets de otras calibraciones o proyectos.

#### Acceptance Criteria

1. THE IAM Task Role for Batch jobs SHALL restrict S3 actions to the specific bucket ARN configured for the calibration, using the pattern `arn:aws:s3:::{bucket_name}` and `arn:aws:s3:::{bucket_name}/*`.
2. THE IAM Task Role SHALL NOT use wildcard resource (`"*"` or `"arn:aws:s3:::*"`) for any S3 action.
3. THE Lambda_Autoscaler IAM Role SHALL only include the following permissions: `batch:ListJobs`, `batch:SubmitJob`, `batch:TerminateJob`, `cloudwatch:PutMetricData`, and `logs:GetLogEvents`.
4. THE Lambda_ExtractPhi IAM Role SHALL only include the following permissions: `logs:FilterLogEvents`, `logs:GetLogEvents`, and `cloudwatch:PutMetricData`.
5. WHERE the ECS generation 1 (legacy) used a KMS Decrypt permission with `Resource = "*"`, THE Terraform_Backend configuration for that resource SHALL either restrict the Resource to a specific KMS key ARN or remove the KMS Decrypt permission if encryption is not in use.

---

### Requirement 4: Eliminación de Datos Sensibles del Código Versionado (Fase 0 — F-04, F-05)

**User Story:** Como responsable de seguridad, quiero que los IDs de cuenta AWS, IDs de VPC y IDs de subnet no aparezcan como valores hardcodeados en archivos versionados en git, para que la topología de red interna no sea visible para cualquier persona con acceso al repositorio.

#### Acceptance Criteria

1. THE Terraform Modules SHALL NOT include hardcoded AWS account IDs (12-digit numeric strings) as default values for any Terraform variable.
2. THE Terraform Modules SHALL NOT include hardcoded VPC IDs (matching `vpc-*`), subnet IDs (matching `subnet-*`), or route table IDs (matching `rtb-*`) as default values in `variables.tf`.
3. THE AWS operational scripts (PowerShell, Python, Bash) SHALL derive the AWS account ID dynamically by calling the AWS STS `GetCallerIdentity` API rather than using a hardcoded numeric string.
4. THE Calibration_Platform SHALL provide a `terraform.tfvars.example` file that documents all required variables without providing real infrastructure values, guiding operators on how to create their own `terraform.tfvars` file (excluded from git via `.gitignore`).

---

### Requirement 5: Identificación Única de Calibraciones (Fases 1–6)

**User Story:** Como científico que ejecuta múltiples calibraciones, quiero que cada calibración tenga un identificador único y estructurado, para poder referenciar calibraciones específicas en logs, alertas, costos de AWS y resultados almacenados en S3 sin ambigüedad.

#### Acceptance Criteria

1. THE Calibration_Platform SHALL generate a `CalibrationId` for every calibration, with the format `CAL-YYYYMMDD-NNN` where `YYYYMMDD` is the UTC date of creation and `NNN` is a zero-padded sequential counter (e.g., `CAL-20261015-001`).
2. WHEN two calibrations are started on the same UTC date, THE Calibration_Platform SHALL assign different sequential suffixes, ensuring both CalibrationIds are unique.
3. THE Calibration_Platform SHALL reject any string as a CalibrationId that does not match the regular expression `^CAL-\d{8}-\d{3}$`.
4. THE Calibration_Platform SHALL use the CalibrationId as a tag on all AWS resources created for that calibration (Batch jobs, CloudWatch log groups, S3 prefixes).
5. THE CLI SHALL display the CalibrationId immediately after initiating a calibration, before any AWS resource creation begins.

---

### Requirement 6: Contrato de Configuración — calibration.yaml (Fases 1–6)

**User Story:** Como operador, quiero que la configuración completa de una calibración esté definida en un solo archivo YAML validado antes de ejecutar cualquier operación en AWS, para evitar que calibraciones con configuraciones incompletas o incorrectas consuman recursos.

#### Acceptance Criteria

1. THE Config_Validator SHALL validate that the `pst_file` field in `calibration.yaml` references a file that exists within the specified model context path before initiating any AWS operation.
2. THE Config_Validator SHALL reject configurations where `initial_agents` is greater than `max_agents`.
3. THE Config_Validator SHALL reject configurations where `port` is outside the range 1024–65535.
4. THE Config_Validator SHALL reject configurations where `ttl_hours` is less than or equal to zero.
5. THE Config_Validator SHALL reject configurations where `s3_bucket`, `terraform_module`, or `ecr_image` fields are empty or missing.
6. WHEN validation fails, THE Config_Validator SHALL return a `ValidationResult` that includes a descriptive message identifying each failed field and the reason for rejection.
7. THE Config_Validator SHALL complete all validation checks locally (without making any AWS API calls) before returning a result.
8. THE Calibration_Platform SHALL provide a documented `calibration.yaml` schema with all fields, their types, default values, and constraints.

---

### Requirement 7: State Machine de Ejecución — ExecutionState (Fases 1–6)

**User Story:** Como operador, quiero que el ciclo de vida de cada calibración esté representado por estados explícitos y bien definidos, para poder monitorear el progreso y detectar en qué fase ocurrió un fallo.

#### Acceptance Criteria

1. THE Calibration_Platform SHALL represent the execution lifecycle of every calibration using the `ExecutionState` enum with the following values: `CREATED`, `VALIDATING`, `BUILDING`, `PROVISIONING`, `STARTING`, `RUNNING`, `FINALIZING`, `COMPLETED`, `FAILED`, `CANCELLING`, `CANCELLED`, `CLEANING`, `CLEANED`.
2. THE Calibration_Platform SHALL follow the normal happy-path state sequence: `CREATED → VALIDATING → BUILDING → PROVISIONING → STARTING → RUNNING → FINALIZING → COMPLETED`.
3. WHEN any phase fails, THE Calibration_Platform SHALL transition the calibration to `FAILED` state and SHALL NOT attempt to continue to the next phase automatically.
4. WHEN a calibration is in `FAILED` state, THE Calibration_Platform SHALL accept the `cmd_stop` command to transition to `CANCELLING → CANCELLED` but SHALL NOT accept any other lifecycle-advancing transition.
5. THE Calibration_Platform SHALL store the current `ExecutionState` in a durable location (S3 manifest or CloudWatch metric) so it persists across Lambda invocations and operator disconnections.

---

### Requirement 8: Lambda Autoscaler Independiente del Operador (Fase 1 — F-03, F-07)

**User Story:** Como operador, quiero que el autoscaler de agentes PEST corra en AWS sin depender de que mi laptop esté conectada, para que una calibración no se detenga ni genere costos innecesarios si mi conexión se interrumpe.

#### Acceptance Criteria

1. THE Lambda_Autoscaler SHALL be invoked automatically by an AWS EventBridge scheduled rule at a configurable interval (default: every 10 minutes), independent of any operator machine or process.
2. THE Lambda_Autoscaler SHALL determine the number of agents needed by reading the master's CloudWatch log group for patterns `"Running model X times"` and `"Calculating Jacobian matrix: running model X times"`, extracting the value of `X`.
3. THE Lambda_Autoscaler SHALL use exclusively the AWS Batch API (`batch:ListJobs`, `batch:SubmitJob`, `batch:TerminateJob`) for all agent management operations, and SHALL NOT call any ECS API (`ecs:ListTasks`, `ecs:StopTask`, `ecs:RunTask`).
4. THE Lambda_Autoscaler SHALL NOT launch more agents than `config.max_agents` minus the count of currently running agents, even if the number of models requested by PEST exceeds that limit.
5. THE Lambda_Autoscaler SHALL terminate agents that have emitted `"Model run complete"` or `"MODEL TIMEOUT"` in their CloudWatch log stream using `batch:TerminateJob`.
6. WHEN the master log group has received no log events in the last 30 minutes, THE Lambda_Autoscaler SHALL publish a `MasterHealth` metric with value `0` to the `PEST/Calibration` CloudWatch namespace and SHALL NOT launch any new agents.
7. THE Lambda_Autoscaler SHALL accept the `calibration_id`, `job_queue_agents`, `log_group_master`, `log_group_agents`, `max_agents`, and `master_ip` as configuration inputs, so it can serve any calibration project without modifying its source code.
8. THE Lambda_Autoscaler SHALL publish an `ActiveWorkers` metric to CloudWatch after each cycle reflecting the count of RUNNING Batch jobs in the agent queue.

---

### Requirement 9: Safe Destroy con Verificación de Resultados (Fase 1 — F-10)

**User Story:** Como operador, quiero que el script de destrucción de infraestructura verifique que los resultados de calibración están guardados en S3 antes de ejecutar `terraform destroy`, para no perder resultados si olvido ejecutar el backup manualmente.

#### Acceptance Criteria

1. WHEN `safe_destroy` is called with `force=False` and the S3 prefix `calibrations/{calibration_id}/modelo/` contains no objects, THE Safe_Destroy SHALL return `DestroyResult(success=False, reason="NO_RESULTS_IN_S3")` without calling `terraform destroy` and without modifying any AWS resource.
2. WHEN `safe_destroy` is called and `s3_results_exist()` returns `True`, THE Safe_Destroy SHALL export CloudWatch Logs from both the master and agent log groups to S3 at the prefix `calibrations/{calibration_id}/logs/` before invoking `terraform destroy`.
3. WHEN `safe_destroy` is called and `s3_results_exist()` returns `True`, THE Safe_Destroy SHALL generate and save a `CalibrationManifest` to S3 before invoking `terraform destroy`.
4. THE Safe_Destroy SHALL stop all active Batch jobs in the master and agent queues before invoking `terraform destroy`.
5. IF `terraform destroy` fails, THEN THE Safe_Destroy SHALL send a CRITICAL notification via SNS that includes the list of AWS resources that require manual cleanup, identified by the `CalibrationId` tag.
6. IF `terraform destroy` fails, THEN THE Safe_Destroy SHALL return `DestroyResult(success=False, reason="TERRAFORM_DESTROY_FAILED")` and SHALL NOT delete any S3 data or CloudWatch logs.
7. WHEN `safe_destroy` completes successfully, THE Safe_Destroy SHALL verify that no AWS resources tagged with `CalibrationId={calibration_id}` remain in ACTIVE state in Batch, and SHALL include any orphaned resources in the `DestroyResult.orphans` list.
8. WHERE `force=True` is explicitly passed, THE Safe_Destroy SHALL proceed with `terraform destroy` even if `s3_results_exist()` returns `False`, after logging a warning that results may be lost.

---

### Requirement 10: Observabilidad — Logs, Métricas y Alarmas (Fase 2)

**User Story:** Como operador, quiero poder ver el estado de una calibración en tiempo real en CloudWatch sin necesidad de conectarme manualmente a los logs individuales, para detectar fallos y actuar antes de que el problema genere costos innecesarios o pérdida de resultados.

#### Acceptance Criteria

1. THE Calibration_Platform SHALL publish all calibration metrics to the `PEST/Calibration` CloudWatch namespace, using `CalibrationId` as a mandatory dimension on every metric.
2. THE Calibration_Platform SHALL publish the following metrics during calibration execution: `MasterHealth` (1=healthy, 0=failed), `ActiveWorkers` (count of RUNNING agent jobs), `CalibrationRuntime` (seconds since calibration start).
3. THE Calibration_Platform SHALL configure CloudWatch Log retention of at least 90 days for master job log groups.
4. THE Calibration_Platform SHALL configure a CloudWatch Alarm on `MasterHealth` that triggers when the value equals 0 for two consecutive evaluation periods of 5 minutes.
5. WHEN a CloudWatch Alarm transitions to the ALARM state, THE Calibration_Platform SHALL send a notification to an SNS topic configured with the operator's email address.
6. THE Calibration_Platform SHALL provision a CloudWatch Alarm that triggers when a calibration's AWS resources have been active for longer than `ttl_hours` (default value conditioned on OQ-07), sending a WARNING notification via SNS.
7. THE Calibration_Platform SHALL enable AWS Container Insights on all Batch Compute Environments to provide CPU and memory utilization metrics without additional instrumentation.

---

### Requirement 11: Extracción de Métricas de Phi y Calidad de Calibración (Fases 2–3 — condicionado OQ-03)

> **Nota:** La implementación completa de este requisito está condicionada a la resolución de **OQ-03**: el formato exacto de las líneas de Phi en el stdout de `pest_hp` debe confirmarse con un log real de master antes de implementar los Metric Filters y la Lambda_ExtractPhi. Los criterios 1–3 pueden implementarse en Fase 2 una vez resuelto OQ-03. Los criterios 4–8 corresponden a Fase 3.

**User Story:** Como científico del equipo, quiero poder ver la evolución del Phi de cada iteración PEST en un dashboard de CloudWatch, para saber si la calibración está convergiendo, mejorando lentamente o estancada sin necesidad de conectarme manualmente a los logs.

#### Acceptance Criteria

1. WHEN the master log group receives a log event containing a Phi value (format confirmed via OQ-03), THE Lambda_ExtractPhi SHALL parse that value and publish it as the `PhiCurrent` metric to the `PEST/Calibration` namespace with the `CalibrationId` dimension.
2. THE Lambda_ExtractPhi SHALL maintain and publish a `PhiBest` metric that represents the lowest Phi value observed during the current calibration run, updating it each time a new Phi reading is lower than the current best.
3. THE Lambda_ExtractPhi SHALL publish a `CurrentIteration` metric representing the PEST iteration number extracted from the log, incrementing it each time a new iteration is detected.
4. THE Quality_Engine SHALL classify each calibration into one of four `QualityState` values: `IMPROVING` (sliding mean relative improvement > 1%), `SLOW_IMPROVEMENT` (0.1%–1%), `STAGNATED` (< 0.1% over the last `stagnation_window_iterations` iterations), or `CONVERGED` (explicit PEST message detected).
5. THE Quality_Engine SHALL transition a calibration to `QualityState.CONVERGED` if and only if the master log contains at least one of the following keywords: `RELPARCHG`, `PHIREDSTP`, `"Optimization complete"`, or `"optimization complete"`. THE Quality_Engine SHALL NOT infer CONVERGED from numerical Phi thresholds alone.
6. WHEN `QualityState.STAGNATED` is detected, THE Quality_Engine SHALL publish a WARNING notification via SNS and SHALL NOT terminate any Batch jobs or modify the `ExecutionState`.
7. THE Quality_Engine SHALL compute the sliding mean relative improvement using only the last `stagnation_window_iterations` Phi readings (default value conditioned on OQ-08), where relative improvement for iteration k is defined as `(Phi_{k-1} - Phi_k) / Phi_{k-1}` when `Phi_{k-1} > 0`.
8. WHEN `phi_history` contains fewer than 2 elements, THE Quality_Engine SHALL return `QualityState.UNKNOWN` without attempting to compute improvement.

---

### Requirement 12: Parser y Pretty-Printer de CalibrationConfig (Fases 1–6)

> **Nota sobre parsers:** Conforme a la guía de calidad de requisitos, los parsers y serializadores se especifican explícitamente junto con su requisito de round-trip.

**User Story:** Como operador, quiero poder escribir la configuración de una calibración en un archivo YAML y cargarla en el sistema con validación completa, y que el sistema pueda serializar de vuelta la configuración validada a YAML para auditoría, para asegurar que lo que se ejecuta es exactamente lo que se configuró.

#### Acceptance Criteria

1. WHEN a valid `calibration.yaml` file is provided, THE Config_Parser SHALL parse it into a `CalibrationConfig` object with all fields correctly populated according to their types and default values.
2. WHEN an invalid `calibration.yaml` file is provided (missing required fields, incorrect types, or constraint violations), THE Config_Parser SHALL return a descriptive error identifying the specific field and violation without raising an unhandled exception.
3. THE Config_Serializer SHALL serialize any `CalibrationConfig` object back into a valid YAML string that, when parsed again by the Config_Parser, produces an equivalent `CalibrationConfig` object (round-trip property).
4. FOR ALL valid `CalibrationConfig` objects, parsing then serializing then parsing SHALL produce a `CalibrationConfig` object equivalent to the original (round-trip equivalence).

---

### Requirement 13: Calibration Manifest — Reproducibilidad (Fase 5)

**User Story:** Como científico, quiero que al finalizar cada calibración se genere un registro inmutable con todos los detalles necesarios para reproducirla exactamente (versión de código, digest de imagen Docker, versión de PEST, parámetros usados), para poder auditar qué binario ejecutó qué calibración y reproducir resultados en el futuro.

#### Acceptance Criteria

1. THE Calibration_Platform SHALL generate a `CalibrationManifest` for every calibration that reaches `ExecutionState.COMPLETED`, `FAILED`, or `CANCELLED`.
2. THE CalibrationManifest SHALL include all of the following reproducibility fields with non-empty values: `git_commit` (full SHA), `docker_image_digest` (SHA256 format, not `:latest` tag), `pest_version` (extracted from master log), `terraform_version`, and `configuration_hash` (SHA256 of the `calibration.yaml` content).
3. THE CalibrationManifest SHALL NOT use the `:latest` tag as the value for `docker_image_digest`. THE docker_image_digest field SHALL contain the immutable SHA256 digest of the image (e.g., `sha256:abc123...`).
4. THE Calibration_Platform SHALL save the `CalibrationManifest` as a JSON file to the S3 path `s3://{bucket}/calibrations/{calibration_id}/manifest.json`.
5. THE Calibration_Platform SHALL include the following scientific metrics in the manifest when available: `phi_initial`, `phi_final`, `phi_reduction_pct`, `total_iterations`, and `total_model_runs`.
6. WHEN `phi_initial` and `phi_final` are both available, THE CalibrationManifest SHALL compute `phi_reduction_pct` as `(phi_initial - phi_final) / phi_initial * 100`, ensuring the computed value is consistent with the stored Phi values.

---

### Requirement 14: Build de Imagen Docker con Tag de Commit SHA (Fase 5 — F-03 reproducibilidad)

**User Story:** Como científico, quiero que las imágenes Docker usadas en calibraciones se identifiquen con el commit Git que las generó, para poder determinar exactamente qué versión del código ejecutó una calibración específica.

#### Acceptance Criteria

1. WHEN a Docker image is built for a calibration, THE Build_System SHALL tag the image with the full Git commit SHA (format: `{ecr_repo}:{git_sha}`) in addition to any other tags.
2. THE Build_System SHALL NOT publish a Docker image to ECR for calibration use using only the `:latest` tag — every published image SHALL include a commit-SHA-based tag.
3. THE CalibrationConfig SHALL accept an `ecr_image` field that references the SHA-tagged image (e.g., `{account}.dkr.ecr.{region}.amazonaws.com/{repo}:{git_sha[:8]}`), which is stored in the `CalibrationManifest.docker_image_digest` field.
4. THE Build_System SHALL verify that the Git working directory has no uncommitted changes before building the image, and SHALL warn the operator if uncommitted changes are detected, since the resulting image would not be reproducible from the recorded commit SHA.

---

### Requirement 15: CLI Python — Interfaz de Operador (Fase 6)

**User Story:** Como operador, quiero poder iniciar, monitorear y detener calibraciones desde un único comando de línea de comandos (`calibrate`), para no tener que recordar ni ejecutar manualmente los ~8 pasos que requiere el flujo actual.

#### Acceptance Criteria

1. THE CLI SHALL provide a `calibrate start <config_path>` command that: (a) validates the configuration, (b) generates a CalibrationId, (c) initiates the calibration workflow, and (d) prints the CalibrationId and a link to the CloudWatch Dashboard.
2. WHEN the CLI receives a `<config_path>` that does not exist on the filesystem, THE CLI SHALL exit with a non-zero exit code and print a descriptive error message, without making any AWS API calls.
3. THE CLI SHALL generate and display the CalibrationId before initiating any AWS API call, so the operator has the reference even if the AWS operation fails immediately after.
4. THE CLI SHALL provide a `calibrate status <calibration_id>` command that queries the current `ExecutionState` and, when available, the current `QualityState` and latest Phi value from CloudWatch.
5. THE CLI SHALL provide a `calibrate stop <calibration_id>` command that stops the calibration's Batch jobs and, with the `--destroy` flag, invokes `safe_destroy` with the appropriate `CalibrationId`.
6. THE CLI SHALL provide a `calibrate list [--last N]` command that retrieves and displays the last N calibrations (default 10) by reading the CalibrationManifest files from S3.
7. THE CLI SHALL use the standard AWS credential chain (environment variables, `~/.aws/credentials`, EC2 instance role) and SHALL NOT store, read, or log AWS credentials or tokens directly.

---

### Requirement 16: Módulo Python Compartido — Calibration Utils (Fase 6 — F-21)

**User Story:** Como desarrollador del equipo, quiero que la lógica común entre los scripts de orquestación esté en un módulo Python compartido (`calibration_utils/`), para eliminar la duplicación de código y garantizar que todos los scripts usan la misma implementación para operaciones críticas como lectura de logs y gestión de jobs Batch.

#### Acceptance Criteria

1. THE Calibration_Utils module SHALL provide a `cloudwatch` submodule with functions `fetch_recent_events(log_group, minutes)`, `parse_iso_timestamp(ts)`, and `clean_message(msg)` that replace the duplicated implementations in `auto_scaling_tasks.py` and `getLog.py`.
2. THE Calibration_Utils module SHALL provide a `batch` submodule with functions `submit_master_job`, `submit_agent_jobs`, `wait_for_master_ip`, `get_running_jobs`, and `terminate_job` that replace the duplicated Batch API calls across existing scripts.
3. THE Calibration_Utils module SHALL provide a `config` submodule with `load_calibration_config`, `validate_calibration_config`, and `generate_calibration_id` functions, which are used by all components (CLI, Lambda_Autoscaler, Safe_Destroy) rather than each implementing their own version.
4. THE Calibration_Utils module SHALL provide a `terraform` submodule with `read_terraform_outputs`, `run_terraform_apply`, and `run_terraform_destroy` functions that replace the multiple duplicated `hcl2` parsers present in `auto_scaling_tasks.py` and `activar_agentes_pest.py`.
5. WHEN `wait_for_master_ip` is called with a `timeout_s` parameter and the master job does not reach RUNNING state within that time, THE batch submodule SHALL return `None` rather than blocking indefinitely or raising an unhandled exception.

---

### Requirement 17: Deprecación de la Arquitectura ECS Fargate Legacy (Fase 1 — F-06)

**User Story:** Como miembro del equipo de operaciones, quiero que el código y los scripts de la arquitectura ECS Fargate (generación 1) estén claramente separados del código activo de AWS Batch (generación 2), para eliminar la confusión sobre qué módulo de Terraform aplicar y qué scripts usar en producción.

#### Acceptance Criteria

1. THE Calibration_Platform repository SHALL move all ECS Fargate generation-1 Terraform modules (`IaC_terraform/Arquitectura_regional/`, `IaC_terraform/ModeloPest/unica_region_EC2/`, `IaC_terraform/ModeloPest/Multiple_Region/`) to a `_legacy/` subdirectory clearly marked as deprecated.
2. THE Calibration_Platform repository SHALL update the root `README.md` to explicitly state that AWS Batch EC2 is the active and production architecture, and that ECS Fargate modules in `_legacy/` are archived and not maintained.
3. THE `null_resource` blocks with `local-exec` PowerShell interpreters in the legacy Terraform modules SHALL be removed from all non-legacy Terraform configurations, as the agent launch logic is handled by `launch_master_agents.py` in the Batch generation.
4. THE Python scripts that call the ECS API (`ecs:RunTask`, `ecs:StopTask`, `ecs:ListTasks`) in `activar_agentes_pest.py` SHALL be moved to the `_legacy/` directory or clearly marked as deprecated, as all agent management in generation 2 uses the AWS Batch API exclusively.

---

### Requirement 18: Dependencias Python Consolidadas (Fase 0 — F-12)

**User Story:** Como desarrollador, quiero que las dependencias Python del proyecto estén consolidadas en un único `pyproject.toml` con versiones pinadas, para que todos los miembros del equipo trabajen con las mismas versiones de librerías y no haya ambigüedad sobre qué instalar.

#### Acceptance Criteria

1. THE Calibration_Platform SHALL maintain a single `pyproject.toml` as the authoritative source of Python dependencies, with all runtime dependencies pinned to specific version ranges (e.g., `boto3>=1.34.0,<2.0`).
2. THE `pyproject.toml` SHALL include `boto3` as an explicit runtime dependency, as it is currently absent from `pyproject.toml` despite being required by all operational scripts.
3. THE Calibration_Platform SHALL remove or clearly mark as redundant any `requirements.txt` files that duplicate or conflict with the dependencies in `pyproject.toml`.
4. THE `pyproject.toml` SHALL include a `[project.optional-dependencies]` section for test dependencies (`pytest`, `pytest-mock`, `hypothesis`, `moto`) so that test tools are not installed in production environments.

---

### Requirement 19: Tests Unitarios y de Propiedades para Scripts Críticos (Fase 6 — F-11)

**User Story:** Como desarrollador, quiero que los scripts Python críticos de orquestación tengan tests unitarios y de propiedades automatizados, para detectar bugs como el F-02 antes de que lleguen a producción y tengan impacto en calibraciones activas.

#### Acceptance Criteria

1. THE Calibration_Platform SHALL include a `tests/` directory with a `pytest` configuration as the test framework.
2. THE tests SHALL cover at minimum: `classify_calibration_quality`, `safe_destroy`, `generate_calibration_id`, `validate_calibration_config`, and the autoscaler's agent count logic.
3. THE tests for `classify_calibration_quality` SHALL use property-based testing (Hypothesis framework) to verify that `QualityState.CONVERGED` is never returned when `convergence_msg_detected=False`, across all possible `phi_history` inputs.
4. THE tests for `safe_destroy` SHALL use mock AWS clients (via `moto`) to verify that `terraform destroy` is never invoked when `s3_results_exist()` returns `False` and `force=False`.
5. THE tests for `validate_calibration_config` SHALL use property-based testing (Hypothesis) to verify that any configuration with `initial_agents > max_agents` always returns `ValidationResult(valid=False)`.
6. THE tests for `generate_calibration_id` SHALL use property-based testing to verify that all generated IDs match `^CAL-\d{8}-\d{3}$` and that multiple IDs generated on the same UTC date have unique sequential suffixes.

---

## Requirement Traceability Matrix

| Requirement | Fase | Finding ref. | Design component | Priority |
|-------------|------|--------------|-----------------|----------|
| R1: Bug retry $EXIT_CODE | 0 | F-02 | Agent_Entrypoint fix | 🔴 CRÍTICO |
| R2: Terraform Backend Remoto | 0 | F-01 | Fix F-01 / backend.tf | 🔴 CRÍTICO |
| R3: IAM Mínimo Privilegio | 0 | F-08 | Fix F-08 / IAM policy | 🟠 ALTO |
| R4: Sin datos sensibles en código | 0 | F-04, F-05 | Security section | 🟠 ALTO |
| R5: CalibrationId único | 1–6 | — | CalibrationConfig, CLI | 🟠 ALTO |
| R6: calibration.yaml contrato | 1–6 | — | Config_Validator, CalibrationConfig | 🟠 ALTO |
| R7: ExecutionState machine | 1–6 | — | ExecutionState enum | 🟠 ALTO |
| R8: Lambda Autoscaler | 1 | F-03, F-07 | Lambda Autoscaler component | 🔴 CRÍTICO |
| R9: Safe Destroy | 1 | F-10 | safe_destroy.py component | 🟠 ALTO |
| R10: Observabilidad métricas/alarmas | 2 | F-16 | CloudWatch metrics table | 🟠 ALTO |
| R11: Extracción Phi y QualityState | 2–3 | F-16 | Lambda_ExtractPhi, Quality classifier | 🟡 MEDIO (OQ-03) |
| R12: Config Parser/Serializer | 1–6 | — | CalibrationConfig / Config_Parser | 🟠 ALTO |
| R13: Calibration Manifest | 5 | — | CalibrationManifest data model | 🟡 MEDIO |
| R14: Docker image SHA tagging | 5 | — | Build_System / reproducibilidad | 🟡 MEDIO |
| R15: CLI Python | 6 | — | CLI component (cmd_start, status, stop, list) | 🟡 MEDIO |
| R16: Calibration Utils módulo | 6 | F-21 | calibration_utils/ component | 🟡 MEDIO |
| R17: Deprecar ECS legacy | 1 | F-06 | Architecture separation | 🟠 ALTO |
| R18: pyproject.toml consolidado | 0 | F-12 | Dependencies section | 🟡 MEDIO |
| R19: Tests unitarios y propiedades | 6 | F-11 | Testing Strategy section | 🟡 MEDIO |
