module "customers" {
  source   = "./modules/customer_function"
  for_each = var.customers

  project     = "predicitive-models"
  environment = each.key
  location    = var.location

  azure_tenant_id = var.azure_tenant_id

  influxdb_url                   = each.value.influxdb_url
  influxdb_org                   = each.value.influxdb_org
  influxdb_token                 = each.value.influxdb_token
  influxdb_device_data_bucket    = each.value.influxdb_device_data_bucket
  influxdb_data_measurement      = each.value.influxdb_data_measurement
  influxdb_predicted_bucket      = each.value.influxdb_predicted_bucket
  influxdb_predicted_measurement = each.value.influxdb_predicted_measurement
}