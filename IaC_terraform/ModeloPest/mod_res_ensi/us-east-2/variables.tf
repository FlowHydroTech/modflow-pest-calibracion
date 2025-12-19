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
  description = "Imagen ECR para el nodo central en us-east-2"
  default     = "312019940349.dkr.ecr.us-east-2.amazonaws.com/pest-mod-res-ensi-master:latest"
}

variable "ecr_image_host_east2" {
  type        = string
  description = "Imagen ECR para los hosts en us-east-2"
  default     = "312019940349.dkr.ecr.us-east-2.amazonaws.com/pest-mod-res-ensi-agente:latest"
}

variable "region_east2" { default = "us-east-2" }

variable "vpc_cidr_east2" { default = "10.10.0.0/16" }

variable "subnet_public_east2" { default = "10.10.0.0/21" }
variable "subnet_private_east2" { default = "10.10.8.0/21" }

variable "central_private_ip" { default = "10.10.10.10" }

variable "pest_port" { default = 4004 }

variable "desired_hosts_east2" { default = 22 }


