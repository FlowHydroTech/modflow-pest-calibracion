# AGENTS.md — Memoria del proyecto para el agente

> Contexto persistente para Kiro (y cualquier agente). Léelo al iniciar sesión.
> Viaja con el repo vía git, así que reemplaza la "memoria" de un chat anterior
> al cambiar de equipo. Si algo aquí contradice el código, el código manda:
> verifica y actualiza este archivo.

---

## Qué es este proyecto

Plataforma para ejecutar **calibraciones PEST de modelos hidrogeológicos MODFLOW
en AWS**. En vez de operar servidores a mano, el modelo se empaqueta en una imagen
Docker, se ejecuta en **AWS Batch** (que levanta y apaga EC2 solo), y el avance se
observa desde CloudWatch. Corre en modo **Master-Agente**: el master (`pest_hp`)
dirige la optimización y mide **Phi** (la "nota" del ajuste; menor = mejor); los
agentes (`agent_hp`) corren el modelo en paralelo y le responden por TCP 4004.

Dos planos:
- **Control Plane** (no cambia entre modelos): `calibration_utils/`, `lambdas/`,
  `scripts/` — orquestación, métricas, autoscaling, destrucción segura. Python.
- **Compute Plane** (NO se toca): AWS Batch EC2 que ejecuta PEST + MODFLOW.

---

## Rama de trabajo (IMPORTANTE)

- Trabajamos SIEMPRE en la rama **`modflow-pest-calibracion-kiro`**.
- **NUNCA tocar `main`.** La rama `fase1/auditoria-y-documentacion` se deja como
  trazabilidad histórica (no trabajar en ella).
- Remoto: `github.com/FlowHydroTech/modflow-pest-calibracion.git`.
- Rutina: `git checkout modflow-pest-calibracion-kiro` → `git pull` al empezar →
  commitear → `git push` al terminar. Al usar dos equipos, push en uno antes de
  pull en el otro para no divergir.

---

## Estado actual (resumen)

Auditada (23 docs), especificada (spec formal), implementada (Fases 0-3, **53
tests pasan**), validada con **POC end-to-end real en AWS** (modelo dummy, <$1), y
con **pipeline reproducible + guía paso a paso listos** para el modelo real.

**Siguiente paso:** ejecutar la calibración REAL de CMDIC Rajos siguiendo
`docs/GUIA_PASO_A_PASO.md`. Bloqueos que dependen del usuario: (1) copiar el modelo
real a `calibrations/cmdic-rajos/app/modelo/`, (2) subir la cuota de vCPU EC2
(`L-1216C47A`, hoy 5).

**El detalle completo y siempre actualizado del estado vive en
`docs/auditoria/ESTADO_Y_CONTINUACION.md`** — ese es el documento de traspaso
canónico. Este AGENTS.md es el índice de entrada.

---

## Mapa del repo (dónde está cada cosa)

| Ruta | Qué es |
|------|--------|
| `docs/auditoria/ESTADO_Y_CONTINUACION.md` | **Documento de traspaso canónico** (estado, commits, próximos pasos) |
| `docs/GUIA_PASO_A_PASO.md` | Guía de 10 secciones para ejecutar una calibración (Tecnología + Modelación) |
| `docs/auditoria/` (23 docs) | Auditoría técnica: hallazgos F-01..F-22, roadmap, open questions (22), research Phi (23) |
| `docs/poc/REPORTE_POC.md` | Reporte de la POC end-to-end en AWS |
| `.kiro/specs/pest-calibration-platform/` | Spec formal: design.md (9 correctness properties), requirements.md (19 EARS), tasks.md (35 tareas) |
| `calibration_utils/` | Control Plane: config, batch, cloudwatch, metrics, quality |
| `lambdas/autoscaler/`, `lambdas/extract_phi/` | Lambdas de escalado y extracción de Phi |
| `scripts/safe_destroy.py` | Destrucción segura (verifica S3 antes de destruir) |
| `calibrations/cmdic-rajos/` | Pipeline reproducible del modelo real (Dockerfile+Wine, entrypoints, calibration.yaml) |
| `IaC_terraform/` | Terraform: bootstrap (backend), módulo talabre-linux/us-east-1 (Batch) |

---

## Lo que NO está en git (copiar aparte en cada equipo)

