locals {
  default_tags = merge(
    var.common_tags,
    {
      Region  = var.aws_region
      Project = var.project_name
    }
  )
}

# -----------------------------------------------------------------------
# CIDR block de la VPC (para reglas de Security Group)
# -----------------------------------------------------------------------
data "aws_vpc" "selected" {
  id = var.vpc_id
}

# -----------------------------------------------------------------------
# IAM — Job Task Role (jobRoleArn)
# Permisos de aplicación para el contenedor del job:
#   - S3: lectura/escritura del modelo y resultados
#   - SSM Messages: ECS Exec (aws ecs execute-command) para debug interactivo
#   - CloudWatch Logs: escritura de logs del proceso PEST
# Trust: ecs-tasks.amazonaws.com es válido tanto para ECS como para Batch EC2
# -----------------------------------------------------------------------
resource "aws_iam_role" "task_role" {
  name = "${var.project_name}-batch-task-role-${var.aws_region}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = local.default_tags
}

resource "aws_iam_role_policy" "task_role_s3" {
  name = "S3Access"
  role = aws_iam_role.task_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "s3:PutObject",
        "s3:GetObject",
        "s3:ListBucket",
        "s3:PutObjectAcl",
        "s3:DeleteObject"
      ]
      Resource = ["arn:aws:s3:::*", "arn:aws:s3:::*/*"]
    }]
  })
}

# SSM Messages: necesario para ECS Exec (aws ecs execute-command --task <id>)
# Requiere también el VPC Endpoint ssmmessages (agregado abajo)
resource "aws_iam_role_policy" "task_role_ssm_messages" {
  name = "SSMMessagesExec"
  role = aws_iam_role.task_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "ssmmessages:CreateControlChannel",
        "ssmmessages:CreateDataChannel",
        "ssmmessages:OpenControlChannel",
        "ssmmessages:OpenDataChannel"
      ]
      Resource = "*"
    }]
  })
}

resource "aws_iam_role_policy" "task_role_logs" {
  name = "CloudWatchLogsWrite"
  role = aws_iam_role.task_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "logs:DescribeLogStreams"
      ]
      Resource = "arn:aws:logs:*:*:*"
    }]
  })
}

# -----------------------------------------------------------------------
# Security Group para los nuevos VPC Endpoints de este módulo
# Permite HTTPS (443) desde la VPC hacia los endpoints
# -----------------------------------------------------------------------
resource "aws_security_group" "vpc_endpoints" {
  name        = "${var.project_name}-batch-vpc-endpoints-sg"
  description = "HTTPS from VPC to VPC Endpoints of the Batch module (ecs, ecs-agent, ecs-telemetry, ssm)"
  vpc_id      = var.vpc_id

  ingress {
    description = "HTTPS from VPC"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.selected.cidr_block]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.default_tags, { Name = "${var.project_name}-batch-vpc-endpoints-sg" })
}

# -----------------------------------------------------------------------
# VPC Endpoints para ECS Agent en EC2 (sin NAT Gateway)
# OBLIGATORIOS: el ECS agent que corre en cada instancia Batch necesita
# alcanzar el control plane de ECS para registrarse y recibir tareas.
# -----------------------------------------------------------------------
resource "aws_vpc_endpoint" "ecs" {
  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.${var.aws_region}.ecs"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = var.private_subnet_ids
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true
  tags                = merge(local.default_tags, { Name = "${var.project_name}-ecs-endpoint" })
}

resource "aws_vpc_endpoint" "ecs_agent" {
  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.${var.aws_region}.ecs-agent"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = var.private_subnet_ids
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true
  tags                = merge(local.default_tags, { Name = "${var.project_name}-ecs-agent-endpoint" })
}

resource "aws_vpc_endpoint" "ecs_telemetry" {
  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.${var.aws_region}.ecs-telemetry"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = var.private_subnet_ids
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true
  tags                = merge(local.default_tags, { Name = "${var.project_name}-ecs-telemetry-endpoint" })
}

