# modflow-pest-calibracion

Repositorio dedicado a la ejecución de Modelos de Calibración PEST con arquitectura en AWS utilizando múltiples regiones y servicios de contenedorización.

## Arquitectura

La arquitectura final del proyecto utiliza una estrategia multi-regional en AWS:

![Arquitectura Regional Final](Arquitectura/Arquitectura%20Regional%20Final.png)

**Características principales:**
- Despliegue en múltiples regiones AWS (us-east-1, us-east-2, us-west-2)
- Servicios ECS Fargate para orquestación de contenedores
- Auto-escalado dinámico de agentes PEST
- Monitoreo centralizado con CloudWatch
- Almacenamiento distribuido con S3
- Gestión de infraestructura con Terraform IaC

## Estructura del Repositorio

```
modflow-pest-calibracion/
├── Arquitectura/                          # Diagramas y documentación de arquitectura
│   ├── Arquitectura_pest.drawio           # Diagramas editables en drawio
│   ├── Arquitectura Regional Final.png    # Arquitectura final utilizada (Multi-región)
│   ├── Arquitectura Multiregional.png     # Diseño multiregional
│   ├── Arquitectura_pest.png              # Arquitectura base
│   ├── Arquirtectura Regional.png         # Arquitectura regional
│   ├── Auto escalado.png                  # Documentación de auto-escalado
│   └── Planilla de costos.png             # Análisis de costos
│
├── Calibracion_Modelo_PEST/               # Configuración y modelos PEST
│   ├── AWS_Comandos/                      # Scripts y comandos para AWS
│   │   ├── AWS_ECR_carga_imagen_docker.ps1
│   │   ├── Docker_comandos.ps1
│   │   ├── EC2_conectar_a_consola_ssm.ps1
│   │   ├── ECS_Fargate_comandos.ps1
│   │   ├── S3_comandos.ps1
│   │   └── cambios terraform.txt
│   ├── Cloudwatch/                        # Scripts de monitoreo y logs
│   │   ├── comandos_logs.ps1
│   │   ├── get_task_logs.py
│   │   ├── get_log_streams.py
│   │   ├── get_task_id.py
│   │   ├── list_tasks.py
│   │   ├── read_logs.py
│   │   ├── cpu/                           # Métricas de CPU
│   │   │   ├── cpu.py
│   │   │   ├── cpu.ps1
│   │   │   ├── cpu.json
│   ├── sqm_reservas/                      # Modelos SQM Reservas
│   │   ├── docker-local-mod-res-ensi/     # Docker Compose local
│   │   │   └── docker-compose.yml
│   │   ├── master/                        # Contenedor maestro (Docker)
│   │   │   ├── Dockerfile
│   │   │   ├── requirements.txt
│   │   │   └── app/
│   │   │       ├── entrypoint_master.sh
│   │   │       ├── entrypoint_agent.sh
│   │   │       ├── entrypoint_autonomo.sh
│   │   │       └── modelo/                # Archivos PEST
│   │   │           ├── *.pst              # Archivos de control PEST
│   │   │           ├── *.tpl              # Templates
│   │   │           ├── *.ins              # Instruction files
│   │   │           ├── *.zone             # Archivos de zona
│   │   │           ├── *.bat              # Scripts de batch
│   │   │           ├── *.smp              # Archivos de muestra
│   │   │           ├── get_flux.py        # Scripts de extracción
│   │   │           └── ...
│   │   └── master1/                       # Variante del contenedor maestro llamada con jacobiando existente
│   │       ├── Dockerfile
│   │       ├── requirements.txt
│   │       └── app/
│   └── Talabre/                           # Modelos Talabre
│       ├── docker_test/                   # Tests locales con Docker
│       │   ├── docker-compose.yml
│       │   └── docker-compose_s30.yml
│       └── master/                        # Contenedor maestro Talabre
│           ├── Dockerfile
│           ├── requirements.txt
│           └── app/
│
├── IaC_terraform/                         # Infraestructura como Código (Terraform)
│   ├── Auditar_Generar_Terraform/         # Scripts de auditoría y generación
│   │   ├── audit_and_generate.py
│   │   ├── audit_resources.tf
│   │   ├── provider.tf
│   │   ├── variables.tf
│   │   ├── locals.tf
│   │   └── .terraform.lock.hcl
│   └── ModeloPest/                        # Configuraciones Terraform por región
│       ├── us-east-1/                     # Región este 1
│       │   ├── main.tf
│       │   ├── variables.tf
│       │   ├── outputs.tf
│       │   ├── terraform.tfstate
│       │   ├── terraform.tfstate.backup
│       │   └── .terraform.lock.hcl
│       ├── us-east-2/                     # Región este 2 (con auto-escalado)
│       │   ├── main.tf
│       │   ├── provider.tf
│       │   ├── variables.tf
│       │   ├── outputs.tf
│       │   ├── auto_scaling_tasks.py
│       │   ├── activar_agentes_pest.py
│       │   ├── desactivar_agentes_pest.py
│       │   ├── terraform.tfstate
│       │   ├── terraform.tfstate.backup
│       │   └── .terraform.lock.hcl
│       ├── us-west-2/                     # Región oeste 2 (con auto-escalado)
│       │   ├── main.tf
│       │   ├── provider.tf
│       │   ├── variables.tf
│       │   ├── outputs.tf
│       │   ├── auto_scaling_tasks.py
│       │   ├── activar_agentes_pest.py
│       │   ├── desactivar_agentes_pest.py
│       │   ├── SSM_Conectar_a_Master.ps1
│       │   ├── terraform.tfstate
│       │   ├── terraform.tfstate.backup
│       │   └── .terraform.lock.hcl
│       ├── Multiple_Region/               # Configuración multi-región consolidada
│       │   ├── main.tf
│       │   ├── variables.tf
│       │   ├── outputs.tf
│       │   ├── terraform.tfvars
│       │   ├── terraform.tfstate
│       │   ├── terraform.tfstate.backup
│       │   └── .terraform.lock.hcl
│       ├── talabre/                       # Configuración regional para Talabre
│       │   └── regional/
│       │       ├── main.tf
│       │       ├── provider.tf
│       │       ├── variables.tf
│       │       ├── outputs.tf
│       │       ├── auto_scaling_tasks.py
│       │       ├── comandos_terraform.ps1
│       │       ├── terraform.tfstate
│       │       ├── terraform.tfstate.backup
│       │       └── .terraform.lock.hcl
│       └── unica_region_EC2/              # Configuración de única región con EC2
│           ├── main.tf
│           ├── variables.tf
│           ├── outputs.tf
│           ├── terraform.tfvars
│           ├── terraform.tfstate
│           ├── terraform.tfstate.backup
│           └── .terraform.lock.hcl
│
├── Cronograma/                            # Documentación de cronograma
├── Documentación PEST/                    # Documentación del modelo PEST
└── README.md                              # Este archivo
```

