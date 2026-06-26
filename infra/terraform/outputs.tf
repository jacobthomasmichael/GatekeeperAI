output "cluster_endpoint" {
  description = "EKS API server endpoint"
  value       = aws_eks_cluster.main.endpoint
}

output "cluster_name" {
  description = "EKS cluster name"
  value       = aws_eks_cluster.main.name
}

output "ecr_registry_url" {
  description = "ECR registry base URL — set this as ECR_REGISTRY in CI secrets and in values-eks.yaml"
  value       = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.region}.amazonaws.com"
}

output "ecr_repo_urls" {
  description = "Full URIs for each ECR repository"
  value = {
    for k, v in aws_ecr_repository.repos : k => v.repository_url
  }
}

output "rds_endpoint" {
  description = "RDS PostgreSQL hostname (use in DATABASE_URL)"
  value       = aws_db_instance.postgres.address
}

output "rds_port" {
  description = "RDS PostgreSQL port"
  value       = aws_db_instance.postgres.port
}

output "redis_endpoint" {
  description = "ElastiCache Redis hostname (use in REDIS_URL)"
  value       = aws_elasticache_cluster.redis.cache_nodes[0].address
}

output "worker_irsa_role_arn" {
  description = "IAM role ARN for the worker pod IRSA annotation — set as worker.irsaRoleArn in values-eks.yaml"
  value       = aws_iam_role.worker_irsa.arn
}

output "efs_id" {
  description = "EFS filesystem ID — set as the volumeHandle in git-repos-pvc.yaml and nginx-apps-pvc.yaml"
  value       = aws_efs_file_system.main.id
}

output "efs_git_repos_access_point_id" {
  description = "EFS access point ID for the git-repos directory"
  value       = aws_efs_access_point.git_repos.id
}

output "efs_nginx_apps_access_point_id" {
  description = "EFS access point ID for the nginx-apps directory"
  value       = aws_efs_access_point.nginx_apps.id
}

output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "private_subnet_ids" {
  description = "Private subnet IDs (EKS nodes, RDS, Redis, EFS)"
  value       = module.vpc.private_subnets
}

output "public_subnet_ids" {
  description = "Public subnet IDs (NAT gateway, NLB)"
  value       = module.vpc.public_subnets
}

output "kubeconfig_command" {
  description = "Run this to update your local kubeconfig after apply"
  value       = "aws eks update-kubeconfig --region ${var.region} --name ${aws_eks_cluster.main.name}"
}

output "build_context_bucket" {
  description = "S3 bucket for Kaniko build contexts — set as aws.buildContextBucket in values-eks.yaml"
  value       = aws_s3_bucket.build_contexts.bucket
}

output "apps_ecr_repository_url" {
  description = "ECR repository URL for user-deployed app images (built by Kaniko)"
  value       = aws_ecr_repository.apps.repository_url
}
