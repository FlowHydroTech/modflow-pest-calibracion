# Resilience Assessment

---

## Análisis de Escenarios de Fallo

### Fallo del Master

| Aspecto | Estado actual |
|---------|--------------|
| **¿Qué ocurre?** | Job Batch del master pasa a `FAILED`. PEST se detiene completamente. Todos los agentes quedan sin trabajo y eventualmente son detenidos por el autoscaler (si está corriendo). |
| **¿Es recuperable?** | **NO** sin reiniciar la calibración completa. El estado de PEST (Jacobiano, iteraciones, parámetros actuales) se pierde porque estaba en el disco efímero del EC2. |
| **Configuración actual** | `retry_strategy.attempts = 1` (sin reintentos). Correcto — reiniciar el master automáticamente sin el estado llevaría a una calibración desde cero sin que el operador lo sepa. |
| **Riesgo principal** | Sin alertas → el operador no sabe que la calibración se detuvo. La infraestructura puede quedar activa (costos). |
| **Mitigación propuesta** | Alerta CRITICAL via SNS cuando el job master pasa a FAILED (ver `12_alerts_strategy.md` A-C1). |

---

### Fallo de un Agente

| Aspecto | Estado actual |
|---------|--------------|
| **¿Qué ocurre?** | PEST detecta que el agente no responde y lo reasigna (corrida del modelo a otro agente disponible). |
| **¿Es recuperable?** | **SÍ**. PEST gestiona internamente la pérdida de agentes. |
| **Retry automático** | Configurado para interrupción Spot: `on_status_reason = "Host EC2 terminated*"` → `action = "RETRY"`. |
| **Sin retry para** | Exit code 137 (OOM Kill), Exit code 130 (SIGINT). Correcto — estos son errores de configuración o memoria. |
| **Riesgo** | Si el bug F-02 (`$RETRY_CODE`) impide el retry de Wine, los agentes que encuentren el error c0000018 fallan sin reintentar. |

---

### Interrupción Spot del Agente

| Aspecto | Estado actual |
|---------|--------------|
| **¿Qué ocurre?** | AWS interrumpe la instancia Spot. Batch detecta el estado `Host EC2 terminated*` y reintenta el job en otra instancia. |
| **¿Es recuperable?** | **SÍ**. Batch maneja esto automáticamente con `evaluate_on_exit`. |
| **Tiempo de recuperación** | ~2-3 min (boot EC2 nueva instancia + pull imagen + Wine init). |
| **Riesgo** | PEST puede tener un timeout para que el agente responda. Si el timeout es más corto que el tiempo de recuperación, PEST descartará la corrida y la reasignará. Esto es aceptable. |

---

### Pérdida de Conectividad del Operador

| Aspecto | Estado actual |
|---------|--------------|
| **¿Qué ocurre?** | El autoscaler (`auto_scaling_tasks.py`) se detiene. |
| **Impacto** | Agentes que terminan corridas no son eliminados → costos innecesarios. Nuevos agentes solicitados por PEST no se lanzan → calibración más lenta o detenida por falta de workers. |
| **¿Es recuperable?** | **PARCIALMENTE**. La calibración en sí puede seguir si hay agentes activos, pero sin nuevos agentes se degrada. |
| **Mitigación propuesta** | Mover autoscaler a Lambda schedulada (Fase 1). |

---

### Falla de una Corrida del Modelo

| Aspecto | Estado actual |
|---------|--------------|
| **¿Qué ocurre?** | El agente ejecuta el modelo y obtiene error. El agente retorna el error a PEST. |
| **Gestión por PEST** | PEST registra el fallo de la corrida y puede continuar con las corridas restantes de la iteración. |
| **Timeout** | `ensibatch_timeout.sh` maneja el timeout de cada corrida individual con `timeout --kill-after=60s "$MODEL_TIMEOUT"`. Variable `MODEL_TIMEOUT` configurable (default 15h). |
| **Exit codes** | 124 = timeout, 137 = killed después del grace period. |
| **¿Es recuperable?** | **SÍ**. PEST continúa la calibración. |

