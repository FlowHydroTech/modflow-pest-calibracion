# Security Assessment

---

## Resumen de Riesgos

| ID | Riesgo | Severidad | Archivo | Estado |
|----|--------|-----------|---------|--------|
| S-01 | Account ID AWS hardcodeado en scripts | 🟠 ALTO | `AWS_ECR_carga_imagen_docker.ps1` | Pendiente |
| S-02 | VPC/Subnet IDs en defaults de variables.tf | 🟠 ALTO | `IaC_terraform/Arquitectura_regional/variables.tf` | Pendiente |
| S-03 | S3 Resource wildcard en IAM task role | 🟠 ALTO | `talabre-linux/us-east-1/main.tf` | Pendiente |
| S-04 | Sin backend Terraform remoto (state contiene ARNs, IPs) | 🟠 ALTO | Todos los módulos TF | Pendiente |
| S-05 | KMS Decrypt sobre Resource `*` | 🟡 MEDIO | `Arquitectura_regional/main.tf` | Pendiente |
| S-06 | ECS Exec habilitado sin auditoría de acceso | 🔵 INFO | job definitions talabre-linux | Revisar |
| S-07 | Imágenes Docker con Wine e instalación via curl sin hash | 🔵 BAJO | `Dockerfile` | Baja prioridad |

---

## Positivo — Buenas Prácticas Identificadas

| Práctica | Evidencia |
|---------|----------|
| ✅ Sin IP pública en ningún contenedor | `assign_public_ip = false` en todos los SGs |
| ✅ VPC Endpoints en lugar de NAT Gateway (gen2) | VPC Endpoints Interface + Gateway en talabre-linux |
| ✅ IMDSv2 requerido en Launch Templates | `http_tokens = "required"` en todos los LT |
| ✅ EBS cifrado | `encrypted = true` en todos los volúmenes EBS |
| ✅ SGs mínimos | TCP 4004 solo desde agentes hacia master; HTTPS 443 solo para endpoints |
| ✅ Sin credenciales AWS en código | No se encontraron access keys ni tokens |
| ✅ `.env` excluido de git | `.gitignore` excluye `.env`, `.envrc` |
| ✅ IAM roles separados por función | task_role, batch_service_role, batch_instance_role |

---

## Análisis Detallado de Riesgos

### S-01 — Account ID hardcodeado

**Archivos afectados:**
- `Estructura_Base/AWS_Comandos/AWS_ECR_carga_imagen_docker.ps1` (múltiples líneas)
- `Estructura_Base/AWS_Comandos/ECS_Fargate_comandos.ps1`

**Riesgo:** El ID de cuenta permite reconocimiento de la cuenta AWS. Aunque no es una credencial de acceso, reduce el nivel de seguridad al exponer información de la cuenta.

**Mitigación:**
```powershell
# En lugar de hardcodear:
$ACCOUNT_ID = "312019940349"

# Usar:
$ACCOUNT_ID = aws sts get-caller-identity --query Account --output text
```

---

### S-02 — VPC/Subnet IDs en código versionado

**Archivos afectados:**
- `IaC_terraform/Arquitectura_regional/variables.tf`: `vpc_id = "vpc-0b08cba4a3d0cf109"`
- `IaC_terraform/ModeloPest/talabre-linux/us-east-1/variables.tf`: `vpc_id = "vpc-03f2a07e3273c4216"`

**Riesgo:** La topología de red es visible para cualquier persona con acceso al repositorio.

**Mitigación:**
```hcl
# Opción 1: terraform.tfvars (excluido de git)
# terraform.tfvars
vpc_id             = "vpc-xxxxxxxx"
private_subnet_ids = ["subnet-xxxxxxxx", "subnet-yyyyyyyy"]

# Opción 2: SSM Parameter Store
data "aws_ssm_parameter" "vpc_id" {
  name = "/${var.project_name}/vpc_id"
}
```

