# mqvpn-configs

povo・SoftBank・会場Wi-Fiの3回線をmqvpnの通信候補にし、DJ・VJと参加者の通信を分けるイベント用ネットワークの設定・構築手順です。配分はmqvpnに任せ、回線名による優先順位は付けません。サーバーとG3 PlusにはDebian 13 amd64を使い、管理PCからSSH経由でAnsibleを実行します。

OS内の構築一式は [`event-network-ansible/`](event-network-ansible/) にあります。

- [GCPプロジェクトのTerraform初期設定](terraform/README.md)
- [Terraformの初回init・plan・apply手順](docs/gcp-terraform-setup.md)
- [構成・設定・実行手順](event-network-ansible/README.md)
- [SSHを準備した後の作業順序](event-network-ansible/HANDOFF.md)
- [Docker検証の結果と実機で残る確認](event-network-ansible/VALIDATION.md)
- [ライセンスの選定と第三者ソフトウェアの扱い](docs/LICENSING.md)

クローンした場合は、最初に作業用inventoryを作成します。すでに実設定がある場合は上書きしません。

```sh
cd event-network-ansible
cp -n inventory/hosts.example.yml inventory/hosts.yml
scripts/prepare.sh
```

`inventory/hosts.yml` のIP・SSHユーザー・鍵のパス・NIC識別子を実機に合わせて設定します。実inventory、秘密鍵・PSK、ダウンロードしたdeb、検証ログ、配布用ZIPはGit管理から除外します。固定パッケージの版・SHA256・取得URLは `artifacts/manifest.json` で管理します。

実機にはまだ適用していません。Docker上での通信・分離・SSH再起動試験は、実会場の無線品質やUSB機器の動作を保証するものではありません。

## ライセンス

本リポジトリ独自のPlaybook・スクリプト・設定・文書は **Apache License 2.0** で提供します。Copyright (c) 2026 honahuku。

第三者ソフトウェアとそのライセンス文面には、それぞれの権利者・ライセンスが適用されます。[LICENSE](LICENSE)、[NOTICE](NOTICE)、[第三者のライセンス文面](licenses/mqvpn-0.18.0/)を参照してください。mqvpnの公式リポジトリは [mp0rta/mqvpn](https://github.com/mp0rta/mqvpn) です。
