# Executive Summary

**Auditoría Técnica — PEST Calibración en AWS**  
**Fecha:** Octubre 2026

---

## Las 15 conclusiones más importantes

### 1. El README describe AWS Batch, pero coexisten dos arquitecturas en paralelo

El repositorio tiene **dos generaciones de arquitectura activas simultáneamente**: la más antigua usa ECS Fargate (con Cloud Map / Service Discovery), la más reciente usa AWS Batch EC2. Ambas tienen código Terraform completo y scripts operacionales. Esta coexistencia genera confusión operacional y riesgo de aplicar la configuración incorrecta.

**Evidencia:** `IaC_terraform/Arquitectura_regional/main.tf` (ECS Fargate activo), `IaC_terraform/ModeloPest/talabre-linux/us-east-1/main.tf` (Batch EC2 activo)

---

### 2. No existe backend Terraform remoto — riesgo crítico de pérdida de control

No hay ningún bloque `backend "s3"` en ningún directorio Terraform. El `terraform.tfstate` es 100% local y está excluido del repositorio por `.gitignore`. Si el archivo local se pierde, `terraform destroy` fallará y los recursos quedarán huérfanos generando costos indefinidamente.

**Evidencia:** `provider.tf` en todos los módulos — ninguno tiene bloque `backend`

---

### 3. Las calibraciones no son reproducibles

No existe ningún mecanismo que registre versión de código (Git SHA), digest de imagen Docker, versión de PEST, parámetros usados, ni métricas de convergencia. Todas las imágenes se publican con el tag `:latest`, lo que hace imposible auditar qué binario ejecutó qué calibración.

---

### 4. La automatización es parcial y manual-intensiva

El flujo completo requiere que un operador ejecute manualmente **~8 pasos**: construir imagen Docker, publicar en ECR, editar `variables.tf`, ejecutar `terraform apply`, lanzar `launch_master_agents.py`, iniciar `auto_scaling_tasks.py`, monitorear, y finalmente `terraform destroy`. Cualquier interrupción en este flujo puede dejar recursos activos y costos no controlados.

---

### 5. El autoscaler depende de que el operador mantenga su máquina conectada

`auto_scaling_tasks.py` es un loop infinito (`while True`) que debe correr en la laptop del operador. Si se pierde la conexión, los agentes que terminan su trabajo no se eliminan (costo innecesario) y los nuevos agentes no se lanzan (calibración se ralentiza o detiene).

**Evidencia:** `auto_scaling_tasks.py` — `while True: ... time.sleep(minutes_sleep*60)`

---

### 6. Bug activo en el mecanismo de retry de agentes Wine

En `entrypoint_agent.sh` se referencia la variable `$RETRY_CODE` que nunca se define. La variable correcta es `$EXIT_CODE`. Este bug hace que el mecanismo de reintento ante el error Wine `c0000018` **nunca funcione**, lo que reduce la estabilidad de los agentes ante errores conocidos de Wine en AWS.

**Evidencia:** `Estructura_Base/nombre_proyecto_modelo/app/entrypoint_agent.sh` — condición `[ $RETRY_CODE -eq 80 ]`

---

### 7. No existe monitoreo del progreso científico (Phi / convergencia)

Los logs de PEST se capturan en CloudWatch pero ningún componente los analiza para extraer el **objective function (Phi)**, el número de iteraciones, ni detectar estancamiento o convergencia. Es imposible saber si una calibración está mejorando sin conectarse manualmente a los logs.

---

### 8. No existe sistema de alertas

No hay CloudWatch Alarms, ni SNS, ni ningún mecanismo que notifique de fallos del master, calibraciones detenidas, o costos anómalos. Un fallo crítico del master puede pasar desapercibido horas.

---

### 9. Datos sensibles de infraestructura en código versionado

El ID de cuenta AWS (`312019940349`) aparece en scripts versionados. Los IDs de VPC, subnets y route tables reales están como valores `default` en `variables.tf`. Esto expone la topología de red a cualquier persona con acceso al repositorio.

