# Findings

> Todos los hallazgos identificados durante la auditoría, ordenados por severidad.  
> Cada hallazgo incluye evidencia concreta desde el repositorio.

---

## Resumen por Severidad

| Severidad | Cantidad | IDs |
|-----------|----------|-----|
| 🔴 CRÍTICO | 3 | F-01, F-02, F-03 |
| 🟠 ALTO | 7 | F-04 a F-10 |
| 🟡 MEDIO | 9 | F-11 a F-19 |
| 🔵 BAJO | 3 | F-20 a F-22 |
| **Total** | **22** | |

---

## 🔴 CRÍTICO

---

### F-01 — Sin backend remoto Terraform / State local

| Atributo | Detalle |
|----------|---------|
| **Categoría** | IaC / Governance |
| **Severidad** | 🔴 CRÍTICO |
| **Evidencia** | `IaC_terraform/Arquitectura_regional/provider.tf`, `IaC_terraform/ModeloPest/talabre-linux/us-east-1/provider.tf` — ninguno tiene bloque `backend {}` |
| **Impacto** | Si se pierde el `terraform.tfstate` local, la infraestructura real no puede ser gestionada por Terraform. `terraform destroy` fallará. Recursos quedarán huérfanos generando costos indefinidamente. Imposible trabajo en equipo simultáneo. |
| **Recomendación** | Configurar backend S3 + DynamoDB locking en todos los módulos activos. Habilitar versionado en el bucket de state. |
| **Esfuerzo** | S |

```hcl
# Lo que falta en todos los provider.tf activos:
terraform {
  backend "s3" {
    bucket         = "mi-cuenta-terraform-state"
    key            = "pest-talabre-linux/us-east-1/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "terraform-state-lock"
    encrypt        = true
  }
}
```

---

### F-02 — Bug activo: `$RETRY_CODE` no definido en entrypoint_agent.sh

| Atributo | Detalle |
|----------|---------|
| **Categoría** | Software Quality / Resiliencia |
| **Severidad** | 🔴 CRÍTICO |
| **Evidencia** | `Estructura_Base/nombre_proyecto_modelo/app/entrypoint_agent.sh` — condición `if [ $RETRY_CODE -eq 80 ]` referencia variable nunca definida. La variable correcta es `$EXIT_CODE`. |
| **Impacto** | El mecanismo de retry ante el error Wine `c0000018` nunca funciona. Los agentes que encuentran este error simplemente fallan sin reintentar, reduciendo la estabilidad de la calibración. |
| **Recomendación** | Corregir `$RETRY_CODE` por `$EXIT_CODE` en la línea de la condición de reintento. |
| **Esfuerzo** | XS |

```bash
# Línea actual (buggy):
if [ $RETRY_CODE -eq 80 ] || echo "wine: failed to map..." 2>&1 | grep -q "c0000018"; then

# Línea correcta:
if [ $EXIT_CODE -eq 80 ] || echo "wine: failed to map..." 2>&1 | grep -q "c0000018"; then
```

---

### F-03 — Autoscaler requiere conexión continua del operador

| Atributo | Detalle |
|----------|---------|
| **Categoría** | Automatización / Resiliencia |
| **Severidad** | 🔴 CRÍTICO |
| **Evidencia** | `IaC_terraform/ModeloPest/talabre-linux/us-east-1/auto_scaling_tasks.py` — `while True: ... time.sleep(minutes_sleep*60)` |
| **Impacto** | Si la conexión o la máquina del operador se interrumpe durante una calibración: (1) agentes que terminan no se eliminan → costo innecesario; (2) agentes nuevos no se lanzan → calibración se ralentiza o se detiene completamente. No hay sistema de alertas que notifique este estado. |
| **Recomendación** | Mover el autoscaler a una Lambda con CloudWatch Events scheduled (cada 10 min) o a una ECS Fargate task de larga duración con reinicio automático. |
| **Esfuerzo** | M |

---

## 🟠 ALTO

---

### F-04 — ID de cuenta AWS hardcodeado en scripts versionados

