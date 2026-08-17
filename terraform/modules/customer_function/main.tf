data "azurerm_resource_group" "resource_group" {
  name = "predicitive-models"
}

resource "azurerm_storage_account" "storage_account" {
  name                     = "pm${var.environment}s1"
  resource_group_name      = data.azurerm_resource_group.resource_group.name
  location                 = var.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
}

resource "azurerm_storage_container" "storage_container" {
  name                  = "${var.project}-storage-container-functions"
  storage_account_id    = azurerm_storage_account.storage_account.id
  container_access_type = "private"
}

# NEW — stores last_processed_time.json for blob state management
resource "azurerm_storage_container" "function_state" {
  name                  = "function-state"
  storage_account_id    = azurerm_storage_account.storage_account.id
  container_access_type = "private"
}

resource "azurerm_log_analytics_workspace" "workspace" {
  name                = "workspace${var.environment}"
  location            = var.location
  resource_group_name = data.azurerm_resource_group.resource_group.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
}

resource "azurerm_application_insights" "application_insights" {
  name                = "${var.project}-${var.environment}-application-insights"
  location            = var.location
  resource_group_name = data.azurerm_resource_group.resource_group.name
  workspace_id        = azurerm_log_analytics_workspace.workspace.id
  application_type    = "other"
}

resource "azurerm_service_plan" "plan" {
  name                = "${var.project}-${var.environment}-plan"
  resource_group_name = data.azurerm_resource_group.resource_group.name
  location            = var.location
  os_type             = "Linux"
  sku_name            = "Y1"
}

resource "azurerm_linux_function_app" "func" {
  name                       = "${var.project}-${var.environment}-function-app"
  resource_group_name        = data.azurerm_resource_group.resource_group.name
  location                   = var.location
  service_plan_id            = azurerm_service_plan.plan.id
  storage_account_name       = azurerm_storage_account.storage_account.name
  storage_account_access_key = azurerm_storage_account.storage_account.primary_access_key

  app_settings = {
    FUNCTIONS_WORKER_RUNTIME       = "python"
    WEBSITE_RUN_FROM_PACKAGE       = 1
    APPINSIGHTS_INSTRUMENTATIONKEY = azurerm_application_insights.application_insights.instrumentation_key
    AzureWebJobsDisableHomepage    = "true"

    # ADDED — real storage connection string for blob state management
    AzureWebJobsStorage = azurerm_storage_account.storage_account.primary_connection_string

    INFLUXDB_URL                      = var.influxdb_url
    INFLUXDB_ORG                      = var.influxdb_org
    INFLUXDB_TOKEN                    = var.influxdb_token
    DEVICE_DATA_BUCKET                = var.influxdb_device_data_bucket
    DEVICE_DATA_MEASUREMENT           = var.influxdb_data_measurement
    PREDICTED_BUCKET                  = var.influxdb_predicted_bucket
    DEVICE_DATA_PREDICTED_MEASUREMENT = var.influxdb_predicted_measurement

    AZURE_TENANT_ID = var.azure_tenant_id

    # REMOVED — not used in your code
    # DEVICE_DATA_PREDICTED_MEASUREMENT = var.influxdb_predicted_measurement
  }

  site_config {
    application_stack {
      python_version = var.python_version
    }
  }
}