## Componentes Principales

### 1. **Master (Orquestador)**
- Coordina la ejecución de múltiples agentes PEST
- Se ejecuta en contenedor ECS Fargate
- Gestiona la asignación de tareas a agentes
- Monitorea el progreso de calibración
- Recopila y consolida resultados

### 2. **Agentes PEST**
- Ejecutan instancias del modelo PEST en paralelo
- Se despliegan automáticamente según demanda
- Comunican resultados al Master
- Auto-escalables según la carga de trabajo

### 3. **Modelos Soportados**
- **sqm_reservas**: Modelo de reservas de agua
- **Talabre**: Modelo regional específico

### 4. **Infraestructura AWS**
- **ECS Fargate**: Orquestación de contenedores sin gestión de servidores
- **ECR**: Repositorio de imágenes Docker privadas
- **CloudWatch**: Monitoreo centralizado y recopilación de logs
- **S3**: Almacenamiento de datos y estados de calibración
- **Terraform**: Gestión de infraestructura como código
- **SSM Session Manager**: Conexión segura a instancias

## Configuración por Región

| Región | Características |
|--------|-----------------|
| **us-east-1** | Configuración base - Región primaria |
| **us-east-2** | Auto-escalado dinámico, múltiples agentes paralelos |
| **us-west-2** | Auto-escalado dinámico, múltiples agentes paralelos |

La arquitectura multi-región permite distribuir la carga de cómputo y optimizar costos.

## Monitoreo y Logs

Los logs de ejecución se centralizan en CloudWatch:
- **Logs de Master**: Orquestación y coordinación
- **Logs de Agentes**: Ejecución de modelos PEST por región
- **Métricas**: CPU, memoria y duración de tareas
- **Exportación**: CSV para análisis y auditoría
- **Histórico**: Disponible en carpeta `/log`

## Requisitos

### Software
- AWS CLI v2 configurada
- Terraform >= 1.0
- Docker (para testing local)
- Python 3.8+ (para scripts de automatización)
- PowerShell 5.0+ (para scripts AWS en Windows)

### Credenciales AWS
- Acceso configurado a múltiples regiones
- Permisos en ECS, ECR, CloudWatch, S3
- Acceso a SSM para conectar a instancias

## Uso

### Deployment Local con Docker
```bash
cd Calibracion_Modelo_PEST/sqm_reservas/docker-local-mod-res-ensi
docker-compose up -d
docker-compose logs -f
```

### Deployment en AWS con Terraform (Multi-región)
```bash
cd IaC_terraform/ModeloPest/Multiple_Region
terraform init
terraform plan
terraform apply
```

### Deployment Regional Específico
```bash
cd IaC_terraform/ModeloPest/us-east-2
terraform init
terraform apply
```

### Activar/Desactivar Agentes Dinámicamente
```bash
# Activar agentes
cd IaC_terraform/ModeloPest/us-east-2
python activar_agentes_pest.py

# Desactivar agentes
python desactivar_agentes_pest.py

# Auto-escalado
python auto_scaling_tasks.py
```

### Monitoreo de Logs
```bash
# Ver logs en tiempo real
cd Calibracion_Modelo_PEST/Cloudwatch
python get_task_logs.py

# Descargar métricas de CPU
cd cpu/
python cpu.py

# Listar tareas activas
python list_tasks.py
```

### Conectar a Master vía SSM (us-west-2)
```powershell
cd IaC_terraform/ModeloPest/us-west-2
.\SSM_Conectar_a_Master.ps1
```

## Documentación Adicional

- **Diagramas de Arquitectura**: [Arquitectura/](Arquitectura/) 
- **Detalles del Modelo PEST**: [Documentación PEST/](Documentaci%C3%B3n%20PEST/)
- **Cronograma del Proyecto**: [Cronograma/](Cronograma/)

## Notas Importantes

- La arquitectura está optimizada para ejecutar calibraciones PEST en paralelo
- El auto-escalado se basa en la demanda de tareas en ECS
- Los logs se almacenan en CloudWatch y se exportan a CSV para análisis
- Los estados de Terraform se mantienen en S3 para colaboración
- Se recomienda usar `terraform` desde las carpetas específicas por región

---

**Última actualización**: Enero 2026  
**Arquitectura activa**: Arquitectura Regional Final (Multi-región con auto-escalado)  
**Versión**: 2.0 - Multi-región con ECS Fargate
