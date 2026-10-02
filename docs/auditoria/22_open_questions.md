# Open Questions

> Decisiones e información que **no pueden resolverse analizando el repositorio** y requieren validación del equipo.

---

## Preguntas Operacionales

### OQ-01 — ¿Están activos los stacks de prototipos con NAT Gateway?

**Pregunta:** ¿Los módulos `Multiple_Region` y `unica_region_EC2` tienen infraestructura actualmente desplegada en AWS?

**Por qué importa:** Si están desplegados, hay NAT Gateways generando ~$32–96/mes en costos fijos aunque no haya calibraciones activas.

**Cómo validar:**
```bash
# En consola AWS → VPC → NAT Gateways → verificar estado Available
# O via CLI:
aws ec2 describe-nat-gateways --filter Name=state,Values=available --region us-west-2
aws ec2 describe-nat-gateways --filter Name=state,Values=available --region us-east-1
aws ec2 describe-nat-gateways --filter Name=state,Values=available --region us-east-2
```

**Impacto de la respuesta:** Si están activos → ejecutar `terraform destroy` inmediatamente en esos módulos.

**🟢 RESUELTO:** La arquitectura de la nueva cuenta FlowHydro (`803037204233`) se
diseñó **sin NAT Gateway**: la VPC usa VPC Endpoints (S3, ECR, CloudWatch Logs,
etc.) para el tráfico a AWS, evitando el costo fijo. La POC se desplegó y destruyó
bajo este patrón (cuenta en ~$0/h en reposo). Los stacks legacy de prototipo deben
revisarse/destruirse en la cuenta antigua si aún existen, pero el diseño objetivo
ya no depende de NAT.

---

### OQ-02 — ¿Existe respaldo del terraform.tfstate actual?

**Pregunta:** ¿El `terraform.tfstate` de los módulos activos (`talabre-linux/us-east-1`, `Arquitectura_regional`) está respaldado en algún lugar fuera de las máquinas locales del equipo?

**Por qué importa:** Si el state local se pierde, `terraform destroy` fallará y los recursos quedarán huérfanos. Antes de migrar al backend S3, necesitamos saber si existe recuperación.

**Impacto de la respuesta:** Define si la migración al backend S3 puede hacerse directamente (`terraform init -migrate-state`) o si hay que reconstruir el state.

**🟢 RESUELTO:** Se desplegó un **backend remoto de Terraform** en la cuenta
FlowHydro: bucket S3 `803037204233-pest-terraform-state` (con versionado y cifrado)
y tabla DynamoDB `terraform-state-lock` para bloqueo. El state ya no vive solo en
máquinas locales; está respaldado y versionado. El módulo `talabre-linux/us-east-1`
se conectó a este backend (resuelve F-01).

---

## Preguntas Técnicas Críticas

### OQ-03 — ¿Cuál es el formato exacto de las líneas Phi en los logs del master?

**Pregunta:** ¿Cómo aparece el objective function (Phi) en el stdout de `pest_hp` para estos modelos específicos?

**Por qué importa:** Sin confirmar el formato exacto, los CloudWatch Metric Filters no pueden implementarse correctamente. El formato puede variar entre versiones de PEST y configuraciones.

**Cómo validar:** Obtener un log real de CloudWatch de una calibración anterior del master. Buscar términos como `Phi`, `phi`, `objective function`, `Current phi`.

**Ejemplo de lo que se espera (a confirmar):**
```
Phi = 8432.50
Current phi = 6234.80 (Measurement: 5891.30  Regularization: 343.50)
```

**Impacto de la respuesta:** Define el patrón regex para los Metric Filters de Fase 2.

**🟢 RESUELTO (vía literatura, pendiente de confirmación con log real):** Los
patrones regex de Phi para PEST_HP se derivaron del estado del arte (documentación
oficial de PEST + pyEMU) y se documentaron en
`docs/auditoria/23_phi_log_format_research.md`. Están implementados en
`lambdas/extract_phi/` y validados en la POC con un log sintético que replica el
formato PEST. Cuando se corra el modelo real CMDIC Rajos, el primer paso es
confirmar que el log del master coincide con los patrones (es ahora una
confirmación, no un bloqueo).

---

### OQ-04 — ¿PEST HP usa binarios Windows (Wine) o Linux nativos para Talabre?

