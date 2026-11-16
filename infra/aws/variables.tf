variable "region" {
  type    = string
  default = "eu-central-1"
}

variable "availability_zones" {
  description = "Two zones: the database, the cache and the nodes are spread over both."
  type        = list(string)
  default     = ["eu-central-1a", "eu-central-1b"]
}

variable "name" {
  type    = string
  default = "cinecloud"
}

variable "kubernetes_version" {
  type    = string
  default = "1.34"
}

variable "node_instance_type" {
  type    = string
  default = "t3.medium"
}

variable "node_count" {
  description = "Nodes of the cluster: as many as needed, between min and max."
  type = object({
    min     = number
    desired = number
    max     = number
  })
  default = { min = 2, desired = 2, max = 4 }
}

variable "api_allowed_cidrs" {
  description = "Who may reach the Kubernetes API from the internet: the admins' addresses, e.g. [\"203.0.113.7/32\"]. No default, so it is never the whole internet by accident."
  type        = list(string)

  validation {
    condition     = length(var.api_allowed_cidrs) > 0 && !contains(var.api_allowed_cidrs, "0.0.0.0/0")
    error_message = "Name the addresses that may reach the Kubernetes API, not the whole internet."
  }
}

variable "database_instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "cache_node_type" {
  type    = string
  default = "cache.t4g.micro"
}

variable "offline" {
  description = "Plan without an AWS account, see providers.tf."
  type        = bool
  default     = false
}
