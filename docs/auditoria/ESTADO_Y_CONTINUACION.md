# Estado del Proyecto y Guia de Continuacion

> Documento de traspaso para continuar el trabajo en una nueva sesion.
> **Ultima actualizacion:** cierre de sesion tras POC exitosa + preparacion del
> pipeline reproducible para el modelo real CMDIC Rajos.

---

## 0. Resumen en una frase

La plataforma de calibraciones PEST en AWS esta: auditada (23 docs), especificada
(spec formal), implementada en codigo (Fases 0-3, 53 tests pasan), validada con una
**POC end-to-end real en AWS** (modelo dummy, costo <$1), y con el **pipeline
reproducible + guia paso a paso listos** para ejecutar el modelo real. Falta copiar
el modelo real a su carpeta, subir la cuota de vCPU, y lanzar la calibracion real.

---

## 1. Rama de trabajo

**Toda la actividad ocurre en la rama:** `fase1/auditoria-y-documentacion`

```bash
git checkout fase1/auditoria-y-documentacion
```

Parte de `main`. NO se ha hecho push ni merge a main todavia.

---

## 2. Historial de commits de esta linea de trabajo

| Commit | Descripcion |
|--------|-------------|
| `7ce79c6` | docs: auditoria tecnica completa (23 documentos en docs/auditoria/) |
| `4ec79a1` | spec: pest-calibration-platform (design, requirements, tasks) |
| `d6efc48` | research: resolver OQ-03 formato de logs Phi via estado del arte |
| `a3935da` | fix(fase0): corregir bug RETRY_CODE + shebang/set -e en entrypoints |
| `35b83bd` | feat(fase0): estabilizacion - backend TF, IAM, limpieza secretos, gitattributes |
| (fase1) | feat(fase1): config + batch + autoscaler + safe_destroy + archivado legacy |
| (fase2) | feat(fase2): observabilidad (metrics.py, observability.tf, validate_phi_log) |
| (fase3) | feat(fase3): quality engine (quality.py) + lambda extract_phi |
| (poc)   | feat: POC end-to-end en AWS + docs/poc/REPORTE_POC.md |
| **PENDIENTE DE COMMIT** | guia paso a paso + estructura calibrations/cmdic-rajos/ + open questions actualizadas |

> **IMPORTANTE:** al abrir la proxima sesion, verificar `git log --oneline` y
> `git status` para confirmar que el ultimo bloque (guia + cmdic-rajos) quedo
> commiteado. Si NO lo esta, ver seccion 7.

---

## 3. Que se completo (acumulado)

### Auditoria tecnica (docs/auditoria/) - 23 docs
Executive summary, arquitectura actual, 22 hallazgos (F-01..F-22), IaC, compute,
observabilidad, calidad, dashboard, alertas, FinOps, seguridad, resiliencia,
reproducibilidad, arquitectura objetivo, roadmap, quick wins, open questions.

### Spec (.kiro/specs/pest-calibration-platform/)
design.md (9 correctness properties), requirements.md (19 reqs EARS), tasks.md
(35 tareas, 6 fases). Los tres VALIDADOS.

### Codigo Fases 0-3 (53 tests pasan)
- `calibration_utils/`: config.py, batch.py, cloudwatch.py, metrics.py, quality.py
- `lambdas/autoscaler/`, `lambdas/extract_phi/`
- `scripts/safe_destroy.py`, `scripts/validate_phi_log_format.py`
- IaC: bootstrap backend remoto, observability.tf (SNS + alarmas)
- Comando de tests: `cd <repo>; $env:PYTHONPATH="."; python -m pytest tests/`

### Infraestructura AWS desplegada (PERSISTENTE, no destruir)
Cuenta FlowHydro `803037204233`, region `us-east-1`, perfil `flowhydro-poc`:
- Bucket S3 state `803037204233-pest-terraform-state` (versionado + cifrado)
- DynamoDB `terraform-state-lock`
- ECR `pest-poc-dummy` (imagen de la POC)
- Bucket S3 `803037204233-pest-poc-results`

### POC end-to-end (COMPLETA, infra de computo YA DESTRUIDA)
- Documentada en `docs/poc/REPORTE_POC.md`
- Se desplego VPC dedicada minima (sin NAT, con VPC Endpoints) + Batch, se corrio
  un modelo dummy, los logs con formato PEST llegaron a CloudWatch, el result.dat a
  S3, y se valido el Quality Engine en vivo (IMPROVING -> CONVERGED, reduccion 99%)
  y safe_destroy (Property 3).
