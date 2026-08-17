variable "location" {
  type = string
}

variable "azure_tenant_id" {
  type = string
}

variable "customers" {
  description = "Map of all customers and their InfluxDB config"
  type = map(object({
    influxdb_url                   = string
    influxdb_org                   = string
    influxdb_token                 = string
    influxdb_device_data_bucket    = string
    influxdb_data_measurement      = string
    influxdb_predicted_bucket      = string
    influxdb_predicted_measurement = string
  }))
}