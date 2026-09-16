# -----------------------------------------------------------------------
# Región y red — mismos valores que us-east-2_cmdic_prior_monte_carlo
# -----------------------------------------------------------------------
variable "aws_region" { default = "us-west-2" }

variable "vpc_id"                  { default = "vpc-0b08cba4a3d0cf109" }
variable "private_subnet_ids"      { default = ["subnet-0168d7d8961145483", "subnet-00f3021ecee723128"] }
variable "private_route_table_ids" { default = ["rtb-056497eebdfc41b40"] }

# -----------------------------------------------------------------------
# Modelo PEST
# -----------------------------------------------------------------------
variable "nombre_modelo"     { default = "cmdic_rajos_ensi.pst" }
variable "nombre_modelo_pest" { default = "cmdic_rajos_ensi.pst" }
# -----------------------------------------------------------------------
# MASTER-AGENT — instancias On-Demand dedicadas
# -----------------------------------------------------------------------

variable "ejecutable_master" { default = "./pest_hp" }
variable "ejecutable_agente" { default = "./agent_hp" }
variable "ejecutable_autonomo" { default = "./pest" }
variable "comando_master"    { default = "/h" }
##variable "comando_master"    { default = "/i /h" }
##variable "comando_master"    { default = "/i /hpstart /h" }
variable "comando_agente"    { default = "/h" }
variable "comando_autonomo" { default = "" }
variable "master_host" { default = "master.pest-cmdic-batch.local" }
variable "pest_port"         { default = 4004 }
variable "model_timeout"         { default = "15h" }
variable "model_timeout_stop"         { default = "10" }
variable "nombre_jacobiano" { default = "CMDIC_Rajos_ensi.jco" }
variable "activate_jacobiano" { default = "0" }

# -----------------------------------------------------------------------
# Proyecto y artefactos
# -----------------------------------------------------------------------
variable "project_name" { default = "pest-cmdic-linux-ensi" }
variable "s3_bucket_linux" { default = "312019940349-pest-cmdic-linux-ensi-west-2" }
variable "ecr_image_linux" { default = "312019940349.dkr.ecr.us-west-2.amazonaws.com/pest-cmdic-linux-ensi:latest" }

# -----------------------------------------------------------------------
# AWS Batch — compute environments
# -----------------------------------------------------------------------
variable "batch_instance_types" {
  description = "Tipos de instancia para los CEs. Usar .large con 2 vCPU/job garantiza 1 job por instancia → máxima frecuencia de turbo single-core."
  type        = list(string)
  # c7i: Intel Sapphire Rapids ~3.6 GHz | c7a: AMD EPYC Genoa ~3.7 GHz
  # c6i: Intel Ice Lake ~3.5 GHz        | c6a: AMD EPYC Milan ~3.6 GHz
  # Múltiples familias = mayor disponibilidad Spot
  default     = ["c7i.large", "c7a.large", "c6i.large", "c6a.large"]
}

variable "batch_max_vcpus" {
  description = "Máximo de vCPUs para el CE Spot. 2000 = 1000 jobs × 2 vCPU/job."
  type        = number
  default     = 2000
}

variable "batch_ondemand_max_vcpus" {
  description = "Máximo de vCPUs para el CE On-Demand (fallback si Spot no tiene capacidad)."
  type        = number
  default     = 500
}

# -----------------------------------------------------------------------
# AWS Batch — job definition
# -----------------------------------------------------------------------
variable "batch_vcpus_per_job" {
  description = "vCPUs por job. 2 vCPU sobre instancia .large = 1 job por instancia = turbo single-core máximo."
  type        = number
  default     = 2
}

variable "batch_memory_per_job_mb" {
  description = "Memoria en MB por job. Instancias .large tienen 4096 MB totales; ECS agent + OS reservan ~400 MB, dejando ~3700 MB disponibles para jobs."
  type        = number
  default     = 3600
}

variable "batch_job_timeout_seconds" {
  description = "Tiempo máximo de ejecución por job en segundos. 36000 = 10 horas. Reemplaza al EventBridge Scheduler del stack ECS."
  type        = number
  default     = 36000
}

variable "batch_retry_attempts" {
  description = "Reintentos automáticos si la instancia Spot es interrumpida (1 = sin reintentos, 2 = 1 reintento)."
  type        = number
  default     = 2
}

variable "batch_disk_size_gb" {
  description = "Disco EBS GB para instancias autonomas/Spot (OS + Docker + modelo)."
  type        = number
  default     = 120
}

variable "master_disk_size_gb" {
  description = "Disco EBS GB para el master PEST (r7iz.large). Modelo + resultados completos."
  type        = number
  default     = 100
}

variable "agent_disk_size_gb" {
  description = "Disco EBS GB para agentes PEST (c7a.medium). Solo archivos temporales de la corrida."
  type        = number
  default     = 50
}

# -----------------------------------------------------------------------
# Tags comunes
# -----------------------------------------------------------------------
variable "common_tags" {
  type = map(string)
  default = {
    Service = "BATCH"
    Owner   = "Modelamiento Numerico"
  }
}


variable "master_batch_memory_mb" {
  description = "Memoria MB para master en r7iz.large (16384 MB totales - ~1024 MB overhead ECS/OS)"
  type        = number
  default     = 15360
}

variable "master_max_vcpus" {
  description = "Max vCPUs CE master (solo 1 master a la vez = 2 vCPU maximos tipicamente)"
  type        = number
  default     = 10
}
variable "master_instance_types" {
  description = "Tipos de instancia para el master PEST (16 GB RAM). Multiples para mayor disponibilidad On-Demand."
  type        = list(string)
  # r7iz: 3.9 GHz Intel Sapphire Rapids (preferido — maxima frecuencia)
  # r6a : 3.6 GHz AMD EPYC Milan        (alta disponibilidad)
  # r6i : 3.5 GHz Intel Ice Lake        (alta disponibilidad)
  default     = ["r7iz.large", "r6a.large", "r6i.large"]
}
variable "agent_memory_mb" {
  description = "Memoria MB para agentes en c7a.medium (2048 MB totales - ~400 MB overhead ECS/OS)"
  type        = number
  default     = 1600
}

variable "agent_max_vcpus" {
  description = "Max vCPUs CE agentes. 1000 agentes x 1 vCPU = 1000 vCPUs."
  type        = number
  default     = 1000
}
