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

---

### OQ-02 — ¿Existe respaldo del terraform.tfstate actual?

**Pregunta:** ¿El `terraform.tfstate` de los módulos activos (`talabre-linux/us-east-1`, `Arquitectura_regional`) está respaldado en algún lugar fuera de las máquinas locales del equipo?

**Por qué importa:** Si el state local se pierde, `terraform destroy` fallará y los recursos quedarán huérfanos. Antes de migrar al backend S3, necesitamos saber si existe recuperación.

**Impacto de la respuesta:** Define si la migración al backend S3 puede hacerse directamente (`terraform init -migrate-state`) o si hay que reconstruir el state.

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

---

### OQ-04 — ¿PEST HP usa binarios Windows (Wine) o Linux nativos para Talabre?

**Pregunta:** ¿Los ejecutables `pest_hp` y `agent_hp` usados en `talabre-linux` son binarios Linux nativos o Windows ejecutados via Wine?

**Contexto:** El `Dockerfile` de `talabre_pest/` instala Wine pero el `chmod +x` sobre `pest_hp` y `agent_hp` sin extensión `.exe` sugiere que podrían ser binarios Linux. El `Dockerfile` de `Estructura_Base` (para CMDIC) sí usa Wine explícitamente en `ensibatch.sh` para múltiples herramientas (`wine ./plproc.exe`, etc.).

**Por qué importa:** Si Talabre usa binarios Linux nativos, Wine no es necesario para ese proyecto y se puede simplificar la imagen considerablemente, eliminando el error `c0000018`.

**Cómo validar:** Ejecutar `file /app/modelo/pest_hp` dentro del contenedor.

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

---

### OQ-08 — ¿Cuántas iteraciones toman normalmente las calibraciones antes de converger?

**Pregunta:** En el histórico de calibraciones, ¿cuántas iteraciones PEST típicamente necesita para converger para los modelos Talabre y CMDIC?

**Por qué importa:** Define los parámetros de la ventana móvil para detección de STAGNATED. Una ventana de 5 iteraciones es muy pequeña si el modelo normalmente converge en 8–10, y muy grande si converge en 100+.

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
| OQ-01 | NAT Gateways activos | 🔴 URGENTE (costo) | Pendiente |
| OQ-02 | Respaldo del terraform.tfstate | 🔴 URGENTE | Pendiente |
| OQ-03 | Formato líneas Phi en logs | 🟠 ALTA (bloquea Fase 2) | Pendiente |
| OQ-04 | Wine vs binarios Linux Talabre | 🟡 MEDIA | Pendiente |
| OQ-05 | Versión PEST | 🟡 MEDIA | Pendiente |
| OQ-06 | Proyectos simultáneos | 🔵 BAJA | Pendiente |
| OQ-07 | Duración y agentes típicos | 🟠 ALTA (bloquea umbrales) | Pendiente |
| OQ-08 | Iteraciones para converger | 🟡 MEDIA (bloquea Fase 3) | Pendiente |
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
