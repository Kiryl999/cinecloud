output "kubeconfig_command" {
  description = "Points kubectl at the new cluster."
  value       = "aws eks update-kubeconfig --region ${var.region} --name ${aws_eks_cluster.main.name}"
}

# What the overlay of this environment sets instead of the in-cluster
# PostgreSQL and Redis of minikube.
output "database_host" {
  value = aws_db_instance.main.address
}

output "database_password_secret" {
  description = "The Secrets Manager secret holding the database password."
  value       = aws_db_instance.main.master_user_secret[0].secret_arn
}

output "redis_url" {
  value = "redis://${aws_elasticache_cluster.main.cache_nodes[0].address}:6379/0"
}
