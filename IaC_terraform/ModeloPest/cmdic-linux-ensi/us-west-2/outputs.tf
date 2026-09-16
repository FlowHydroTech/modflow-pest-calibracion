output "job_queue_name" {
  description = "Job Queue modo autonomo (Spot + On-Demand fallback)"
  value       = aws_batch_job_queue.pest_agents.name
}

output "job_queue_arn" {
  value = aws_batch_job_queue.pest_agents.arn
}

output "job_definition_name" {
  description = "Job Definition modo autonomo"
  value       = aws_batch_job_definition.pest_agent-autonomo.name
}

output "job_definition_arn" {
  value = aws_batch_job_definition.pest_agent-autonomo.arn
}

output "spot_compute_env_arn" {
  value = aws_batch_compute_environment.spot.arn
}

output "ondemand_compute_env_arn" {
  value = aws_batch_compute_environment.ondemand.arn
}

output "batch_instances_sg_id" {
  description = "ID del SG de instancias Batch (agentes)"
  value       = aws_security_group.batch_instances.id
}

output "cloudwatch_log_group" {
  description = "Log group jobs autonomos"
  value       = aws_cloudwatch_log_group.batch_logs.name
}

output "cloudwatch_log_group_master" {
  description = "Log group proceso master PEST (Batch EC2 r7iz.large)"
  value       = aws_cloudwatch_log_group.master_logs.name
}

output "cloudwatch_log_group_agents" {
  description = "Log group agentes Batch (Batch EC2 c7a.medium)"
  value       = aws_cloudwatch_log_group.agent_logs.name
}

# -----------------------------------------------------------------------
# MASTER-AGENT outputs
# -----------------------------------------------------------------------
output "master_sg_id" {
  description = "ID del SG del master PEST"
  value       = aws_security_group.master.id
}

output "master_job_queue" {
  description = "Job Queue master PEST (r7iz.large On-Demand)"
  value       = aws_batch_job_queue.master_queue.name
}

output "master_job_definition" {
  description = "Job Definition master PEST"
  value       = aws_batch_job_definition.pest_master.name
}

output "agent_job_queue" {
  description = "Job Queue agentes PEST (c7a.medium On-Demand)"
  value       = aws_batch_job_queue.agent_queue.name
}

output "agent_job_definition" {
  description = "Job Definition agentes PEST"
  value       = aws_batch_job_definition.pest_agent_master.name
}
