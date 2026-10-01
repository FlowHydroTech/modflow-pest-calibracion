# Proposed Automated Workflow

> Flujo futuro completo end-to-end para ejecutar una calibración.  
> **Estado:** Diseño conceptual — NO implementado.

---

## Visión General

```
calibrate start config/talabre.yaml
           │
           ▼
       CONFIG ──────────────── Valida estructura y campos requeridos
           │
           ▼
       VALIDATE ────────────── Verifica modelo, credenciales AWS, VPC
           │
           ▼
       BUILD ───────────────── docker build + tag SHA + push ECR
           │
           ▼
       DEPLOY ──────────────── terraform init + plan + apply
           │
           ▼
       RUN ─────────────────── submit master + wait IP + submit N agents
           │
           ▼
       MONITOR ─────────────── Loop: leer logs → métricas → escalar agentes
           │
           ▼
       EVALUATE ────────────── Clasificar IMPROVING/STAGNATED/CONVERGED
           │
           ▼
       STORE ───────────────── Verificar S3 + exportar logs + generar Manifest
           │
           ▼
       NOTIFY ──────────────── SNS email con resumen de la calibración
           │
           ▼
       DESTROY ─────────────── terraform destroy (solo si resultados confirmados)
```

---

## Etapas Detalladas

### 1. CONFIG

```yaml
# config/talabre_calibration.yaml
calibration:
  id: "pest-talabre-linux-{fecha}"        # auto-generado si no se provee
  project_name: "pest-talabre-linux"
  description: "Calibración escenario A — parámetros kh/kv"

model:
  pst_file: "talabre_pwadj_ddn.pst"
  version: "v2.3"

docker:
  context_path: "."
  dockerfile: "Dockerfile"
  push_tag_latest: true

infrastructure:
  region: "us-east-1"
  terraform_module: "IaC_terraform/ModeloPest/talabre-linux/us-east-1"
  s3_bucket: "312019940349-pest-talabre-east-1"

execution:
  initial_agents: 50
  max_agents: 300
  pest_port: 4004
  infra_ttl_hours: 72       # alarma si supera este tiempo

notifications:
  email: "equipo@empresa.com"
```

**Validaciones en esta etapa:**
- Campos requeridos presentes
- `terraform_module` existe en el repositorio
- `pst_file` existe en `app/modelo/` dentro del contexto Docker

---

### 2. VALIDATE

```
Validaciones técnicas:
  ✓ AWS credentials configuradas y vigentes
  ✓ ECR repository existe en la región
  ✓ S3 bucket existe y es accesible con escritura
  ✓ VPC ID y subnets existen en la región
  ✓ Terraform instalado con versión requerida
  ✓ Docker instalado y corriendo
  ✗ Si algo falla → abortar con mensaje claro antes de crear recursos
```

---

### 3. BUILD

```bash
# Captura metadata de reproducibilidad
GIT_SHA=$(git rev-parse HEAD)
GIT_BRANCH=$(git branch --show-current)
BUILD_TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)

# Build con tags múltiples
docker build \
  --label "git.sha=${GIT_SHA}" \
  --label "build.timestamp=${BUILD_TIMESTAMP}" \
  -t ${ECR_URI}:${GIT_SHA:0:8} \
  -t ${ECR_URI}:latest \
  .

# Push ambos tags
docker push ${ECR_URI}:${GIT_SHA:0:8}
docker push ${ECR_URI}:latest

# Obtener digest inmutable para el manifest
IMAGE_DIGEST=$(aws ecr describe-images \
  --repository-name ${REPO_NAME} \
  --image-ids imageTag=${GIT_SHA:0:8} \
  --query 'imageDetails[0].imageDigest' --output text)
```

---

### 4. DEPLOY

```bash
cd ${TERRAFORM_MODULE}

# Actualizar variable con nueva imagen (digest o SHA tag)
export TF_VAR_ecr_image_linux="${ECR_URI}:${GIT_SHA:0:8}"
export TF_VAR_project_name="${PROJECT_NAME}"

terraform init \
  -backend-config="bucket=${TF_STATE_BUCKET}" \
  -backend-config="key=${PROJECT_NAME}/${REGION}/terraform.tfstate" \
  -backend-config="region=${REGION}" \
  -backend-config="dynamodb_table=terraform-state-lock"

terraform plan -out=tfplan
terraform apply -auto-approve tfplan

# Capturar outputs
JOB_QUEUE_MASTER=$(terraform output -raw master_job_queue)
JOB_QUEUE_AGENTS=$(terraform output -raw agent_job_queue)
LOG_GROUP_MASTER=$(terraform output -raw cloudwatch_log_group_master)
```

---

### 5. RUN

```python
# Lógica de launch_master_agents.py (ya existe, integrar en el flujo)

# 1. Submit master job
master_job_id = submit_master(job_queue=JOB_QUEUE_MASTER, ...)

# 2. Esperar hasta RUNNING con polling activo
master_ip = wait_for_master_ip(job_id=master_job_id, timeout_s=600)
if not master_ip:
    raise RuntimeError("Master no obtuvo IP en 10 minutos")

# 3. Submit N agentes con MASTER_HOST override
agent_ids = submit_agents(master_ip, N_initial_agents)

# 4. Registrar en el manifest en progreso
write_manifest_in_progress(calibration_id, master_job_id, master_ip)
```

