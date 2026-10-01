# FinOps Assessment

---

## Principales Cost Drivers

| Recurso | Costo aprox. | Tipo | Observaciones |
|---------|-------------|------|---------------|
| Batch EC2 agentes (c7a.medium Spot) | $0.007–0.015/h por agente | Variable | ~70% ahorro vs On-Demand |
| Batch EC2 agentes (c7a.medium OD fallback) | $0.034/h por agente | Variable | Solo cuando Spot no disponible |
| Batch EC2 master (r6a.xlarge On-Demand) | $0.24/h | Variable | Solo mientras calibración activa |
| EBS gp3 agentes (50 GB) | ~$0.004/h | Variable | Mientras el job corre |
| EBS gp3 master (100 GB) | ~$0.008/h | Variable | Mientras el job corre |
| VPC Endpoints Interface | ~$0.01/h × 7-9 endpoints | Variable | ~$0.07–0.09/h total, solo mientras deploy |
| S3 almacenamiento | $0.023/GB/mes | Fijo bajo | Relativamente bajo |
| CloudWatch Logs (ingestión) | $0.50/GB ingestado | Variable | Principal variable en volumen |
| CloudWatch Custom Metrics | $0.30/métrica/mes | Fijo bajo | Bajo — <$5/mes total |
| CloudWatch Dashboard | $3/dashboard/mes | Fijo bajo | Negligible |
| ECR almacenamiento | $0.10/GB/mes | Fijo | Imágenes Docker ~5-20 GB |
| **NAT Gateway** (prototipos) | **$32/mes + $0.045/GB** | **Fijo alto** | **⚠️ Si algún prototipo está desplegado** |

---

## Estimación de Costo por Calibración Típica

> ⚠️ **REQUIERE VALIDACIÓN** de duración y cantidad de agentes real para tu caso.

Usando como ejemplo de referencia: 50 agentes × 48 horas:

| Recurso | Cálculo | Costo |
|---------|---------|-------|
| 50 agentes Spot c7a.medium | 50 × 48h × $0.01/h | $24.00 |
| 1 master r6a.xlarge OD | 1 × 48h × $0.24/h | $11.52 |
| VPC Endpoints (9 × 48h × $0.01/h) | 9 × 48 × $0.01 | $4.32 |
| EBS agentes (50 × 50 GB × 48h / 720h × $0.08) | — | $2.67 |
| EBS master (100 GB × 48h / 720h × $0.08) | — | $0.53 |
| S3 + CloudWatch Logs | ~$1-3 | $2.00 |
| **Total estimado** | | **~$45** |

Para calibraciones más largas (7 días) o con más agentes (200), escalar proporcionalmente.

---

## Oportunidades de Optimización

### 🟢 Alto impacto / Baja complejidad (Quick Wins)

| Oportunidad | Ahorro estimado | Esfuerzo |
|-------------|----------------|----------|
| **Verificar y destruir NAT Gateways de prototipos** | $32–96/mes (si activos) | XS |
| **Tag CalibrationID** para visibilidad por calibración en Cost Explorer | Visibilidad | XS |
| **Budget Alerts AWS** | Detección temprana de sobrecosto | XS |
| **Aumentar retención en CW a 7 días para agentes** (actualmente 30) | $0.50/GB × reducción volumen | XS |

### 🟡 Medio impacto / Complejidad media

| Oportunidad | Ahorro estimado | Esfuerzo |
|-------------|----------------|----------|
| **TTL automático de infraestructura** — alerta + auto-destroy | Variable (evita horas/días de infra olvidada) | M |
| **VPC Endpoints compartidos** entre proyectos en la misma VPC | ~$0.07/h × número de deploys paralelos | M |
| **Rightsizing del master** — verificar si r6a.xlarge o r6i.xlarge es correcto para cada modelo | 10-30% del costo del master | S |

### 🔵 Bajo impacto / Info

| Oportunidad | Observación |
|-------------|-------------|
| Fargate Spot para agentes (en gen1) | Ya resuelto con Batch Spot en gen2 |
| CloudWatch Logs — comprimir logs de agentes | Reducción volumétrica moderada |
| ECR lifecycle policy | Eliminar imágenes antiguas automáticamente |

---

## Costos de la Arquitectura Objetivo (con mejoras)

La arquitectura objetivo agrega:

| Nuevo servicio | Costo estimado | Observación |
|---------------|----------------|-------------|
| Lambda autoscaler (5 min/10 min) | < $1/mes | Dentro de free tier para invocaciones |
| Lambda extracción Phi | < $1/mes | Triggered por logs, pocas invocaciones |
| SNS | < $1/mes | Pocas notificaciones |
| CloudWatch Custom Metrics (10) | $3/mes | 10 métricas × $0.30/mes |
| CloudWatch Dashboard | $3/mes | Por dashboard |
| S3 Terraform state | < $1/mes | Bucket S3 + DynamoDB mínimo |
| **Total overhead adicional** | **~$8-10/mes** | Independiente de calibraciones activas |

---

## Política de Retención de Logs Propuesta

| Log Group | Retención actual | Retención propuesta | Razón |
|-----------|-----------------|---------------------|-------|
| `/batch/{project}-master` | 30 días | 90 días | Logs científicos críticos |
| `/batch/{project}-agents` | 30 días | 14 días + export S3 | Volumen alto, análisis en S3 |
| `/batch/{project}` (autónomo) | 30 días | 14 días | Menor importancia |

---

## Control de Costos — Acciones Inmediatas

1. **Verificar NAT Gateways** en consola AWS → ir a VPC → NAT Gateways → verificar si `Multiple_Region` o `unica_region_EC2` están desplegados.

2. **Activar AWS Cost Explorer** con granularidad diaria si no está activo.

3. **Crear Budget Alert:**
   ```
   AWS Budgets → Crear budget → Cost Budget
   Umbral: $50/día o $500/mes (ajustar según uso real)
   Notificación: 80% del umbral → Warning; 100% → Critical
   ```

4. **Agregar tag CalibrationID** a todos los recursos Batch cuando se lanza una calibración:
   ```python
   batch_client.submit_job(
       ...
       tags={"CalibrationID": "talabre-20260601-001"}
   )
   ```
