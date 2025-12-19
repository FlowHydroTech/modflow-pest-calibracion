############################################
# Terraform y providers
############################################
terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

provider "aws" {
  region = var.region_west2
}

provider "aws" {
  alias  = "use1"
  region = var.region_east1
}

provider "aws" {
  alias  = "use2"
  region = var.region_east2
}

############################################
# Data: AZs
############################################
data "aws_availability_zones" "west2" {}
data "aws_availability_zones" "east1" {
  provider = aws.use1
}
data "aws_availability_zones" "east2" {
  provider = aws.use2
}

############################################
# VPC us-west-2 (central)
############################################
resource "aws_vpc" "west2" {
  cidr_block           = var.vpc_cidr_west2
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags = { Name = "${var.project_name}-vpc-west2" }
}

resource "aws_internet_gateway" "west2" {
  vpc_id = aws_vpc.west2.id
  tags = { Name = "${var.project_name}-igw-west2" }
}

resource "aws_subnet" "west2_public" {
  vpc_id                  = aws_vpc.west2.id
  cidr_block              = var.subnet_public_west2
  availability_zone       = data.aws_availability_zones.west2.names[0]
  map_public_ip_on_launch = true
  tags = { Name = "${var.project_name}-subnet-public-west2" }
}

resource "aws_subnet" "west2_private" {
  vpc_id            = aws_vpc.west2.id
  cidr_block        = var.subnet_private_west2
  availability_zone = data.aws_availability_zones.west2.names[1]
  tags = { Name = "${var.project_name}-subnet-private-west2" }
}

resource "aws_eip" "west2_nat_eip" {
  domain = "vpc"
  tags = { Name = "${var.project_name}-nat-eip-west2" }
}

resource "aws_nat_gateway" "west2" {
  allocation_id = aws_eip.west2_nat_eip.id
  subnet_id     = aws_subnet.west2_public.id
  tags = { Name = "${var.project_name}-nat-west2" }
  depends_on = [aws_internet_gateway.west2]
}

resource "aws_route_table" "west2_public" {
  vpc_id = aws_vpc.west2.id
  tags   = { Name = "${var.project_name}-rt-public-west2" }
}

resource "aws_route" "west2_public_inet" {
  route_table_id         = aws_route_table.west2_public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.west2.id
}

resource "aws_route_table_association" "west2_public_assoc" {
  route_table_id = aws_route_table.west2_public.id
  subnet_id      = aws_subnet.west2_public.id
}

resource "aws_route_table" "west2_private" {
  vpc_id = aws_vpc.west2.id
  tags   = { Name = "${var.project_name}-rt-private-west2" }
}

resource "aws_route" "west2_private_nat" {
  route_table_id         = aws_route_table.west2_private.id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.west2.id
}

resource "aws_route_table_association" "west2_private_assoc" {
  route_table_id = aws_route_table.west2_private.id
  subnet_id      = aws_subnet.west2_private.id
}

############################################
# VPC us-east-1 (hosts)
############################################
resource "aws_vpc" "east1" {
  provider              = aws.use1
  cidr_block            = var.vpc_cidr_east1
  enable_dns_support    = true
  enable_dns_hostnames  = true
  tags = { Name = "${var.project_name}-vpc-east1" }
}

resource "aws_internet_gateway" "east1" {
  provider = aws.use1
  vpc_id   = aws_vpc.east1.id
  tags     = { Name = "${var.project_name}-igw-east1" }
}

resource "aws_subnet" "east1_public" {
  provider                = aws.use1
  vpc_id                  = aws_vpc.east1.id
  cidr_block              = var.subnet_public_east1
  availability_zone       = data.aws_availability_zones.east1.names[0]
  map_public_ip_on_launch = true
  tags = { Name = "${var.project_name}-subnet-public-east1" }
}

resource "aws_subnet" "east1_private" {
  provider         = aws.use1
  vpc_id           = aws_vpc.east1.id
  cidr_block       = var.subnet_private_east1
  availability_zone = data.aws_availability_zones.east1.names[1]
  tags = { Name = "${var.project_name}-subnet-private-east1" }
}

