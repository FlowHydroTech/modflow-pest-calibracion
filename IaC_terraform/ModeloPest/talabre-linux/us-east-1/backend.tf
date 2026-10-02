# =======================================================================
# Backend remoto de Terraform (Fase 0 - F-01)
# El state se almacena en S3 con locking en DynamoDB. Los valores concretos
# (bucket, key, region, tabla) se pasan en `terraform init` mediante
# -backend-config para no hardcodear nombres de infraestructura en el codigo:
#
#   terraform init \
#     -backend-config="bucket=<ACCOUNT_ID>-pest-terraform-state" \
#     -backend-config="key=pest-talabre-linux/us-east-1/terraform.tfstate" \
#     -backend-config="region=us-east-1" \
#     -backend-config="dynamodb_table=terraform-state-lock"
#
# El bucket y la tabla se crean una sola vez con el modulo IaC_terraform/bootstrap.
# =======================================================================

terraform {
  backend "s3" {
    encrypt = true
    # bucket, key, region y dynamodb_table se proveen via -backend-config
  }
}