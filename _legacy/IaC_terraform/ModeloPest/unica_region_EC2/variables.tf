variable "project_name" {
  type        = string
  default     = "pest-talabre"
}

variable "s3_bucket_name" { default = "312019940349-pest-talabre" }

variable "common_tags" {
  type = map(string)
  default = {
    Service = "PEST"
    Project = "pest-talabre"
    Owner   = "Modelamiento Numerico"
  }
}

# URLs completas de las imágenes en ECR (incluyendo tag)
variable "ecr_image_central" {
  type        = string
  description = "Imagen ECR para el nodo central en us-west-2"
}

variable "ecr_image_host_west2" {
  type        = string
  description = "Imagen ECR para los hosts en us-west-2"
}


variable "region_west2" { default = "us-west-2" }

variable "vpc_cidr_west2" { default = "10.10.0.0/16" }

variable "subnet_public_west2" { default = "10.10.0.0/24" }
variable "subnet_private_west2" { default = "10.10.10.0/24" }

variable "central_private_ip" { default = "10.10.10.10" }

variable "pest_port" { default = 4004 }

variable "desired_hosts_west2" { default = 1 }

variable "ecr_repo_central" { default = "pest-central" }
variable "ecr_repo_host" { default = "pest-host" }

