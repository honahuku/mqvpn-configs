output "state_bucket_name" {
  description = "初回構築後にGCS backendで使用するバケット名。"
  value       = google_storage_bucket.terraform_state.name
}

output "project_number" {
  description = "GCPから取得し、期待値と照合したプロジェクト番号。"
  value       = data.google_project.target.number
}
