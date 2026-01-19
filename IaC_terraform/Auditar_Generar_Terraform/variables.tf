variable "vpc_id" {
  description = "VPC ID where resources will be created"
  type        = string
  default     = "vpc-0d15e6b1598fd08ef"
}

variable "private_subnet_ids" {
  description = "Private subnet IDs for resources"
  type        = list(string)
  default     = ["subnet-05c73f5c0f5f90c2c", "subnet-0e1c6e6f0f5f90c2d"]
}

variable "private_route_table_ids" {
  description = "Private route table IDs for S3 gateway endpoint"
  type        = list(string)
  default     = []
}
