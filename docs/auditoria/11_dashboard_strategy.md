# Dashboard / Visor Strategy

---

## Pregunta Central

**¿CloudWatch Dashboard es suficiente como primer visor?**

**Sí — para el MVP, CloudWatch Dashboard resuelve el caso de uso principal.**

---

## Nivel 1: CloudWatch Dashboard (MVP recomendado)

### ¿Qué puede mostrar?

| Widget | Fuente | Disponibilidad |
|--------|--------|---------------|
| Serie de tiempo Phi por iteración | Custom Metric (Metric Filter) | Después de implementar Metric Filters |
| Número de agentes activos | Batch API / Custom Metric | Después de Lambda autoscaler |
| CPU del master | CloudWatch Container Insights o EC2 | Si habilitado en CE |
| RAM del master | CloudWatch Container Insights | Si habilitado en CE |
| Estado de alarms | CloudWatch Alarm Widget | Después de crear alarms |
| Logs recientes del master | CloudWatch Logs Insights Widget | Disponible hoy |
| Jobs activos en Batch | Batch Metrics (limitado) | Disponible parcialmente |

### Ventajas del CloudWatch Dashboard

- ✅ Costo casi nulo (~$3/mes por dashboard + $0.30/métrica custom/mes)
- ✅ Sin infraestructura adicional que gestionar
- ✅ Disponible inmediatamente al crear los Metric Filters
- ✅ Acceso controlado por IAM existente
- ✅ Auto-refresh configurable (cada 10s, 1min, 5min)
- ✅ Alertas visibles directamente en el dashboard
- ✅ Filtro por período temporal

### Limitaciones del CloudWatch Dashboard

- ❌ No es accesible sin credenciales AWS (los modeladores necesitan acceso a la consola)
- ❌ Poca personalización visual comparado con Grafana
- ❌ No puede mostrar tabla de calibraciones activas/históricas multi-proyecto
- ❌ Sin estado visual IMPROVING/STAGNATED/CONVERGED como badge de color
- ❌ Sin comparación entre calibraciones pasadas

---

## Nivel 2: Visor Web Propio (Post-MVP)

### ¿Cuándo considerar un visor web propio?

Solo si se necesita al menos uno de los siguientes:

- Acceso para usuarios sin credenciales AWS (modeladores, gerencia, clientes)
- Historial de múltiples calibraciones con comparación de Phi
- Vista consolidada multi-proyecto simultáneo
- Interfaz personalizada para no-técnicos
- Comparación de calibraciones pasadas y actuales

### Opción mínima recomendada si se llega al Nivel 2

**Opción A: API Lambda + S3 Frontend (recomendada)**

```
S3 (HTML/JS estático) + CloudFront
    ↓
Lambda (FastAPI o handler simple)
    ↓
CloudWatch Metrics API + S3 (para manifests)
```

- Sin base de datos propia (CloudWatch como datastore)
- Sin servidor permanente (Lambda on-demand)
- Costo: ~$1-5/mes
- Los datos ya existen en CloudWatch

**Opción B: Grafana managed (AWS Managed Grafana)**

- Acceso por SSO
- Soporte nativo para CloudWatch como datasource
- Mayor costo pero más funcional

**NO recomendado en esta etapa:** DynamoDB como datastore de calibraciones, Elasticsearch, Kibana, backend Python persistente.

---

## Layout MVP del Dashboard

```
╔══════════════════════════════════════════════════════════════════════╗
║  🔬 PEST CALIBRATION MONITOR                                         ║
║  pest-talabre-linux | us-east-1 | Actualizado: hace 2 min            ║
╠═══════════════════════════════╦══════════════════════════════════════╣
║  Estado de la Calibración     ║  Alarms                              ║
║  ┌─────────────────────────┐  ║  ● Master fallido      ✅ OK         ║
║  │ IMPROVING               │  ║  ● Sin actividad 30min  ✅ OK        ║
║  │ Iteración: 12           │  ║  ● Phi sin mejorar      ✅ OK        ║
║  │ Tiempo: 4h 23m          │  ║  ● TTL infraestructura  ✅ OK        ║
║  └─────────────────────────┘  ║                                      ║
╠═══════════════════════════════╬══════════════════════════════════════╣
║  Phi Evolution                ║  Infrastructure                      ║
║  [Line Chart: Phi vs iter]    ║  Master:  ✅ RUNNING                 ║
║  8432 ↓                       ║  Agentes activos: 47                 ║
║       6234 ↓                  ║  Agentes fallidos: 2                 ║
║            3891 ↓             ║  CPU Master: 62%                     ║
║                 2105 ↓        ║  RAM Master: 78%                     ║
╠═══════════════════════════════╩══════════════════════════════════════╣
║  Modelos ejecutados por iteración                                    ║
║  [Bar Chart]                                                         ║
╠══════════════════════════════════════════════════════════════════════╣
║  Recent Logs — Master (últimas 100 líneas)                           ║
║  [CloudWatch Logs Insights Widget]                                   ║
╚══════════════════════════════════════════════════════════════════════╝
```

---

## Información a Visualizar (Prioritizada)

### Estado de la calibración (más importante)

| Campo | Fuente | Estado |
|-------|--------|--------|
| Estado (IMPROVING/STAGNATED/etc.) | Custom Metric → Alarm | Fase 3 |
| Iteración actual | Custom Metric (Metric Filter) | Fase 2 |
| Phi inicial | Custom Metric (primer valor) | Fase 2 |
| Phi actual | Custom Metric (último valor) | Fase 2 |
| Reducción % | Calculado | Fase 2 |
| Tiempo transcurrido | Batch job startedAt | Fase 2 |

### Infraestructura

| Campo | Fuente |
|-------|--------|
| Estado master | Batch job status |
| Agentes activos | Batch list_jobs RUNNING |
| Agentes fallidos | Batch list_jobs FAILED |
| CPU master | Container Insights |
| RAM master | Container Insights |

### Logs recientes

Logs Insights query para el master:
```
fields @timestamp, @message
| filter @logStream like /master/
| sort @timestamp desc
| limit 50
```

---

## Decisión Recomendada

**MVP: CloudWatch Dashboard** → Implementar en Fase 4.

**Criterios para ir al Nivel 2:**
- El equipo de modelamiento necesita acceder sin credenciales AWS
- Se quiere comparar múltiples calibraciones históricas
- Se necesita acceso móvil o compartible con stakeholders externos

Hasta que alguno de estos criterios aplique, CloudWatch Dashboard es suficiente y más simple de mantener.
