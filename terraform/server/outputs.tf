output "server_ipv4" {
  description = "mqvpnの接続先とAnsibleのSSH接続先に使う固定公開IPv4。"
  value       = google_compute_address.vpn.address
}

output "ssh_destination" {
  description = "管理PCの対応する秘密鍵で接続するSSH宛先。"
  value       = "${var.ssh_user}@${google_compute_address.vpn.address}"
}

output "ansible_server" {
  description = "Ansible inventoryへ転記する値。WANのIF名は接続後に実機から取得します。"
  value = {
    ansible_host             = google_compute_address.vpn.address
    ansible_user             = var.ssh_user
    ansible_port             = 22
    event_server_ip          = google_compute_address.vpn.address
    event_server_admin_cidrs = sort(tolist(var.admin_ipv4_cidrs))
  }
}

output "server_configuration" {
  description = "リージョン、通常VM、課金に関係する設定の確認用。"
  value = {
    project_id         = data.google_project.target.project_id
    project_number     = tostring(data.google_project.target.number)
    region             = local.region
    zone               = google_compute_instance.vpn.zone
    machine_type       = google_compute_instance.vpn.machine_type
    provisioning_model = "STANDARD"
    network_tier       = var.network_tier
    boot_disk_type     = "pd-standard"
    boot_disk_gib      = 20
  }
}
