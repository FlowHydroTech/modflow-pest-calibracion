#configurar región AWS
variable "aws_region" {default = "us-west-2" }
#configurar VPC y subnets de la región seleccionada (privadas para mayor seguridad)
variable "vpc_id" { default = "vpc-0b08cba4a3d0cf109" } #VPC por defecto de la región seleccionada
variable "private_subnet_ids" {  default = ["subnet-0ce131779fb30b6a7", "subnet-00f3021ecee723128"] } #seleccione 2 subredes privadas en distintas zonas de disponibilidad
variable "private_route_table_ids" { default = ["rtb-056497eebdfc41b40"] } #tabla de rutas asociada a las subredes privadas
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
variable "project_name" { default = "mod-test" }
variable "s3_bucket" { default = "312019940349-test-capacitacion" }
variable "ecr_image" { default = "312019940349.dkr.ecr.us-west-2.amazonaws.com/pest-test:latest" }
variable "ecr_image_stop" { default = "312019940349.dkr.ecr.us-west-2.amazonaws.com/pest-test-stop:latest" }
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
  default     = "agente-001"
}