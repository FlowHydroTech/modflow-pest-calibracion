# Compute Architecture Assessment

---

## Contexto del Workload PEST

Antes de comparar alternativas, es fundamental entender el patrón de cómputo:

| Característica | Detalle |
|---------------|---------|
| **Tipo de proceso** | Master-Agent (PEST HP) |
| **Master** | Single-thread, CPU-intensivo, estado mutable en disco, larga duración |
| **Agentes** | N procesos independientes, single-thread cada uno, sin estado compartido |
| **Comunicación** | Agentes → Master via TCP 4004 (baja bandwidth, periódica) |
| **Duración** | Horas a días por calibración |
| **Pattern CPU** | Single-thread al máximo (PEST no es multi-thread) → turbo single-core crítico |
| **RAM Master** | ~10–30 GB (modelo completo + Jacobiano en memoria) |
| **RAM por Agente** | ~2–4 GB (una corrida del modelo) |
| **Disco Master** | ~50–100 GB (modelo + resultados acumulados) |
| **Disco por Agente** | ~20–50 GB (imagen + archivos temporales) |
| **Tolerancia interrupción** | Agentes: alta (PEST reasigna trabajo). Master: crítico, no debe interrumpirse |
| **Paralelismo** | Hasta ~1000 agentes simultáneos en calibraciones grandes |

---

## Alternativas Evaluadas

### 1. ECS Fargate (gen1 — en uso, a deprecar)

| Aspecto | Detalle |
|---------|---------|
| **Ventajas** | Sin gestión de EC2; arranque ~30s; Cloud Map para DNS master |
| **Desventajas** | CPU máx 4 vCPU por tarea; RAM máx ~30 GB; disco efímero máx 200 GB; sin elección de tipo de instancia; sin Spot nativo con retry automático; precio premium vs EC2 |
| **Riesgos** | Wine en Fargate tiene problemas conocidos (error c0000018 documentado en código); ECS Service reinicia el master si PEST termina (pierde estado) |
| **Costo relativo** | ALTO — Fargate cobra vCPU + GB/h a precio premium |
| **Complejidad** | BAJA |
| **Adecuación al proyecto** | ⚠️ MEDIA — subóptimo para workload CPU-intensivo single-thread de larga duración |

**Por qué se migró:** El límite de CPU/RAM de Fargate es insuficiente para modelos grandes. El precio es ~30–50% más caro que EC2 equivalente. El master como ECS Service reinicia automáticamente, lo que es incorrecto para PEST (perdería el estado de optimización).

---

### 2. AWS Batch EC2 (gen2 — arquitectura actual ✅ RECOMENDADO)

| Aspecto | Detalle |
|---------|---------|
| **Ventajas** | Instancia dedicada por agente; turbo single-core máximo (~3.7 GHz c7a); Spot con retry automático; timeout nativo por job; discos gp3 configurables por rol; sin límite de RAM/disco como Fargate; múltiples familias de instancias para disponibilidad Spot |
| **Desventajas** | Arranque más lento (~2–3 min para boot EC2 + pull imagen); requiere gestión de Launch Template; mayor complejidad inicial vs Fargate |
| **Riesgos** | La IP del master debe inyectarse dinámicamente en cada agente (resuelto en `launch_master_agents.py`) |
| **Costo relativo** | BAJO-MEDIO — Spot ~70% ahorro vs On-Demand; EC2 más barato que Fargate equivalente |
| **Complejidad** | MEDIA |
| **Adecuación al proyecto** | ✅ ALTA — diseñado exactamente para workloads batch paralelos de larga duración |

**Configuración actual por rol:**

| Rol | Instancia | vCPU | RAM | Disco | Modo |
|-----|-----------|------|-----|-------|------|
| Master | r6a.xlarge / r6i.xlarge | 4 | 30 GB | 100 GB gp3 | On-Demand |
| Agentes (autonomo/Spot) | c7i/c7a/c6i/c6a.large | 2 | 3.6 GB | 120 GB gp3 | Spot + OD fallback |
| Agentes (M/A) | c7a.medium | 1 | 1.6 GB | 50 GB gp3 | On-Demand |

**Rationale de instancias:**
- `c7a.medium` para agentes: 1 vCPU/job = 1 job por instancia = turbo single-core máximo sin contención. AMD EPYC Genoa ~3.7 GHz.
- `r6a/r6i.xlarge` para master: alta RAM para modelo completo. On-Demand para evitar interrupciones.
- Múltiples familias en CE Spot: mayor disponibilidad, menor riesgo de interrupción.

