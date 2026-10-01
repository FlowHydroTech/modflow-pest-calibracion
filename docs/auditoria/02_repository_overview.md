# Repository Overview

## Propósito del Repositorio

Este repositorio contiene la infraestructura, el código de orquestación y las plantillas para ejecutar **calibraciones del modelo hidrológico MODFLOW usando PEST/PEST++** en AWS.

**PEST** (Parameter ESTimation) ajusta parámetros del modelo hasta que el comportamiento simulado se acerque a las observaciones de campo. En esta implementación, PEST corre en modo **Master-Agent paralelo**:

- Un proceso **master** gestiona el algoritmo de optimización (Levenberg-Marquardt)
- Múltiples **agentes** ejecutan el modelo numérico en paralelo para calcular el Jacobiano

Los modelos que se calibran son modelos **hidrogeológicos de acuíferos** relacionados con operaciones mineras (referencias a Talabre, CMDIC, SQM, en el norte de Chile).

---

## Estructura de Directorios

```
modflow-pest-calibracion/
│
├── main.py                          ← placeholder vacío (solo print)
├── pyproject.toml                   ← dependencias Python del proyecto raíz
├── requirements.txt                 ← dependencias alternativas (desincronizadas)
├── README.md                        ← documentación principal (actualizada a Batch)
├── .gitignore                       ← excluye .terraform/, *.tfstate, modelos, datos
├── .python-version                  ← Python 3.12
│
├── docs/                            ← [NUEVO] documentación de auditoría
│   └── auditoria/                   ← documentos de esta fase
│
├── Arquitectura/                    ← diagramas PNG/drawio de arquitectura (históricos)
│   ├── Arquitectura_pest.png
│   ├── Arquitectura Multiregional.png
│   └── ...
│
├── Calibracion_Modelo_PEST/         ← implementaciones reales por proyecto/modelo
│   ├── Cloudwatch/                  ← scripts de análisis y consulta de logs
│   │   ├── getLog.py                ← exportar logs CW a CSV/Excel
│   │   ├── consolidate_logs.py      ← consolidar múltiples archivos Excel
│   │   ├── reviw_log.py             ← análisis básico de streams
│   │   ├── get_task_logs.py         ← logs por tarea ECS
│   │   ├── cpu/cpu.py               ← métricas CPU desde CloudWatch
│   │   └── ...
│   │
│   ├── cmdic_linux_compile/         ← Dockerfile proyecto CMDIC (modelo minero)
│   ├── sqm_reservas/                ← ⚠️ versión anterior ECS Fargate (legacy)
│   │   ├── master/, master1/, master - east2/  ← múltiples variantes
│   │   └── docker-local-mod-res-ensi/
│   ├── Talabre/                     ← ⚠️ versión anterior ECS Fargate (legacy)
│   │   ├── master/                  ← Dockerfile ubuntu:20.04
│   │   └── docker_test/             ← docker-compose de pruebas locales
│   └── talabre_pest/                ← Dockerfile Talabre con PEST nativo Linux
│
├── Cronograma/                      ← planificación del proyecto
│
├── Documentación PEST/              ← documentación técnica de PEST/PEST++
│
├── Estructura_Base/                 ← ✅ PLANTILLA para nuevos proyectos
│   ├── AWS_Comandos/                ← scripts PowerShell de operación manual
│   │   ├── AWS_ECR_carga_imagen_docker.ps1
│   │   ├── ECS_Fargate_comandos.ps1
│   │   ├── Docker_comandos.ps1
│   │   ├── S3_comandos.ps1
│   │   └── EC2_conectar_a_consola_ssm.ps1
│   └── nombre_proyecto_modelo/      ← ✅ template base para nuevos proyectos
│       ├── app/
│       │   ├── entrypoint_master.sh      ← entry del contenedor master
│       │   ├── entrypoint_agent.sh       ← entry del contenedor agente
│       │   ├── entrypoint_autonomo.sh    ← entry para modo autónomo
│       │   ├── ensibatch.sh              ← traducción Linux del .bat del modelo
│       │   └── ensibatch_timeout.sh      ← versión con timeout máximo
│       ├── Dockerfile                    ← Ubuntu 25.04 + Wine + PEST + AWS CLI
│       ├── requirements.txt              ← solo pandas
│       └── InfraestructuraModeloPest/    ← referenciada en README pero vacía en git
│           ├── scripts/                  ← scripts apuntan a talabre-linux en la práctica
│           └── us-west-2/
│
└── IaC_terraform/                   ← ✅ toda la infraestructura como código
    ├── Arquitectura_regional/       ← ⚠️ ECS Fargate (gen1, presente pero a deprecar)
    │   ├── main.tf                  ← ECS Cluster + Task Defs + Service + VPC Endpoints
    │   ├── variables.tf             ← ⚠️ VPC IDs hardcodeados como default
    │   ├── outputs.tf
    │   ├── provider.tf
    │   ├── activar_agentes_pest.py  ← lanza agentes vía ECS run-task (legacy)
    │   ├── desactivar_agentes_pest.py
    │   ├── auto_scaling_tasks.py    ← autoscaler (mezcla ECS y Batch)
    │   └── SSM_Conectar_a_Master.ps1
    │
    ├── Auditar_Generar_Terraform/   ← utilidad para auditar recursos AWS existentes
    │   ├── audit_and_generate.py    ← audita SGs, VPC endpoints, ECS, IAM
    │   └── audit_resources.tf       ← template generado automáticamente
    │
    └── ModeloPest/                  ← implementaciones por proyecto/región
        ├── talabre-linux/           ← ✅ AWS Batch EC2 (gen2, arquitectura actual)
        │   └── us-east-1/
        │       ├── main.tf          ← Batch CE (Spot+OD+Master), queues, job defs
        │       ├── variables.tf     ← instancias, vCPUs, memoria, timeouts
        │       ├── outputs.tf
        │       ├── provider.tf
        │       ├── launch_master_agents.py    ← ✅ orquestador principal
        │       ├── stop_master_agents.py      ← detener master y/o agentes
        │       ├── auto_scaling_tasks.py      ← ⚠️ valores hardcodeados
        │       ├── backup_logs.py             ← exportar logs CW a CSV
        │       ├── analizar_agentes.py        ← análisis Excel de agentes
        │       └── launch_master_agents_stop.py
        │
        ├── talabre/regional/        ← ⚠️ ECS Fargate Talabre (gen1, a deprecar)
        │   ├── main.tf              ← ECS + Cloud Map + VPC Endpoints
        │   └── activar_agentes_pest.py
        │
        ├── cmdic-linux-ensi/us-west-2/   ← proyecto CMDIC
        ├── mod_cmdic/us-west-2/          ← proyecto mod CMDIC
        ├── mod_res_ensi/                 ← proyecto mod_res_ensi
        ├── Multiple_Region/              ← ⚠️ prototipo multiregión con NAT GW
        │   └── main.tf              ← VPC Peering + NAT GW × 3 regiones (costoso)
        └── unica_region_EC2/             ← ⚠️ prototipo EC2 una región con NAT GW
            └── main.tf              ← EC2 master + Fargate hosts + NAT GW
```

