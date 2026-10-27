terraform {
  required_version = ">= 1.10, < 2.0"
  required_providers {
    aws    = { source = "hashicorp/aws", version = "= 6.66.0" }
    rhcs   = { source = "terraform-redhat/rhcs", version = "= 1.7.9" }
    random = { source = "hashicorp/random", version = "= 3.9.1" }
  }
  backend "s3" {
    key          = "rosa/terraform.tfstate"
    region       = "eu-central-1"
    use_lockfile = true
    encrypt      = true
  }
}
variable "expected_account_id" { type = string }
variable "region" {
  type    = string
  default = "eu-central-1"
}
variable "openshift_version" {
  type    = string
  default = "4.21.34"
}
provider "aws" {
  region              = var.region
  allowed_account_ids = [var.expected_account_id]
  default_tags {
    tags = { Project = "lemonade-demo", Owner = "mdargatz", ManagedBy = "terraform" }
  }
}
provider "rhcs" {}
data "terraform_remote_state" "foundation" {
  backend = "s3"
  config = {
    bucket = "lemonade-demo-tfstate-${var.expected_account_id}"
    key    = "foundation/terraform.tfstate"
    region = var.region
  }
}
resource "random_password" "admin" {
  length           = 24
  special          = true
  override_special = "-_"
}
module "hcp" {
  source                              = "terraform-redhat/rosa-hcp/rhcs"
  version                             = "1.7.5"
  cluster_name                        = "lemonade-demo"
  openshift_version                   = var.openshift_version
  machine_cidr                        = data.terraform_remote_state.foundation.outputs.network.vpc_cidr
  aws_subnet_ids                      = concat(data.terraform_remote_state.foundation.outputs.network.public_subnet_ids, data.terraform_remote_state.foundation.outputs.network.private_subnet_ids)
  aws_availability_zones              = [data.terraform_remote_state.foundation.outputs.network.availability_zone]
  replicas                            = 3
  cluster_autoscaler_enabled          = false
  compute_machine_type                = "m6i.2xlarge"
  aws_billing_account_id              = var.expected_account_id
  tags                                = { Project = "lemonade-demo", Owner = "mdargatz", ManagedBy = "terraform" }
  create_account_roles                = true
  account_role_prefix                 = "lemonade-account"
  create_oidc                         = true
  create_operator_roles               = true
  operator_role_prefix                = "lemonade-operator"
  admin_credentials_username          = "cluster-admin"
  admin_credentials_password          = random_password.admin.result
  wait_for_create_complete            = true
  wait_for_std_compute_nodes_complete = true
}
# There is deliberately no GPU machine-pool resource. Adding one requires owner approval.
output "cluster_id" { value = module.hcp.cluster_id }
output "api_url" { value = module.hcp.cluster_api_url }
output "console_url" { value = module.hcp.cluster_console_url }
output "admin_password" {
  value     = random_password.admin.result
  sensitive = true
}