resource "aws_eip" "east1_nat_eip" {
  provider = aws.use1
  domain   = "vpc"
  tags     = { Name = "${var.project_name}-nat-eip-east1" }
}

resource "aws_nat_gateway" "east1" {
  provider      = aws.use1
  allocation_id = aws_eip.east1_nat_eip.id
  subnet_id     = aws_subnet.east1_public.id
  tags          = { Name = "${var.project_name}-nat-east1" }
  depends_on    = [aws_internet_gateway.east1]
}

resource "aws_route_table" "east1_public" {
  provider = aws.use1
  vpc_id   = aws_vpc.east1.id
  tags     = { Name = "${var.project_name}-rt-public-east1" }
}

resource "aws_route" "east1_public_inet" {
  provider               = aws.use1
  route_table_id         = aws_route_table.east1_public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.east1.id
}

resource "aws_route_table_association" "east1_public_assoc" {
  provider       = aws.use1
  route_table_id = aws_route_table.east1_public.id
  subnet_id      = aws_subnet.east1_public.id
}

resource "aws_route_table" "east1_private" {
  provider = aws.use1
  vpc_id   = aws_vpc.east1.id
  tags     = { Name = "${var.project_name}-rt-private-east1" }
}

resource "aws_route" "east1_private_nat" {
  provider               = aws.use1
  route_table_id         = aws_route_table.east1_private.id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.east1.id
}

resource "aws_route_table_association" "east1_private_assoc" {
  provider       = aws.use1
  route_table_id = aws_route_table.east1_private.id
  subnet_id      = aws_subnet.east1_private.id
}

############################################
# VPC us-east-2 (hosts)
############################################
resource "aws_vpc" "east2" {
  provider              = aws.use2
  cidr_block            = var.vpc_cidr_east2
  enable_dns_support    = true
  enable_dns_hostnames  = true
  tags = { Name = "${var.project_name}-vpc-east2" }
}

resource "aws_internet_gateway" "east2" {
  provider = aws.use2
  vpc_id   = aws_vpc.east2.id
  tags     = { Name = "${var.project_name}-igw-east2" }
}

resource "aws_subnet" "east2_public" {
  provider                = aws.use2
  vpc_id                  = aws_vpc.east2.id
  cidr_block              = var.subnet_public_east2
  availability_zone       = data.aws_availability_zones.east2.names[0]
  map_public_ip_on_launch = true
  tags = { Name = "${var.project_name}-subnet-public-east2" }
}

resource "aws_subnet" "east2_private" {
  provider         = aws.use2
  vpc_id           = aws_vpc.east2.id
  cidr_block       = var.subnet_private_east2
  availability_zone = data.aws_availability_zones.east2.names[1]
  tags = { Name = "${var.project_name}-subnet-private-east2" }
}

resource "aws_eip" "east2_nat_eip" {
  provider = aws.use2
  domain   = "vpc"
  tags     = { Name = "${var.project_name}-nat-eip-east2" }
}

resource "aws_nat_gateway" "east2" {
  provider      = aws.use2
  allocation_id = aws_eip.east2_nat_eip.id
  subnet_id     = aws_subnet.east2_public.id
  tags          = { Name = "${var.project_name}-nat-east2" }
  depends_on    = [aws_internet_gateway.east2]
}

resource "aws_route_table" "east2_public" {
  provider = aws.use2
  vpc_id   = aws_vpc.east2.id
  tags     = { Name = "${var.project_name}-rt-public-east2" }
}

resource "aws_route" "east2_public_inet" {
  provider               = aws.use2
  route_table_id         = aws_route_table.east2_public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.east2.id
}

resource "aws_route_table_association" "east2_public_assoc" {
  provider       = aws.use2
  route_table_id = aws_route_table.east2_public.id
  subnet_id      = aws_subnet.east2_public.id
}

