# Reporte de la POC - Plataforma de Calibraciones PEST en AWS

**Fecha:** 2 de octubre de 2026
**Cuenta AWS:** FlowHydro (803037204233), region us-east-1
**Usuario:** flowhydro-poc (IAM)
**Objetivo:** Validar el circuito end-to-end de la arquitectura con un modelo dummy,
sin esperar al modelo real, gastando el minimo posible de los creditos de POC.

---

## 1. Resumen ejecutivo

La POC valido **las cuatro fases implementadas** (estabilizacion, automatizacion IaC,
observabilidad y Quality Engine) ejecutando una calibracion simulada de punta a punta
en AWS. El circuito completo funciono: construccion de imagen, publicacion en ECR,
provisionamiento de infraestructura con Terraform, ejecucion en AWS Batch EC2, captura
de logs en CloudWatch, extraccion y clasificacion de calidad (Phi), y destruccion segura
con verificacion de resultados en S3.

**Resultado: EXITOSO.** Todos los eslabones del circuito objetivo quedaron demostrados.

---

## 2. Alcance de la prueba

| Aspecto | Decision para la POC | Motivo |
|---------|---------------------|--------|
| Modelo | Dummy (script que simula PEST_HP sin Wine) | Validar el circuito sin esperar el modelo real |
| Wine | NO (imagen Linux nativa) | El dummy no requiere binarios Windows; valida OQ-04 (es viable sin Wine) |
| Red | VPC dedicada minima con VPC Endpoints, sin NAT Gateway | Refleja la arquitectura objetivo (subred privada) sin costo fijo de NAT |
| Computo | AWS Batch EC2, instancia c7i-flex.large (Free Tier) | Minimo costo; cuenta nueva restringida a Free Tier |
| Modo | Autonomo (job master unico, sin agentes) | Suficiente para validar logs -> metricas -> clasificacion |

---

## 3. Componentes desplegados y validados

### Infraestructura persistente (se conserva)
- **S3 state backend:** `803037204233-pest-terraform-state` (versionado + cifrado)
- **DynamoDB lock:** `terraform-state-lock`
- **ECR:** `pest-poc-dummy` (imagen dummy, tag por commit SHA)
- **S3 resultados:** `803037204233-pest-poc-results` (contiene el result.dat del dummy)

### Infraestructura efimera (creada y destruida)
- **Red POC:** 1 VPC, 2 subredes privadas, route table, SG, 1 gateway endpoint (S3),
  9 interface endpoints (ECR, logs, ECS, SSM, etc.) - 17 recursos
- **Batch POC:** compute environment, job queue, job definition, IAM roles,
  security group, log group - 16 recursos

---

## 4. Circuito validado (end-to-end)

| # | Etapa | Resultado |
|---|-------|-----------|
| 1 | `terraform apply` red POC (backend remoto S3) | 17 recursos creados. Backend remoto operativo (F-01). |
| 2 | `docker build` imagen dummy (sin Wine, linux/amd64) | 554 MB, tag por commit SHA (reproducibilidad). |
| 3 | `docker push` a ECR | Digest `sha256:e3113a4b...` publicado. |
| 4 | `terraform apply` Batch POC | 16 recursos. Compute environment VALID. |
| 5 | `batch submit-job` calibracion dummy (CAL-20261002-002) | Job SUCCEEDED en instancia c7i-flex.large. |
| 6 | Logs del master en CloudWatch | Formato PEST correcto (iteraciones + Phi + convergencia). |
| 7 | Quality Engine sobre logs reales de AWS | Clasificacion correcta (ver seccion 5). |
| 8 | Resultado en S3 | `result.dat` subido a calibrations/CAL-20261002-002/modelo/. |
| 9 | `safe_destroy` - verificacion S3 (Property 3) | Detecta resultados: permitiria destruir; sin resultados: abortaria. |
| 10 | `terraform destroy` red + batch | 33 recursos destruidos. Cuenta limpia ($0/h). |

---

## 5. Validacion del Quality Engine (medicion de calidad)

Los logs reales del job en AWS fueron procesados por el Quality Engine:

**Evolucion de Phi extraida de los logs del master:**

```
Iteracion 1: 10000 -> 4000   (mejora 60%)
Iteracion 2:  4000 -> 1600   (mejora 60%)
Iteracion 3:  1600 -> 640    (mejora 60%)
Iteracion 4:   640 -> 256    (mejora 60%)
Iteracion 5:   256 -> 102    (mejora 60%)
Iteracion 6:   102 -> 40     (mejora 61%)
Final phi: 40    (reduccion total: 99.0%)
```

**Clasificacion:**

| Momento | Estado | Correcto |
|---------|--------|----------|
| Durante la calibracion (iter 3, sin mensaje de convergencia) | IMPROVING | SI (mejora > 1%) |
| Al final (mensaje "RELPARSTP" detectado) | CONVERGED | SI |

**Propiedades de correctitud verificadas en vivo:**
- **Property 1:** CONVERGED se asigno SOLO porque PEST emitio el mensaje explicito,
  no por inferir del Phi numerico.
- **Property 3:** safe_destroy detecto resultados en S3 para la calibracion real y
  habria abortado para una inexistente.

---

## 6. Hallazgos y aprendizajes de la POC

1. **Cuenta nueva restringida a Free Tier:** AWS Batch no pudo lanzar `optimal` ni
   `t3.small` por la politica de Free Tier de la cuenta. Solucion: usar
   `c7i-flex.large` (2 vCPU, Free Tier, aceptada por Batch). *Para el modelo real
   habra que solicitar aumento de cuota / levantar la restriccion Free Tier para
   usar las instancias de produccion (r6a.xlarge master, c7a.medium agentes).*
2. **Recrear un compute environment** requiere destruir primero la job queue que lo
   referencia (dependencia de Batch). Documentado para operacion.
3. **Terraform no borra buckets S3 con datos** (proteccion correcta). safe_destroy
   debe gestionar la evacuacion de resultados antes del destroy final.
4. **El circuito sin Wine funciona** (OQ-04): confirma que si los binarios PEST_HP
   son Linux nativos, la imagen puede prescindir de Wine.

---

## 7. Costo de la POC

| Recurso | Costo incurrido |
|---------|-----------------|
| Computo Batch (1 job, ~1 min, Free Tier) | ~$0 |
| VPC Endpoints (activos < 1 h) | centavos |
| S3 + DynamoDB + ECR (en reposo) | centavos/mes |
| **Total POC** | **< $1 de los $100 de credito** |

Tras la limpieza (Opcion 1): **$0/hora** de infraestructura efimera. Creditos
practicamente intactos para la prueba con el modelo real.

---

## 8. Estado y siguiente paso

**Validado:** las 4 fases (0-3) funcionan de punta a punta en AWS real.

**Siguiente:** prueba con el **modelo real** (ya recibido). Requiere:
- Colocar el modelo en `app/modelo/` (archivos .pst, .tpl, .ins, MODFLOW, binarios).
- Confirmar si los binarios pest_hp/agent_hp son Linux o Windows (define si la imagen
  usa Wine).
- Construir la imagen real y publicarla en ECR.
- Ajustar `terraform.tfvars` con el dimensionamiento del modelo (RAM, nro de agentes).
- Solicitar aumento de cuota EC2 si se usan instancias de produccion fuera de Free Tier.
- Lanzar la calibracion real por el mismo circuito ya validado.