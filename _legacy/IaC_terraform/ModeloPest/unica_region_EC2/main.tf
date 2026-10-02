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

# Usar solo el provider por defecto en west-2
provider "aws" {
  region = var.region_west2
}

############################################
# Data: AZs
############################################
data "aws_availability_zones" "west2" {}

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
# S3 bucket para escritura del nodo central
############################################
data "aws_s3_bucket" "results" {
  bucket = var.s3_bucket_name
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
# SG del nodo central: permite 4004/TCP e ICMP desde VPC west2 (solo)
resource "aws_security_group" "central_sg" {
  name        = "${var.project_name}-central-sg"
  description = "Acceso al puerto PEST y ping desde la VPC central"
  vpc_id      = aws_vpc.west2.id
  tags        = { Name = "${var.project_name}-central-sg" }
}

# Inbound 4004 desde CIDR de la VPC west2 (quitar reglas que apuntaban a east1/east2)
resource "aws_security_group_rule" "central_in_tcp_west2" {
  type              = "ingress"
  security_group_id = aws_security_group.central_sg.id
  from_port         = var.pest_port
  to_port           = var.pest_port
  protocol          = "tcp"
  cidr_blocks       = [var.vpc_cidr_west2]
}

# Inbound ICMP (ping) desde CIDR de la VPC west2 (quitar reglas east1/east2)
resource "aws_security_group_rule" "central_in_icmp_west2" {
  type              = "ingress"
  security_group_id = aws_security_group.central_sg.id
  from_port         = -1
  to_port           = -1
  protocol          = "icmp"
  cidr_blocks       = [var.vpc_cidr_west2]
}

# Outbound permitir todo
resource "aws_security_group_rule" "central_out_all" {
  type              = "egress"
  security_group_id = aws_security_group.central_sg.id
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
}

# Security Group para VPC Endpoints Interface (ECR API y ECR DKR) - mantiene en west2
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


# SG para hosts en west2 (mantener)
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

    # Cron job para sincronizar con S3 cada 1 hora
    BUCKET_NAME=${var.s3_bucket_name}
    CRON_CMD="aws s3 sync /app/modelo s3://$BUCKET_NAME/app/modelo --delete"
    (crontab -l 2>/dev/null; echo "0 * * * * $CRON_CMD") | crontab -

    # Login ECR y ejecutar contenedor central
    REGION=${var.region_west2}
    CENTRAL_IMAGE=${var.ecr_image_central}

    aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $(echo $CENTRAL_IMAGE | cut -d'/' -f1)

    docker pull $CENTRAL_IMAGE

    # Poblar /app/modelo en el host con el contenido de la imagen si está vacío
    if [ -z "$(ls -A /app/modelo 2>/dev/null)" ]; then
      echo "Rellenando /app/modelo desde la imagen $CENTRAL_IMAGE"
      docker create --name tmp-populate "$CENTRAL_IMAGE"
      # Copia el contenido del contenedor a la ruta del host
      docker cp tmp-populate:/app/modelo/. /app/modelo/
      docker rm tmp-populate
    fi

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

# Capacity providers Fargate Spot
resource "aws_ecs_cluster_capacity_providers" "west2" {
  cluster_name       = aws_ecs_cluster.west2.name
  capacity_providers = ["FARGATE"]
  default_capacity_provider_strategy {
    capacity_provider = "FARGATE"
    weight            = 1000
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

  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_execution_role.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }
  container_definitions = jsonencode([
    {
      name      = local.host_container_name,
      image     = var.ecr_image_host_west2,
      essential = true,
      cpu       = 1024,
      memory    = 2048,
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

############################################
# ECS Services (host) por región
############################################
resource "aws_ecs_service" "host_west2" {
  name                = "${var.project_name}-host-service-west2"
  cluster             = aws_ecs_cluster.west2.id
  task_definition     = aws_ecs_task_definition.host_west2.arn
  desired_count       = var.desired_hosts_west2
  #se comenta para usar capacity providers
  launch_type         = "FARGATE"
  platform_version    = "LATEST"
  enable_ecs_managed_tags = true
  propagate_tags      = "SERVICE"

  #mezcla Spot + OnDemand (fallback)
  # capacity_provider_strategy {
  #   capacity_provider = "FARGATE_SPOT"
  #   weight            = 7
  # }
  # capacity_provider_strategy {
  #   capacity_provider = "FARGATE"
  #   weight            = 3
  # }

  network_configuration {
    subnets         = [aws_subnet.west2_private.id]
    security_groups = [aws_security_group.host_west2_sg.id]
    assign_public_ip = false
  }
}

resource "aws_appautoscaling_target" "host_west2" {
  max_capacity       = 1000
  min_capacity       = 20
  resource_id        = "service/${aws_ecs_cluster.west2.name}/${aws_ecs_service.host_west2.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "host_west2_cpu" {
  name               = "${var.project_name}-host-cpu-target"
  service_namespace  = "ecs"
  resource_id        = aws_appautoscaling_target.host_west2.resource_id
  scalable_dimension = aws_appautoscaling_target.host_west2.scalable_dimension
  policy_type        = "TargetTrackingScaling"

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value       = 80.0
    scale_in_cooldown  = 180
    scale_out_cooldown = 180
    disable_scale_in   = true 
  }
}