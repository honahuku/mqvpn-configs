locals {
  project_id     = "mqvpn-servers"
  project_number = "601341793638"
}

provider "google" {
  project = local.project_id
}

data "google_project" "target" {
  project_id = local.project_id

  lifecycle {
    postcondition {
      condition     = tostring(self.number) == local.project_number
      error_message = "プロジェクトIDと番号の組み合わせがmqvpn-serversと一致しません。"
    }
  }
}