- Instancia que acepto Batch en cuenta nueva Free Tier: **c7i-flex.large**.
- Red (17 recursos) + Batch (16 recursos) **DESTRUIDOS** (opcion 1 de limpieza).
  La cuenta esta en ~$0/h en reposo.
- Costo total de la POC: **menos de 1 USD**.

### Pipeline reproducible para el modelo real (NUEVO en esta sesion)
- `calibrations/cmdic-rajos/`: Dockerfile (Ubuntu 24.04 + Wine), entrypoints
  (master/agent/autonomo), `calibration.yaml` (dimensionado y validado),
  requirements.txt, README.md, .gitignore (excluye app/modelo/*).
- `app/modelo/` esta VACIO (solo .gitkeep): el modelo real NO se versiona (~4.5 GB).
- `docs/GUIA_PASO_A_PASO.md`: guia completa de 10 secciones para Tecnologia y
  Modelacion (intro, roles, prerequisitos, glosario, 10 pasos, monitoreo/metricas,
  troubleshooting, FinOps, reproducibilidad, referencias).

### Modelo real CMDIC Rajos (inspeccionado, NO copiado al repo)
- Archivo original: `modelacion/pest_ensi_v13.rar` (635 MB -> 4.56 GB descomprimido
  en `modelacion/extracted/pest_ensi_v13/`). `modelacion/` esta git-ignored.
- Control PEST `CMDIC_Rajos.pst`: **15.116 parametros, 243 observaciones, 8 grupos,
  NOPTMAX=20**. Comando de modelo: `./model.sh`.
- **Necesita Wine (esquema hibrido):** `pest_hp`, `agent_hp`, `mfusgt270` son
  binarios Linux nativos; PERO `plproc.exe`, `usgbud2smp1.exe`, `usgmod2smp.exe`
  son .exe Windows que `model.sh` ejecuta con wine.
- Archivos grandes: `.gsf` 514 MB, `.dis` 343 MB.

---

## 4. Decisiones y lecciones criticas (NO re-descubrir)

1. **Encoding UTF-8 sin BOM SIEMPRE.** Al escribir archivos con PowerShell usar
   `New-Object System.Text.UTF8Encoding $false` + `WriteAllText`. Un
   `Get-Content -Raw` + `WriteAllText` sin encoding corrompe acentos (ó -> Ã³).
2. **Line endings LF** forzados por `.gitattributes` en *.sh/*.py/*.tf. CRLF rompe
   bash en los contenedores Linux de Batch.
3. **Login ECR en Windows:** capturar el token en variable, NO pipe directo
   (`$token = (aws ecr get-login-password).Trim(); $token | docker login ...`).
   El pipe directo falla con 400 Bad Request.
4. **docker build** siempre `--platform linux/amd64 --provenance=false` (Batch EC2
   es amd64; evita manifests multi-arch que dan "exec format error").
5. **Cuenta nueva = Free Tier restringido.** Batch rechaza t3.small/optimal/t3.micro;
   la POC uso c7i-flex.large. El modelo real necesita subir la cuota vCPU.
6. **AWS CLI:** `C:\Program Files\Amazon\AWSCLIV2\aws.exe`. Siempre
   `$env:AWS_PAGER=""; $env:AWS_PROFILE="flowhydro-poc"`.
7. **Terraform:** `aws_batch_compute_environment` usa `compute_environment_name`
   (no `name`). Variables TF con `type` Y `default` en una linea fallan (usar
   multilinea). Validar con `-backend=false`; limpiar `.terraform/` tras validar.
8. **Herramientas locales:** 7-Zip `C:\Program Files\7-Zip\7z.exe`, Docker 29.7.2,
   Python 3.13 (miniforge) con pytest/hypothesis/moto/boto3/pyyaml instalados.

---

## 5. Preguntas abiertas (estado actual)

| ID | Estado | Nota |
|----|--------|------|
| OQ-01 (NAT Gateways) | 🟢 RESUELTO | Arquitectura sin NAT (VPC Endpoints). Revisar stacks legacy en cuenta antigua si existen. |
| OQ-02 (backup tfstate) | 🟢 RESUELTO | Backend remoto S3 versionado + lock DynamoDB desplegado. |
| OQ-03 (formato logs Phi) | 🟢 RESUELTO (por literatura) | Patrones en doc 23. Confirmar con log real del master en la 1a corrida real. |
| OQ-04 (Wine vs nativo) | 🟢 RESUELTO | CMDIC es hibrido: PEST/MODFLOW nativos + utilidades .exe via Wine -> Wine SI necesario. |
| OQ-05 (version PEST) | 🟡 PENDIENTE | `file`/`--version` sobre pest_hp dentro del contenedor. |
| OQ-07 (duracion tipica) | 🟡 PARCIAL | Dimensionamiento conocido (15116 params). Falta duracion/agentes de corrida historica. |
| OQ-08 (iteraciones tipicas) | 🟡 PARCIAL | NOPTMAX=20 conocido. Falta en cuantas converge tipicamente. |
| OQ-09 (regularizacion) | 🟡 PENDIENTE | Revisar seccion de regularizacion del .pst real. |
| OQ-10 (restricciones AWS) | 🟡 PENDIENTE | Afecta Fase 6 (Step Functions/Lambda/CodeBuild). |

Detalle completo en `docs/auditoria/22_open_questions.md`.

---

## 6. SIGUIENTE PASO: ejecutar la calibracion REAL (CMDIC Rajos)

Seguir la `docs/GUIA_PASO_A_PASO.md` paso a paso. Resumen de lo que falta, en orden:

### Bloqueos que dependen del usuario (hacer PRIMERO, en paralelo)
1. **Copiar el modelo real** a `calibrations/cmdic-rajos/app/modelo/` (hoy vacio).
   Fuente ya descomprimida: `modelacion/extracted/pest_ensi_v13/`. Copiar el
   contenido (los archivos, no la carpeta contenedora).
2. **Solicitar aumento de cuota vCPU EC2** (`L-1216C47A`, hoy = 5). Service Quotas
   -> EC2 -> "Running On-Demand Standard instances". AWS tarda minutos a 1-2 dias.
   Pedir un valor acorde a max_agents (ej. 300 agentes c7a.medium -> pedir ~350-400).

### Pasos tecnicos (ya documentados en la guia, secciones 3-10)
3. Revisar `calibrations/cmdic-rajos/calibration.yaml` (completar `alert_email`).
4. Build imagen Docker (con Wine) + tag por commit SHA.
5. Crear repo ECR `pest-cmdic-rajos` + push.
6. Preparar `terraform.tfvars` + `backend.hcl` (key `pest-cmdic-rajos/...`).
7. `terraform apply` del modulo talabre-linux/us-east-1 (red + Batch).
8. `python launch_master_agents.py 50` (master + agentes).
9. Monitorear: CloudWatch Logs + metricas namespace `PEST/Calibration`.
10. Interpretar Phi (Modelacion decide convergencia).
11. `safe_destroy` + `terraform destroy` + descargar resultados de S3.

### Primera verificacion al correr real (confirma OQ-03/OQ-05)
En el primer log del master, confirmar que las lineas de Phi matchean los patrones
de `lambdas/extract_phi/` (correr `scripts/validate_phi_log_format.py` contra un
tramo de log real). Y capturar la version de PEST (OQ-05).

### Opcional / futuro (NO bloquea la POC)
- **Floci** (https://github.com/floci-io/floci): emulador local de AWS, posible capa
  de tests de integracion del Control Plane (Terraform plan + boto3 sin costo). NO
  reemplaza la corrida real en Batch (no ejecuta la calibracion PEST). Evaluar con
  una POC chica (terraform plan del modulo de red contra Floci) antes de invertir.

---

## 7. Comando para retomar rapido

```powershell
cd c:\Users\Cesar\aws-calibracion\modflow-pest-calibracion
git checkout fase1/auditoria-y-documentacion
git log --oneline -10          # confirmar que guia + cmdic-rajos estan commiteados
git status                     # debe estar limpio (modelacion/ y app/modelo/* ignorados)
# Leer este documento y docs/GUIA_PASO_A_PASO.md
# Continuar en la seccion 6: ejecutar la calibracion real
```

### Si el bloque "guia + cmdic-rajos" NO quedo commiteado:
```powershell
git add docs/GUIA_PASO_A_PASO.md docs/auditoria/22_open_questions.md `
        docs/auditoria/ESTADO_Y_CONTINUACION.md calibrations/
git status   # verificar que modelacion/ y calibrations/.../app/modelo/* NO aparecen
git commit -m "docs: guia paso a paso + estructura reproducible cmdic-rajos + open questions"
```
