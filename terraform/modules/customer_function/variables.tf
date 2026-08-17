variable "project" {
  type        = string
  description = "Project name"
}

variable "environment" {
  type        = string
  description = "Environment (dev / stage / prod)"
}

variable "location" {
  type        = string
  description = "Azure region to deploy module to"
}

variable "python_version" {
  default = "3.10"
}

variable "azure_tenant_id" {
  sensitive = false
}


variable "influxdb_url" {
  description = "URL of the InfluxDB database where the calibration will be stored"
}

variable "influxdb_org" {

}

variable "influxdb_token" {
  sensitive = true
}


variable "influxdb_device_data_bucket" {
  description = "Bucket where inline probes send the measurements"
}

variable "influxdb_data_measurement" {
  description = "Measurement where the inline probes send the data"
}


variable "influxdb_predicted_bucket" {
  description = "InfluxDB bucket where predicted values are written"
}

variable "influxdb_predicted_measurement" {
  type        = string
  description = "Measurement where the predicted values are stored"
  default     = "Predicted_Parameters"
}