**Pregunta:** ¿Los ejecutables `pest_hp` y `agent_hp` usados en `talabre-linux` son binarios Linux nativos o Windows ejecutados via Wine?

**Contexto:** El `Dockerfile` de `talabre_pest/` instala Wine pero el `chmod +x` sobre `pest_hp` y `agent_hp` sin extensión `.exe` sugiere que podrían ser binarios Linux. El `Dockerfile` de `Estructura_Base` (para CMDIC) sí usa Wine explícitamente en `ensibatch.sh` para múltiples herramientas (`wine ./plproc.exe`, etc.).

**Por qué importa:** Si Talabre usa binarios Linux nativos, Wine no es necesario para ese proyecto y se puede simplificar la imagen considerablemente, eliminando el error `c0000018`.

**Cómo validar:** Ejecutar `file /app/modelo/pest_hp` dentro del contenedor.

**🟢 RESUELTO (inspección del modelo real CMDIC Rajos):** El modelo real
(`pest_ensi_v13`) usa un **esquema híbrido**:
- `pest_hp`, `agent_hp` y `mfusgt270` son **binarios Linux nativos** (se ejecutan
  directo, sin Wine).
- Las **utilidades de post-proceso SÍ requieren Wine**: `plproc.exe`,
  `usgbud2smp1.exe` y `usgmod2smp.exe` son ejecutables Windows invocados con `wine`
  dentro de `model.sh` en cada evaluación del modelo.

Conclusión: **Wine es necesario** para el modelo CMDIC Rajos (no se puede eliminar),
pero solo para las utilidades de post-proceso, no para el motor PEST/MODFLOW. El
`Dockerfile` de `calibrations/cmdic-rajos/` instala Ubuntu 24.04 + Wine por esta
razón. (Para Talabre, cuyos binarios son nativos y sin utilidades Windows, Wine sí
podría eliminarse — confirmar al recibir ese modelo.)

---

### OQ-05 — ¿Qué versión específica de PEST/PEST++ se usa?

**Pregunta:** ¿Qué versión de `pest_hp` está compilada en las imágenes Docker actuales?

**Por qué importa:** El formato de los mensajes de log (incluyendo Phi) y los criterios de convergencia pueden variar entre versiones. Los Metric Filters deben diseñarse para la versión correcta.

**Cómo validar:** Revisar el output de `pest_hp` sin argumentos o `pest_hp --version` si está disponible. O revisar el log del master de una calibración anterior.

---

### OQ-06 — ¿Múltiples proyectos corren simultáneamente en la misma VPC?

**Pregunta:** ¿Es posible que haya calibraciones de CMDIC y Talabre corriendo al mismo tiempo en la misma región y VPC?

**Por qué importa:** Si sí, los VPC Endpoints podrían compartirse entre proyectos (ahorro de costo). Si no, no hay beneficio en compartirlos.

**Impacto de la respuesta:** Define si la modularización de VPC Endpoints tiene valor económico real.

---

## Preguntas Científicas

### OQ-07 — ¿Cuál es la duración típica de una calibración completa y cuántos agentes se usan?

**Pregunta:** En calibraciones recientes que convergieron exitosamente: ¿cuántas horas tomaron? ¿Cuántos agentes se usaron en promedio?

**Por qué importa:**
- Define el TTL razonable de la infraestructura para las alarmas
- Define el costo estimado por calibración
- Define los umbrales de "tiempo sin actividad" para alertas
- Sirve para calibrar los umbrales de STAGNATED (si el modelo normalmente tarda 2 iteraciones, una ventana de 5 es excesiva)

**🟡 PARCIALMENTE RESUELTO (inspección del `.pst` real):** El modelo CMDIC Rajos
tiene **15.116 parámetros ajustables, 243 observaciones, 8 grupos de observación y
NOPTMAX=20**. El número de parámetros es el factor dominante del costo: cada
iteración calcula un Jacobiano que corre el modelo del orden de una vez por
parámetro, lo que justifica decenas a cientos de agentes en paralelo. Por eso el
`calibration.yaml` dimensiona `initial_agents: 50`, `max_agents: 300` y un master
con 32 GB RAM. **Falta aún** el dato empírico de duración total y nº de agentes de
una corrida que convergió (requiere ejecutar el modelo real o un log histórico);
el `ttl_hours: 96` del `calibration.yaml` es una red de seguridad conservadora,
no una medición.