| Atributo | Detalle |
|----------|---------|
| **Categoría** | Seguridad |
| **Severidad** | 🟠 ALTO |
| **Evidencia** | `Estructura_Base/AWS_Comandos/AWS_ECR_carga_imagen_docker.ps1` (múltiples líneas con `312019940349`), `Estructura_Base/AWS_Comandos/ECS_Fargate_comandos.ps1` |
| **Impacto** | El ID de cuenta AWS es visible para cualquier persona con acceso al repositorio. Facilita reconocimiento de la cuenta. |
| **Recomendación** | Reemplazar por `$(aws sts get-caller-identity --query Account --output text)`. |
| **Esfuerzo** | XS |

---

### F-05 — VPC/Subnet IDs hardcodeados como default en variables.tf

| Atributo | Detalle |
|----------|---------|
| **Categoría** | Seguridad / IaC |
| **Severidad** | 🟠 ALTO |
| **Evidencia** | `IaC_terraform/Arquitectura_regional/variables.tf`: `vpc_id = "vpc-0b08cba4a3d0cf109"`, `private_subnet_ids = ["subnet-0ce131779fb30b6a7", "subnet-00f3021ecee723128"]`, `private_route_table_ids = ["rtb-056497eebdfc41b40"]` |
| **Impacto** | Información de infraestructura de red real en código versionado. Cualquier persona con acceso al repositorio conoce la topología VPC. |
| **Recomendación** | Mover a archivo `terraform.tfvars` excluido de git (`.gitignore`), o usar AWS SSM Parameter Store como fuente de datos. |
| **Esfuerzo** | S |

---

### F-06 — Dos generaciones de arquitectura activas sin separación clara

| Atributo | Detalle |
|----------|---------|
| **Categoría** | Mantenibilidad |
| **Severidad** | 🟠 ALTO |
| **Evidencia** | `IaC_terraform/Arquitectura_regional/main.tf` (ECS Fargate), `IaC_terraform/ModeloPest/talabre-linux/us-east-1/main.tf` (Batch EC2), `Calibracion_Modelo_PEST/sqm_reservas/` (ECS legacy), `activar_agentes_pest.py` (llama a ECS run-task) |
| **Impacto** | Confusión operacional. Riesgo de aplicar `terraform apply` en el módulo incorrecto. Dificultad de mantenimiento. Los scripts de gen1 y gen2 usan APIs distintas (ECS vs Batch). |
| **Recomendación** | Deprecar y mover la generación ECS Fargate a una carpeta `_legacy/` o rama de archivo. Mantener solo la arquitectura Batch EC2 como código activo. |
| **Esfuerzo** | S |

---

### F-07 — auto_scaling_tasks.py con valores hardcodeados para un proyecto específico

| Atributo | Detalle |
|----------|---------|
| **Categoría** | Mantenibilidad / Automatización |
| **Severidad** | 🟠 ALTO |
| **Evidencia** | `IaC_terraform/ModeloPest/talabre-linux/us-east-1/auto_scaling_tasks.py`: `log_group_master = f"/batch/pest-talabre-linux-master"`, `cluster_name = f"pest-talabre-linux-agent-ce_Batch_da2c473c-..."`, `agent_job_queue = f"pest-talabre-linux-agent-queue"` |
| **Impacto** | El script solo funciona para el proyecto `pest-talabre-linux`. Para cualquier otro proyecto se deben editar manualmente estas líneas. |
| **Recomendación** | Leer todos los valores desde `variables.tf` o como argumentos CLI. Los nombres de recursos siguen el patrón `{project_name}-*` y ya están disponibles en `variables.tf`. |
| **Esfuerzo** | S |

---

### F-08 — Política S3 demasiado amplia en talabre-linux (wildcard `*`)

| Atributo | Detalle |
|----------|---------|
| **Categoría** | Seguridad (IAM) |
| **Severidad** | 🟠 ALTO |
| **Evidencia** | `IaC_terraform/ModeloPest/talabre-linux/us-east-1/main.tf` — `resource "aws_iam_role_policy" "task_role_s3"`: `Resource = ["arn:aws:s3:::*", "arn:aws:s3:::*/*"]` |
| **Impacto** | Un contenedor comprometido podría leer, escribir o listar **cualquier bucket S3** de la cuenta AWS, no solo el de la calibración. Viola el principio de mínimo privilegio. |
| **Recomendación** | Restringir a los ARNs del bucket específico: `"arn:aws:s3:::${var.s3_bucket_linux}"` y `"arn:aws:s3:::${var.s3_bucket_linux}/*"`. |
| **Esfuerzo** | XS |