---

### 3. ECS sobre EC2

| Aspecto | Detalle |
|---------|---------|
| **Ventajas** | Similar a Batch EC2 pero con control del cluster ECS |
| **Desventajas** | Mayor complejidad operacional; requiere gestión manual del Auto Scaling Group; sin gestión nativa de jobs/queues; sin timeout nativo por tarea |
| **Adecuación** | ⚠️ MEDIA — AWS Batch EC2 es estrictamente superior para jobs batch |

---

### 4. AWS Batch Fargate

| Aspecto | Detalle |
|---------|---------|
| **Ventajas** | Sin gestión de EC2; retry automático de Batch |
| **Desventajas** | Mismas limitaciones de CPU/RAM que ECS Fargate; sin elección de tipo de instancia; precio Fargate premium |
| **Adecuación** | ❌ BAJA para este workload — CPU single-thread intensivo no se beneficia de Fargate |

---

### 5. Step Functions (como capa de orquestación)

| Aspecto | Detalle |
|---------|---------|
| **Ventajas** | Orquestación visual y auditada; retry configurable; integración nativa con Batch submit_job; manejo de errores declarativo |
| **Desventajas** | Costo por state transitions (~$0.025 por 1000); no gestiona el cómputo en sí |
| **Adecuación** | ✅ ALTA como capa de orquestación sobre Batch EC2 — **no reemplaza el cómputo, lo orquesta** |
| **Recomendación** | Usar en Fase 6 para automatizar el flujo completo: validar → build → apply → launch → monitor → store → destroy |

---

## Comparativa Rápida

| Criterio | ECS Fargate | Batch EC2 | ECS EC2 | Batch Fargate |
|----------|-------------|-----------|---------|---------------|
| Turbo single-core | ⚠️ Limitado | ✅ Máximo | ✅ Máximo | ⚠️ Limitado |
| RAM ilimitada | ❌ Máx 30 GB | ✅ Cualquier instancia | ✅ Cualquier instancia | ❌ Máx 30 GB |
| Disco flexible | ❌ Máx 200 GB | ✅ EBS configurable | ✅ EBS configurable | ❌ Máx 200 GB |
| Spot con retry | ❌ Fargate Spot manual | ✅ Nativo en Batch | ❌ Manual | ✅ Nativo |
| Timeout nativo | ❌ | ✅ Job timeout | ❌ | ✅ Job timeout |
| Sin gestión EC2 | ✅ | ❌ | ❌ | ✅ |
| Costo relativo | Alto | Bajo-Medio | Medio | Alto |
| Arranque | Rápido (~30s) | Lento (~2-3 min) | Lento | Rápido |
| **Adecuación PEST** | ⚠️ Media | **✅ Alta** | ⚠️ Media | ❌ Baja |

---

## Recomendación Final

**Mantener AWS Batch EC2 (gen2) como arquitectura de cómputo.** Es la elección correcta.

**Para agentes:** Batch Spot (c7a.medium + c7i/c7a/c6i/c6a.large) con On-Demand como fallback automático. La configuración actual es correcta.

**Para master:** Batch On-Demand (r6a.xlarge o r6i.xlarge). On-Demand garantiza que el proceso central no sea interrumpido. La configuración actual es correcta.

**Adiciones recomendadas:**
- Step Functions como orquestador del flujo completo (Fase 6)
- Lambda para autoscaler y monitoreo (Fase 1)

**No se recomienda migrar a ECS EC2 ni volver a ECS Fargate.**

---

## Nota sobre Wine

La elección de ejecutar `pest_hp.exe` y `agent_hp.exe` (binarios Windows) via Wine en Linux es una restricción del proyecto (los binarios PEST compilados son para Windows). Esta decisión tiene implicancias operativas:

1. **Error c0000018 de Wine** es conocido y está documentado en el código. Ocurre cuando múltiples instancias Wine compiten por memoria compartida en arranque paralelo.
2. **Mitigación actual:** lock file en `entrypoint_agent.sh` + retry (con bug activo, ver F-02).
3. **REQUIERE VALIDACIÓN:** ¿Existen versiones Linux nativas de `pest_hp` y `agent_hp`? El directorio `talabre_pest/Dockerfile` sugiere que `pest_hp` y `agent_hp` son **binarios Linux nativos** (solo se hace `chmod +x`). Si es así, Wine podría no ser necesario para Talabre. Para CMDIC, `ensibatch.sh` explícitamente usa `wine ./plproc.exe`, `wine ./usgbud2smp.exe`, etc.