---

### OQ-08 — ¿Cuántas iteraciones toman normalmente las calibraciones antes de converger?

**Pregunta:** En el histórico de calibraciones, ¿cuántas iteraciones PEST típicamente necesita para converger para los modelos Talabre y CMDIC?

**Por qué importa:** Define los parámetros de la ventana móvil para detección de STAGNATED. Una ventana de 5 iteraciones es muy pequeña si el modelo normalmente converge en 8–10, y muy grande si converge en 100+.

**🟡 PARCIALMENTE RESUELTO (inspección del `.pst` real):** El control PEST de CMDIC
Rajos (`CMDIC_Rajos.pst`) tiene **NOPTMAX = 20**, es decir, un tope de 20
iteraciones. Esto acota el máximo (no habrá convergencias en 100+ iteraciones) y
hace que la ventana por defecto de 5 iteraciones para STAGNATED sea razonable
(25% del máximo). Falta aún el dato histórico de **en cuántas iteraciones converge
típicamente** (requiere una corrida real o un log pasado) para afinar el umbral.
Los defaults de `QualityConfig` (ventana=5) son el punto de partida fundamentado.

---

### OQ-09 — ¿Se usa regularización en las calibraciones?

**Pregunta:** ¿Los archivos `.pst` de Talabre/CMDIC incluyen regularización? Si sí, ¿se monitorea Phi_medicion y Phi_regularizacion por separado?

**Por qué importa:** Con regularización, Phi_total puede reducirse por razones distintas a la mejora del ajuste a observaciones. Para clasificar la calidad de la calibración correctamente se necesita monitorear Phi_medicion separadamente.

---

## Preguntas de Gobernanza

### OQ-10 — ¿Existe alguna restricción corporativa sobre servicios AWS?

**Pregunta:** ¿Hay restricciones de política corporativa sobre el uso de servicios como Lambda, Step Functions, CodeBuild, o DynamoDB en la cuenta AWS usada para calibraciones?

**Por qué importa:** La arquitectura objetivo (Fase 6) usa Step Functions, Lambda y CodeBuild. Si alguno de estos servicios está bloqueado por política, la arquitectura propuesta debe ajustarse.

---

## Estado de las Preguntas

| ID | Pregunta | Urgencia | Estado |
|----|----------|----------|--------|
| OQ-01 | NAT Gateways activos | 🔴 URGENTE (costo) | 🟢 Resuelto (sin NAT; VPC con endpoints) |
| OQ-02 | Respaldo del terraform.tfstate | 🔴 URGENTE | 🟢 Resuelto (backend S3 versionado + lock DynamoDB) |
| OQ-03 | Formato líneas Phi en logs | 🟠 ALTA (bloquea Fase 2) | 🟢 Resuelto por literatura (confirmar con log real) |
| OQ-04 | Wine vs binarios Linux Talabre | 🟡 MEDIA | 🟢 Resuelto (híbrido: PEST nativo + utilidades Wine) |
| OQ-05 | Versión PEST | 🟡 MEDIA | Pendiente |
| OQ-06 | Proyectos simultáneos | 🔵 BAJA | Pendiente |
| OQ-07 | Duración y agentes típicos | 🟠 ALTA (bloquea umbrales) | 🟡 Parcial (dimensionamiento conocido; falta histórico) |
| OQ-08 | Iteraciones para converger | 🟡 MEDIA (bloquea Fase 3) | 🟡 Parcial (NOPTMAX=20; falta convergencia típica) |
| OQ-09 | Uso de regularización | 🟡 MEDIA (afecta Fase 3) | Pendiente |
| OQ-10 | Restricciones corporativas AWS | 🟡 MEDIA (afecta Fase 6) | Pendiente |

---

## Próximos Pasos para Resolver

**Reunión de revisión recomendada (30–60 min):**

1. Revisar OQ-01 en consola AWS durante la reunión (5 min, alta urgencia)
2. Confirmar OQ-02 con cada miembro del equipo que ejecuta Terraform
3. Obtener un log real del master de una calibración anterior para OQ-03
4. Responder OQ-07 con datos del histórico de calibraciones
5. Discutir OQ-10 con el área de infraestructura/cloud