---

### F-09 — null_resource con local-exec PowerShell en Terraform

| Atributo | Detalle |
|----------|---------|
| **Categoría** | IaC / Portabilidad |
| **Severidad** | 🟠 ALTO |
| **Evidencia** | `IaC_terraform/Arquitectura_regional/main.tf` y `IaC_terraform/ModeloPest/talabre/regional/main.tf` — `null_resource "run_agent_once"` con `interpreter = ["PowerShell", "-Command"]` |
| **Impacto** | (1) Solo puede ejecutarse en Windows. (2) No es idempotente — un `terraform apply` repetido puede lanzar agentes duplicados. (3) Genera side effects no registrados en el state. (4) Difícil de auditar. (5) No compatible con CI/CD en Linux. |
| **Recomendación** | Eliminar el `null_resource`. La lógica de lanzamiento de agentes ya existe correctamente en `launch_master_agents.py`. En gen2 (Batch) este problema ya está resuelto. |
| **Esfuerzo** | S |

---

### F-10 — No hay verificación de backup antes de terraform destroy

| Atributo | Detalle |
|----------|---------|
| **Categoría** | Resiliencia / Operaciones |
| **Severidad** | 🟠 ALTO |
| **Evidencia** | El flujo de trabajo (README) requiere ejecutar manualmente `backup_logs.py` y luego `terraform destroy` como pasos separados sin ningún enlace entre ellos. |
| **Impacto** | Si el operador ejecuta `terraform destroy` sin completar el backup, los resultados en disco del master se pierden (EBS con `delete_on_termination = true`). Los entrypoints hacen `aws s3 cp` al finalizar PEST, pero si el job fue terminado manualmente antes de completarse, el upload puede no haberse ejecutado. |
| **Recomendación** | Crear un script wrapper `safe_destroy.py` que (1) verifique existencia de resultados en S3, (2) ejecute `backup_logs.py`, y (3) solo entonces ejecute `terraform destroy`. |
| **Esfuerzo** | S |

---

## 🟡 MEDIO

---

### F-11 — Sin tests en el proyecto Python

| Atributo | Detalle |
|----------|---------|
| **Categoría** | Calidad de Software |
| **Severidad** | 🟡 MEDIO |
| **Evidencia** | No existe directorio `tests/`. `pyproject.toml` no incluye pytest. `main.py` es un placeholder. |
| **Impacto** | No hay forma de verificar que los scripts de orquestación funcionan correctamente antes de usarlos en producción. El bug F-02 es un ejemplo de lo que se detectaría con tests. |
| **Recomendación** | Agregar pytest. Priorizar tests unitarios para funciones críticas: parseo de logs, escalado, extracción de IP del master. |
| **Esfuerzo** | M |

---

### F-12 — Dependencias desincronizadas entre pyproject.toml y requirements.txt

| Atributo | Detalle |
|----------|---------|
| **Categoría** | Calidad de Software |
| **Severidad** | 🟡 MEDIO |
| **Evidencia** | `pyproject.toml`: `mkdocs`, `openpyxl`, `pandas`, `python-hcl2`. `requirements.txt`: `boto3`, `pandas`, `python-hcl2`, `pyyaml`, `openpyxl`. `boto3` ausente en `pyproject.toml`. Versiones distintas (`pandas>=3.0.5` vs `pandas>=2.0`). |
| **Impacto** | Ambigüedad sobre qué dependencias son necesarias. Entornos de desarrollo inconsistentes entre miembros del equipo. |
| **Recomendación** | Consolidar en `pyproject.toml` con versiones pinadas (`==` o rangos razonables). Eliminar `requirements.txt` redundante. |
| **Esfuerzo** | XS |

---

### F-13 — entrypoint_master.sh y entrypoint_autonomo.sh sin shebang ni set -e

| Atributo | Detalle |
|----------|---------|
| **Categoría** | Calidad de Software |
| **Severidad** | 🟡 MEDIO |
| **Evidencia** | `Estructura_Base/nombre_proyecto_modelo/app/entrypoint_master.sh` y `entrypoint_autonomo.sh` no tienen `#!/bin/bash` al inicio ni `set -e`. |
| **Impacto** | Un error en cualquier comando no detiene el script. El upload a S3 al final podría ejecutarse incluso si PEST falló. Sin shebang, el comportamiento depende del shell de invocación. |
| **Recomendación** | Agregar `#!/bin/bash` y `set -e` (o manejo explícito de errores) al inicio de ambos scripts. |
| **Esfuerzo** | XS |