---

### S-03 — S3 Resource wildcard en task role

**Archivo:** `IaC_terraform/ModeloPest/talabre-linux/us-east-1/main.tf`

```hcl
# Estado actual (inseguro):
Resource = ["arn:aws:s3:::*", "arn:aws:s3:::*/*"]

# Estado correcto:
Resource = [
  "arn:aws:s3:::${var.s3_bucket_linux}",
  "arn:aws:s3:::${var.s3_bucket_linux}/*"
]
```

**Riesgo:** Un contenedor comprometido podría leer, escribir o listar cualquier bucket S3 de la cuenta.

---

### S-04 — State Terraform sin cifrado ni acceso controlado

El `terraform.tfstate` local contiene:
- ARNs de todos los recursos (roles IAM, security groups, etc.)
- IDs de instancias y recursos
- En algunos casos, valores de outputs (pueden incluir IPs privadas)

**Sin backend remoto**, este archivo puede:
- Perderse (riesgo operacional)
- Compartirse inadvertidamente
- No tener control de quién lo modifica

**Mitigación:** Backend S3 con cifrado SSE-KMS, versionado habilitado, y política de acceso restrictiva.

---

### S-05 — KMS Decrypt con Resource wildcard

**Archivo:** `IaC_terraform/Arquitectura_regional/main.tf`

```hcl
# Estado actual:
{
  Effect = "Allow"
  Action = ["kms:Decrypt"]
  Resource = "*"
  Condition = {
    StringEquals = {
      "kms:ViaService" = "ssmmessages.${var.aws_region}.amazonaws.com"
    }
  }
}
```

La condición `kms:ViaService` limita el uso al servicio SSM Messages, lo que reduce el riesgo. Sin embargo, `Resource = "*"` sigue siendo más amplio de lo necesario si existe una clave KMS específica.

**Acción:** Si no se usa KMS, eliminar este bloque. Si se usa, restringir al ARN de la clave específica.

---

### S-06 — ECS Exec habilitado

`enableExecuteCommand = true` está configurado en todas las job definitions del módulo talabre-linux. Esto permite:
```bash
aws ecs execute-command --cluster ... --task ... --container ... --command "/bin/bash"
```

**Esto es correcto y necesario** para soporte operativo. Sin embargo, requiere:
- Control de quién tiene permiso `ecs:ExecuteCommand` en IAM
- Auditoría de sesiones SSM (CloudTrail)

**Recomendación:** Verificar que el permiso `ecs:ExecuteCommand` esté restringido por política IAM a los roles de Soporte TI específicos.

---

## Checklist de Seguridad

```
[x] Sin credenciales en código
[x] Sin IP pública en contenedores
[x] IMDSv2 required en EC2
[x] EBS cifrado
[x] VPC Endpoints (sin NAT en gen2)
[x] SGs mínimos (solo puertos necesarios)
[ ] Account ID removido de scripts
[ ] VPC IDs removidos de variables.tf defaults
[ ] S3 Resource restringido al bucket específico
[ ] Backend S3 con cifrado para state
[ ] Auditoría CloudTrail activa
[ ] ECR scan on push habilitado
[ ] IAM permissions boundary para roles de Batch
```

---

## Recomendaciones de Seguridad Priorizadas

| Prioridad | Acción | Esfuerzo |
|-----------|--------|---------|
| 1 | Restringir S3 Resource de `*` al bucket específico | XS |
| 2 | Remover VPC IDs de defaults en variables.tf | XS |
| 3 | Remover account ID de scripts — reemplazar por llamada STS | XS |
| 4 | Implementar backend S3 con cifrado para state | S |
| 5 | Habilitar ECR scan on push para detectar CVEs en imágenes | XS |
| 6 | Revisar permisos `ecs:ExecuteCommand` en políticas IAM de usuarios | S |
| 7 | Agregar CloudTrail trail si no existe | S |
