# AWS Cloud – Arquitectura para Calibración de Modelos con PEST

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![AWS](https://img.shields.io/badge/AWS-Cloud-orange.svg)](https://aws.amazon.com/)
[![MODFLOW](https://img.shields.io/badge/MODFLOW-6-green.svg)](https://www.usgs.gov/software/modflow-6-usgs-modular-hydrologic-model)
[![PEST](https://img.shields.io/badge/PEST++-v5-red.svg)](http://www.pestpp.org/)

## Descripción

Este repositorio contiene una arquitectura escalable en **AWS** para ejecutar procesos de **calibración automática de modelos numéricos** (MODFLOW u otros) mediante las herramientas **PEST** y **PEST++**.

### Características Principales


### ¿Qué Resuelve?

Las calibraciones de modelos hidrogeológicos complejos pueden tomar **días o semanas** en equipos locales. Esta arquitectura distribuye el trabajo entre múltiples agentes en la nube, reduciendo significativamente los tiempos de ejecución mediante un esquema **Master-Workers**.



## Resumen rápido (para reunión)
- **Estado actual:** `README` actualizado; backup en `README.backup.md`.
---

## Arquitectura General

> Diagrama editable: `Arquitectura/Arquitectura_pest.drawio`

La arquitectura se compone de los siguientes bloques principales:

### Componentes AWS Utilizados

1. **Amazon VPC**


   - Red privada donde operan el servidor maestro y los agentes.
   - Subred pública: EC2 Maestro
   - Subred privada: Agentes ECS

2. **Amazon S3 – Modelo / Resultados**


   - Almacena el modelo base (archivos MODFLOW, plantillas PEST, control)
   - Guarda estados intermedios y resultados finales

3. **Amazon EC2 – Servidor Maestro**


   - Ejecuta `pest_hp.exe` o `beopest.exe` como proceso maestro
   - Scripts de coordinación, lectura/escritura en S3 y publicación en SQS
   - Responsabilidades: coordinar agentes, controlar iteraciones y monitoreo

4. **Amazon ECS – Agentes de Cómputo**


   - Contenedores Docker en subred privada
   - Auto-scaling para levantar N workers según demanda
   - Ejecutan simulaciones y envían resultados a S3

5. **Amazon ECR – Registro de Contenedores**


   - Almacena imágenes Docker con el runtime PEST/MODFLOW y scripts (`run_agent.sh`)

6. **Amazon SQS – Cola de Distribución de Tareas**


   - Permite desacoplamiento, tolerancia a fallos y escalabilidad

7. **Amazon CloudWatch Logs**


   - Centraliza logs de maestro y agentes; facilita auditoría y debugging

---

## Flujo de Ejecución (diagramas)

```mermaid
flowchart TB

    S3[(S3|Modelos/Inputs)]
    EC2[EC2 Maestro|PEST Master]
    SQS[SQS Queue|Distribución]
    ECS[ECS Workers|Agentes]
    CW[(CloudWatch|Logs)]

    S3 -->|1. Descarga modelo| EC2
    EC2 -->|2. Publica tareas| SQS
    SQS -->|3. Consume tareas| ECS
    ECS -->|4. Guarda resultados| S3
    ECS -->|5. Logs| CW
    EC2 -->|6. Logs| CW
    S3 -->|7. Lee resultados| EC2
```

Y, para que se vea "como código / batch", incluí este bloque sencillo que puedes copiar/pegar:

```text
:: Arquitectura (secuencia)
S3 -> EC2_MASTER    :: subir/leer modelos
SQS -> ECS_WORKERS   :: consumir tareas y ejecutar simulaciones
ECS_WORKERS -> S3    :: subir resultados
ECS_WORKERS -> CW    :: enviar logs
EC2_MASTER -> CW     :: logs y monitoreo
```

---

## Proceso paso a paso

1. **Carga del modelo** — El usuario sube el modelo inicial y archivos PEST a S3.
2. **Inicialización** — EC2 Maestro descarga el modelo, configura PEST y genera el plan de ejecución.
3. **Distribución de tareas** — El maestro publica jobs en SQS; cada tarea contiene parámetros a evaluar.
4. **Escalado de agentes** — ECS levanta N agentes según demanda.
5. **Procesamiento paralelo** — Cada agente toma una tarea, ejecuta la simulación y sube resultados a S3.
6. **Consolidación** — El maestro reúne resultados, evalúa convergencia y avanza iteraciones.
7. **Finalización** — Resultados finales en S3; agentes se desactivan.

- Costos controlados (ECS Spot + apagado automático)
- Aislamiento de red mediante VPC / subred privada
- Fácil integración con pipelines (Terraform)
- Logs unificados en CloudWatch
- Reproducible y automatizable

---


## ¿MODFLOW vs PEST? (Aclaración importante)

| Componente | ¿Qué es? | Rol en este proyecto |
|---|---|---|
| **MODFLOW** | Modelo numérico para simulación hidrogeológica | Se ejecuta muchas veces durante la calibración |
| **PEST / PEST++** | Herramienta de calibración que ajusta parámetros del modelo | Coordina iteraciones y optimiza parámetros usando MODFLOW como "motor" |


```text
/aws-pest-calibration/
├── terraform/
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   ├── modules/
│       ├── ec2_master/
│       ├── ecs_agents/
│       ├── sqs/
│       ├── vpc/
│       ├── ecr/
│       └── iam/
├── scripts/
│   ├── startup_master.sh
│   ├── startup_agent.sh
│   ├── run_master.sh
│   └── run_agent.sh
├── docker/
│   ├── Dockerfile
├── docs/
│   └── arquitectura_aws.md

└── README.md

```

---

## Próximos pasos

* Definir número de agentes según tamaño del modelo

* Ajustar imagen Docker del agente

* Implementar Terraform

* Integrar CI/CD para despliegue automático

* Probar calibración end-to-end