---

### F-14 — ensibatch.sh tiene estructura irregular y shebang fuera de lugar

| Atributo | Detalle |
|----------|---------|
| **Categoría** | Calidad de Software |
| **Severidad** | 🟡 MEDIO |
| **Evidencia** | `Estructura_Base/nombre_proyecto_modelo/app/ensibatch.sh` — `#!/usr/bin/env bash` aparece en la línea 14 (no al inicio). Las primeras líneas se ejecutan sin el shebang. |
| **Impacto** | Comportamiento impredecible. El `rm -f` inicial puede ejecutarse con un shell diferente al esperado. Dificulta el mantenimiento y la revisión. |
| **Recomendación** | Mover el shebang al inicio del archivo. Separar la lógica de limpieza de la lógica de ejecución. |
| **Esfuerzo** | XS |

---

### F-15 — Imagen Docker usa ubuntu:25.04 (versión no-LTS)

| Atributo | Detalle |
|----------|---------|
| **Categoría** | Reproducibilidad / Estabilidad |
| **Severidad** | 🟡 MEDIO |
| **Evidencia** | `Estructura_Base/nombre_proyecto_modelo/Dockerfile`, `Calibracion_Modelo_PEST/talabre_pest/Dockerfile`: `FROM ubuntu:25.04`. La imagen legacy en `Talabre/master/Dockerfile` usa `ubuntu:20.04`. |
| **Impacto** | Ubuntu 25.04 es una versión de soporte corto (no-LTS). Los paquetes de Wine pueden cambiar entre versiones de Ubuntu y romper la imagen sin previo aviso. |
| **Recomendación** | Migrar a `ubuntu:22.04 LTS` o `ubuntu:24.04 LTS` con versiones fijas de Wine (`wine=9.*`). |
| **Esfuerzo** | S |

---

### F-16 — Sin métricas de Phi ni observabilidad del progreso científico

| Atributo | Detalle |
|----------|---------|
| **Categoría** | Observabilidad |
| **Severidad** | 🟡 MEDIO |
| **Evidencia** | `auto_scaling_tasks.py` — `find_logs = ["Running model", "Calculating Jacobian matrix", "Parallelisation of lambda search"]`. No incluye ningún término relacionado con el objective function. |
| **Impacto** | Es imposible saber si una calibración está mejorando, convergiendo o estancada sin conectarse manualmente a los logs. No hay visibilidad científica del progreso. |
| **Recomendación** | Agregar CloudWatch Metric Filters que capturen las líneas de Phi del log del master. Ver documento `10_calibration_quality.md`. |
| **Esfuerzo** | M |

---

### F-17 — Tiempo de espera hardcodeado de 4 minutos en Terraform gen1

| Atributo | Detalle |
|----------|---------|
| **Categoría** | IaC |
| **Severidad** | 🟡 MEDIO |
| **Evidencia** | `IaC_terraform/Arquitectura_regional/main.tf` — `resource "time_sleep" "wait_4_minutes"`: `create_duration = "4m"` |
| **Impacto** | Si el master tarda más de 4 minutos en estar listo (por imagen grande o cold start lento), los agentes intentan conectar antes de que PEST escuche en el puerto 4004. Tiempo arbitrario sin verificación real. |
| **Recomendación** | En gen2 (Batch) este problema ya está resuelto con polling activo en `launch_master_agents.py`. Confirmar que la gen1 está deprecada. |
| **Esfuerzo** | S |

---

### F-18 — Módulos Multiple_Region y unica_region_EC2 con NAT Gateway activo

| Atributo | Detalle |
|----------|---------|
| **Categoría** | FinOps |
| **Severidad** | 🟡 MEDIO |
| **Evidencia** | `IaC_terraform/ModeloPest/Multiple_Region/main.tf` — `aws_nat_gateway.west2`, `aws_nat_gateway.east1`, `aws_nat_gateway.east2`. `IaC_terraform/ModeloPest/unica_region_EC2/main.tf` — `aws_nat_gateway.west2`. |
| **Impacto** | Cada NAT Gateway genera ~$32/mes en costos fijos + $0.045/GB procesados. Si alguno de estos stacks está desplegado: $32–$96/mes en costos activos aunque no haya calibraciones corriendo. |
| **Recomendación** | **REQUIERE VALIDACIÓN:** verificar en consola AWS si estos stacks están desplegados. Si sí, ejecutar `terraform destroy`. |
| **Esfuerzo** | XS (verificación) / S (si hay que destruir) |