# -----------------------------------------------------------------------
# VPC Endpoints para pull de imagen desde ECR sin IP publica ni NAT
# ecr.api: GetAuthorizationToken y APIs de ECR
# ecr.dkr: registry Docker privado de ECR
# s3     : capas de imagen almacenadas por ECR en S3
# logs   : envio de logs awslogs desde ECS/Batch
# -----------------------------------------------------------------------
resource "aws_vpc_endpoint" "ecr_api" {
  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.${var.aws_region}.ecr.api"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = var.private_subnet_ids
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true
  tags                = merge(local.default_tags, { Name = "${var.project_name}-ecr-api-endpoint" })
}

resource "aws_vpc_endpoint" "ecr_dkr" {
  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.${var.aws_region}.ecr.dkr"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = var.private_subnet_ids
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true
  tags                = merge(local.default_tags, { Name = "${var.project_name}-ecr-dkr-endpoint" })
}

resource "aws_vpc_endpoint" "logs" {
  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.${var.aws_region}.logs"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = var.private_subnet_ids
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true
  tags                = merge(local.default_tags, { Name = "${var.project_name}-logs-endpoint" })
}

resource "aws_vpc_endpoint" "s3" {
  vpc_id            = var.vpc_id
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = var.private_route_table_ids
  tags              = merge(local.default_tags, { Name = "${var.project_name}-s3-endpoint" })
}

# -----------------------------------------------------------------------
# VPC Endpoints para SSM Session Manager (acceso a instancias EC2 sin NAT)
# Permiten ejecutar `aws ssm start-session --target <instance-id>` desde
# cualquier lugar sin exponer las instancias a Internet.
# ssm         : protocolo de control del agente SSM
# ssmmessages : canal de datos (también usado por ECS Exec)
# ec2messages : entrega de comandos Run Command al agente SSM
# -----------------------------------------------------------------------
resource "aws_vpc_endpoint" "ssm" {
  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.${var.aws_region}.ssm"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = var.private_subnet_ids
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true
  tags                = merge(local.default_tags, { Name = "${var.project_name}-ssm-endpoint" })
}

resource "aws_vpc_endpoint" "ssmmessages" {
  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.${var.aws_region}.ssmmessages"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = var.private_subnet_ids
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true
  tags                = merge(local.default_tags, { Name = "${var.project_name}-ssmmessages-endpoint" })
}

resource "aws_vpc_endpoint" "ec2messages" {
  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.${var.aws_region}.ec2messages"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = var.private_subnet_ids
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true
  tags                = merge(local.default_tags, { Name = "${var.project_name}-ec2messages-endpoint" })
}

# -----------------------------------------------------------------------
# IAM — Batch Service Role
# Permite a AWS Batch gestionar EC2, Auto Scaling y redes en tu cuenta
# -----------------------------------------------------------------------
resource "aws_iam_role" "batch_service_role" {
  name = "${var.project_name}-batch-service-role-${var.aws_region}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "batch.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = local.default_tags
}

resource "aws_iam_role_policy_attachment" "batch_service_policy" {
  role       = aws_iam_role.batch_service_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBatchServiceRole"
}

# -----------------------------------------------------------------------
# IAM — EC2 Instance Role para instancias Batch
# El ECS agent en cada instancia usa este rol para:
#   - Registrar la instancia en el cluster ECS interno de Batch
#   - Hacer pull de imágenes ECR (autorización)
#   - Enviar logs a CloudWatch
# NOTA: los permisos S3 de la aplicación van en el jobRoleArn, no aquí.
# -----------------------------------------------------------------------
resource "aws_iam_role" "batch_instance_role" {
  name = "${var.project_name}-batch-instance-role-${var.aws_region}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = local.default_tags
}

resource "aws_iam_role_policy_attachment" "batch_instance_ecs_policy" {
  role       = aws_iam_role.batch_instance_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceforEC2Role"
}

