variable "project_id" {
  description = "初期設定側で準備した既存GCPプロジェクトのID。"
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "既存プロジェクトのIDを指定してください。"
  }
}

variable "expected_project_number" {
  description = "意図しないプロジェクトへの作成を防ぐために照合するプロジェクト番号。"
  type        = string

  validation {
    condition     = can(regex("^[0-9]+$", var.expected_project_number))
    error_message = "確認済みのプロジェクト番号を数字の文字列で指定してください。"
  }
}

variable "name" {
  description = "サーバーと専用リソースの名前の接頭辞。"
  type        = string
  default     = "mqvpn-event"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,19}[a-z0-9]$", var.name))
    error_message = "英小文字で始まる3〜21文字の英小文字・数字・ハイフンを指定してください。末尾は英数字です。"
  }
}

variable "zone" {
  description = "東京リージョン内のゾーン。空き状況に応じて変更できます。"
  type        = string
  default     = "asia-northeast1-a"

  validation {
    condition     = contains(["asia-northeast1-a", "asia-northeast1-b", "asia-northeast1-c"], var.zone)
    error_message = "東京のasia-northeast1-a/b/cから選択してください。"
  }
}

variable "admin_ipv4_cidrs" {
  description = "管理PCがSSH接続に使う送信元IPv4 CIDR。/32推奨、/24より広い範囲は禁止。"
  type        = set(string)

  validation {
    condition = length(var.admin_ipv4_cidrs) > 0 && alltrue([
      for cidr in var.admin_ipv4_cidrs : can(cidrnetmask(cidr)) && try(tonumber(split("/", cidr)[1]) >= 24, false)
    ])
    error_message = "管理元のIPv4 CIDRを/24〜/32の範囲で1件以上指定してください。0.0.0.0/0は使えません。"
  }
}

variable "ssh_user" {
  description = "Google guest agentが公開鍵とともに作成するSSH管理ユーザー。"
  type        = string
  default     = "eventadmin"

  validation {
    condition     = can(regex("^[a-z][a-z0-9_]{0,30}$", var.ssh_user)) && var.ssh_user != "root"
    error_message = "root以外の、英小文字で始まる31文字以内のユーザー名を指定してください。"
  }
}

variable "ssh_public_key" {
  description = "管理PCのOpenSSH公開鍵1行。秘密鍵は指定しません。"
  type        = string

  validation {
    condition     = can(regex("^(ssh-ed25519|ssh-rsa|ecdsa-sha2-nistp[0-9]+) [A-Za-z0-9+/=]+( [^\\r\\n]+)?$", trimspace(var.ssh_public_key)))
    error_message = "ED25519、RSA、ECDSAのOpenSSH公開鍵を1行で指定してください。"
  }
}

variable "network_tier" {
  description = "外部IPv4とVMで共通のネットワーク階層。費用を抑える初期値はSTANDARD。"
  type        = string
  default     = "STANDARD"

  validation {
    condition     = contains(["STANDARD", "PREMIUM"], var.network_tier)
    error_message = "STANDARDまたはPREMIUMを指定してください。PREMIUMの送信料は別途確認が必要です。"
  }
}
