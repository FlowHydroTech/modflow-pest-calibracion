# Quick Wins

> Mejoras de **alto impacto + bajo esfuerzo + bajo riesgo**.  
> Estas son las primeras acciones a implementar, idealmente en el primer sprint.

---

## Criterios de selección

Para ser Quick Win, una mejora debe cumplir:
- ⏱️ **Esfuerzo:** XS o S (menos de 1-2 días de trabajo)
- 💥 **Impacto:** Elimina un riesgo crítico o agrega valor operacional relevante
- 🛡️ **Riesgo:** Bajo — no introduce regresiones ni cambios disruptivos

---

## Lista Priorizada

### 🔴 Urgentes (riesgos activos)

| # | Mejora | Impacto | Esfuerzo | Área |
|---|--------|---------|---------|------|
| **QW-01** | **Backend S3 + DynamoDB para Terraform** — añadir bloque `backend "s3"` a los módulos activos (`Arquitectura_regional` y `talabre-linux/us-east-1`) | Elimina el mayor riesgo operacional: pérdida de state = pérdida de control de infraestructura | S | IaC |
| **QW-02** | **Corregir `$RETRY_CODE` → `$EXIT_CODE`** en `entrypoint_agent.sh` — una línea de cambio | Fix de bug real que impide el retry ante errores Wine | XS | Software |
| **QW-03** | **Agregar `#!/bin/bash` y `set -e`** a `entrypoint_master.sh` y `entrypoint_autonomo.sh` | Previene ejecución silenciosa con errores; garantiza que el upload a S3 no corre si PEST falló | XS | Software |
| **QW-04** | **Restringir S3 Resource** de `Resource = ["arn:aws:s3:::*"]` al bucket específico en `talabre-linux/main.tf` | Mínimo privilegio: un contenedor comprometido no accede a todos los buckets S3 | XS | Seguridad |

### 🟠 Alta prioridad (seguridad y visibilidad)

| # | Mejora | Impacto | Esfuerzo | Área |
|---|--------|---------|---------|------|
| **QW-05** | **Mover VPC IDs a `.tfvars`** excluido de git — crear `terraform.tfvars.example` como referencia | Elimina topología de red del código versionado | XS | Seguridad |
| **QW-06** | **Verificar NAT Gateways de prototipos** en consola AWS — si están activos, destruirlos | Ahorro potencial de $32–$96/mes en recursos ociosos | XS | FinOps |
| **QW-07** | **Tags de Cost Allocation** — agregar `CalibrationID` y `Environment` a todos los recursos Batch | Visibilidad de costo por calibración en Cost Explorer; sin costo adicional | XS | FinOps |
| **QW-08** | **Budget Alert AWS** — crear alerta de presupuesto ($X/día o $Y/mes) | Detecta sobrecosto antes de que sea significativo | XS | FinOps |

### 🟡 Valor operacional inmediato

| # | Mejora | Impacto | Esfuerzo | Área |
|---|--------|---------|---------|------|
| **QW-09** | **CloudWatch Metric Filters para Phi** — una vez confirmado el formato del log real, configurar Metric Filter en `/batch/project-master` | Phi visible como métrica en CloudWatch en tiempo real | S | Observabilidad |
| **QW-10** | **SNS Topic + Alarm master fallido** — CloudWatch Event Rule para job Batch en estado FAILED + SNS email | El operador recibe email cuando el master falla; no más calibraciones detenidas sin detectar | S | Alertas |
| **QW-11** | **CloudWatch Dashboard básico** — Phi evolution + agentes activos + logs recientes | Visibilidad operacional sin abrir múltiples pantallas en la consola | S | Observabilidad |
| **QW-12** | **Parametrizar `auto_scaling_tasks.py`** — leer project_name, log_group, job_queue desde `variables.tf` en lugar de hardcodear | Script reutilizable para cualquier proyecto sin modificar código | S | Automatización |
| **QW-13** | **Script `safe_destroy.py`** — wrapper que verifica S3, ejecuta backup, y solo entonces ejecuta `terraform destroy` | Previene pérdida de resultados por destroy prematuro | S | Resiliencia |
| **QW-14** | **Unificar dependencias Python** — consolidar `requirements.txt` y `pyproject.toml` con versiones consistentes | Entornos de desarrollo reproducibles entre miembros del equipo | XS | Calidad |

---

## Orden de Implementación Recomendado

```
Sprint 1 (semana 1):
  QW-02 → corregir bug (5 min)
  QW-03 → agregar shebang (5 min)
  QW-04 → restringir S3 (10 min)
  QW-05 → mover VPC IDs (30 min)
  QW-14 → unificar dependencias (30 min)
  QW-06 → verificar NAT GW (15 min en consola AWS)
  QW-07 → tags CalibrationID (30 min)
  QW-08 → Budget Alert (15 min en consola AWS)

Sprint 2 (semana 2):
  QW-01 → backend Terraform S3 (2-4 horas — requiere crear bucket y tabla DDB)
  QW-10 → SNS + alarm master fallido (2-3 horas)
  QW-13 → safe_destroy.py (2-3 horas)
  QW-12 → parametrizar autoscaler (3-4 horas)

Sprint 3 (semana 3):
  QW-09 → Metric Filters Phi (2-3 horas, requiere validar formato log)
  QW-11 → Dashboard básico (2-3 horas, requiere QW-09)
```

---

## Impacto Acumulado de Quick Wins

Después de implementar todos los Quick Wins:

| Área | Antes | Después |
|------|-------|---------|
| Riesgo pérdida de infraestructura | 🔴 Crítico | ✅ Controlado |
| Bug retry Wine | 🔴 Activo | ✅ Corregido |
| Costos NAT GW ociosos | ⚠️ Posibles | ✅ Eliminados o identificados |
| Privilegios S3 | 🟠 Wildcard | ✅ Restringido |
| Observabilidad Phi | ❌ Ausente | ✅ Métrica en CloudWatch |
| Alertas master fallido | ❌ Ausente | ✅ Email automático |
| Dashboard | ❌ Ausente | ✅ Básico operativo |
| Costo por calibración visible | ❌ No visible | ✅ Etiquetado |
| Destroy seguro | ❌ Manual sin verificación | ✅ Script con checks |

**Esfuerzo total estimado:** 2–3 sprints de 1 semana.  
**Costo de implementación:** Bajo (solo tiempo de desarrollo, sin servicios adicionales costosos).