# SSM Session Manager: permite conectarse directamente a las instancias EC2
# via `aws ssm start-session --target <instance-id>` sin necesidad de SSH ni IGW.
# Requiere los VPC Endpoints ssm, ssmmessages y ec2messages (agregados abajo).
resource "aws_iam_role_policy_attachment" "batch_instance_ssm_policy" {
  role       = aws_iam_role.batch_instance_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "batch_instance_profile" {
  name = "${var.project_name}-batch-instance-profile-${var.aws_region}"
  role = aws_iam_role.batch_instance_role.name
  tags = local.default_tags
}

# -----------------------------------------------------------------------
# Security Group para instancias EC2 Batch
# Los agentes PEST inician la conexión hacia el master (outbound TCP 4004)
# No se requiere inbound desde el exterior.
# IMPORTANTE: el SG del master PEST debe permitir inbound TCP 4004
# desde este SG (ver outputs.tf para obtener el ID).
# -----------------------------------------------------------------------
resource "aws_security_group" "batch_instances" {
  name        = "${var.project_name}-batch-instances-sg"
  description = "SG for Batch EC2 instances running PEST agents - egress only"
  vpc_id      = var.vpc_id

  egress {
    description = "All outbound: PEST agents to master TCP 4004, HTTPS to VPC endpoints 443"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.default_tags, { Name = "${var.project_name}-batch-instances-sg" })
}

# -----------------------------------------------------------------------
# Launch Template
# Configura el volumen EBS de las instancias para alojar OS + Docker + modelo
# http_put_response_hop_limit = 2: OBLIGATORIO para que los contenedores
# puedan acceder al IMDS (Instance Metadata Service) y obtener credenciales IAM
# -----------------------------------------------------------------------
resource "aws_launch_template" "batch_lt" {
  name_prefix = "${var.project_name}-batch-lt-"
  description = "Instancias Batch: disco ${var.batch_disk_size_gb} GB gp3, IMDSv2"

  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      volume_size           = var.batch_disk_size_gb
      volume_type           = "gp3"
      delete_on_termination = true
      encrypted             = true
    }
  }

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
  }

  tag_specifications {
    resource_type = "instance"
    tags          = merge(local.default_tags, { Name = "${var.project_name}-batch-ec2" })
  }

  tag_specifications {
    resource_type = "volume"
    tags          = local.default_tags
  }

  tags = local.default_tags
}

# Launch Template para el master PEST (r7iz.large — 100 GB para modelo + resultados)
resource "aws_launch_template" "master_lt" {
  name_prefix = "${var.project_name}-master-lt-"
  description = "Master PEST: disco ${var.master_disk_size_gb} GB gp3, IMDSv2"

  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      volume_size           = var.master_disk_size_gb
      volume_type           = "gp3"
      delete_on_termination = true
      encrypted             = true
    }
  }

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
  }

  tag_specifications {
    resource_type = "instance"
    tags          = merge(local.default_tags, { Name = "${var.project_name}-master-ec2", Role = "Master" })
  }

  tag_specifications {
    resource_type = "volume"
    tags          = local.default_tags
  }

  tags = local.default_tags
}

# Launch Template para los agentes PEST (c7a.medium — 50 GB para modelo + temporales)
resource "aws_launch_template" "agent_lt" {
  name_prefix = "${var.project_name}-agent-lt-"
  description = "Agentes PEST: disco ${var.agent_disk_size_gb} GB gp3, IMDSv2"

  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      volume_size           = var.agent_disk_size_gb
      volume_type           = "gp3"
      delete_on_termination = true
      encrypted             = true
    }
  }

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
  }

  tag_specifications {
    resource_type = "instance"
    tags          = merge(local.default_tags, { Name = "${var.project_name}-agent-ec2", Role = "Agent" })
  }

  tag_specifications {
    resource_type = "volume"
    tags          = local.default_tags
  }

  tags = local.default_tags
}

# -----------------------------------------------------------------------
# Compute Environment — Spot (prioridad alta, ~70% ahorro)
# SPOT_CAPACITY_OPTIMIZED: selecciona el pool de capacidad Spot más abundante
# para minimizar interrupciones. Las familias c7i/c7a/c6i/c6a
# se especifican como .large para garantizar 1 job por instancia con
# 2 vCPU/job → cada core activo puede turbear al máximo (~3.6-3.7 GHz).
# -----------------------------------------------------------------------
resource "aws_batch_compute_environment" "spot" {
  compute_environment_name = "${var.project_name}-spot-ce"
  type                     = "MANAGED"
  state                    = "ENABLED"
  service_role             = aws_iam_role.batch_service_role.arn

  compute_resources {
    type                = "SPOT"
    allocation_strategy = "SPOT_CAPACITY_OPTIMIZED"
    instance_type       = var.batch_instance_types
    min_vcpus           = 0
    max_vcpus           = var.batch_max_vcpus
    instance_role       = aws_iam_instance_profile.batch_instance_profile.arn
    subnets             = var.private_subnet_ids
    security_group_ids  = [aws_security_group.batch_instances.id]

    launch_template {
      launch_template_id = aws_launch_template.batch_lt.id
      version            = "$Latest"
    }

    tags = merge(local.default_tags, { CostMode = "Spot" })
  }

  tags       = local.default_tags
  depends_on = [aws_iam_role_policy_attachment.batch_service_policy]
}

