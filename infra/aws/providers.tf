provider "aws" {
  region = var.region

  skip_credentials_validation = var.offline
  skip_requesting_account_id  = var.offline
  skip_metadata_api_check     = var.offline

  default_tags {
    tags = {
      Project   = "cinecloud"
      ManagedBy = "terraform"
    }
  }
}
