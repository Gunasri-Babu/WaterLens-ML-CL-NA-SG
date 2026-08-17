location        = "Central US"
azure_tenant_id = "43d0b737-2ed8-4f79-b017-1592baab9626"

customers = {

  # ── NextTier ───────────────────────────────────────────────
  nextier = {
    influxdb_url                   = "https://us-central1-1.gcp.cloud2.influxdata.com"
    influxdb_org                   = "it@waterlensusa.com"
    influxdb_token                 = "raS4k9joVC754-w2UCto3Usj6Vy2aef-00EhCpVRjA7f6NPWQaj3qBUnG8YCKEMyuf3IdDNqgti3eBB_B_37Vw=="
    influxdb_device_data_bucket    = "NEXTIER"
    influxdb_data_measurement      = "sensorDataEnriched"
    influxdb_predicted_bucket      = "NEXTIER"
    influxdb_predicted_measurement = "Predicted_Parameters"
  }

  # ── Add new customer below — nothing else changes ──────────
  step = {
  influxdb_url                   = "https://us-central1-1.gcp.cloud2.influxdata.com"
  influxdb_org                   = "it@waterlensusa.com"
  influxdb_token                 = "raS4k9joVC754-w2UCto3Usj6Vy2aef-00EhCpVRjA7f6NPWQaj3qBUnG8YCKEMyuf3IdDNqgti3eBB_B_37Vw=="
  influxdb_device_data_bucket    = "STEP"
  influxdb_data_measurement      = "sensorDataEnriched"
  influxdb_predicted_bucket      = "STEP"
  influxdb_predicted_measurement = "Predicted_Parameters"
   }
}