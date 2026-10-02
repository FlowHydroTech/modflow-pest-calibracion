# _legacy/ - Codigo archivado (generacion 1: ECS Fargate)

> Estos modulos y scripts estan ARCHIVADOS y NO se mantienen. Se conservan solo
> como referencia historica. NO usar en produccion.

## Por que estan aqui (F-06)

El proyecto migro de una arquitectura ECS Fargate (generacion 1) a AWS Batch EC2
(generacion 2). La auditoria (docs/auditoria/) determino que Batch EC2 es la
arquitectura correcta para el workload PEST (ver 07_compute_architecture.md).

Mantener ambas generaciones en el codigo activo generaba:
- Confusion sobre que modulo de Terraform aplicar.
- Riesgo de aplicar la configuracion incorrecta.
- Scripts que usaban APIs distintas (ECS vs Batch).

## Que se archivo

| Ruta original | Motivo |
|---------------|--------|
| IaC_terraform/Arquitectura_regional/ | ECS Fargate gen1 + null_resource PowerShell + KMS wildcard |
| IaC_terraform/ModeloPest/talabre/regional/ | ECS Fargate gen1 (Talabre) |
| IaC_terraform/ModeloPest/Multiple_Region/ | Prototipo multiregion con NAT Gateways (costo fijo) |
| IaC_terraform/ModeloPest/unica_region_EC2/ | Prototipo EC2+Fargate con NAT Gateway |

Los scripts `activar_agentes_pest.py`, `desactivar_agentes_pest.py` y
`auto_scaling_tasks.py` incluidos aqui usan la API de ECS (`ecs:RunTask`,
`ecs:StopTask`, `ecs:ListTasks`), reemplazada en gen2 por la API de AWS Batch
en `calibration_utils/batch.py` y el Lambda Autoscaler.

## Arquitectura activa

La arquitectura de produccion vive en:
- `IaC_terraform/ModeloPest/talabre-linux/us-east-1/` - AWS Batch EC2 (gen2)
- `IaC_terraform/bootstrap/` - backend remoto de Terraform (S3 + DynamoDB)
- `calibration_utils/`, `lambdas/`, `scripts/` - Control Plane en Python

## Nota sobre OQ-01 (costo)

Si `Multiple_Region` o `unica_region_EC2` estuvieron desplegados, sus NAT
Gateways generan ~$32/mes por region aunque esten archivados en el codigo.
Verificar en la consola AWS y ejecutar `terraform destroy` sobre el state
correspondiente si aun existen recursos activos (OQ-01).