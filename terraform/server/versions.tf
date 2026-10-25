terraform {
  required_version = ">= 1.17.0, < 2.0.0"

  backend "local" {
    path = "terraform.tfstate"
  }

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "8.8.1"
    }
  }
}