# -----------------------------------------------------------------------
# Compute Environment — On-Demand (fallback automático)
# Batch usa este CE si Spot no tiene capacidad disponible en ningún pool.
# max_vcpus reducido para controlar costos en modo fallback.
# -----------------------------------------------------------------------
resource "aws_batch_compute_environment" "ondemand" {
  compute_environment_name = "${var.project_name}-ondemand-ce"
  type                     = "MANAGED"
  state                    = "ENABLED"
  service_role             = aws_iam_role.batch_service_role.arn

  compute_resources {
    type                = "EC2"
    allocation_strategy = "BEST_FIT_PROGRESSIVE"
    instance_type       = var.batch_instance_types
    min_vcpus           = 0
    max_vcpus           = var.batch_ondemand_max_vcpus
    instance_role       = aws_iam_instance_profile.batch_instance_profile.arn
    subnets             = var.private_subnet_ids
    security_group_ids  = [aws_security_group.batch_instances.id]

    launch_template {
      launch_template_id = aws_launch_template.batch_lt.id
      version            = "$Latest"
    }

    tags = merge(local.default_tags, { CostMode = "OnDemand" })
  }

  tags       = local.default_tags
  depends_on = [aws_iam_role_policy_attachment.batch_service_policy]
}

# -----------------------------------------------------------------------
# Job Queue
# Spot (order=1) se intenta primero; On-Demand (order=2) es el fallback.
# -----------------------------------------------------------------------
resource "aws_batch_job_queue" "pest_agents" {
  name     = "${var.project_name}-job-queue"
  state    = "ENABLED"
  priority = 1

  compute_environment_order {
    order               = 1
    compute_environment = aws_batch_compute_environment.spot.arn
  }

  compute_environment_order {
    order               = 2
    compute_environment = aws_batch_compute_environment.ondemand.arn
  }

  tags = local.default_tags
}

# -----------------------------------------------------------------------
# CloudWatch Log Groups
# Separados por tipo de proceso para facilitar la observabilidad:
#   batch_logs  : jobs autonomos y benchmark
#   master_logs : proceso master PEST (ECS Fargate)
#   agent_logs  : agentes Batch en modo master-agent
# -----------------------------------------------------------------------
resource "aws_cloudwatch_log_group" "batch_logs" {
  name              = "/batch/${var.project_name}"
  retention_in_days = 30
  tags              = local.default_tags
}

resource "aws_cloudwatch_log_group" "master_logs" {
  name              = "/batch/${var.project_name}-master"
  retention_in_days = 30
  tags              = local.default_tags
}

resource "aws_cloudwatch_log_group" "agent_logs" {
  name              = "/batch/${var.project_name}-agents"
  retention_in_days = 30
  tags              = local.default_tags
}

