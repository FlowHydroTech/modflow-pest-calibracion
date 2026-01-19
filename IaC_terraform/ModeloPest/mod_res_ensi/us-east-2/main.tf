locals {
  default_tags = merge(
    var.common_tags,
    {
      Region  = var.aws_region,
      Project = var.project_name
    }
  )
}

resource "aws_cloudwatch_log_group" "ecs_logs_pest_autonomo" {
  name              = "/ecs/${var.project_name}-${var.aws_region}-autonomo"
  retention_in_days = 30
  tags              = local.default_tags
}

resource "aws_cloudwatch_log_group" "ecs_logs_pest_master" {
  name              = "/ecs/${var.project_name}-${var.aws_region}-master"
  retention_in_days = 30
  tags              = local.default_tags
}

resource "aws_cloudwatch_log_group" "ecs_logs_pest_agente" {
  name              = "/ecs/${var.project_name}-${var.aws_region}-agente"
  retention_in_days = 30
  tags              = local.default_tags
}

resource "aws_iam_role" "ecs_task_execution" {
  name = "${var.project_name}-ecsTaskExecution-${var.aws_region}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect = "Allow",
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      },
      Action = "sts:AssumeRole"
    }]
  })
  tags = local.default_tags
}

# IAM Role para la tarea (acceso a S3) (ya existe, creado previamente)
resource "aws_iam_role" "task_role" {
  name = "${var.project_name}-ecsTaskS3WriteRole-${var.aws_region}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect = "Allow",
      Principal = { Service = "ecs-tasks.amazonaws.com" },
      Action = "sts:AssumeRole"
    }]
  })
  tags = local.default_tags
}

resource "aws_iam_policy" "s3_write_policy" {
  name   = "${var.project_name}-S3WritePolicy-${var.aws_region}"
  policy = jsonencode({ 
    Version = "2012-10-17",
    Statement = [
      {
        Sid = "S3WriteResults",
        Effect = "Allow",
        Action = [
          "s3:PutObject",
          "s3:AbortMultipartUpload",
          "s3:ListBucket",
          "s3:PutObjectAcl"
        ],
        Resource = [
          "arn:aws:s3:::${var.s3_bucket}",
          "arn:aws:s3:::${var.s3_bucket}/*"
        ]
      }
    ]
   }) 
  tags = local.default_tags
}

resource "aws_iam_role_policy_attachment" "attach_s3_write" {
  role       = aws_iam_role.task_role.name
  policy_arn = aws_iam_policy.s3_write_policy.arn
}

resource "aws_iam_role_policy_attachment" "ecs_execution_policy" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy_attachment" "logs_execution" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Policy to allow the ECS task execution role to get ECR authorization token
resource "aws_iam_policy" "ecr_get_auth_policy" {
  name = "${var.project_name}-ECRGetAuthorizationToken-${var.aws_region}"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer"
        ],
        Resource = "*"
      }
    ]
  })
  tags = local.default_tags
}

resource "aws_iam_role_policy_attachment" "attach_ecr_get_auth" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = aws_iam_policy.ecr_get_auth_policy.arn
}

# Policy para permitir ECS Exec (SSM Session Manager)
resource "aws_iam_policy" "ecs_exec_policy" {
  name = "${var.project_name}-ECSExecPolicy-${var.aws_region}"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Sid = "AllowSSMMessages",
        Effect = "Allow",
        Action = [
          "ssmmessages:CreateControlChannel",
          "ssmmessages:CreateDataChannel",
          "ssmmessages:OpenControlChannel",
          "ssmmessages:OpenDataChannel"
        ],
        Resource = "*"
      },
      {
        Sid = "AllowECSExecLogging",
        Effect = "Allow",
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ],
        Resource = "arn:aws:logs:${var.aws_region}:*:log-group:/ecs/*"
      },
      {
        Sid = "AllowKMSDecrypt",
        Effect = "Allow",
        Action = [
          "kms:Decrypt"
        ],
        Resource = "*",
        Condition = {
          StringEquals = {
            "kms:ViaService" = "ssmmessages.${var.aws_region}.amazonaws.com"
          }
        }
      }
    ]
  })
  tags = local.default_tags
}

