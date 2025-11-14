🧠 AWS Cloud – Arquitectura para Calibración de Modelos con PEST

Este repositorio contiene la arquitectura propuesta para ejecutar procesos de calibración de modelos numéricos (MODFLOW u otros) mediante la herramienta PEST / PEST++, utilizando una infraestructura escalable y paralelizada en AWS.

El diseño se basa en un esquema Master–Workers, donde un servidor maestro distribuye tareas a múltiples agentes (workers) desplegados dinámicamente sobre ECS, permitiendo ejecutar calibraciones complejas en tiempos reducidos.
----
🏗️ Arquitectura General

(Reemplazar con tu imagen final)

La arquitectura se compone de los siguientes bloques principales:
---
☁️ Componentes AWS Utilizados
1. Amazon VPC

Red privada donde operan el servidor maestro y los agentes.

Se divide en:

Subred pública: EC2 Maestro

Subred privada: Agentes ECS

2. Amazon S3 – Modelo / Resultados

Usado para:

Almacenar el modelo base (archivos MODFLOW, PEST, templates, control)

Mantener estados de calibración

Guardar resultados finales

3. Amazon EC2 – Servidor Maestro

El nodo central donde se ejecuta:

pest_hp.exe o beopest.exe como master

Scripts de coordinación y envío de tareas

Descarga/lectura de archivos desde S3

Envío de tareas a la cola SQS

Responsabilidades del Maestro:

Coordinar agentes

Controlar iteraciones del proceso PEST

Monitorear y sincronizar outputs

4. Amazon ECS – Agentes de Cómputo

Desplegados dentro de una subred privada

Auto Scaling Group configurado para levantar N workers

Utilizan una imagen de contenedor almacenada en Amazon ECR

Los agentes ejecutan:

pest_hp.exe o scripts de simulación

Cálculos individuales del Jacobiano

Evaluaciones del modelo

5. Amazon ECR – Imagen del Contenedor

Almacena:

Imagen Docker con ambiente PEST/Model Engine

Librerías y dependencias

Scripts de agente (run_agent.sh)

6. Amazon SQS – Distribución de Tareas

El maestro publica tareas (parámetros, seeds, partes del Jacobiano)

Cada agente toma una tarea de la cola

Permite:

Escalabilidad

Tolerancia a fallos

Procesamiento asíncrono

7. Amazon CloudWatch Logs

Logs del maestro

Logs de agentes (via ECS Task Logging)

Auditoría de fallos, iteraciones y resultados

----

🔄 Flujo de Ejecución Completo


flowchart TB

subgraph S3[S3 - Modelos / Inputs]
end

subgraph MAESTRO[EC2 Maestro]
end

subgraph AGENTES[ECS Workers]
end

subgraph SQS[SQS - Distribution Queue]
end

S3 --> MAESTRO
MAESTRO --> SQS
SQS --> AGENTES
AGENTES --> S3
AGENTES --> CLOUDWATCH
MAESTRO --> CLOUDWATCH[(CloudWatch Logs)]


----

⚙️ Proceso paso a paso

El usuario sube un modelo inicial a S3.

EC2 Maestro descarga modelo, configura PEST y genera tareas.

El maestro envía jobs a SQS.

ECS levanta N agentes según demanda.

Cada agente:

Descarga insumo desde S3

Ejecuta iteración

Retorna resultados a S3

Envia logs a CloudWatch

El maestro reúne los resultados y continúa la iteración del algoritmo PEST.

Una vez finalizado, todos los resultados quedan almacenados en S3.

-----

🚀 Ventajas de la Arquitectura

Escalable horizontalmente (decenas o cientos de agentes)

Costos controlados (ECS Spot + apagado automático)

Aislamiento de red por VPC / subred privada

Fácil integración con pipelines (Terraform)

Logs unificados en CloudWatch

Reproducible y automatizable

----

¿MODFLOW vs PEST? (Aclaración importante)
Componente	¿Qué es?	Rol en este proyecto
MODFLOW	Modelo numérico para simulación hidrogeológica	Se ejecuta muchas veces durante la calibración
PEST / PEST++	Herramienta de calibración que ajusta parámetros del modelo	Coordina iteraciones y optimiza parámetros usando MODFLOW como “motor”


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
│   └── agent-runtime/
├── docs/
│   └── arquitectura_aws.md
└── README.md

------

🧭 Próximos pasos

Definir número de agentes según tamaño del modelo

Ajustar imagen Docker del agente

Implementar Terraform

Integrar CI/CD para despliegue automático

Probar calibración end-to-end