---

### 6. MONITOR

```python
# Ejecutado por Lambda schedulada cada 10 minutos

def monitor_calibration(calibration_id, project_name, region):
    # 1. Verificar que el master sigue RUNNING
    if not is_master_running(project_name):
        send_alert_critical("Master FAILED", calibration_id)
        return

    # 2. Leer logs recientes del master
    events = get_recent_log_events(LOG_GROUP_MASTER, minutes=15)

    # 3. Extraer número de modelos solicitados
    models_needed = extract_model_count(events)

    # 4. Contar agentes activos
    agents_running = count_running_agents(AGENT_JOB_QUEUE)

    # 5. Publicar métricas a CloudWatch
    publish_metric("AgentsRunning", agents_running)

    # 6. Escalar si necesario
    if models_needed > agents_running:
        launch_more_agents(models_needed - agents_running)

    # 7. Detener agentes que completaron
    stop_completed_agents(LOG_GROUP_AGENTS)
```

---

### 7. EVALUATE

```python
# Ejecutado por Lambda cada vez que hay un nuevo evento Phi en CloudWatch

def evaluate_calibration_quality(phi_history):
    if len(phi_history) < 2:
        return "INSUFFICIENT_DATA"

    # Calcular mejora relativa en ventana
    recent = phi_history[-5:]
    improvements = [
        (recent[i-1] - recent[i]) / recent[i-1]
        for i in range(1, len(recent))
        if recent[i-1] > 0
    ]

    if not improvements:
        return "FAILED"

    sliding_improvement = sum(improvements) / len(improvements)

    if check_pest_convergence_message():
        return "CONVERGED"
    elif sliding_improvement > 0.01:
        return "IMPROVING"
    elif sliding_improvement > 0.001:
        return "SLOW_IMPROVEMENT"
    else:
        return "STAGNATED"

# Publicar estado como Custom Metric
publish_metric("CalibrationQualityStatus", quality_state_to_value(state))
```

---

### 8. STORE

```python
def store_results(calibration_id, project_name, s3_bucket):
    # 1. Verificar que los resultados están en S3
    if not s3_results_exist(s3_bucket, f"calibrations/{calibration_id}/modelo/"):
        raise RuntimeError("Resultados no encontrados en S3 — NO se destruirá la infraestructura")

    # 2. Exportar logs de CloudWatch a S3
    export_cloudwatch_logs(LOG_GROUP_MASTER, s3_bucket, f"calibrations/{calibration_id}/logs/master/")
    export_cloudwatch_logs(LOG_GROUP_AGENTS, s3_bucket, f"calibrations/{calibration_id}/logs/agents/")

    # 3. Generar y guardar Calibration Manifest
    manifest = generate_manifest(calibration_id, ...)
    s3_client.put_object(
        Bucket=s3_bucket,
        Key=f"calibrations/{calibration_id}/manifest.yaml",
        Body=yaml.dump(manifest)
    )
```

---

### 9. NOTIFY

```python
def notify_completion(calibration_id, manifest):
    message = f"""
    Calibración completada: {calibration_id}
    Estado: {manifest['status']}
    Duración: {manifest['timestamps']['duration_hours']:.1f} horas
    Phi inicial: {manifest['calibration']['initial_phi']:.2f}
    Phi final: {manifest['calibration']['final_phi']:.2f}
    Reducción: {manifest['calibration']['phi_reduction_pct']:.1f}%
    Iteraciones: {manifest['calibration']['total_iterations']}
    Resultados en: s3://{manifest['results']['s3_bucket']}/{manifest['results']['s3_model_prefix']}
    """
    sns_client.publish(TopicArn=SNS_TOPIC_ARN, Subject=f"Calibración {calibration_id}", Message=message)
```

---

### 10. DESTROY

```python
def safe_destroy(calibration_id, terraform_module, s3_bucket):
    # Verificación final antes de destruir
    assert s3_results_exist(s3_bucket, ...)
    assert manifest_exists(s3_bucket, calibration_id)

    # Detener jobs activos
    stop_all_agents(AGENT_JOB_QUEUE)
    stop_master(MASTER_JOB_QUEUE)

    # Terraform destroy
    subprocess.run([
        "terraform", "destroy", "-auto-approve"
    ], cwd=terraform_module, check=True)

    # Verificar que no quedaron recursos activos
    verify_no_orphan_resources(project_name, region)
```

---

## Manejo de Errores por Etapa

| Etapa | Error posible | Acción |
|-------|--------------|--------|
| VALIDATE | Credenciales inválidas | Abortar con mensaje claro |
| BUILD | docker build falla | Abortar — no crear infraestructura |
| DEPLOY | terraform apply falla | Intentar terraform destroy parcial, alertar |
| RUN | Master no obtiene IP en 10 min | Abortar, destroy, alertar |
| MONITOR | Master falla | Alerta CRITICAL, no destruir auto |
| STORE | Resultados no en S3 | NO destruir infra, alertar operador |
| DESTROY | terraform destroy falla | Listar recursos a eliminar manualmente, alertar |