resource "aws_route_table" "east2_private" {
  provider = aws.use2
  vpc_id   = aws_vpc.east2.id
  tags     = { Name = "${var.project_name}-rt-private-east2" }
}

resource "aws_route" "east2_private_nat" {
  provider               = aws.use2
  route_table_id         = aws_route_table.east2_private.id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.east2.id
}

resource "aws_route_table_association" "east2_private_assoc" {
  provider       = aws.use2
  route_table_id = aws_route_table.east2_private.id
  subnet_id      = aws_subnet.east2_private.id
}

############################################
# VPC Peering (central <-> east1 & east2)
############################################
resource "aws_vpc_peering_connection" "west2_east1" {
  vpc_id        = aws_vpc.west2.id
  peer_vpc_id   = aws_vpc.east1.id
  peer_region   = var.region_east1
  tags = { Name = "${var.project_name}-peer-west2-east1" }
}

resource "aws_vpc_peering_connection_accepter" "west2_east1_accepter" {
  provider                  = aws.use1
  vpc_peering_connection_id = aws_vpc_peering_connection.west2_east1.id
  auto_accept               = true
  tags = { Name = "${var.project_name}-peer-accept-west2-east1" }
}

resource "aws_vpc_peering_connection" "west2_east2" {
  vpc_id        = aws_vpc.west2.id
  peer_vpc_id   = aws_vpc.east2.id
  peer_region   = var.region_east2
  tags = { Name = "${var.project_name}-peer-west2-east2" }
}

resource "aws_vpc_peering_connection_accepter" "west2_east2_accepter" {
  provider                  = aws.use2
  vpc_peering_connection_id = aws_vpc_peering_connection.west2_east2.id
  auto_accept               = true
  tags = { Name = "${var.project_name}-peer-accept-west2-east2" }
}

# Rutas en VPC central hacia east1 y east2
resource "aws_route" "west2_private_to_east1" {
  route_table_id         = aws_route_table.west2_private.id
  destination_cidr_block = var.vpc_cidr_east1
  vpc_peering_connection_id = aws_vpc_peering_connection.west2_east1.id
}
resource "aws_route" "west2_private_to_east2" {
  route_table_id         = aws_route_table.west2_private.id
  destination_cidr_block = var.vpc_cidr_east2
  vpc_peering_connection_id = aws_vpc_peering_connection.west2_east2.id
}

# Rutas en east1/east2 hacia VPC central
resource "aws_route" "east1_private_to_west2" {
  provider               = aws.use1
  route_table_id         = aws_route_table.east1_private.id
  destination_cidr_block = var.vpc_cidr_west2
  vpc_peering_connection_id = aws_vpc_peering_connection.west2_east1.id
}
resource "aws_route" "east2_private_to_west2" {
  provider               = aws.use2
  route_table_id         = aws_route_table.east2_private.id
  destination_cidr_block = var.vpc_cidr_west2
  vpc_peering_connection_id = aws_vpc_peering_connection.west2_east2.id
}

############################################
# S3 bucket para escritura del nodo central
############################################
data "aws_s3_bucket" "results" {
  bucket = var.s3_bucket_name
  #tags   = { Name = "${var.project_name}-results" }
}

