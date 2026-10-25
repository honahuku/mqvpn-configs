output "project_id" {
  description = "Terraformで管理するGCPプロジェクトID。"
  value       = data.google_project.target.project_id
}

output "project_number" {
  description = "GCPから取得し、期待値と照合したプロジェクト番号。"
  value       = data.google_project.target.number
}