# -----------------------------------------------------------------------
# Job Definition
# Define el contenedor, recursos, timeout y reintentos.
# ID_PARAMETRO se sobreescribe en cada submit_job() del lanzador Python.
# jobRoleArn: task role creado en este módulo con permisos S3, SSM y Logs.
# timeout: reemplaza al EventBridge Scheduler del stack ECS anterior.
# retry_strategy: Batch reintenta automáticamente en interrupciones Spot.
# Conexión a instancias: SSM Session Manager via `aws ssm start-session
#   --target <instance-id>` (requiere AmazonSSMManagedInstanceCore en
#   batch_instance_role + VPC Endpoints ssm/ssmmessages/ec2messages).
# -----------------------------------------------------------------------
resource "aws_batch_job_definition" "pest_agent-autonomo" {
  name = "${var.project_name}-job-def"
  type = "container"

  container_properties = jsonencode({
    image   = var.ecr_image_linux
    command = ["/bin/bash", "/app/entrypoint_autonomo.sh"]

    resourceRequirements = [
      { type = "VCPU",   value = tostring(var.batch_vcpus_per_job) },
      { type = "MEMORY", value = tostring(var.batch_memory_per_job_mb) }
    ]

    environment = [
      { name = "NOMBRE_MODELO",     value = var.nombre_modelo },
      { name = "NOMBRE_MODELO_PEST", value = var.nombre_modelo_pest },
      { name = "EJECUTABLE_AUTONOMO", value = var.ejecutable_autonomo },
      { name = "COMANDO_AUTONOMO",    value = var.comando_autonomo },
      { name = "PEST_PORT",         value = tostring(var.pest_port) },
      { name = "BUCKET_NAME",       value = var.s3_bucket_linux },
      { name = "PROJECT_NAME",      value = var.project_name },
      { name = "AWS_REGION",        value = var.aws_region },
      { name = "ID_PARAMETRO",      value = "0" }
    ]

    jobRoleArn = aws_iam_role.task_role.arn

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.batch_logs.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "batch"
      }
    }
  })

  retry_strategy {
    attempts = var.batch_retry_attempts
  }

  tags = local.default_tags
}

# =======================================================================
# MASTER-AGENT — Master y agentes PEST como jobs Batch EC2
# Master : r7iz.large (On-Demand) — gran memoria para el modelo PEST
# Agentes: c7a.medium (On-Demand) — 1 vCPU optimo para single-thread
# Comunicacion: agentes se conectan TCP 4004 a la IP privada del master
# Sin IP publica: instancias en subnets privadas unicamente
# =======================================================================

# Security Group para el master: acepta TCP 4004 solo desde agentes Batch
resource "aws_security_group" "master" {
  name        = "${var.project_name}-master-sg"
  description = "PEST master: TCP 4004 inbound from Batch agents only"
  vpc_id      = var.vpc_id

  ingress {
    description     = "PEST agents TCP 4004"
    from_port       = 4004
    to_port         = 4004
    protocol        = "tcp"
    security_groups = [aws_security_group.batch_instances.id]
  }

  ingress {
    description     = "ICMP ping desde agentes (diagnostico)"
    from_port       = -1
    to_port         = -1
    protocol        = "icmp"
    security_groups = [aws_security_group.batch_instances.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.default_tags, { Name = "${var.project_name}-master-sg" })
}

# -----------------------------------------------------------------------
# MASTER-AGENT — Compute Environment master (16 GB RAM, On-Demand)
# Multiples tipos de instancia para mayor disponibilidad:
#   r7iz.large: 3.9 GHz Intel Sapphire Rapids (preferido)
#   r6a.large : 3.6 GHz AMD EPYC Milan        (fallback)
#   r6i.large : 3.5 GHz Intel Ice Lake        (fallback)
# BEST_FIT_PROGRESSIVE elige el disponible con mejor ajuste de costo.
# SG propio: solo agentes Batch pueden conectarse al puerto 4004 del master
# -----------------------------------------------------------------------
resource "aws_batch_compute_environment" "master_ce" {
  compute_environment_name = "${var.project_name}-master-ce"
  type                     = "MANAGED"
  state                    = "ENABLED"
  service_role             = aws_iam_role.batch_service_role.arn

  compute_resources {
    type                = "EC2"
    allocation_strategy = "BEST_FIT_PROGRESSIVE"
    instance_type       = var.master_instance_types
    min_vcpus           = 0
    max_vcpus           = var.master_max_vcpus
    instance_role       = aws_iam_instance_profile.batch_instance_profile.arn
    subnets             = var.private_subnet_ids
    security_group_ids  = [aws_security_group.master.id]

    launch_template {
      launch_template_id = aws_launch_template.master_lt.id
      version            = "$Latest"
    }

    tags = merge(local.default_tags, { Role = "Master", CostMode = "OnDemand" })
  }

  tags       = local.default_tags
  depends_on = [aws_iam_role_policy_attachment.batch_service_policy]
}

resource "aws_batch_job_queue" "master_queue" {
  name     = "${var.project_name}-master-queue"
  state    = "ENABLED"
  priority = 1

  compute_environment_order {
    order               = 1
    compute_environment = aws_batch_compute_environment.master_ce.arn
  }

  tags = local.default_tags
}

# -----------------------------------------------------------------------
# MASTER-AGENT — Batch Job Definition para el master PEST
# r7iz.large: 2 vCPU / 15360 MB (16 GB - overhead ECS/OS ~1 GB)
# portMappings: expone TCP 4004 en la IP privada del EC2 host (bridge mode).
# El orquestador Python obtiene esa IP via Batch->ECS->EC2 APIs y la pasa
# a los agentes como MASTER_HOST. retry_strategy=1: el master no se reinicia.
# -----------------------------------------------------------------------
resource "aws_batch_job_definition" "pest_master" {
  name = "${var.project_name}-master-job-def"
  type = "container"

  container_properties = jsonencode({
    image   = var.ecr_image_linux
    command = ["/bin/bash", "/app/entrypoint_master.sh"]
    enableExecuteCommand = true

    resourceRequirements = [
      { type = "VCPU",   value = "4" },
      { type = "MEMORY", value = tostring(var.master_batch_memory_mb) }
    ]

    portMappings = [
      { hostPort = var.pest_port, containerPort = var.pest_port, protocol = "tcp" }
    ]

    environment = [
      { name = "NOMBRE_MODELO",      value = var.nombre_modelo },
      { name = "NOMBRE_MODELO_PEST", value = var.nombre_modelo_pest },
      { name = "EJECUTABLE_MASTER",  value = var.ejecutable_master },
      { name = "COMANDO_MASTER",     value = var.comando_master },
      { name = "PEST_PORT",          value = tostring(var.pest_port) },
      { name = "BUCKET_NAME",        value = var.s3_bucket_linux },
      { name = "PROJECT_NAME",       value = var.project_name },
      { name = "AWS_REGION",         value = var.aws_region },
      { name = "ACTIVATE_JCO",       value = var.activate_jacobiano },
      { name = "JCO_NAME",           value = var.nombre_jacobiano }
    ]

    jobRoleArn = aws_iam_role.task_role.arn

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.master_logs.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "master"
      }
    }
  })

  retry_strategy {
    attempts = 1
  }

  tags = local.default_tags
}

