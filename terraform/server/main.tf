locals {
  region = "asia-northeast1"
  labels = {
    application = "mqvpn"
    purpose     = "event-network"
  }
}

provider "google" {
  project = var.project_id
  region  = local.region
  zone    = var.zone
}

data "google_project" "target" {
  project_id = var.project_id

  lifecycle {
    postcondition {
      condition     = tostring(self.number) == var.expected_project_number
      error_message = "プロジェクト番号が確認済みの値と一致しません。"
    }
  }
}

resource "google_compute_network" "vpn" {
  project                 = data.google_project.target.project_id
  name                    = "${var.name}-vpc"
  auto_create_subnetworks = false
  routing_mode            = "REGIONAL"
}

resource "google_compute_subnetwork" "vpn" {
  project       = data.google_project.target.project_id
  name          = "${var.name}-subnet"
  region        = local.region
  network       = google_compute_network.vpn.id
  ip_cidr_range = "10.90.0.0/24"
  stack_type    = "IPV4_ONLY"
}

resource "google_compute_address" "vpn" {
  project      = data.google_project.target.project_id
  name         = "${var.name}-ipv4"
  region       = local.region
  address_type = "EXTERNAL"
  network_tier = var.network_tier
}

resource "google_compute_firewall" "vpn" {
  project       = data.google_project.target.project_id
  name          = "${var.name}-vpn"
  network       = google_compute_network.vpn.name
  direction     = "INGRESS"
  source_ranges = ["0.0.0.0/0"]
  target_tags   = [var.name]

  allow {
    protocol = "udp"
    ports    = ["443"]
  }

  allow {
    protocol = "icmp"
  }
}

resource "google_compute_firewall" "ssh" {
  project       = data.google_project.target.project_id
  name          = "${var.name}-ssh"
  network       = google_compute_network.vpn.name
  direction     = "INGRESS"
  source_ranges = var.admin_ipv4_cidrs
  target_tags   = [var.name]

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }
}

resource "google_service_account" "vpn" {
  project      = data.google_project.target.project_id
  account_id   = "${var.name}-vm"
  display_name = "mqvpn event server (no project IAM roles)"
}

resource "google_compute_instance" "vpn" {
  project             = data.google_project.target.project_id
  name                = var.name
  zone                = var.zone
  machine_type        = "e2-standard-2"
  can_ip_forward      = true
  deletion_protection = false
  tags                = [var.name]
  labels              = local.labels

  boot_disk {
    auto_delete = true

    initialize_params {
      image = "debian-cloud/debian-13"
      type  = "pd-standard"
      size  = 20
    }
  }

  network_interface {
    subnetwork = google_compute_subnetwork.vpn.id

    access_config {
      nat_ip       = google_compute_address.vpn.address
      network_tier = var.network_tier
    }
  }

  scheduling {
    provisioning_model  = "STANDARD"
    preemptible         = false
    automatic_restart   = true
    on_host_maintenance = "MIGRATE"
  }

  shielded_instance_config {
    enable_secure_boot          = true
    enable_vtpm                 = true
    enable_integrity_monitoring = true
  }

  # OS Loginとmetadata公開鍵を混在させず、既存AnsibleのSSHユーザーを固定します。
  metadata = {
    enable-oslogin         = "FALSE"
    block-project-ssh-keys = "TRUE"
    serial-port-enable     = "FALSE"
    ssh-keys               = "${var.ssh_user}:${trimspace(var.ssh_public_key)}"
  }

  # デフォルトサービスアカウントの権限を継承しないため、専用IDを使います。
  service_account {
    email  = google_service_account.vpn.email
    scopes = ["https://www.googleapis.com/auth/cloud-platform"]
  }
}