resource "aws_iam_role_policy_attachment" "attach_ecs_exec" {
  role       = aws_iam_role.task_role.name
  policy_arn = aws_iam_policy.ecs_exec_policy.arn
}

resource "aws_ecs_cluster" "cluster-pest" {
  name = "${var.project_name}-cluster-${var.aws_region}"
  tags = local.default_tags
}

# Security Group para el master (acceso TCP:4004)
resource "aws_security_group" "ecs_master_sg" {
  name                   = "${var.project_name}-master-sg-${var.aws_region}"
  description            = "Allow TCP 4004 from ECS tasks group"
  vpc_id                 = var.vpc_id
  revoke_rules_on_delete = true
  tags                   = local.default_tags
}

# Security Group para las tareas (clientes)
resource "aws_security_group" "ecs_tasks_sg" {
  name                   = "${var.project_name}-tasks-sg-${var.aws_region}"
  description            = "SG for ECS tasks"
  vpc_id                 = var.vpc_id
  revoke_rules_on_delete = true
  tags                   = local.default_tags
}

# Permitir desde tareas hacia master en 4004
resource "aws_security_group_rule" "allow_tasks_to_master" {
  type                     = "ingress"
  from_port                = var.pest_port
  to_port                  = var.pest_port
  protocol                 = "tcp"
  security_group_id        = aws_security_group.ecs_master_sg.id
  source_security_group_id = aws_security_group.ecs_tasks_sg.id
}

# Security group for VPC interface endpoints (ECR / STS / Logs)
resource "aws_security_group" "vpc_endpoints_sg" {
  name                   = "${var.project_name}-endpoints-sg-${var.aws_region}"
  description            = "SG attached to VPC interface endpoints (ECR, STS, Logs)"
  vpc_id                 = var.vpc_id
  revoke_rules_on_delete = true
  tags                   = local.default_tags
}

# Allow ECS tasks to connect to the endpoints on HTTPS
resource "aws_security_group_rule" "endpoint_allow_from_tasks" {
  type                     = "ingress"
  from_port                = 443
  to_port                  = 443
  protocol                 = "tcp"
  security_group_id        = aws_security_group.vpc_endpoints_sg.id
  source_security_group_id = aws_security_group.ecs_tasks_sg.id
}

# Allow master to connect to the endpoints on HTTPS
resource "aws_security_group_rule" "endpoint_allow_from_master" {
  type                     = "ingress"
  from_port                = 443
  to_port                  = 443
  protocol                 = "tcp"
  security_group_id        = aws_security_group.vpc_endpoints_sg.id
  source_security_group_id = aws_security_group.ecs_master_sg.id
}

# Allow VPC endpoint ENIs to send responses (egress) to the network
resource "aws_security_group_rule" "vpc_endpoints_allow_egress_all" {
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  security_group_id = aws_security_group.vpc_endpoints_sg.id
  cidr_blocks       = ["0.0.0.0/0"]
}

# Private DNS namespace para service discovery
resource "aws_service_discovery_private_dns_namespace" "sd_namespace" {
  name = "${var.project_name}.local"
  vpc  = var.vpc_id
  description = "Private DNS namespace for ${var.project_name}"
  tags = local.default_tags
}

# Cloud Map service para el master
resource "aws_service_discovery_service" "master_sd" {
  name = "master"
  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.sd_namespace.id
    dns_records {
      ttl  = 60
      type = "A"
    }
    routing_policy = "MULTIVALUE"
  }
  health_check_custom_config {
    failure_threshold = 1
  }
  tags = local.default_tags
}

# Regla de egress para el security group del master
resource "aws_security_group_rule" "master_egress_all" {
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  security_group_id = aws_security_group.ecs_master_sg.id
  cidr_blocks       = ["0.0.0.0/0"]
}

# Regla de egress para el security group de las tareas
resource "aws_security_group_rule" "tasks_egress_all" {
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  security_group_id = aws_security_group.ecs_tasks_sg.id
  cidr_blocks       = ["0.0.0.0/0"]
}