---

### F-19 — KMS Decrypt con Resource wildcard en policy gen1

| Atributo | Detalle |
|----------|---------|
| **Categoría** | Seguridad |
| **Severidad** | 🟡 MEDIO |
| **Evidencia** | `IaC_terraform/Arquitectura_regional/main.tf` — `aws_iam_policy.ecs_exec_policy`: `Action = ["kms:Decrypt"]` con `Resource = "*"` |
| **Impacto** | Los contenedores ECS podrían intentar descifrar cualquier clave KMS de la cuenta si obtienen el ARN. |
| **Recomendación** | Si se usa cifrado KMS, limitar el Resource al ARN de la clave específica. Si no se usa KMS, eliminar este permiso. |
| **Esfuerzo** | XS |

---

## 🔵 BAJO

---

### F-20 — main.py raíz completamente vacío

| Atributo | Detalle |
|----------|---------|
| **Categoría** | Calidad de Software |
| **Severidad** | 🔵 BAJO |
| **Evidencia** | `main.py` — `print("Hello from modflow-pest-calibracion!")` |
| **Impacto** | No hay punto de entrada para automatización del proyecto desde Python. Oportunidad perdida para un CLI. |
| **Recomendación** | Usar como CLI principal del proyecto (ej. con `click` o `typer`) o eliminar si no tiene propósito. |
| **Esfuerzo** | XS |

---

### F-21 — Duplicación de lógica entre múltiples scripts

| Atributo | Detalle |
|----------|---------|
| **Categoría** | Mantenibilidad |
| **Severidad** | 🔵 BAJO |
| **Evidencia** | Las funciones `fetch_events()`, `parse_iso()`, y `clean_message()` aparecen duplicadas en `Calibracion_Modelo_PEST/Cloudwatch/getLog.py` y en `IaC_terraform/ModeloPest/talabre-linux/us-east-1/auto_scaling_tasks.py`. La función `read_terraform_variables()` aparece duplicada en `activar_agentes_pest.py` y `auto_scaling_tasks.py`. |
| **Impacto** | Cambios en la lógica deben hacerse en múltiples lugares. Inconsistencias posibles entre versiones. |
| **Recomendación** | Crear un módulo Python compartido `calibration_utils/` con submódulos para CloudWatch, Batch, Terraform. |
| **Esfuerzo** | S |

---

### F-22 — Retención CloudWatch Logs de 30 días sin exportación a S3

| Atributo | Detalle |
|----------|---------|
| **Categoría** | Observabilidad / Compliance |
| **Severidad** | 🔵 BAJO |
| **Evidencia** | Todos los `main.tf` con `aws_cloudwatch_log_group` tienen `retention_in_days = 30`. |
| **Impacto** | Logs de calibraciones terminadas hace más de 30 días no están disponibles para análisis retrospectivo o auditoría. |
| **Recomendación** | Configurar exportación automática de logs a S3 antes del vencimiento. El script `backup_logs.py` ya cubre este caso si se ejecuta oportunamente. Considerar aumentar retención del master a 90 días. |
| **Esfuerzo** | XS |

---

## Matriz de Priorización

```
IMPACTO
  Alto │ F-01 F-02 F-08  │  F-03 F-10 F-04  │  F-05 F-06 F-07
       │  F-16 F-09       │                   │
       │─────────────────────────────────────────────────────────
 Medio │                  │  F-11 F-13 F-14  │  F-15 F-17 F-18
       │                  │  F-12             │  F-19
       │─────────────────────────────────────────────────────────
  Bajo │                  │                   │  F-20 F-21 F-22
       │──────────────────────────────────────────────────────────
            Bajo               Medio               Alto
                            ESFUERZO
```

> **Cuadrante superior-izquierdo** = Quick Wins (alto impacto, bajo esfuerzo): F-01, F-02, F-08, F-13, F-14, F-12