---

## Modelos Identificados

| Proyecto | Descripción | Región | Arquitectura |
|----------|-------------|--------|--------------|
| **talabre-linux** | Modelo Talabre (depósito de relaves) | us-east-1 | ✅ Batch EC2 (gen2) |
| **cmdic-linux-ensi** | Modelo CMDIC ENSI (rajo minero) | us-west-2 | ⚠️ Ver código |
| **mod_cmdic** | Variante CMDIC | us-west-2 | ⚠️ Ver código |
| **mod_res_ensi** | Modelo de reservas ENSI | us-east-2 / us-west-2 | ⚠️ ECS Fargate (gen1) |
| **sqm_reservas** | Reservas SQM | us-east-2 | ⚠️ ECS Fargate (legacy) |

---

## Tecnologías Utilizadas

| Tecnología | Versión / Detalle | Uso |
|------------|-------------------|-----|
| **Python** | 3.12 | Scripts de orquestación, análisis de logs |
| **PEST / PEST HP** | REQUIERE VALIDACIÓN | Calibración de parámetros |
| **MODFLOW USG** | USGT v2.7.0 (compilado en Linux) | Modelo numérico hidrogeológico |
| **Wine** | 64-bit, Ubuntu 25.04 | Ejecutar binarios Windows de PEST en Linux |
| **Docker** | Ubuntu 25.04 base | Contenedor de ejecución |
| **Terraform** | >= 1.6.0 | Infrastructure as Code |
| **AWS Batch** | EC2 (gen2) | Cómputo principal (master y agentes) |
| **Amazon ECS / Fargate** | (gen1, a deprecar) | Arquitectura anterior |
| **Amazon ECR** | — | Registro de imágenes Docker |
| **Amazon S3** | — | Almacenamiento de resultados y logs |
| **Amazon CloudWatch** | Logs + Events | Logging centralizado |
| **AWS SSM** | Session Manager | Acceso interactivo a contenedores |
| **pandas** | >= 2.0 | Análisis de logs en Excel/CSV |
| **boto3** | >= 1.34 | SDK AWS para Python |
| **python-hcl2** | >= 4.0 | Lectura de archivos Terraform desde Python |

---

## Convenciones de Nomenclatura

El proyecto sigue un patrón consistente de naming:

```
{project_name}-{recurso}-{region}
```

Ejemplos:
- `pest-talabre-linux-master-queue`
- `pest-talabre-linux-batch-task-role-us-east-1`
- `/batch/pest-talabre-linux-master`

Los tags de AWS incluyen mínimamente:
- `Service`: `BATCH` o `FARGATE`
- `Owner`: `Modelamiento Numerico`
- `Region`: región AWS
- `Project`: nombre del proyecto

**Oportunidad de mejora:** Agregar `Environment`, `CostCenter`, y `CalibrationID`.
