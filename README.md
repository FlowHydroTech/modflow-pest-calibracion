# PEST Calibración — Modelos Hidrogeológicos en AWS

Repositorio para la ejecución paralela de calibraciones PEST de modelos hidrogeológicos (MODFLOW-USG) usando contenedores ECS Fargate en AWS.

## Índice

- [Descripción general](#descripción-general)
- [Arquitectura](#arquitectura)
- [Estructura del repositorio](#estructura-del-repositorio)
- [Requisitos](#requisitos)
- [Guía rápida: Configurar un nuevo proyecto](#guía-rápida-configurar-un-nuevo-proyecto)
- [Flujo operacional completo](#flujo-operacional-completo)
  - [Fase 0: Preparación del modelo](#fase-0-preparación-del-modelo)
  - [Fase 1: Docker build y push a ECR](#fase-1-docker-build-y-push-a-ecr)
  - [Fase 2: Despliegue de infraestructura](#fase-2-despliegue-de-infraestructura)
  - [Fase 3: Ejecución de la calibración](#fase-3-ejecución-de-la-calibración)
  - [Fase 4: Respaldo de resultados](#fase-4-respaldo-de-resultados)
  - [Fase 5: Limpieza](#fase-5-limpieza)
- [Referencia de comandos](#referencia-de-comandos)
- [Configuración por proyecto](#configuración-por-proyecto)
- [Monitoreo y logs](#monitoreo-y-logs)
- [Troubleshooting](#troubleshooting)
- [Notas para usuarios Mac (zsh)](#notas-para-usuarios-mac-zsh)

---

## Descripción general

PEST (Parameter ESTimation) calibra modelos numéricos ajustando parámetros hasta que el modelo reproduzca observaciones reales. Para un modelo con N parámetros, PEST necesita correr el modelo N veces por iteración (cálculo de la matriz Jacobiana), lo que sin paralelismo puede tomar días o semanas.

Esta plataforma paraleliza el proceso usando la arquitectura master-agents de PEST_HP sobre AWS ECS Fargate:

- Un **master** (`pest_hp.exe`) coordina la calibración y distribuye trabajo
- Múltiples **agents** (`agent_hp.exe`) ejecutan el modelo en paralelo (hasta 1498 simultáneos)
- Un **auto-scaler** lee los logs del master y ajusta dinámicamente la cantidad de agents

Con 450 parámetros, el Jacobiano pasa de ~450 horas (secuencial) a ~1 hora (450 agents en paralelo).

## Arquitectura

```
┌─────────────────────────────────────────────────────────────────────┐
│ AWS Cloud                                                           │
│                                                                     │
│  ┌──────────┐     ┌──────────┐     ┌──────────────────────────────┐ │
│  │   ECR    │     │    S3    │     │      CloudWatch Logs         │ │
│  │ (imagen) │     │ (backup) │     │ (master / agente / autonomo)│ │
│  └────┬─────┘     └────┬─────┘     └──────────────────────────────┘ │
│       │                │                        ▲                   │
│  ┌────┴────────────────┴────────────────────────┴──────────────────┐│
│  │ ECS Cluster (Fargate)                                           ││
│  │                                                                  ││
│  │  ┌─────────────────────┐    TCP:4004    ┌───────────────────┐   ││
│  │  │ Master (ECS Service)│◄──────────────►│ Agent 1 (ECS Task)│   ││
│  │  │ pest_hp.exe         │                └───────────────────┘   ││
│  │  │ 2 vCPU / 10 GB RAM │                ┌───────────────────┐   ││
│  │  │                     │◄──────────────►│ Agent 2 (ECS Task)│   ││
│  │  │ Service Discovery:  │                └───────────────────┘   ││
│  │  │ master.{proj}.local │                        ...             ││
│  │  └─────────────────────┘                ┌───────────────────┐   ││
│  │                                    ◄───►│ Agent N (ECS Task)│   ││
│  │                                         │ 1 vCPU / 3 GB RAM│   ││
│  │                                         └───────────────────┘   ││
│  └──────────────────────────────────────────────────────────────────┘│
│                                                                     │
│  VPC Endpoints: ECR API, ECR DKR, STS, Logs, SSM, SSMMessages,    │
│                 EC2Messages, S3 (Gateway)                           │
└─────────────────────────────────────────────────────────────────────┘
         ▲
         │ auto_scaling_tasks.py (máquina local)
         │ Lee logs del master cada 2-3 min
         │ Lanza/detiene agents según demanda
    ┌────┴────┐
    │ Laptop  │
    │ del     │
    │ usuario │
    └─────────┘
```

**Componentes clave:**

- **Master**: ECS Service Fargate (se reinicia solo si falla). Ejecuta `pest_hp.exe` en modo host paralelo, escucha en TCP:4004 para recibir conexiones de agents.
- **Agents**: ECS Tasks efímeros. Cada uno ejecuta `agent_hp.exe`, se conecta al master vía Service Discovery DNS (`master.{proyecto}.local:4004`), corre el modelo completo y devuelve resultados.
- **Auto-scaler**: Script Python que corre en la máquina local. Monitorea logs del master en CloudWatch, detecta cuántos agents necesita PEST y los lanza o detiene.
- **Service Discovery (Cloud Map)**: Registra la IP privada del master como `master.{proyecto}.local` para que los agents lo encuentren sin IPs hardcodeadas.
- **VPC Endpoints**: Permiten que los contenedores (sin IP pública) se comuniquen con servicios AWS (ECR, CloudWatch, S3, SSM).

**Cadena de ejecución del modelo (ensibatch.bat):**

```
ENSIMOD → PLPROC (kx, ss, vani) → MODFLOW-USG → get_flux.py → usgmod2obs → smpdiff
```

**Ciclo de PEST (una iteración):**

1. Corrida inicial del modelo (1 agent)
2. Cálculo del Jacobiano: corre el modelo N veces (N = cantidad de parámetros, en paralelo)
3. Lambda search: prueba ~37 combinaciones de parámetros
4. Si no converge y quedan iteraciones (NOPTMAX), vuelve al paso 2

## Estructura del repositorio

```
modflow-pest-calibracion/
├── Arquitectura/                              # Diagramas
│   ├── Arquitectura_pest.drawio               # Fuente editable (6 pestañas)
│   └── *.png                                  # Exportaciones de los diagramas
│
├── Calibracion_Modelo_PEST/                   # Modelos Docker por proyecto
│   ├── sqm_reservas/
│   │   ├── master/                            # Imagen Docker para mod_res_ensi
│   │   │   ├── Dockerfile
│   │   │   ├── requirements.txt
│   │   │   └── app/
│   │   │       ├── entrypoint_master.sh       # Entrypoint del master
│   │   │       ├── entrypoint_agent.sh        # Entrypoint del agent
│   │   │       ├── entrypoint_autonomo.sh     # Entrypoint modo autónomo (sin agents)
│   │   │       └── modelo/                    # Archivos PEST + MODFLOW (gitignored)
│   │   │           ├── mod_res_ensi.pst       # Control PEST
│   │   │           ├── ensibatch.bat           # Script de ejecución del modelo
│   │   │           ├── *.tpl, *.ins            # Templates e instructions PEST
│   │   │           └── ...                     # Datos MODFLOW, kriging, etc.
│   │   ├── master1/                           # Variante con Jacobiano existente
│   │   └── docker-local-mod-res-ensi/         # Docker Compose para test local
│   │
│   ├── Talabre/                               # Modelo Talabre
│   │   ├── master/                            # Imagen Docker para Talabre
│   │   └── docker_test/                       # Docker Compose para test local
│   │
│   └── Cloudwatch/                            # Scripts de consulta de logs
│       ├── get_task_logs.py                   # Descargar logs de un task
│       ├── get_log_streams.py                 # Listar log streams
│       ├── list_tasks.py                      # Listar tasks activos
│       ├── read_logs.py                       # Leer logs filtrados
│       ├── consolidate_logs.py                # Consolidar logs en CSV
│       └── cpu/                               # Métricas de CPU
│
├── IaC_terraform/                             # Infraestructura como código
│   ├── Arquitectura_regional/                 # Template base para nuevos proyectos
│   │   ├── main.tf                            # Terraform principal
│   │   ├── variables.tf                       # Variables configurables
│   │   ├── outputs.tf
│   │   ├── provider.tf
│   │   ├── auto_scaling_tasks.py              # Auto-scaler
│   │   ├── activar_agentes_pest.py            # Lanzar agents manualmente
│   │   └── desactivar_agentes_pest.py         # Detener todos los agents
│   │
│   ├── ModeloPest/                            # Configuraciones por proyecto
│   │   ├── mod_res_ensi/                      # Modelo SQM Reservas
│   │   │   ├── us-west-2/                     # Región Oregon
│   │   │   ├── us-east-2/                     # Región Ohio
│   │   │   └── us-east-1/                     # Región Virginia (sin auto-scaler)
│   │   └── talabre/                           # Modelo Talabre
│   │       └── regional/
│   │
│   └── Auditar_Generar_Terraform/             # Script de auditoría de recursos AWS
│
├── Documentación PEST/                        # Manuales oficiales PEST (PDFs)
├── Cronograma/                                # Gantt del proyecto
└── README.md                                  # Este archivo
```

**Nota sobre `app/modelo/`**: Los archivos del modelo están en `.gitignore` (`**/app/modelo/**`) porque son pesados (~2.5 GB por modelo) y específicos de cada calibración. Se proveen fuera de Git por el especialista hidrogeólogo.

## Requisitos

### Software

| Herramienta | Versión mínima | Instalación |
|-------------|---------------|-------------|
| AWS CLI v2 | 2.x | [aws.amazon.com/cli](https://aws.amazon.com/cli/) |
| Terraform | 1.0+ | [terraform.io](https://www.terraform.io/downloads) |
| Docker Desktop | 4.x | [docker.com](https://www.docker.com/products/docker-desktop/) |
| Python | 3.8+ | [python.org](https://www.python.org/) |
| Session Manager Plugin | Latest | [docs.aws.amazon.com](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html) |

### Dependencias Python

```bash
# Opción 1: pip (estándar)
pip install -r requirements.txt

# Opción 2: uv (más rápido, recomendado)
# Instalar uv: https://docs.astral.sh/uv/getting-started/installation/
uv pip install -r requirements.txt

# Opción 3: venv aislado con uv
uv venv .venv
source .venv/bin/activate   # Mac/Linux
# .venv\Scripts\activate    # Windows
uv pip install -r requirements.txt
```

El archivo `requirements.txt` incluye: `boto3`, `pandas`, `python-hcl2`, `pyyaml`, `openpyxl`.

### Credenciales AWS

```bash
# Verificar acceso
aws sts get-caller-identity

# Permisos necesarios: ECS, ECR, CloudWatch, S3, IAM, EC2 (VPC/SG), SSM, Service Discovery
```

### Nota importante sobre Docker en Mac con Apple Silicon (M1/M2/M3)

Fargate requiere imágenes **linux/amd64**. En Mac ARM, siempre usar `--platform linux/amd64` en el build:

```bash
docker build --platform linux/amd64 -t mi-imagen .
```

---

## Guía rápida: Configurar un nuevo proyecto

Para un modelo nuevo, usar `IaC_terraform/Arquitectura_regional/` como template:

```bash
# 1. Copiar el template
cp -r IaC_terraform/Arquitectura_regional/ IaC_terraform/ModeloPest/{nombre_proyecto}/
cd IaC_terraform/ModeloPest/{nombre_proyecto}/

# 2. Editar variables.tf con los valores del proyecto
#    (ver sección "Configuración por proyecto" más abajo)

# 3. Copiar los archivos del modelo al directorio Docker
#    (el especialista entrega los archivos)
cp -r /ruta/archivos/modelo/ /ruta/a/Calibracion_Modelo_PEST/{proyecto}/master/app/modelo/

# 4. Seguir el flujo operacional desde la Fase 1
```

---

## Flujo operacional completo

### Fase 0: Preparación del modelo

El especialista hidrogeólogo entrega los archivos del modelo:

- Archivos PEST: `.pst` (control), `.tpl` (templates), `.ins` (instructions)
- Archivos MODFLOW: `.dat`, `.nam`, `.gsf`, etc.
- Scripts: `.bat` (batch de ejecución), `.py` (post-proceso)
- Kriging factors, pilot points, zonas

El ingeniero de datos coloca estos archivos en:

```
Calibracion_Modelo_PEST/{proyecto}/master/app/modelo/
```

**Verificar el `.pst`**: La línea 9 del archivo `.pst` contiene NOPTMAX (máximo de iteraciones). Para pruebas rápidas, poner `1`.

```bash
# Ver NOPTMAX (primer número de la línea 9)
sed -n '9p' app/modelo/*.pst
# Ejemplo: "1      0.005  4     4     0.005   4"  →  NOPTMAX = 1
```

**Verificar los `.bat`**: Si los `.bat` llaman a Python, la ruta debe apuntar al ejecutable dentro de Wine:

```bash
# En los .bat, reemplazar:
#   "python ./get_flux.py"  →  "C:\python311\python.exe ./get_flux.py"
# Esto es necesario porque PEST corre bajo Wine en Linux
```

### Fase 1: Docker build y push a ECR

```bash
# Ir al directorio del Docker del proyecto
cd Calibracion_Modelo_PEST/{proyecto}/master/
```

**Crear repositorio ECR** (solo la primera vez):

<!-- tabs:start -->
#### **bash / zsh (Mac/Linux)**
```bash
aws ecr create-repository \
  --repository-name {nombre-repo} \
  --region {region}
```

#### **PowerShell (Windows)**
```powershell
aws ecr create-repository `
  --repository-name {nombre-repo} `
  --region {region}
```
<!-- tabs:end -->

**Build y push:**

<!-- tabs:start -->
#### **bash / zsh (Mac/Linux)**
```bash
# Build (en Mac ARM, siempre con --platform)
docker build --platform linux/amd64 \
  -t <account-id>.dkr.ecr.{region}.amazonaws.com/{nombre-repo}:latest .

# Login ECR
aws ecr get-login-password --region {region} | \
  docker login --username AWS --password-stdin \
  <account-id>.dkr.ecr.{region}.amazonaws.com

# Push
docker push <account-id>.dkr.ecr.{region}.amazonaws.com/{nombre-repo}:latest
```

#### **PowerShell (Windows)**
```powershell
# Build
docker build -t <account-id>.dkr.ecr.{region}.amazonaws.com/{nombre-repo}:latest .

# Login ECR
aws ecr get-login-password --region {region} | `
  docker login --username AWS --password-stdin `
  <account-id>.dkr.ecr.{region}.amazonaws.com

# Push
docker push <account-id>.dkr.ecr.{region}.amazonaws.com/{nombre-repo}:latest
```
<!-- tabs:end -->

### Fase 2: Despliegue de infraestructura

```bash
cd IaC_terraform/ModeloPest/{proyecto}/{region}/

# Editar variables.tf antes de desplegar
# (ver sección "Configuración por proyecto")

terraform init
terraform plan      # Revisar qué se va a crear (~45 recursos)
terraform apply     # Confirmar con "yes"
```

**⚠️ En Mac/zsh**: El `terraform apply` puede fallar en el último paso (`null_resource.run_agent_once`) porque usa PowerShell. Esto es esperable. Los 44 recursos anteriores se crean correctamente. El agent inicial se lanza manualmente en la Fase 3.

**Qué crea Terraform:**
- ECS Cluster + Task Definitions (master, agent, autonomo)
- IAM Roles (execution role, task role con acceso a S3/SSM/CloudWatch)
- Security Groups (master: ingress TCP:4004, agents: egress)
- VPC Endpoints (8 endpoints para conectividad sin IP pública)
- CloudWatch Log Groups (retención 30 días)
- Service Discovery (namespace + servicio DNS para el master)
- ECS Service del master (se inicia automáticamente)

### Fase 3: Ejecución de la calibración

El master se inicia automáticamente con el ECS Service. Verificar que esté corriendo:

<!-- tabs:start -->
#### **bash / zsh (Mac/Linux)**
```bash
# Verificar master
aws ecs list-tasks \
  --cluster {proyecto}-cluster-{region} \
  --service-name {proyecto}-master-service \
  --region {region} \
  --query "taskArns" --output text

# Ver logs del master
aws logs tail /ecs/{proyecto}-{region}-master --region {region} --follow
```

#### **PowerShell (Windows)**
```powershell
# Verificar master
aws ecs list-tasks `
  --cluster {proyecto}-cluster-{region} `
  --service-name {proyecto}-master-service `
  --region {region} `
  --query "taskArns" --output text
```
<!-- tabs:end -->

**Lanzar el primer agent** (necesario en Mac donde el `null_resource` falla, u opcionalmente en Windows si se quiere lanzar manualmente):

<!-- tabs:start -->
#### **bash / zsh (Mac/Linux)**
```bash
# Obtener el Security Group ID desde Terraform
SG_ID=$(terraform output -raw ecs_tasks_sg_id)

aws ecs run-task \
  --region {region} \
  --cluster {proyecto}-cluster-{region} \
  --launch-type FARGATE \
  --task-definition {proyecto}-task-agente-{region} \
  --count 1 \
  --enable-execute-command \
  --network-configuration "{
    \"awsvpcConfiguration\": {
      \"assignPublicIp\": \"DISABLED\",
      \"securityGroups\": [\"$SG_ID\"],
      \"subnets\": [\"subnet-xxx\", \"subnet-yyy\"]
    }
  }"
```

#### **PowerShell (Windows)**
```powershell
$SG_ID = terraform output -raw ecs_tasks_sg_id

$networkConfig = @"
{"awsvpcConfiguration":{"assignPublicIp":"DISABLED","securityGroups":["$SG_ID"],"subnets":["subnet-xxx","subnet-yyy"]}}
"@

aws ecs run-task `
  --region {region} `
  --cluster {proyecto}-cluster-{region} `
  --launch-type FARGATE `
  --task-definition {proyecto}-task-agente-{region} `
  --count 1 `
  --enable-execute-command `
  --network-configuration $networkConfig
```
<!-- tabs:end -->

**Iniciar el auto-scaler** (en una terminal separada, dejar corriendo):

```bash
cd IaC_terraform/ModeloPest/{proyecto}/{region}/
python3 auto_scaling_tasks.py  # Mac/Linux
python auto_scaling_tasks.py   # Windows
```

El auto-scaler:
1. Lee `variables.tf` para obtener configuración del cluster
2. Cada 2-3 minutos consulta los logs del master en CloudWatch
3. Detecta mensajes como `"Running model 450 times"` y lanza 450 agents
4. Detecta agents completados y los detiene
5. Se repite hasta que el usuario lo detenga con Ctrl+C

**Monitorear el progreso:**

<!-- tabs:start -->
#### **bash / zsh (Mac/Linux)**
```bash
# Contar agents activos
aws ecs list-tasks \
  --cluster {proyecto}-cluster-{region} \
  --family {proyecto}-task-agente-{region} \
  --desired-status RUNNING \
  --region {region} \
  --query "length(taskArns)" --output text

# Ver últimos logs del master (buscar "Running model")
aws logs filter-log-events \
  --log-group-name /ecs/{proyecto}-{region}-master \
  --filter-pattern "Running model" \
  --region {region} \
  --query "events[-5:].message" --output text
```

#### **PowerShell (Windows)**
```powershell
# Contar agents activos
aws ecs list-tasks `
  --cluster {proyecto}-cluster-{region} `
  --family {proyecto}-task-agente-{region} `
  --desired-status RUNNING `
  --region {region} `
  --query "length(taskArns)" --output text
```
<!-- tabs:end -->

### Fase 4: Respaldo de resultados

Cuando la calibración termina (o cuando el especialista lo solicita), hay que respaldar los resultados desde el contenedor del master a S3 y luego a la máquina local.

#### Paso 1: Conectar al master vía ECS Exec (SSM)

<!-- tabs:start -->
#### **bash / zsh (Mac/Linux)**
```bash
# Obtener el Task ID del master
TASK_ID=$(aws ecs list-tasks \
  --cluster {proyecto}-cluster-{region} \
  --service-name {proyecto}-master-service \
  --region {region} \
  --query 'taskArns[0]' --output text | awk -F'/' '{print $NF}')

echo "Task ID del master: $TASK_ID"

# Conectar al contenedor
aws ecs execute-command \
  --cluster {proyecto}-cluster-{region} \
  --task $TASK_ID \
  --container {proyecto}-master \
  --interactive \
  --command "/bin/bash" \
  --region {region}
```

#### **PowerShell (Windows)**
```powershell
# Obtener el Task ID del master
$TASK_ID = aws ecs list-tasks `
    --cluster {proyecto}-cluster-{region} `
    --service-name {proyecto}-master-service `
    --region {region} `
    --query 'taskArns[0]' `
    --output text | ForEach-Object { $_.Split('/')[-1] }

echo "Task ID del master: $TASK_ID"

# Conectar al contenedor
aws ecs execute-command `
  --cluster {proyecto}-cluster-{region} `
  --task $TASK_ID `
  --container {proyecto}-master `
  --interactive `
  --command "/bin/bash" `
  --region {region}
```
<!-- tabs:end -->

#### Paso 2: Dentro del contenedor, subir a S3

```bash
# Formato de backup: backup/YYYYMMDD_HHMM
aws s3 cp /app/modelo s3://{bucket}/backup/$(date +%Y%m%d_%H%M) --recursive

# Salir del contenedor
exit
```

#### Paso 3: Descargar a máquina local

```bash
# Crear carpeta de respaldo local
mkdir respaldo_{proyecto}_{region}_$(date +%Y%m%d_%H%M)
cd respaldo_{proyecto}_{region}_$(date +%Y%m%d_%H%M)

# Descargar desde S3
aws s3 sync s3://{bucket}/backup/{YYYYMMDD_HHMM} . --region {region}
```

### Fase 5: Limpieza

#### Detener agents manualmente (si el auto-scaler no lo hizo)

```bash
cd IaC_terraform/ModeloPest/{proyecto}/{region}/
python3 desactivar_agentes_pest.py  # Mac/Linux
python desactivar_agentes_pest.py   # Windows
```

#### Respaldar logs de CloudWatch

**⚠️ Hacer ANTES de `terraform destroy`**, ya que el destroy elimina los log groups y los logs se pierden permanentemente. Estos logs son esenciales para diagnosticar errores post-ejecución.

```bash
cd Calibracion_Modelo_PEST/Cloudwatch/

# Logs del master (progreso PEST, errores, asignación de agents)
python getLog.py \
  --log-group "/ecs/<nombre-proyecto>-<region>-master" \
  --region <region> \
  --start YYYY-MM-DD \
  --end YYYY-MM-DD \
  --output <nombre-proyecto>_<region>_master_logs_<fecha>.xlsx \
  --format excel

# Logs de agents (ejecución del modelo, tiempos, errores)
python getLog.py \
  --log-group "/ecs/<nombre-proyecto>-<region>-agente" \
  --region <region> \
  --start YYYY-MM-DD \
  --end YYYY-MM-DD \
  --output <nombre-proyecto>_<region>_agente_logs_<fecha>.xlsx \
  --format excel
```

Los archivos Excel resultantes contienen el log stream (identificador de cada task/máquina) en cada fila, lo que permite filtrar logs de un agent específico si se necesita investigar un error.

#### Destruir infraestructura (si ya no se necesita)

```bash
cd IaC_terraform/ModeloPest/{proyecto}/{region}/
terraform destroy
```

**⚠️ Antes de destruir:** Asegurarse de que los resultados están respaldados. `terraform destroy` elimina los log groups de CloudWatch (30 días de logs se pierden).

**⚠️ En Mac/zsh:** Si el destroy falla por el `null_resource`, eliminarlo del state primero:

```bash
terraform state rm null_resource.run_agent_once
terraform state rm time_sleep.wait_4_minutes
terraform destroy
```

---

## Referencia de comandos

### ECR (Elastic Container Registry)

| Acción | Comando |
|--------|---------|
| Crear repo | `aws ecr create-repository --repository-name {repo} --region {region}` |
| Login | `aws ecr get-login-password --region {region} \| docker login --username AWS --password-stdin <account-id>.dkr.ecr.{region}.amazonaws.com` |
| Build (Mac ARM) | `docker build --platform linux/amd64 -t <account-id>.dkr.ecr.{region}.amazonaws.com/{repo}:latest .` |
| Build (Windows/Linux) | `docker build -t <account-id>.dkr.ecr.{region}.amazonaws.com/{repo}:latest .` |
| Push | `docker push <account-id>.dkr.ecr.{region}.amazonaws.com/{repo}:latest` |

### ECS (Elastic Container Service)

| Acción | bash / zsh | PowerShell |
|--------|-----------|------------|
| Listar tasks | `aws ecs list-tasks --cluster {cluster} --region {region}` | (igual) |
| Contar agents | `aws ecs list-tasks --cluster {c} --family {f} --desired-status RUNNING --query "length(taskArns)" --output text` | (igual) |
| Conectar a master | Ver [Fase 4: Respaldo](#fase-4-respaldo-de-resultados) | Ver [Fase 4: Respaldo](#fase-4-respaldo-de-resultados) |
| Force redeploy | `aws ecs update-service --cluster {c} --service {s} --force-new-deployment --region {r}` | (igual, con backticks) |

### S3

| Acción | Comando |
|--------|---------|
| Crear bucket | `aws s3api create-bucket --bucket {bucket} --region {region} --create-bucket-configuration LocationConstraint={region}` |
| Backup (desde contenedor) | `aws s3 cp /app/modelo s3://{bucket}/backup/{fecha} --recursive` |
| Descargar respaldo | `aws s3 sync s3://{bucket}/backup/{fecha} . --region {region}` |
| Listar backups | `aws s3 ls s3://{bucket}/backup/ --region {region}` |

### Docker (utilidades)

| Acción | Comando |
|--------|---------|
| Limpiar imágenes no usadas | `docker image prune -a` |
| Limpiar build cache | `docker builder prune -f` |
| Ver historial de imagen | `docker history --no-trunc {imagen}` |
| Test local con compose | `cd Calibracion_Modelo_PEST/{proyecto}/docker-local-*/; docker-compose up -d` |

---

## Configuración por proyecto

Cada despliegue regional tiene un `variables.tf` que configura el proyecto. Los valores que **siempre** hay que ajustar para un nuevo proyecto o región:

```hcl
# --- Identificación del proyecto ---
variable "project_name"    { default = "<nombre-proyecto>" }     # Nombre único (se usa en todos los recursos)
variable "aws_region"      { default = "<region>" }              # Ej: us-west-2, us-east-2

# --- Red ---
variable "vpc_id"                  { default = "<vpc-id>" }              # VPC del despliegue
variable "private_subnet_ids"      { default = ["<subnet-1>", "<subnet-2>"] }  # Mínimo 2 subnets
variable "private_route_table_ids" { default = ["<rtb-id>"] }

# --- Almacenamiento e imágenes ---
variable "s3_bucket"   { default = "<account-id>-pest-<nombre-proyecto>-<region>" }
variable "ecr_image"   { default = "<account-id>.dkr.ecr.<region>.amazonaws.com/<nombre-proyecto>:latest" }

# --- PEST ---
variable "nombre_modelo_pest" { default = "<nombre-modelo>" }   # Nombre del .pst (sin extensión)
variable "nombre_jacobiano"   { default = "<nombre-jacobiano>" } # Prefijo del Jacobiano (ej: mod_res_1)
variable "ejecutable_master"  { default = "pest_hp.exe" }        # o beopest.exe
variable "ejecutable_agente"  { default = "agent_hp.exe" }
variable "comando_master"     { default = "/h" }                 # Modo host paralelo
variable "comando_agente"     { default = "/h" }
variable "pest_port"          { default = "4004" }               # Puerto TCP del master

# --- Agentes ---
variable "initial_count" { default = 1 }                         # Agents iniciales
variable "max_agents"    { default = 1498 }                      # Máximo de agents (límite Fargate)
```

**Ejemplo real** (proyecto mod-res-ensi en Oregon):
```hcl
variable "project_name"        { default = "pest-mod-res-ensi" }
variable "aws_region"          { default = "us-west-2" }
variable "vpc_id"              { default = "<vpc-id>" }
variable "private_subnet_ids"  { default = ["<subnet-az-a>", "<subnet-az-b>"] }
variable "s3_bucket"           { default = "<account-id>-pest-mod-res-ensi-west-2" }
variable "ecr_image"           { default = "<account-id>.dkr.ecr.us-west-2.amazonaws.com/pest-mod-res-ensi:latest" }
variable "nombre_modelo_pest"  { default = "mod_res_ensi" }
variable "nombre_jacobiano"    { default = "mod_res_1" }
```

### Convención de nombres

| Recurso | Formato |
|---------|---------|
| Cluster ECS | `{project_name}-cluster-{region}` |
| Task Def Master | `{project_name}-task-master-{region}` |
| Task Def Agent | `{project_name}-task-agente-{region}` |
| Service Master | `{project_name}-master-service` |
| Bucket S3 | `{account}-pest-{project_name}-{region}` |
| Log Group Master | `/ecs/{project_name}-{region}-master` |
| Log Group Agent | `/ecs/{project_name}-{region}-agente` |
| DNS Service Discovery | `master.{project_name}.local` |

### Proyectos activos

| Proyecto | Modelo | Regiones | Bucket |
|----------|--------|----------|--------|
| mod-res-ensi | SQM Reservas (MODFLOW-USG) | us-west-2, us-east-2 | `<account-id>-pest-mod-res-ensi-{region}` |
| talabre | Talabre | us-west-2 | `<account-id>-pest-talabre` |

---

## Monitoreo y logs

### CloudWatch Log Groups

Cada despliegue crea 3 log groups con retención de 30 días:

| Log Group | Contenido |
|-----------|-----------|
| `/ecs/{proyecto}-{region}-master` | Logs del master: progreso PEST, iteraciones, errores |
| `/ecs/{proyecto}-{region}-agente` | Logs de todos los agents: ejecución del modelo, tiempos |
| `/ecs/{proyecto}-{region}-autonomo` | Logs del modo autónomo (master + modelo en un solo task) |

### Consultas útiles de logs

```bash
# Últimos 20 logs del master
aws logs tail /ecs/{proyecto}-{region}-master --region {region} --since 1h

# Buscar errores en agents
aws logs filter-log-events \
  --log-group-name /ecs/{proyecto}-{region}-agente \
  --filter-pattern "ERROR" \
  --region {region} \
  --query "events[].message" --output text

# Ver progreso de iteraciones PEST
aws logs filter-log-events \
  --log-group-name /ecs/{proyecto}-{region}-master \
  --filter-pattern "Running model" \
  --region {region} \
  --query "events[].message" --output text
```

### Scripts de consulta (Calibracion_Modelo_PEST/Cloudwatch/)

| Script | Uso |
|--------|-----|
| `get_task_logs.py` | Descargar logs completos de un task específico |
| `get_log_streams.py` | Listar streams activos de un log group |
| `list_tasks.py` | Listar tasks activos en un cluster |
| `read_logs.py` | Leer logs con filtros personalizados |
| `consolidate_logs.py` | Consolidar logs de múltiples streams en CSV |

---

## Troubleshooting

### `terraform apply` falla con "PowerShell: executable file not found"

El `null_resource.run_agent_once` usa PowerShell. En Mac/Linux, esto falla. **No es un problema**: los 44 recursos anteriores se crean correctamente. Lanza el primer agent manualmente (ver Fase 3).

### El agent está RUNNING pero no tiene logs

El agent puede tardar 1-2 minutos en producir logs mientras inicializa Wine y verifica conectividad. Esperar y reintentar.

### El agent no conecta al master

Verificar:
1. Service Discovery registró al master: `aws servicediscovery list-instances --service-id {id} --region {region}`
2. Security Group del master permite ingress TCP:4004 desde el SG de agents
3. VPC endpoints están creados y activos: `aws ec2 describe-vpc-endpoints --region {region} --query "VpcEndpoints[].ServiceName"`

### `aws ecs execute-command` falla

Necesitas el Session Manager Plugin instalado. Verificar:
```bash
session-manager-plugin --version
```
Instalarlo desde: https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html

### El auto-scaler no detecta cambios en agents necesarios

El script busca keywords específicos en los logs del master:
- `"Running model"`
- `"Calculating Jacobian matrix"`
- `"Parallelisation of lambda search"`

Si PEST usa mensajes diferentes (otra versión), ajustar la variable `find_logs` en `auto_scaling_tasks.py`.

### Investigar un error en un agent específico

Cuando un agent falla, PEST le asigna un número y registra su IP en los logs del master. Para rastrear los logs de ese agent:

1. **Buscar el agent en los logs del master** (por número o por error):
   ```bash
   aws logs filter-log-events \
     --log-group-name /ecs/{proyecto}-{region}-master \
     --filter-pattern "agent" \
     --region {region} \
     --query "events[].message" --output text | grep -i "error\|fail\|agent 42"
   ```
   Esto muestra la IP del agent problemático (ej: `Agent host: "172.31.47.131"`).

2. **Encontrar el log stream del agent por IP** en el Excel de logs (si ya se exportó) o en CloudWatch:
   ```bash
   aws logs filter-log-events \
     --log-group-name /ecs/{proyecto}-{region}-agente \
     --filter-pattern "172.31.47.131" \
     --region {region} \
     --query "events[0].logStreamName" --output text
   ```

3. **Ver los logs completos de ese agent**:
   ```bash
   aws logs get-log-events \
     --log-group-name /ecs/{proyecto}-{region}-agente \
     --log-stream-name "ecs/{proyecto}-agente/{task-id}" \
     --region {region} \
     --query "events[].message" --output text
   ```

   O si se tiene el Excel exportado con `getLog.py`, simplemente filtrar la columna de log stream por el task-id del agent.

### Docker build falla por falta de espacio

```bash
docker system prune -a    # Elimina todo lo no usado (imágenes, containers, cache)
docker builder prune -f   # Solo build cache
```

### Terraform destroy falla por dependencias

Si quedan tasks corriendo al destruir:
```bash
# Primero detener todos los agents
python3 desactivar_agentes_pest.py

# Si sigue fallando, forzar la eliminación del service
aws ecs update-service \
  --cluster {proyecto}-cluster-{region} \
  --service {proyecto}-master-service \
  --desired-count 0 \
  --region {region}

# Esperar a que los tasks se detengan, luego
terraform destroy
```

---

## Notas para usuarios Mac (zsh)

### Diferencias principales con Windows/PowerShell

| Concepto | Windows (PowerShell) | Mac (zsh/bash) |
|----------|---------------------|----------------|
| Continuación de línea | `` ` `` (backtick) | `\` (backslash) |
| Variables | `$variable` | `$VARIABLE` |
| Docker build | `docker build -t ...` | `docker build --platform linux/amd64 -t ...` |
| `null_resource` en Terraform | Funciona | Falla (lanzar agent manual) |
| `Select-String` | Nativo | Usar `grep` |
| `ForEach-Object` | Nativo | Usar `awk` o `cut` |

### Alias útiles (agregar a `~/.zshrc`)

```bash
# Listar agents activos para un proyecto
pest-agents() {
  aws ecs list-tasks \
    --cluster "$1-cluster-$2" \
    --family "$1-task-agente-$2" \
    --desired-status RUNNING \
    --region "$2" \
    --query "length(taskArns)" --output text
}
# Uso: pest-agents <nombre-proyecto> <region>

# Conectar al master
pest-master() {
  TASK_ID=$(aws ecs list-tasks \
    --cluster "$1-cluster-$2" \
    --service-name "$1-master-service" \
    --region "$2" \
    --query 'taskArns[0]' --output text | awk -F'/' '{print $NF}')
  aws ecs execute-command \
    --cluster "$1-cluster-$2" \
    --task "$TASK_ID" \
    --container "$1-master" \
    --interactive \
    --command "/bin/bash" \
    --region "$2"
}
# Uso: pest-master <nombre-proyecto> <region>

# Tail logs del master
pest-logs() {
  aws logs tail "/ecs/$1-$2-master" --region "$2" --follow
}
# Uso: pest-logs <nombre-proyecto> <region>
```

---

## Histórico de cambios

| Fecha | Versión | Descripción |
|-------|---------|-------------|
| Oct 2025 | 1.0 | Arquitectura inicial con EC2 como master |
| Nov 2025 | 1.5 | Migración a ECS Fargate, auto-scaling manual |
| Dic 2025 | 2.0 | Multi-región con auto-scaling dinámico |
| Ene 2026 | 2.1 | Modelo mod_res_ensi en producción, 3 regiones |
| Feb 2026 | 2.2 | Documentación unificada, soporte Mac/zsh |

---

**Branches**: `main` (estable), `dev` (desarrollo activo)  
**Última actualización**: Febrero 2026