/* VPC Endpoints to allow Fargate tasks in private subnets to reach ECR, STS and S3
   - Interface endpoints for ECR API, ECR DKR and STS
   - Gateway endpoint for S3 (requires route table IDs)
*/

resource "aws_vpc_endpoint" "ecr_api" {
  vpc_id            = var.vpc_id
  service_name      = "com.amazonaws.${var.aws_region}.ecr.api"
  vpc_endpoint_type = "Interface"
  subnet_ids        = var.private_subnet_ids
  security_group_ids = [aws_security_group.vpc_endpoints_sg.id]
  private_dns_enabled = true
  tags = local.default_tags
}

resource "aws_vpc_endpoint" "ecr_dkr" {
  vpc_id            = var.vpc_id
  service_name      = "com.amazonaws.${var.aws_region}.ecr.dkr"
  vpc_endpoint_type = "Interface"
  subnet_ids        = var.private_subnet_ids
  security_group_ids = [aws_security_group.vpc_endpoints_sg.id]
  private_dns_enabled = true
  tags = local.default_tags
}

resource "aws_vpc_endpoint" "sts" {
  vpc_id            = var.vpc_id
  service_name      = "com.amazonaws.${var.aws_region}.sts"
  vpc_endpoint_type = "Interface"
  subnet_ids        = var.private_subnet_ids
  security_group_ids = [aws_security_group.vpc_endpoints_sg.id]
  private_dns_enabled = true
  tags = local.default_tags
}

resource "aws_vpc_endpoint" "logs" {
  vpc_id            = var.vpc_id
  service_name      = "com.amazonaws.${var.aws_region}.logs"
  vpc_endpoint_type = "Interface"
  subnet_ids        = var.private_subnet_ids
  security_group_ids = [aws_security_group.vpc_endpoints_sg.id]
  private_dns_enabled = true
  tags = local.default_tags
}

# VPC Endpoints para ECS Exec (SSM)
resource "aws_vpc_endpoint" "ssm" {
  vpc_id            = var.vpc_id
  service_name      = "com.amazonaws.${var.aws_region}.ssm"
  vpc_endpoint_type = "Interface"
  subnet_ids        = var.private_subnet_ids
  security_group_ids = [aws_security_group.vpc_endpoints_sg.id]
  private_dns_enabled = true
  tags = local.default_tags
}

resource "aws_vpc_endpoint" "ssmmessages" {
  vpc_id            = var.vpc_id
  service_name      = "com.amazonaws.${var.aws_region}.ssmmessages"
  vpc_endpoint_type = "Interface"
  subnet_ids        = var.private_subnet_ids
  security_group_ids = [aws_security_group.vpc_endpoints_sg.id]
  private_dns_enabled = true
  tags = local.default_tags
}

resource "aws_vpc_endpoint" "ec2messages" {
  vpc_id            = var.vpc_id
  service_name      = "com.amazonaws.${var.aws_region}.ec2messages"
  vpc_endpoint_type = "Interface"
  subnet_ids        = var.private_subnet_ids
  security_group_ids = [aws_security_group.vpc_endpoints_sg.id]
  private_dns_enabled = true
  tags = local.default_tags
}

resource "aws_vpc_endpoint" "s3" {
  count             = length(var.private_route_table_ids) > 0 ? 1 : 0
  vpc_id            = var.vpc_id
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = var.private_route_table_ids
  tags = local.default_tags
}

# Security group rules to allow tasks/master to reach the interface endpoints (HTTPS)
# Interface endpoints have ENIs that use the security groups we attached above.
# We must allow inbound TCP/443 to those SGs from the ECS tasks/master SGs.
resource "aws_security_group_rule" "allow_tasks_to_endpoints_https_self" {
  type                     = "ingress"
  from_port                = 443
  to_port                  = 443
  protocol                 = "tcp"
  security_group_id        = aws_security_group.ecs_tasks_sg.id
  source_security_group_id = aws_security_group.ecs_tasks_sg.id
}

