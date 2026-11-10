terraform {
  required_version = ">= 1.10, < 2.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "= 6.66.0" }
  }
  backend "s3" {
    key          = "sandbox/terraform.tfstate"
    use_lockfile = true
    encrypt      = true
  }
}
variable "expected_account_id" { type = string }
variable "region" { type = string }
variable "cluster_id" { type = string }
variable "oidc_issuer" { type = string }
variable "worker_security_group" { type = string }
variable "subnet_id" { type = string }
variable "image_creation_enabled" { default = true }
provider "aws" {
  region              = var.region
  allowed_account_ids = [var.expected_account_id]
  default_tags { tags = { Project = "lemonade-demo", Component = "agent-sandbox", Cluster = var.cluster_id, ManagedBy = "terraform" } }
}
locals {
  issuer           = trimprefix(var.oidc_issuer, "https://")
  prefix           = "arn:aws:ec2:${var.region}:${var.expected_account_id}"
  bucket           = "podvm-lemonade-${var.expected_account_id}-${var.cluster_id}"
  region_condition = { StringEquals = { "aws:RequestedRegion" = var.region } }
}
resource "aws_iam_role" "osc" {
  name = "lemonade-sandbox-${var.cluster_id}"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect    = "Allow", Action = "sts:AssumeRoleWithWebIdentity",
    Principal = { Federated = "arn:aws:iam::${var.expected_account_id}:oidc-provider/${local.issuer}" },
    Condition = { StringEquals = { "${local.issuer}:sub" = "system:serviceaccount:openshift-sandboxed-containers-operator:default", "${local.issuer}:aud" = "openshift" } }
  }] })
}
resource "aws_iam_role_policy" "runtime" {
  role = aws_iam_role.osc.id
  name = "bounded-peer-pods"
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["ec2:Describe*"], Resource = "*", Condition = local.region_condition },
    { Effect = "Allow", Action = "ec2:RunInstances", Resource = ["${local.prefix}:instance/*"], Condition = { StringEquals = { "aws:RequestTag/Project" = "lemonade-demo", "aws:RequestTag/Cluster" = var.cluster_id, "ec2:InstanceType" = "t3.medium" } } },
    { Effect = "Allow", Action = "ec2:RunInstances", Resource = ["arn:aws:ec2:${var.region}::image/*", "${local.prefix}:subnet/${var.subnet_id}", "${local.prefix}:security-group/${var.worker_security_group}", "${local.prefix}:network-interface/*", "${local.prefix}:volume/*"], Condition = local.region_condition },
    { Effect = "Allow", Action = "ec2:CreateTags", Resource = "${local.prefix}:instance/*", Condition = { StringEquals = { "ec2:CreateAction" = "RunInstances", "aws:RequestTag/Project" = "lemonade-demo", "aws:RequestTag/Cluster" = var.cluster_id } } },
    { Effect = "Allow", Action = ["ec2:TerminateInstances"], Resource = "${local.prefix}:instance/*", Condition = { StringEquals = { "ec2:ResourceTag/Project" = "lemonade-demo", "ec2:ResourceTag/Cluster" = var.cluster_id } } }
  ] })
}
# Temporary image-builder permissions. The installer refuses a pre-existing vmimport role.
resource "aws_iam_role_policy" "image" {
  count = var.image_creation_enabled ? 1 : 0
  role  = aws_iam_role.osc.id
  name  = "temporary-podvm-image"
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["iam:CreateRole", "iam:PutRolePolicy", "iam:GetRole", "iam:ListRolePolicies", "iam:ListAttachedRolePolicies", "iam:DeleteRole", "iam:DeleteRolePolicy", "iam:PassRole"], Resource = "arn:aws:iam::${var.expected_account_id}:role/vmimport" },
    { Effect = "Allow", Action = ["s3:CreateBucket", "s3:DeleteBucket", "s3:GetBucketLocation", "s3:ListBucket", "s3:GetBucketAcl"], Resource = "arn:aws:s3:::${local.bucket}" },
    { Effect = "Allow", Action = ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"], Resource = "arn:aws:s3:::${local.bucket}/*" },
    { Effect = "Allow", Action = "s3:ListAllMyBuckets", Resource = "*" },
    { Effect = "Allow", Action = ["ec2:ImportSnapshot", "ec2:DescribeImportSnapshotTasks", "ec2:RegisterImage", "ec2:DescribeImages", "ec2:DescribeSnapshots", "ec2:CreateTags", "ec2:DeleteSnapshot", "ec2:DeregisterImage"], Resource = "*", Condition = local.region_condition }
  ] })
}
resource "aws_vpc_security_group_ingress_rule" "agent" {
  security_group_id            = var.worker_security_group
  referenced_security_group_id = var.worker_security_group
  from_port                    = 15150
  to_port                      = 15150
  ip_protocol                  = "tcp"
  description                  = "Lemonade OSC peer-pod agent; project worker SG only"
}
# The existing ROSA self rule already covers TCP 9000; do not duplicate/own it.
output "platform" {
  value = { role_arn = aws_iam_role.osc.arn, bucket = local.bucket, cluster_id = var.cluster_id, subnet_id = var.subnet_id, security_group = var.worker_security_group }
}
