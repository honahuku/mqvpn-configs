# 東京のmqvpnサーバー

通常VMを東京に1台作り、既存のDebian 13向けAnsibleへ引き渡すTerraform設定です。この作業からリソースはまだ作成していません。サーバーのstateは手元の `terraform/server/terraform.tfstate` に保存し、プロジェクト初期設定とは分離します。

## 初期構成

表1: 作成するリソース

| 対象 | 設定 |
|---|---|
| VM | `e2-standard-2`、2 vCPU・8GiB、通常VM。Spotは使用しない |
| 配置 | 東京 `asia-northeast1`。既定ゾーンは `asia-northeast1-a` |
| OS・ディスク | Debian 13 amd64、20GiBの `pd-standard` |
| 外部IP | 固定IPv4、既定はStandard Tier |
| VPC | 専用VPCと東京のIPv4サブネット `10.90.0.0/24` |
| 受信 | UDP 443とICMP。SSH 22は指定した管理元IPv4だけ |
| VMの権限 | 専用サービスアカウント。プロジェクトのIAMロールは付与しない |

Cloud NAT、ロードバランサー、Cloud VPN、追加の監視基盤は作りません。mqvpn自体とOS内のFW・NAT・転送設定は[既存Ansible](../../event-network-ansible/README.md)が担当します。VMのIP転送許可だけは本設定で有効化します。

## 初期設定側との接続

別途進めている初期設定でCompute Engine・IAM APIを有効化した後に使います。サーバーのstate保管用GCSバケットは不要です。この設定はバケット・API・プロジェクトを重複管理しません。

`terraform.tfvars.example` を参照し、既存プロジェクトのID、確認済みの番号、管理PCの送信元IPv4 `/32`、SSH公開鍵をローカルの `terraform.tfvars` に指定します。SSH秘密鍵は使わず、このディレクトリやGCPへコピーしません。実tfvarsはGitから除外しています。

backendは `local` で、保存先はこのディレクトリの `terraform.tfstate` です。stateとバックアップはGit管理から除外しています。stateには機微な値が含まれ得るため、公開せず手元でバックアップし、以後も同じstateを引き継いで実行します。別環境で適用済みなら、既存stateの所在を確認して引き継ぐまで新しい空stateで適用しません。

`backend.hcl.example` は将来GCSへ移行する場合の参考として残しており、現在は使いません。今回の変更は保存先の設定だけで、既存stateの移行処理は実行していません。GCP操作の認証は初期設定側と同じADCを使います。

OS Loginを無効化し、VM固有のmetadata公開鍵で `eventadmin` に接続する構成です。プロジェクト全体のSSH公開鍵は受け入れません。組織ポリシーがOS Loginを必須にする場合は、そのポリシーへ合わせた認証設計への変更が必要です。[metadata公開鍵の管理](https://docs.cloud.google.com/compute/docs/connect/add-ssh-keys)

## 費用

1日1,000円未満を目指してStandard Tierと最小限のリソースを選んでいますが、これは課金上限を強制する設定ではありません。VMの処理能力は実通信で検証し、参加者全体の通信量とCPU使用率を見て判断します。

Standard Tierのインターネット送信には、現在の掲載条件でアカウント全体・全リージョン共通の月200GiB無料枠があり、その後の最初の課金帯は$0.085/GiBです。会場へ返す動画データとVPNの付加データ・再送も送信量に含みます。無料トライアルのクレジットとは別の条件であり、両方の残量を適用前に確認します。[ネットワーク料金](https://cloud.google.com/vpc/network-pricing)

無料枠内でもVM・ディスク・外部IPv4には費用がかかります。VMの料金は東京・Linux・通常利用で公式計算機に入力して確認し、JPY課金単価と税を含めて判断します。[VM料金](https://cloud.google.com/products/compute/pricing/general-purpose?hl=en)、[計算機](https://cloud.google.com/products/calculator)

`network_tier = "PREMIUM"` に変更する場合は通信料を再計算します。Standard Tierとの経路品質差は実際の会場・回線で比較します。VMを停止しただけではディスク・固定IPなどの費用は止まりません。イベント後はこのserver stateが管理するリソースの撤去を確認し、完了するまで手元のstateを保持します。

## Ansibleへの引き渡し

本人による適用後、`ansible_server` 出力を既存inventoryのサーバー設定へ転記します。`server_ipv4` はG3側の `event_server_ip` にも使います。`ssh_destination` はSSH接続先です。WANのIF名は捏造せず、`scripts/manage.sh connect` で取得して `event_server_wan` に設定します。

TerraformはmqvpnのPSKやCA秘密鍵を扱いません。SSH・sudoとネットワーク構成を確認してから、既存Ansibleのサーバー構築へ進みます。GCPの受信FWとAnsibleのOS内FWは両方で許可が必要なため、管理元CIDRを一致させます。

## 検証

[検証専用CI](../../.github/workflows/terraform-server.yml)はTerraform 1.17.0、Google provider 8.8.1、TFLint 0.64.0を使います。fmt、backend未接続の初期化、validate、mock providerによるplanテスト、TFLintを実行します。GCPの認証情報とapplyは使いません。テストは東京・通常VM・VMサイズ・OS・Standard Tier・SSH制限と、不正なゾーン・SSH公開範囲・プロジェクト番号の拒否を対象にします。

CIは実環境のstateを読み書きしません。アップロードする `.terraform.lock.hcl` はproviderの依存lockで、リソースのstateである `terraform.tfstate` とは別のファイルです。

コミット `e0f15cd` の[CI](https://github.com/honahuku/mqvpn-settings/actions/runs/40155065571)でfmt、初期化、validate、mockテスト4件、TFLintが成功しました。初回のfmt指摘は修正済みです。provider lockはそのCIが生成したartifactから取得したものを保存し、手書きのチェックサムは使いません。以後のCIはlockを読み取り専用にして検証します。ActionはNode.js 24対応の公式リリースをコミットSHAで固定します。

この結果は実GCPへのplan・適用や性能試験を含みません。クォータ、課金先、組織ポリシー、実際のSSH接続と通信性能は、実環境で確認します。