**Evidencia:** `AWS_ECR_carga_imagen_docker.ps1`, `IaC_terraform/Arquitectura_regional/variables.tf`

---

### 10. La arquitectura de cómputo más madura (Batch EC2) es la correcta para este workload

AWS Batch EC2 con instancias dedicadas (c7a.medium por agente, r6a.xlarge para master) es técnicamente superior a ECS Fargate para calibraciones PEST: instancias dedicadas maximizan la frecuencia de turbo single-core, Spot nativo reduce costos ~70%, y el timeout por job elimina la necesidad de un scheduler externo. La decisión de migrar a Batch fue correcta.

---

### 11. Los Dockerfiles usan Wine para ejecutar binarios PEST Windows en Linux

La imagen base (Ubuntu 25.04) instala Wine 64-bit para ejecutar `pest_hp.exe` y `agent_hp.exe`. Existe un problema conocido y documentado en el código (`wine: failed to map the shared user data: c0000018`) que causa fallos intermitentes en los agentes. El modelo numérico (MODFLOW via `mfusgt270`) sí se compila nativamente en Linux.

---

### 12. El `main.py` raíz está vacío y el proyecto Python no tiene estructura

`main.py` contiene solo `print("Hello from modflow-pest-calibracion!")`. No hay módulos compartidos, no hay tests, las dependencias en `pyproject.toml` y `requirements.txt` están desincronizadas, y la lógica está duplicada entre múltiples scripts sueltos.

---

### 13. Los scripts de operación tienen valores hardcodeados para un proyecto específico

`auto_scaling_tasks.py` tiene hardcodeados los nombres de log groups, cluster y job queue para `pest-talabre-linux`. No puede usarse para otro proyecto sin modificación manual del código fuente.

**Evidencia:** `auto_scaling_tasks.py` — `log_group_master = f"/batch/pest-talabre-linux-master"`

---

### 14. Hay prototipos con NAT Gateways que pueden estar generando costos fijos

Los módulos `Multiple_Region` y `unica_region_EC2` crean NAT Gateways (~$32/mes por región). Si alguno de estos stacks está actualmente desplegado, se generan entre $32 y $96/mes en costos fijos independientemente de si hay calibraciones activas. Los stacks de producción (talabre-linux) usan VPC Endpoints en su lugar, lo cual es correcto.

**REQUIERE VALIDACIÓN en consola AWS.**

---

### 15. La base técnica es sólida — los problemas son de automatización y gobernanza

La arquitectura Batch EC2, el diseño de networking con VPC Endpoints, los entrypoints de contenedor, el mecanismo de autoscaling basado en logs, y la estructura de IAM son técnicamente correctos. Con esfuerzo moderado, el sistema puede evolucionar hacia una solución completamente automatizada, observable y reproducible sin rediseñar la arquitectura fundamental.

---

## Respuestas a las preguntas clave

| Pregunta | Respuesta |
|----------|-----------|
| ¿Cómo funciona hoy? | Batch EC2 con orquestación Python manual desde la laptop del operador |
| ¿ECS Fargate sigue siendo la alternativa? | No — AWS Batch EC2 es la arquitectura activa y correcta |
| ¿Terraform está bien diseñado para create/destroy por calibración? | Parcialmente — falta backend remoto y verificación pre-destroy |
| ¿Qué sigue siendo manual? | Build Docker, terraform apply/destroy, lanzar scripts, autoscaler |
| ¿Cómo monitorear en tiempo real? | CloudWatch Metric Filters sobre logs del master → Custom Metrics → Dashboard |
| ¿Qué métricas de PEST podemos extraer? | Phi, iteración, corridas de modelo — visibles en stdout del master |
| ¿CloudWatch Dashboard es suficiente como primer visor? | Sí, para el MVP |
| ¿Cuáles son los Quick Wins? | Backend Terraform, corregir bug retry, Metric Filters, alertas SNS |