| Qué | Dónde | Cómo |
|-----|-------|------|
| Modelo real (~5.2 GB) | `modelacion/` y `calibrations/cmdic-rajos/app/modelo/` | USB/disco externo. NUNCA por git (está en .gitignore). |
| Credenciales AWS | `~/.aws/` perfil `flowhydro-poc` | `aws configure --profile flowhydro-poc` |
| Terraform locales | `terraform.tfvars`, `backend.hcl` | Recrear desde los `.example` (guía §5). El tfstate vive en backend S3. |
| Herramientas | — | AWS CLI, Terraform, Docker, 7-Zip, Python (guía §3.1) |

---

## Decisiones y lecciones críticas (NO re-descubrir)

1. **Encoding UTF-8 sin BOM SIEMPRE** al escribir archivos con PowerShell
   (`New-Object System.Text.UTF8Encoding $false` + `WriteAllText`). `Get-Content
   -Raw` + `WriteAllText` sin encoding corrompe acentos (o-acento -> Ã³). Las
   herramientas de edición del agente ya escriben UTF-8; cuidado solo con scripts PS.
2. **Line endings LF** forzados por `.gitattributes` en *.sh/*.py/*.tf. CRLF rompe
   bash en los contenedores Linux de Batch.
3. **Login ECR en Windows:** token en variable, NO pipe directo
   (`$t=(aws ecr get-login-password).Trim(); $t | docker login ...`). Pipe directo
   da 400 Bad Request.
4. **docker build** siempre `--platform linux/amd64 --provenance=false` (Batch es
   amd64; evita "exec format error").
5. **Cuenta nueva = Free Tier restringido.** Batch rechaza t3.small/optimal/t3.micro;
   la POC usó `c7i-flex.large`. El modelo real necesita subir la cuota vCPU.
6. **Modelo real CMDIC necesita Wine (híbrido):** `pest_hp`/`agent_hp`/`mfusgt270`
   son Linux nativos; `plproc.exe`/`usgbud2smp1.exe`/`usgmod2smp.exe` son .exe
   Windows que `model.sh` corre con wine.
7. **CMDIC_Rajos.pst:** 15.116 parámetros, 243 observaciones, 8 grupos, NOPTMAX=20.
8. **AWS:** cuenta FlowHydro `803037204233`, región `us-east-1`, perfil
   `flowhydro-poc`. CLI en `C:\Program Files\Amazon\AWSCLIV2\aws.exe`. Siempre
   `$env:AWS_PAGER=""; $env:AWS_PROFILE="flowhydro-poc"`.
9. **Infra AWS persistente (no destruir):** bucket state
   `803037204233-pest-terraform-state`, DynamoDB `terraform-state-lock`, ECR
   `pest-poc-dummy`, bucket `803037204233-pest-poc-results`. La infra de cómputo de
   la POC YA fue destruida (cuenta en ~$0/h).
10. **Terraform:** `aws_batch_compute_environment` usa `compute_environment_name`
    (no `name`). Variables con `type` Y `default` en una línea fallan (multilínea).
    Validar con `-backend=false`; limpiar `.terraform/` tras validar.

---

## Cómo trabajamos (preferencias)

- **No sobreingenierizar.** Resolver lo que se pide, sin abstracciones de más.
- **No añadir tests salvo que se pidan** explícitamente.
- Responder y documentar **en español**.
- Verificar antes de afirmar que algo funciona (correr tests/build/comando real).
- **Nunca commitear** `modelacion/`, datos del modelo, credenciales ni
  `terraform.tfvars`/`backend.hcl`. Al commitear, agregar archivos por nombre
  (no `git add .`) y revisar `git diff --cached --stat`.
- Tests: `cd <repo>; $env:PYTHONPATH="."; python -m pytest tests/`

---

## Pendiente / futuro (no bloquea)

- Ejecutar la calibración real (ver `ESTADO_Y_CONTINUACION.md` §6 y la guía).
- Confirmar OQ-03 (formato log Phi) y OQ-05 (versión PEST) en la 1a corrida real.
- **Floci** (emulador local de AWS, github.com/floci-io/floci): posible capa de
  tests de integración del Control Plane sin costo. NO reemplaza la corrida real en
  Batch. Evaluar con una POC chica antes de invertir.
