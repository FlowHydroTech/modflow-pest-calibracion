#configurar región AWS
variable "aws_region" {default = "us-east-2" }
#configurar VPC y subnets de la región seleccionada (deben ser privadas para mayor seguridad)
variable "vpc_id" { default = "vpc-0d15e6b1598fd08ef" }
variable "private_subnet_ids" {  default = ["subnet-017a501a7e052200f", "subnet-0357178626be5cf43"] }
variable "private_route_table_ids" { default     = ["rtb-04dee429f7aa02db0"] }
#nombre del modelo PEST que se debe ejecutar pest_hp.exe <nombre_modelo_pest> /h :4004
variable "ejecutable_autonomo" { default = "pest.exe" }
variable "ejecutable_master" { default = "pest_hp.exe" }
variable "ejecutable_agente" { default = "agent_hp.exe" }
variable "nombre_modelo_pest" { default = "mod_res_ensi.pst" }
variable "comando_master" { default = "/h" }
variable "comando_agente" { default = "/h" }
variable "nombre_jacobiano" { default = "mod_res_ensi.jco" }
variable "pest_port" { default = 4004 }
#nombre del proyecto para tags y nombres de recursos en AWS
variable "project_name" { default = "mod-res-ensi" }
variable "s3_bucket" { default = "312019940349-pest-mod-res-ensi-east-2" }
variable "ecr_image" { default = "312019940349.dkr.ecr.us-east-2.amazonaws.com/pest-mod-res-ensi:latest" }
variable "ecr_image_stop" { default = "312019940349.dkr.ecr.us-east-2.amazonaws.com/pest-mod-res-ensi-stop:latest" }
#cantidad de agentes a levantar con run-task
variable "agent_count" { default = 1 }
variable "common_tags" {
  type = map(string)
  default = {
    Service = "FARGATE"
    Owner   = "Modelamiento Numerico"
  }
}

variable "master_run_id" {
  description = "Identificador que fuerza la ejecución puntual del master cuando cambia. Dejar vacío para no ejecutar."
  type        = string
  default     = "master-001"
}
variable "agent_run_id" {
  description = "Identificador que fuerza la ejecución puntual de los agentes cuando cambia. Dejar vacío para no ejecutar."
  type        = string
  default     = "agente"
}