---

### S3 No Disponible Temporalmente

| Aspecto | Estado actual |
|---------|--------------|
| **¿Qué ocurre?** | Los entrypoints ejecutan `aws s3 cp` sin retry. Si S3 falla, el comando falla. |
| **Entrypoint_master** | Si S3 falla al final, los resultados **no se respaldan automáticamente**. El script termina con error pero la calibración ya terminó. |
| **Riesgo** | Pérdida de resultados si S3 no está disponible en el momento del upload final. |
| **Mitigación** | Agregar retry con backoff exponencial al `aws s3 cp` o usar `aws s3 sync --retry`. |

---

### Terraform Falla Parcialmente

| Aspecto | Estado actual |
|---------|--------------|
| **¿Qué ocurre?** | Algunos recursos se crean, otros no. El `terraform.tfstate` queda en estado intermedio. |
| **Sin backend remoto** | El state local puede quedar corrupto. Si el operador pierde el state file, no puede hacer `terraform destroy` para limpiar los recursos parciales. |
| **Riesgo** | Recursos huérfanos (VPC Endpoints, instancias EC2, etc.) generando costos. |
| **Mitigación** | Backend S3 remoto + DynamoDB locking (F-01). |

---

### Calibración Queda Detenida Sin Ser Detectada

| Aspecto | Estado actual |
|---------|--------------|
| **¿Qué ocurre?** | El job master falla silenciosamente. La infraestructura sigue activa. |
| **Detección** | Solo si el operador revisa manualmente. Sin alertas automáticas. |
| **Costo** | VPC Endpoints + posibles instancias activas continúan generando costos. |
| **Mitigación** | CloudWatch Alarm "sin actividad en logs del master por 30 min" → SNS (Fase 2). |

---

## Matriz de Recuperabilidad

| Escenario | Recuperable | Requiere intervención | Datos en riesgo |
|-----------|-------------|----------------------|-----------------|
| Fallo master | ❌ Restart completo | Sí — manual | Estado PEST perdido |
| Fallo agente | ✅ Automático (PEST) | No | Ninguno |
| Interrupción Spot | ✅ Automático (Batch) | No | Ninguno |
| Pérdida conexión operador | ⚠️ Parcial | Sí — manual | Degradación de rendimiento |
| Falla corrida individual | ✅ Automático (PEST) | No | Ninguno |
| S3 temporalmente no disponible | ⚠️ Parcial | Sí — si falló upload final | Resultados del master |
| Terraform parcial + state perdido | ❌ Difícil | Sí — limpieza manual AWS | Recursos huérfanos |
| Calibración detenida sin detectar | ❌ No detectada | Sí — cuando se descubre | Costos acumulados |

---

## Dónde NO Deben Existir Retries Ciegos

| Caso | Por qué NO reintentar automáticamente |
|------|--------------------------------------|
| Master fallido | Reiniciar significa calibración desde cero. El operador debe decidir conscientemente. |
| Error de permisos S3/IAM | Reintentar no ayuda si el bucket no existe o hay error de permisos. |
| Modelo `.pst` no encontrado | Error de configuración — reintentar no lo resolverá. |
| Falta de capacidad Spot en todas las AZs | Reintentar con Spot no ayuda si no hay capacidad disponible → pasar a On-Demand. |

---

## Mejoras de Resiliencia Propuestas

| Mejora | Prioridad | Esfuerzo |
|--------|-----------|---------|
| Alertas CRITICAL para master fallido | ALTA | S |
| Mover autoscaler a Lambda (sin dependencia de conexión) | ALTA | M |
| Retry con backoff en `aws s3 cp` de entrypoints | MEDIA | XS |
| Script `safe_destroy.py` con verificación S3 antes de destroy | ALTA | S |
| Health check explícito del master antes de lanzar agentes | MEDIA | XS |
| Backend S3 para state Terraform | CRÍTICA | S |
