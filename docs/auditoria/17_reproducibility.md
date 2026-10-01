# Reproducibility Assessment

---

## Estado Actual de Trazabilidad

| Componente | ¿Se registra? | Dónde | Problema |
|------------|--------------|-------|----------|
| Versión del modelo (.pst) | ❌ No | — | Sin control de versiones del modelo |
| Git commit SHA del código | ❌ No | — | No se captura en ningún punto |
| Tag/digest de imagen Docker | ❌ No | Solo `:latest` en variables.tf | Tag mutable — distintas imágenes pueden tener el mismo tag |
| Versión de PEST | ❌ No | Solo en imagen (no registrado) | REQUIERE VALIDACIÓN del binario |
| Parámetros de calibración | ⚠️ Parcial | `variables.tf` local | No versionado, no archivado |
| Configuración (CPU/RAM/workers) | ⚠️ Parcial | `variables.tf` local | No asociado a la calibración específica |
| Timestamp inicio | ⚠️ Parcial | CloudWatch Logs (en log) | No estructurado, no consultable |
| Timestamp fin | ⚠️ Parcial | CloudWatch Logs (en log) | No estructurado |
| Versión infraestructura | ❌ No | — | Sin tagging de versión de IaC |
| Ubicación de resultados en S3 | ⚠️ Parcial | Hardcodeada en variables.tf | No asociada a la calibración específica |
| Phi inicial y final | ❌ No | Solo en logs como texto | No estructurado ni archivado |
| Estado de convergencia | ❌ No | Solo en logs | No registrado de forma estructurada |

---

## Problema Central: Tag `:latest`

Todas las imágenes se publican con el tag `:latest`:

```hcl
# variables.tf — todas las variantes usan :latest
variable "ecr_image_linux" {
  default = "312019940349.dkr.ecr.us-east-1.amazonaws.com/pest-talabre-linux:latest"
}
```

**Consecuencia:** No es posible saber qué versión del código y del modelo PEST se usó en una calibración pasada. Si se construye y publica una nueva imagen, todas las referencias a `:latest` apuntan automáticamente a la nueva versión.

**Solución:** Usar digests inmutables o tags versionados:
```bash
# Tag versionado (commitSHA)
docker tag pest-talabre-linux:latest \
    312019940349.dkr.ecr.us-east-1.amazonaws.com/pest-talabre-linux:$(git rev-parse --short HEAD)

# El digest es siempre inmutable:
# 312019940349.dkr.ecr.us-east-1.amazonaws.com/pest-talabre-linux@sha256:abc123...
```

---

## Calibration Manifest — Diseño Conceptual

Un Calibration Manifest es un archivo YAML/JSON generado automáticamente al finalizar cada calibración. Contiene toda la información necesaria para reproducir exactamente el mismo experimento.

### Estructura propuesta

```yaml
# Generado automáticamente al finalizar la calibración
# Almacenado en: s3://{bucket}/calibrations/{calibration_id}/manifest.yaml

calibration_id: "pest-talabre-linux-20260615-001"
status: "COMPLETED"           # COMPLETED | FAILED | STAGNATED | CONVERGED

timestamps:
  start: "2026-06-15T08:30:00Z"
  end: "2026-06-16T02:15:00Z"
  duration_hours: 17.75

model:
  name: "talabre_pwadj_ddn"
  pst_file: "talabre_pwadj_ddn.pst"
  version: "v2.3"             # etiqueta semántica del modelo (a definir)

code:
  git_sha: "abc123def456"
  git_branch: "main"
  git_tag: "v1.2.0"           # si existe

docker:
  image_uri: "312019940349.dkr.ecr.us-east-1.amazonaws.com/pest-talabre-linux:latest"
  image_digest: "sha256:abc123def456..."   # digest inmutable
  pest_version: "17.5"         # extraído del log del master

infrastructure:
  region: "us-east-1"
  terraform_module: "IaC_terraform/ModeloPest/talabre-linux/us-east-1"
  compute:
    master_instance: "r6a.xlarge"
    master_vcpus: 4
    master_memory_gb: 30
    agent_instance: "c7a.medium"
    agent_vcpus: 1
    agent_memory_gb: 1.6
    max_agents: 300
    compute_mode: "Spot+OnDemand"

calibration:
  initial_phi: 8432.5
  final_phi: 312.7
  phi_reduction_pct: 96.3
  total_iterations: 18
  total_model_runs: 4320
  convergence_status: "CONVERGED"
  convergence_criterion: "RELPARCHG"   # mensaje emitido por PEST

results:
  s3_bucket: "312019940349-pest-talabre-east-1"
  s3_model_prefix: "calibrations/pest-talabre-linux-20260615-001/modelo/"
  s3_logs_prefix: "calibrations/pest-talabre-linux-20260615-001/logs/"
  s3_manifest_path: "calibrations/pest-talabre-linux-20260615-001/manifest.yaml"
```

---

## Generación del Manifest — Lógica

```python
# Pseudocódigo para generar el manifest al finalizar una calibración

def generate_manifest(project_name, region, calibration_id):
    manifest = {
        "calibration_id": calibration_id,
        "status": "COMPLETED",
        "timestamps": {
            "start": get_batch_job_start_time(project_name),
            "end": get_batch_job_end_time(project_name),
        },
        "code": {
            "git_sha": subprocess.check_output(["git", "rev-parse", "HEAD"]).strip().decode(),
            "git_branch": subprocess.check_output(["git", "branch", "--show-current"]).strip().decode(),
        },
        "docker": {
            "image_uri": get_image_from_variables_tf(),
            "image_digest": get_ecr_image_digest(),  # via ECR API
            "pest_version": extract_pest_version_from_logs(),  # CloudWatch
        },
        "calibration": {
            "initial_phi": get_first_phi_from_logs(),   # CloudWatch Metric
            "final_phi": get_last_phi_from_logs(),
            "total_iterations": count_iterations_from_logs(),
        },
        "results": {
            "s3_bucket": get_from_variables_tf("s3_bucket_linux"),
            "s3_model_prefix": f"calibrations/{calibration_id}/modelo/",
        }
    }
    
    # Guardar en S3
    s3_client.put_object(
        Bucket=manifest["results"]["s3_bucket"],
        Key=f"calibrations/{calibration_id}/manifest.yaml",
        Body=yaml.dump(manifest)
    )
    
    return manifest
```

---

## Plan de Implementación de Reproducibilidad

### Fase 1 (corto plazo) — Mínimo viable
- [ ] Usar tags versionados (commit SHA) en imágenes Docker
- [ ] Registrar en los logs del entrypoint: Git SHA, nombre de imagen, timestamp

### Fase 5 (mediano plazo) — Calibration Manifest
- [ ] Implementar generación automática del manifest al finalizar
- [ ] Almacenar en S3 junto a los resultados
- [ ] Incluir Phi inicial/final, iteraciones, convergencia

### Fase 6 (largo plazo) — Reproducibilidad completa
- [ ] Versionar el modelo (.pst) con semántica clara
- [ ] Capturar digest inmutable de imagen en el manifest
- [ ] CI/CD que garantice build reproducible (sin cambios entre tags)
