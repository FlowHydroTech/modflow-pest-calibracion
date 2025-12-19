variable "project_name" {
  type        = string
  default     = "pest-mod-res-ensi"
}

variable "s3_bucket_name" { default = "312019940349-pest-mod-res-ensi" }

variable "common_tags" {
  type = map(string)
  default = {
    Service = "PEST"
    Project = "pest-mod-res-ensi"
    Owner   = "Modelamiento Numerico"
  }
}

# URLs completas de las imágenes en ECR (incluyendo tag)
variable "ecr_image_central" {
  type        = string
  description = "Imagen ECR para el nodo central en us-east-1"
  default     = "312019940349.dkr.ecr.us-east-1.amazonaws.com/pest-mod-res-ensi-master:latest"
}

variable "ecr_image_host_east1" {
  type        = string
  description = "Imagen ECR para los hosts en us-east-1"
  default     = "312019940349.dkr.ecr.us-east-1.amazonaws.com/pest-mod-res-ensi-agente:latest"
}


variable "region_east1" { default = "us-east-1" }

variable "vpc_cidr_east1" { default = "10.10.0.0/16" }

variable "subnet_public_east1" { default = "10.10.0.0/21" }
variable "subnet_private_east1" { default = "10.10.8.0/21" }

variable "central_private_ip" { default = "10.10.10.10" }

variable "pest_port" { default = 4004 }

variable "desired_hosts_east1" { default = 1 }

variable "ecr_repo_central" { default = "pest-central" }
variable "ecr_repo_host" { default = "pest-host" }

