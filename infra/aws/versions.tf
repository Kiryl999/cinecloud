# The AWS target architecture of CineCloud: a network, an EKS cluster for the
# app, and PostgreSQL and Redis as managed services. The app itself is
# deployed into the cluster as on minikube, by Argo CD from k8s/.

terraform {
  required_version = ">= 1.16"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.70"
    }
  }

}
