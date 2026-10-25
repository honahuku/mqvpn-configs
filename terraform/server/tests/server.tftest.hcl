mock_provider "google" {
  mock_data "google_project" {
    defaults = {
      number = "123456789012"
    }
  }
}

variables {
  project_id              = "example-mqvpn-event"
  expected_project_number = "123456789012"
  admin_ipv4_cidrs        = ["198.51.100.10/32"]
  ssh_public_key          = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITestOnlyNotARealKey event-test"
}

run "tokyo_on_demand_server" {
  command = plan

  assert {
    condition     = google_compute_instance.vpn.zone == "asia-northeast1-a" && google_compute_subnetwork.vpn.region == "asia-northeast1"
    error_message = "VMとサブネットは東京に配置する必要があります。"
  }

  assert {
    condition     = google_compute_instance.vpn.scheduling[0].provisioning_model == "STANDARD" && !google_compute_instance.vpn.scheduling[0].preemptible
    error_message = "Spot・preemptibleを使用してはいけません。"
  }

  assert {
    condition     = google_compute_instance.vpn.machine_type == "e2-standard-2" && google_compute_instance.vpn.boot_disk[0].initialize_params[0].size == 20
    error_message = "予算用の初期構成はe2-standard-2と20GiBディスクです。"
  }

  assert {
    condition     = google_compute_instance.vpn.boot_disk[0].initialize_params[0].image == "debian-cloud/debian-13"
    error_message = "Ansibleに合わせてDebian 13を使用する必要があります。"
  }

  assert {
    condition     = google_compute_address.vpn.network_tier == "STANDARD" && google_compute_instance.vpn.network_interface[0].access_config[0].network_tier == "STANDARD"
    error_message = "固定IPとVMの階層を揃え、初期値はStandard Tierにする必要があります。"
  }

  assert {
    condition     = toset(google_compute_firewall.ssh.source_ranges) == var.admin_ipv4_cidrs
    error_message = "SSHは指定した管理元だけに許可する必要があります。"
  }

  assert {
    condition     = google_compute_instance.vpn.metadata["block-project-ssh-keys"] == "TRUE" && google_compute_instance.vpn.metadata["enable-oslogin"] == "FALSE"
    error_message = "SSH認証方式を固定し、プロジェクト共通の鍵を許可しない必要があります。"
  }

  assert {
    condition     = google_compute_instance.vpn.can_ip_forward && google_compute_instance.vpn.shielded_instance_config[0].enable_secure_boot
    error_message = "VPN転送とSecure Bootを有効化する必要があります。"
  }
}

run "reject_non_tokyo_zone" {
  command = plan

  variables {
    zone = "us-central1-a"
  }

  expect_failures = [var.zone]
}

run "reject_public_ssh" {
  command = plan

  variables {
    admin_ipv4_cidrs = ["0.0.0.0/0"]
  }

  expect_failures = [var.admin_ipv4_cidrs]
}

run "reject_wrong_project" {
  command = plan

  variables {
    expected_project_number = "999999999999"
  }

  expect_failures = [data.google_project.target]
}
