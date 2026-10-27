terraform {
  required_version = ">= 1.10, < 2.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "= 6.66.0" }
  }
  backend "s3" {
    key          = "foundation/terraform.tfstate"
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
variable "availability_zone" {
  type    = string
  default = "eu-central-1a"
}
provider "aws" {
  region              = var.region
  allowed_account_ids = [var.expected_account_id]
  default_tags {
    tags = { Project = "lemonade-demo", Owner = "mdargatz", ManagedBy = "terraform" }
  }
  # ROSA adds its own cluster ownership tags to these subnets.
  ignore_tags { key_prefixes = ["kubernetes.io/cluster/"] }
}
module "vpc" {
  source               = "terraform-aws-modules/vpc/aws"
  version              = "6.7.3"
  name                 = "lemonade-demo"
  cidr                 = "10.42.0.0/16"
  azs                  = [var.availability_zone]
  private_subnets      = ["10.42.0.0/18"]
  public_subnets       = ["10.42.128.0/20"]
  enable_nat_gateway   = true
  single_nat_gateway   = true
  enable_dns_hostnames = true
  enable_dns_support   = true
  public_subnet_tags   = { "kubernetes.io/role/elb" = "1" }
  private_subnet_tags  = { "kubernetes.io/role/internal-elb" = "1" }
}
output "network" {
  value = {
    vpc_id             = module.vpc.vpc_id
    vpc_cidr           = module.vpc.vpc_cidr_block
    public_subnet_ids  = module.vpc.public_subnets
    private_subnet_ids = module.vpc.private_subnets
    availability_zone  = var.availability_zone
  }
}
