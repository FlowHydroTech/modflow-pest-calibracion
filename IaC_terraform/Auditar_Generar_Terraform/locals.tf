# Archivos que definen variables locales y tags
locals {
  default_tags = merge(
    var.common_tags,
    {
      Region  = "us-east-2"
      Project = "mod-res-ensi"
    }
  )
}

variable "common_tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default = {
    Owner       = "Modelamiento Numerico"
    Service     = "FARGATE"
    Environment = "production"
  }
}
