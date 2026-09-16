output "ecs_tasks_sg_id" {
	description = "Security Group ID used by ECS tasks"
	value       = aws_security_group.ecs_tasks_sg.id
}

output "ecs_master_sg_id" {
	description = "Security Group ID used by the ECS master task"
	value       = aws_security_group.ecs_master_sg.id
}

output "vpc_endpoints_sg_id" {
	description = "Security Group ID attached to VPC interface endpoints"
	value       = aws_security_group.vpc_endpoints_sg.id
}

output "ecs_cluster_name" {
	description = "ECS cluster name"
	value       = aws_ecs_cluster.cluster-pest.name
}

output "task_definition_master_arn" {
	description = "ARN of the master ECS task definition"
	value       = aws_ecs_task_definition.task-pest-master.arn
}

output "task_definition_agent_arn" {
	description = "ARN of the agent ECS task definition"
	value       = aws_ecs_task_definition.task-pest-agente.arn
}