# -----------------------------------------------------------------------
# MASTER-AGENT — Batch Job Definition para agentes
# MASTER_HOST se sobreescribe en cada submit_job con la IP privada del master.
# retry_strategy = 1: no reintentar agentes si el master se cayo.
# -----------------------------------------------------------------------
resource "aws_batch_job_definition" "pest_agent_master" {
  name = "${var.project_name}-agent-job-def"
  type = "container"

  container_properties = jsonencode({
    image   = var.ecr_image_linux
    command = ["/bin/bash", "/app/entrypoint_agent.sh"]
    enableExecuteCommand = true

    resourceRequirements = [
      { type = "VCPU",   value = "1" },
      { type = "MEMORY", value = tostring(var.agent_memory_mb) }
    ]

    environment = [
      { name = "NOMBRE_MODELO",       value = var.nombre_modelo },
      { name = "NOMBRE_MODELO_PEST",  value = var.nombre_modelo_pest },
      { name = "EJECUTABLE_AGENTE",   value = var.ejecutable_agente },
      { name = "COMANDO_AGENTE",      value = var.comando_agente },
      { name = "PEST_PORT",           value = tostring(var.pest_port) },
      { name = "BUCKET_NAME",         value = var.s3_bucket_linux },
      { name = "PROJECT_NAME",        value = var.project_name },
      { name = "AWS_REGION",          value = var.aws_region },
      { name = "MASTER_HOST",         value = var.master_host },
      { name = "MODEL_TIMEOUT",       value = tostring(var.model_timeout) }
    ]

    jobRoleArn = aws_iam_role.task_role.arn

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.agent_logs.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "agent"
      }
    }
  })

  retry_strategy {
    attempts = 1
    evaluate_on_exit {
      on_status_reason = "Host EC2 terminated*"
      action           = "RETRY"
    }
    evaluate_on_exit {
      on_reason = "CannotPullContainerError*"
      action    = "RETRY"
    }
    evaluate_on_exit {
      on_exit_code = "137"
      action       = "EXIT"
    }
    evaluate_on_exit {
      on_exit_code = "130"
      action       = "EXIT"
    }
  }

  tags = local.default_tags
}