resource "aws_security_group_rule" "allow_tasks_to_endpoints_https_master" {
  type                     = "ingress"
  from_port                = 443
  to_port                  = 443
  protocol                 = "tcp"
  security_group_id        = aws_security_group.ecs_master_sg.id
  source_security_group_id = aws_security_group.ecs_tasks_sg.id
}

resource "aws_security_group_rule" "allow_master_to_endpoints_https_self" {
  type                     = "ingress"
  from_port                = 443
  to_port                  = 443
  protocol                 = "tcp"
  security_group_id        = aws_security_group.ecs_master_sg.id
  source_security_group_id = aws_security_group.ecs_master_sg.id
}

resource "aws_ecs_task_definition" "task-pest-autonomo" {
  family                   = "${var.project_name}-task-${var.aws_region}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "1024"
  memory                   = "2048"
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.task_role.arn
  tags                     = local.default_tags

  container_definitions = jsonencode([{
    name      = "${var.project_name}-container"
    image     = var.ecr_image
    essential = true
    command   = ["/bin/bash", "/app/entrypoint_autonomo.sh"]
    environment = [
        { name = "NOMBRE_MODELO_PEST", value = var.nombre_modelo_pest },
        { name = "EJECUTABLE_AUTONOMO", value = var.ejecutable_autonomo },
        { name = "BUCKET_NAME", value = var.s3_bucket },
        { name = "PROJECT_NAME", value = var.project_name },
        { name = "AWS_REGION", value = var.aws_region }
        ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.ecs_logs_pest_autonomo.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "ecs"
      }
    }
  }])
}

# Task definition para el master
resource "aws_ecs_task_definition" "task-pest-master" {
  family                   = "${var.project_name}-task-master-${var.aws_region}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "2048"
  memory                   = "10240"     # 10 GB
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.task_role.arn
  tags                     = local.default_tags

  ephemeral_storage {
    size_in_gib = 30    #ajuste considerando tamaño de la imagen y archivos generados por el modelo en el master
  }

  container_definitions = jsonencode([{
    name      = "${var.project_name}-master"
    image     = var.ecr_image
    essential = true
    command   = ["/bin/bash", "/app/entrypoint_master.sh"]
    environment = [
      { name = "BUCKET_NAME", value = var.s3_bucket },
      { name = "EJECUTABLE_MASTER", value = var.ejecutable_master },
      { name = "NOMBRE_MODELO_PEST", value = var.nombre_modelo_pest },
      { name = "PEST_PORT", value = tostring(var.pest_port) },
      { name = "PROJECT_NAME", value = var.project_name },
      { name = "AWS_REGION", value = var.aws_region },
      { name = "JACOBIANO_NAME", value = var.nombre_jacobiano }
    ]
    portMappings = [
      { containerPort = 4004, protocol = "tcp" }
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.ecs_logs_pest_master.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "ecs"
      }
    }
  }])
}

# Task definition para el agente
resource "aws_ecs_task_definition" "task-pest-agente" {
  family                   = "${var.project_name}-task-agente-${var.aws_region}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "1024"
  memory                   = "3072"
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.task_role.arn
  tags                     = local.default_tags

  ephemeral_storage {
    size_in_gib = 30    #ajuste considerando tamaño de la imagen y archivos generados por el modelo en el master
  }

  container_definitions = jsonencode([{
    name      = "${var.project_name}-agente"
    image     = var.ecr_image
    essential = true
    command   = ["/bin/bash", "/app/entrypoint_agent.sh"]
    environment = [
        { name = "NOMBRE_MODELO_PEST", value = var.nombre_modelo_pest },
        { name = "EJECUTABLE_AGENTE", value = var.ejecutable_agente },
        { name = "MASTER_HOST", value = "master.${var.project_name}.local" },
        { name = "PEST_PORT", value = tostring(var.pest_port) },
        { name = "BUCKET_NAME", value = var.s3_bucket },
        { name = "PROJECT_NAME", value = var.project_name },
        { name = "AWS_REGION", value = var.aws_region }
        ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.ecs_logs_pest_agente.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "ecs"
      }
    }
  }])
}

