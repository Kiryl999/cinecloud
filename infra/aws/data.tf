resource "aws_security_group" "data" {
  name        = "${var.name}-data"
  description = "PostgreSQL and Redis, for the nodes of the cluster"
  vpc_id      = aws_vpc.main.id
}

resource "aws_vpc_security_group_ingress_rule" "postgres" {
  security_group_id            = aws_security_group.data.id
  referenced_security_group_id = aws_eks_cluster.main.vpc_config[0].cluster_security_group_id
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
}

resource "aws_vpc_security_group_ingress_rule" "redis" {
  security_group_id            = aws_security_group.data.id
  referenced_security_group_id = aws_eks_cluster.main.vpc_config[0].cluster_security_group_id
  ip_protocol                  = "tcp"
  from_port                    = 6379
  to_port                      = 6379
}

#  PostgreSQL 

resource "aws_db_subnet_group" "main" {
  name       = var.name
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_db_instance" "main" {
  identifier = var.name

  engine         = "postgres"
  engine_version = "16" # the version CI tests against
  instance_class = var.database_instance_class

  allocated_storage = 20
  storage_type      = "gp3"
  storage_encrypted = true

  db_name  = "cinecloud"
  username = "cinecloud"
  # AWS creates the password and keeps it in Secrets Manager: it appears
  # neither in this code nor in the Terraform state
  manage_master_user_password = true

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.data.id]
  publicly_accessible    = false

  backup_retention_period = 7
  # a second instance in the other zone takes over within a minute or two;
  # left off for the demo, where it would double the cost
  multi_az = false

  # a demo: `terraform destroy` removes it without a last snapshot
  skip_final_snapshot = true
}

#  Redis 

resource "aws_elasticache_subnet_group" "main" {
  name       = var.name
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_elasticache_cluster" "main" {
  cluster_id      = var.name
  engine          = "redis"
  engine_version  = "7.1"
  node_type       = var.cache_node_type
  num_cache_nodes = 1
  port            = 6379

  subnet_group_name  = aws_elasticache_subnet_group.main.name
  security_group_ids = [aws_security_group.data.id]
}
