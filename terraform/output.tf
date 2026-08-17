# ── NextTier ──────────────────────────────────────────────────
output "nextier_function_app_hostname" {
  value = module.customers["nextier"].function_app_hostname
}

# ── Step ──────────────────────────────────────────────────────
output "step_function_app_hostname" {
  value = module.customers["step"].function_app_hostname
}