# Task definition para el agente-stop
# resource "aws_ecs_task_definition" "task-pest-agente-stop" {
#   family                   = "${var.project_name}-task-agente-stop-${var.aws_region}"
#   requires_compatibilities = ["FARGATE"]
#   network_mode             = "awsvpc"
#   cpu                      = "1024"
#   memory                   = "2048"
#   execution_role_arn       = aws_iam_role.ecs_task_execution.arn
#   task_role_arn            = aws_iam_role.task_role.arn
#   tags                     = local.default_tags

#   container_definitions = jsonencode([{
#     name      = "${var.project_name}-agente-stop"
#     image     = var.ecr_image_stop
#     essential = true
#     command   = ["/bin/bash", "/app/entrypoint_agent.sh"]
#     environment = [
#         { name = "NOMBRE_MODELO_PEST", value = var.nombre_modelo_pest },
#         { name = "EJECUTABLE_AGENTE", value = var.ejecutable_agente },
#         { name = "MASTER_HOST", value = "master.${var.project_name}.local" },
#         { name = "PEST_PORT", value = tostring(var.pest_port) },
#         { name = "BUCKET_NAME", value = var.s3_bucket },
#         { name = "PROJECT_NAME", value = var.project_name },
#         { name = "AWS_REGION", value = var.aws_region }
#         ]
#     logConfiguration = {
#       logDriver = "awslogs"
#       options = {
#         awslogs-group         = aws_cloudwatch_log_group.ecs_logs_pest_agente.name
#         awslogs-region        = var.aws_region
#         awslogs-stream-prefix = "ecs" 
#       }
#     }
#   }])
# }

# ECS Service para el master con Service Discovery
resource "aws_ecs_service" "master_service" {
  name                   = "${var.project_name}-master-service"
  cluster                = aws_ecs_cluster.cluster-pest.id
  task_definition        = aws_ecs_task_definition.task-pest-master.arn
  desired_count          = 1
  launch_type            = "FARGATE"
  enable_execute_command = true
  force_new_deployment   = true

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.ecs_master_sg.id]
    assign_public_ip = false
  }

  service_registries {
    registry_arn = aws_service_discovery_service.master_sd.arn
  }

  tags = local.default_tags

  depends_on = [
    aws_service_discovery_service.master_sd,
    aws_ecs_task_definition.task-pest-master,
    aws_iam_role_policy_attachment.attach_ecs_exec,
    aws_iam_role_policy_attachment.attach_s3_write
  ]

  lifecycle {
    ignore_changes = [desired_count]
  }
}

#Esperar 2 minutos para asegurar que el master esté listo antes de iniciar los agentes
resource "time_sleep" "wait_2_minutes" {
  create_duration = "1m"
  
  triggers = {
    agent_run_id = var.agent_run_id
  }
}

# Ejecutar los agentes con run-task (one-shot). Cambiar `agent_run_id` fuerza una nueva ejecución.
resource "null_resource" "run_agent_once" {
  triggers = {
    agent_run_id = var.agent_run_id
    agent_count  = tostring(var.agent_count)
  }

  depends_on = [
    time_sleep.wait_2_minutes,
    aws_ecs_task_definition.task-pest-agente,
    aws_security_group.ecs_tasks_sg
  ]

  provisioner "local-exec" {
    interpreter = ["PowerShell", "-Command"]
    command = <<EOT
$path = [System.IO.Path]::Combine($env:TEMP, "agent_network.json")
$json = '${jsonencode({awsvpcConfiguration = { subnets = var.private_subnet_ids, securityGroups = [aws_security_group.ecs_tasks_sg.id], assignPublicIp = "DISABLED" } })}'
[System.IO.File]::WriteAllBytes($path, [System.Text.Encoding]::UTF8.GetBytes($json))
aws ecs run-task --region ${var.aws_region} --cluster ${aws_ecs_cluster.cluster-pest.name} --launch-type FARGATE --task-definition ${aws_ecs_task_definition.task-pest-agente.arn} --count ${var.agent_count} --enable-execute-command --network-configuration file://$path
Remove-Item $path -Force
EOT
  }
}