############################################
# IAM para nodo central (EC2 -> ECR, S3 y Cloudwatch)
############################################
resource "aws_iam_role" "central_role" {
  name = "${var.project_name}-central-ec2-role"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17",
    Statement = [{
      Effect    = "Allow",
      Principal = { Service = "ec2.amazonaws.com" },
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_policy" "central_s3_policy" {
  name        = "${var.project_name}-central-s3-write"
  description = "Permitir escritura en el bucket S3 de resultados."
  policy      = jsonencode({
    Version   = "2012-10-17",
    Statement = [
      {
        Sid      = "S3WriteResults",
        Effect   = "Allow",
        Action   = ["s3:PutObject", "s3:AbortMultipartUpload", "s3:ListBucket", "s3:PutObjectAcl"],
        Resource = [
          data.aws_s3_bucket.results.arn,
          "${data.aws_s3_bucket.results.arn}/*"
        ]
      },
      {
        Sid      = "ECRAuthAndPull",
        Effect   = "Allow",
        Action   = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer",
          "ecr:DescribeRepositories",
          "ecr:BatchCheckLayerAvailability"
        ],
        Resource = "*"
      },
      {
        Sid      = "LogsBasic",
        Effect   = "Allow",
        Action   = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ],
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "attach_central_s3" {
  role       = aws_iam_role.central_role.name
  policy_arn = aws_iam_policy.central_s3_policy.arn
}

resource "aws_iam_policy" "central_logs_policy" {
  name        = "${var.project_name}-central-logs-policy"
  description = "Permitir al EC2 enviar logs a CloudWatch Logs"
  policy      = jsonencode({
    Version   = "2012-10-17",
    Statement = [{
      Effect   = "Allow",
      Action   = [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      Resource = "*"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "attach_central_logs" {
  role       = aws_iam_role.central_role.name
  policy_arn = aws_iam_policy.central_logs_policy.arn
}

resource "aws_iam_role_policy_attachment" "central_ssm_attach" {
  role       = aws_iam_role.central_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "central_profile" {
  name = "${var.project_name}-central-instance-profile"
  role = aws_iam_role.central_role.name
}


############################################
# IAM para nodo central (EC2 -> Cloudwatch)
############################################

resource "aws_iam_role" "ec2_cloudwatch_role" {
  name = "${var.project_name}-ec2-cloudwatch-role"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17",
    Statement = [{
      Effect    = "Allow",
      Principal = { Service = "ec2.amazonaws.com" },
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ec2_cloudwatch_attach" {
  role       = aws_iam_role.ec2_cloudwatch_role.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
}

resource "aws_iam_instance_profile" "ec2_cloudwatch_profile" {
  name = "${var.project_name}-ec2-cloudwatch-profile"
  role = aws_iam_role.ec2_cloudwatch_role.name
}

############################################
# IAM para nodos host (FARGATE -> ECR)
############################################
resource "aws_iam_role" "ecs_task_execution_role" {
  name = "${var.project_name}-ecs-task-execution-role"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17",
    Statement = [{
      Effect    = "Allow",
      Principal = { Service = "ecs-tasks.amazonaws.com" },
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution_role_policy" {
  role       = aws_iam_role.ecs_task_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}


############################################
# Security Groups: central y hosts
############################################
# SG del nodo central: permite 4004/TCP e ICMP desde VPCs east1/east2 y west2
resource "aws_security_group" "central_sg" {
  name        = "${var.project_name}-central-sg"
  description = "Acceso al puerto PEST y ping desde VPCs peered"
  vpc_id      = aws_vpc.west2.id
  tags        = { Name = "${var.project_name}-central-sg" }
}

# Inbound 4004 desde CIDRs de VPCs
resource "aws_security_group_rule" "central_in_tcp_west2" {
  type              = "ingress"
  security_group_id = aws_security_group.central_sg.id
  from_port         = var.pest_port
  to_port           = var.pest_port
  protocol          = "tcp"
  cidr_blocks       = [var.vpc_cidr_west2]
}
resource "aws_security_group_rule" "central_in_tcp_east1" {
  type              = "ingress"
  security_group_id = aws_security_group.central_sg.id
  from_port         = var.pest_port
  to_port           = var.pest_port
  protocol          = "tcp"
  cidr_blocks       = [var.vpc_cidr_east1]
}
resource "aws_security_group_rule" "central_in_tcp_east2" {
  type              = "ingress"
  security_group_id = aws_security_group.central_sg.id
  from_port         = var.pest_port
  to_port           = var.pest_port
  protocol          = "tcp"
  cidr_blocks       = [var.vpc_cidr_east2]
}

# Inbound ICMP (ping) desde CIDRs de VPCs
resource "aws_security_group_rule" "central_in_icmp_west2" {
  type              = "ingress"
  security_group_id = aws_security_group.central_sg.id
  from_port         = -1
  to_port           = -1
  protocol          = "icmp"
  cidr_blocks       = [var.vpc_cidr_west2]
}
resource "aws_security_group_rule" "central_in_icmp_east1" {
  type              = "ingress"
  security_group_id = aws_security_group.central_sg.id
  from_port         = -1
  to_port           = -1
  protocol          = "icmp"
  cidr_blocks       = [var.vpc_cidr_east1]
}
resource "aws_security_group_rule" "central_in_icmp_east2" {
  type              = "ingress"
  security_group_id = aws_security_group.central_sg.id
  from_port         = -1
  to_port           = -1
  protocol          = "icmp"
  cidr_blocks       = [var.vpc_cidr_east2]
}

# Outbound permitir todo (para iniciar conexiones y ECR/S3)
resource "aws_security_group_rule" "central_out_all" {
  type              = "egress"
  security_group_id = aws_security_group.central_sg.id
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
}

# Security Group para VPC Endpoints Interface (ECR API y ECR DKR)
resource "aws_security_group" "endpoint" {
  name        = "${var.project_name}-endpoint-sg"
  description = "Permitir trafico interno en 443 hacia los endpoints de ECR"
  vpc_id      = aws_vpc.west2.id

  # Permitir tráfico entrante en HTTPS desde las subnets privadas
  ingress {
    description = "HTTPS desde subnets privadas"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [aws_vpc.west2.cidr_block]  # todo el rango de la VPC
  }

  # Permitir todo el tráfico de salida
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-endpoint-sg"
  }
}


# SG para hosts en cada región
resource "aws_security_group" "host_west2_sg" {
  name        = "${var.project_name}-host-west2-sg"
  description = "Hosts permiten 4004/TCP e ICMP desde VPC central"
  vpc_id      = aws_vpc.west2.id
  tags        = { Name = "${var.project_name}-host-west2-sg" }
}

resource "aws_security_group_rule" "host_west2_in_tcp" {
  type              = "ingress"
  security_group_id = aws_security_group.host_west2_sg.id
  from_port         = var.pest_port
  to_port           = var.pest_port
  protocol          = "tcp"
  cidr_blocks       = [var.vpc_cidr_west2]
}
resource "aws_security_group_rule" "host_west2_in_icmp" {
  type              = "ingress"
  security_group_id = aws_security_group.host_west2_sg.id
  from_port         = -1
  to_port           = -1
  protocol          = "icmp"
  cidr_blocks       = [var.vpc_cidr_west2]
}
resource "aws_security_group_rule" "host_west2_out_all" {
  type              = "egress"
  security_group_id = aws_security_group.host_west2_sg.id
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
}

resource "aws_security_group" "host_east1_sg" {
  provider    = aws.use1
  name        = "${var.project_name}-host-east1-sg"
  description = "Hosts permiten 4004/TCP e ICMP desde VPC central"
  vpc_id      = aws_vpc.east1.id
  tags        = { Name = "${var.project_name}-host-east1-sg" }
}
resource "aws_security_group_rule" "host_east1_in_tcp" {
  provider          = aws.use1
  type              = "ingress"
  security_group_id = aws_security_group.host_east1_sg.id
  from_port         = var.pest_port
  to_port           = var.pest_port
  protocol          = "tcp"
  cidr_blocks       = [var.vpc_cidr_west2]
}
resource "aws_security_group_rule" "host_east1_in_icmp" {
  provider          = aws.use1
  type              = "ingress"
  security_group_id = aws_security_group.host_east1_sg.id
  from_port         = -1
  to_port           = -1
  protocol          = "icmp"
  cidr_blocks       = [var.vpc_cidr_west2]
}
resource "aws_security_group_rule" "host_east1_out_all" {
  provider          = aws.use1
  type              = "egress"
  security_group_id = aws_security_group.host_east1_sg.id
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
}

resource "aws_security_group" "host_east2_sg" {
  provider    = aws.use2
  name        = "${var.project_name}-host-east2-sg"
  description = "Hosts permiten 4004/TCP e ICMP desde VPC central"
  vpc_id      = aws_vpc.east2.id
  tags        = { Name = "${var.project_name}-host-east2-sg" }
}
resource "aws_security_group_rule" "host_east2_in_tcp" {
  provider          = aws.use2
  type              = "ingress"
  security_group_id = aws_security_group.host_east2_sg.id
  from_port         = var.pest_port
  to_port           = var.pest_port
  protocol          = "tcp"
  cidr_blocks       = [var.vpc_cidr_west2]
}
resource "aws_security_group_rule" "host_east2_in_icmp" {
  provider          = aws.use2
  type              = "ingress"
  security_group_id = aws_security_group.host_east2_sg.id
  from_port         = -1
  to_port           = -1
  protocol          = "icmp"
  cidr_blocks       = [var.vpc_cidr_west2]
}
resource "aws_security_group_rule" "host_east2_out_all" {
  provider          = aws.use2
  type              = "egress"
  security_group_id = aws_security_group.host_east2_sg.id
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
}

############################################
# EC2 nodo central (us-west-2)
############################################
data "aws_ami" "amazon_linux_2" {
  owners      = ["amazon"]
  most_recent = true
  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-*-x86_64-gp2"]
  }
}

resource "aws_instance" "central" {
  ami                         = data.aws_ami.amazon_linux_2.id
  instance_type               = "t3.medium"
  subnet_id                   = aws_subnet.west2_private.id
  private_ip                  = var.central_private_ip
  associate_public_ip_address = false
  iam_instance_profile        = aws_iam_instance_profile.central_profile.name
  vpc_security_group_ids      = [aws_security_group.central_sg.id]
  tags = {
    Name = "${var.project_name}-central-ec2"
    Role = "central-node"
    Servicio = "PEST"
    Owner = "Modelamiento Numerico"
  }
  root_block_device {
    volume_size = 50   # tamaño en GB
    volume_type = "gp3"
  }

  user_data = <<-EOF
    #!/bin/bash
    set -xe

    yum update -y
    yum install -y amazon-cloudwatch-agent docker awscli iputils 

    systemctl enable docker
    systemctl start docker

    # Crear directorio para modelo
    mkdir -p /app/modelo

    # Configuración CloudWatch Agent
    cat <<CWAGENTCFG >/opt/aws/amazon-cloudwatch-agent/bin/config.json
    {
      "logs": {
        "logs_collected": {
          "files": {
            "collect_list": [
              {
                "file_path": "/var/log/messages",
                "log_group_name": "${var.project_name}-ec2-central",
                "log_stream_name": "system-messages",
                "timestamp_format": "%b %d %H:%M:%S"
              },
              {
                "file_path": "/var/log/cloud-init.log",
                "log_group_name": "${var.project_name}-ec2-central",
                "log_stream_name": "cloud-init",
                "timestamp_format": "%Y-%m-%d %H:%M:%S"
              }
            ]
          }
        }
      }
    }
  CWAGENTCFG

    # Iniciar CloudWatch Agent
    /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
      -a fetch-config -m ec2 -c file:/opt/aws/amazon-cloudwatch-agent/bin/config.json -s

    # Cron job para sincronizar con S3 cada 5 minutos
    BUCKET_NAME=${var.s3_bucket_name}
    CRON_CMD="aws s3 sync /app s3://$BUCKET_NAME --delete"
    (crontab -l 2>/dev/null; echo "*/5 * * * * $CRON_CMD") | crontab -

    # Login ECR y ejecutar contenedor central
    REGION=${var.region_west2}
    CENTRAL_IMAGE=${var.ecr_image_central}

    aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $(echo $CENTRAL_IMAGE | cut -d'/' -f1)

    docker pull $CENTRAL_IMAGE

    docker run -d --name pest-central \
      -p ${var.pest_port}:${var.pest_port} \
      -v /app/modelo:/app/modelo \
      --log-driver=awslogs \
      --log-opt awslogs-region=${var.region_west2} \
      --log-opt awslogs-group=${var.project_name}-ec2-central-container \
      --log-opt awslogs-stream=pest-central \
      --restart=always \
      $CENTRAL_IMAGE
  EOF

  depends_on = [
    aws_nat_gateway.west2
  ]
}

############################################
# ECS Clusters (hosts) por región
############################################
# us-west-2 cluster
resource "aws_ecs_cluster" "west2" {
  name = "${var.project_name}-ecs-west2"
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

# us-east-1 cluster
resource "aws_ecs_cluster" "east1" {
  provider = aws.use1
  name     = "${var.project_name}-ecs-east1"
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

# us-east-2 cluster
resource "aws_ecs_cluster" "east2" {
  provider = aws.use2
  name     = "${var.project_name}-ecs-east2"
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

# Capacity providers Fargate Spot
resource "aws_ecs_cluster_capacity_providers" "west2" {
  cluster_name       = aws_ecs_cluster.west2.name
  capacity_providers = ["FARGATE_SPOT"]
  default_capacity_provider_strategy {
    capacity_provider = "FARGATE_SPOT"
    weight            = 1
  }
}

resource "aws_ecs_cluster_capacity_providers" "east1" {
  provider           = aws.use1
  cluster_name       = aws_ecs_cluster.east1.name
  capacity_providers = ["FARGATE_SPOT"]
  default_capacity_provider_strategy {
    capacity_provider = "FARGATE_SPOT"
    weight            = 1
  }
}

resource "aws_ecs_cluster_capacity_providers" "east2" {
  provider           = aws.use2
  cluster_name       = aws_ecs_cluster.east2.name
  capacity_providers = ["FARGATE_SPOT"]
  default_capacity_provider_strategy {
    capacity_provider = "FARGATE_SPOT"
    weight            = 1
  }
}

############################################
# CloudWatch Logs para EC2 central
############################################

resource "aws_cloudwatch_log_group" "ec2_central_logs" {
  name              = "${var.project_name}-ec2-central"
  retention_in_days = 30
}

############################################
# CloudWatch Logs para tareas y EC2 Central
############################################
resource "aws_cloudwatch_log_group" "hosts" {
  name              = "/ecs/${var.project_name}/hosts"
  retention_in_days = 30
}

resource "aws_cloudwatch_log_group" "hosts_e1" {
  provider          = aws.use1
  name              = "/ecs/${var.project_name}/hosts-east1"
  retention_in_days = 30
}

resource "aws_cloudwatch_log_group" "hosts_e2" {
  provider          = aws.use2
  name              = "/ecs/${var.project_name}/hosts-east2"
  retention_in_days = 30
}

resource "aws_cloudwatch_log_group" "ec2_central_container_logs" {
  name              = "${var.project_name}-ec2-central-container"
  retention_in_days = 30
}

############################################
# ECS Task Definitions (host) por región
############################################
locals {
  host_container_name = "pest-host"
}

# west2 task def
resource "aws_ecs_task_definition" "host_west2" {
  family                   = "${var.project_name}-host-west2"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "1024"
  memory                   = "2048"

  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn   # obligatorio
  task_role_arn            = aws_iam_role.ecs_task_execution_role.arn   # opcional, si el contenedor necesita permisos adicionales
  
  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }
  container_definitions = jsonencode([
    {
      name      = local.host_container_name,
      image     = var.ecr_image_host_west2,
      essential = true,
      portMappings = [
        { containerPort = var.pest_port, hostPort = var.pest_port, protocol = "tcp" }
      ],
      logConfiguration = {
        logDriver = "awslogs",
        options = {
          awslogs-group         = aws_cloudwatch_log_group.hosts.name,
          awslogs-region        = var.region_west2,
          awslogs-stream-prefix = "ecs"
        }
      }
    }
  ])
}

# east1 task def
resource "aws_ecs_task_definition" "host_east1" {
  provider                 = aws.use1
  family                   = "${var.project_name}-host-east1"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "1024"
  memory                   = "2048"
  
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn   # obligatorio
  task_role_arn            = aws_iam_role.ecs_task_execution_role.arn   # opcional, si el contenedor necesita permisos adicionales
  
  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }
  container_definitions = jsonencode([
    {
      name      = local.host_container_name,
      image     = var.ecr_image_host_east1,
      essential = true,
      portMappings = [
        { containerPort = var.pest_port, hostPort = var.pest_port, protocol = "tcp" }
      ],
      logConfiguration = {
        logDriver = "awslogs",
        options = {
          awslogs-group         = aws_cloudwatch_log_group.hosts_e1.name,
          awslogs-region        = var.region_east1,
          awslogs-stream-prefix = "ecs"
        }
      }
    }
  ])
}

# east2 task def
resource "aws_ecs_task_definition" "host_east2" {
  provider                 = aws.use2
  family                   = "${var.project_name}-host-east2"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "1024"
  memory                   = "2048"
  
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn   # obligatorio
  task_role_arn            = aws_iam_role.ecs_task_execution_role.arn   # opcional, si el contenedor necesita permisos adicionales
  
  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }
  container_definitions = jsonencode([
    {
      name      = local.host_container_name,
      image     = var.ecr_image_host_east2,
      essential = true,
      portMappings = [
        { containerPort = var.pest_port, hostPort = var.pest_port, protocol = "tcp" }
      ],
      logConfiguration = {
        logDriver = "awslogs",
        options = {
          awslogs-group         = aws_cloudwatch_log_group.hosts_e2.name,
          awslogs-region        = var.region_east2,
          awslogs-stream-prefix = "ecs"
        }
      }
    }
  ])
}

############################################
# ECS Services (host) por región
############################################
resource "aws_ecs_service" "host_west2" {
  name                               = "${var.project_name}-host-service-west2"
  cluster                            = aws_ecs_cluster.west2.id
  task_definition                    = aws_ecs_task_definition.host_west2.arn
  desired_count                      = var.desired_hosts_west2
  launch_type                        = "FARGATE"
  platform_version                   = "LATEST"
  enable_ecs_managed_tags            = true
  propagate_tags                     = "SERVICE"

  network_configuration {
    subnets         = [aws_subnet.west2_private.id]
    security_groups = [aws_security_group.host_west2_sg.id]
    assign_public_ip = false
  }

  depends_on = [
    aws_vpc_peering_connection.west2_east1,
    aws_vpc_peering_connection.west2_east2
  ]
}

resource "aws_ecs_service" "host_east1" {
  provider                           = aws.use1
  name                               = "${var.project_name}-host-service-east1"
  cluster                            = aws_ecs_cluster.east1.id
  task_definition                    = aws_ecs_task_definition.host_east1.arn
  desired_count                      = var.desired_hosts_east1
  launch_type                        = "FARGATE"
  platform_version                   = "LATEST"
  enable_ecs_managed_tags            = true
  propagate_tags                     = "SERVICE"

  network_configuration {
    subnets          = [aws_subnet.east1_private.id]
    security_groups  = [aws_security_group.host_east1_sg.id]
    assign_public_ip = false
  }

  depends_on = [
    aws_vpc_peering_connection.west2_east1
  ]
}

resource "aws_ecs_service" "host_east2" {
  provider                           = aws.use2
  name                               = "${var.project_name}-host-service-east2"
  cluster                            = aws_ecs_cluster.east2.id
  task_definition                    = aws_ecs_task_definition.host_east2.arn
  desired_count                      = var.desired_hosts_east2
  launch_type                        = "FARGATE"
  platform_version                   = "LATEST"
  enable_ecs_managed_tags            = true
  propagate_tags                     = "SERVICE"

  network_configuration {
    subnets          = [aws_subnet.east2_private.id]
    security_groups  = [aws_security_group.host_east2_sg.id]
    assign_public_ip = false
  }

  depends_on = [
    aws_vpc_peering_connection.west2_east2
  ]
}

