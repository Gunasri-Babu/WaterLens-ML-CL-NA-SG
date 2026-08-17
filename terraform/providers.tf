terraform {
  required_providers {
    azurerm = {
      source = "hashicorp/azurerm"
      # Root module should specify the maximum provider version
      # The ~> operator is a convenient shorthand for allowing only patch releases within a specific minor release.
      version = "~> 4.0"
    }

    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }
}

provider "azurerm" {
  subscription_id      = "02cc222e-0bf7-428a-9714-e25c9e64ab18"
  features {}
}