# =======================================================================
# MASTER-AGENT — Compute Environment agentes (c7a.medium On-Demand)
# c7a.medium: 1 vCPU / 2 GB RAM — 1 job por instancia, AMD EPYC Genoa
# Usa batch_instances SG (egress abierto para conectar al master TCP 4004)
# =======================================================================
resource "aws_batch_compute_environment" "agent_ce" {
  compute_environment_name = "${var.project_name}-agent-ce"
  type                     = "MANAGED"
  state                    = "ENABLED"
  service_role             = aws_iam_role.batch_service_role.arn

  compute_resources {
    type                = "EC2"
    allocation_strategy = "BEST_FIT_PROGRESSIVE"
    instance_type       = ["c7a.medium"]
    min_vcpus           = 0
    max_vcpus           = var.agent_max_vcpus
    instance_role       = aws_iam_instance_profile.batch_instance_profile.arn
    subnets             = var.private_subnet_ids
    security_group_ids  = [aws_security_group.batch_instances.id]

    launch_template {
      launch_template_id = aws_launch_template.agent_lt.id
      version            = "$Latest"
    }

    tags = merge(local.default_tags, { Role = "Agent", CostMode = "OnDemand" })
  }

  tags       = local.default_tags
  depends_on = [aws_iam_role_policy_attachment.batch_service_policy]
}

resource "aws_batch_job_queue" "agent_queue" {
  name     = "${var.project_name}-agent-queue"
  state    = "ENABLED"
  priority = 1

  compute_environment_order {
    order               = 1
    compute_environment = aws_batch_compute_environment.agent_ce.arn
  }

  tags = local.default_tags
}

# -----------------------------------------------------------------------
# MASTER-AGENT — Batch Job Definition para agentes STOP (que hace fallar el modelo)
# MASTER_HOST se sobreescribe en cada submit_job con la IP privada del master.
# retry_strategy = 1: no reintentar agentes si el master se cayo.
# -----------------------------------------------------------------------
resource "aws_batch_job_definition" "pest_agent_stop_master" {
  name = "${var.project_name}-agent-stop-job-def"
  type = "container"

  container_properties = jsonencode({
    image   = var.ecr_image_linux
    command = ["/bin/bash", "/app/entrypoint_agent.sh"]
    enableExecuteCommand = true

    resourceRequirements = [
      { type = "VCPU",   value = "1" },
      { type = "MEMORY", value = tostring(var.agent_memory_mb) }
    ]

    environment = [
      { name = "NOMBRE_MODELO",       value = var.nombre_modelo },
      { name = "NOMBRE_MODELO_PEST",  value = var.nombre_modelo_pest },
      { name = "EJECUTABLE_AGENTE",   value = var.ejecutable_agente },
      { name = "COMANDO_AGENTE",      value = var.comando_agente },
      { name = "PEST_PORT",           value = tostring(var.pest_port) },
      { name = "BUCKET_NAME",         value = var.s3_bucket_linux },
      { name = "PROJECT_NAME",        value = var.project_name },
      { name = "AWS_REGION",          value = var.aws_region },
      { name = "MASTER_HOST",         value = var.master_host },
      { name = "MODEL_TIMEOUT",       value = tostring(var.model_timeout_stop) }
    ]

    jobRoleArn = aws_iam_role.task_role.arn

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.agent_logs.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "agent"
      }
    }
  })

  retry_strategy {
    attempts = 1
    evaluate_on_exit {
      on_status_reason = "Host EC2 terminated*"
      action           = "RETRY"
    }
    evaluate_on_exit {
      on_reason = "CannotPullContainerError*"
      action    = "RETRY"
    }
    evaluate_on_exit {
      on_exit_code = "137"
      action       = "EXIT"
    }
    evaluate_on_exit {
      on_exit_code = "130"
      action       = "EXIT"
    }
  }

  tags = local.default_tags
}