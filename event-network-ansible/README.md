# Debian 13 イベントネットワーク

20人・約40端末のイベントで、DJ・VJの通信を優先し、携帯2回線をmqvpnで会場外サーバーへ接続する構成です。**このPCからSSHで両マシンへAnsibleを実行します。** サーバー・G3の実機にはまだ適用していません。

要件元は[DJネットワーク](https://app.notion.com/p/honahuku/DJ-40007494944e806191c1fd925b3f764b)と本チャットです。OSは両端Debian 13 amd64、携帯はPixel 6＋所有povo、809SH＋SoftBankを想定します。AP・ルーターのメーカーには依存しません。TP-LinkとBUFFALOの調達は前提にしていません。

## 構成と初期設定

```text
Pixel 6 ─USB─ povo ───────┐
809SH ──USB─ softbank ────┤ G3 ── mqvpn ── Debian 13サーバー ── Internet
会場Wi-Fi ─ venue（任意）─┘  ├─ djlan ── スイッチ ── DJ・VJ
                            └─ guestlan ── 参加者ルーター／AP ── 約40端末
```

表1: 初期ネットワークと帯域設定

| 項目 | 初期値・動作 |
|---|---|
| DJ・VJ | G3 `192.168.50.1/24`、DHCP `.100–.199` |
| 管理PC | DJ側の `192.168.50.10` を予約。SSHを許可するIPは明示指定 |
| 参加者側のG3 | `192.168.60.1/24` |
| ルーター接続（既定） | ルーターWAN `.60.2/24`、GW/DNS `.60.1`、ルーターLAN `192.168.70.0/24` |
| AP接続 | `event_guest_mode: ap`。G3がDHCP `.60.100–.229` を配布 |
| VPN | `10.77.0.0/24`、UDP 443 |
| 参加者の合計帯域 | 下り8Mbps、上り1Mbps。現地測定後に変更する仮値 |
| トンネルへの上り | 全体15Mbps、出演者優先。仮値 |
| mqvpn | **0.18.0固定**、両端 `wlb_udp_pin`、Hybrid有効、TCP上限512 |
| 通常利用 | povo・SoftBankの2本だけ。会場Wi-Fiは自動では混ぜない |
| 障害時 | 片回線断はmqvpnに任せる。会場Wi-Fiへの切替は管理者が実施 |
| VPN停止時 | 利用者LANからのインターネット転送を遮断。直接WANへ迂回しない |
| IPv6 | 利用者LANのIPv6転送を遮断。IPv4専用の初版 |

ネットワークアドレスは仮値です。携帯側、会場Wi-Fi、現在の管理LANとの重複を調べます。ルーター方式では参加者がNATでまとめられるため、G3での制御は参加者全体が単位です。AP方式では参加者IPを識別できますが、初版の帯域設定は全体上限＋フローごとのfq_codelです。**端末ごとの厳密な公平分配は実装していません。**

`wlb_udp_pin`はYouTube等の内部QUICを1接続ごとに1回線へ寄せる初期案です。1本の内部QUIC接続で帯域合算する設定ではありません。実動画で比較し、必要なら両端の `event_scheduler` を変更します。HybridはTCPに作用します。受信用にクライアントのUDP複製機能を使う構成ではありません。

## このPCで編集する設定

このPCの `inventory/hosts.yml` に設定欄を用意してあります。Gitからクローンした場合は `inventory/hosts.example.yml` を `inventory/hosts.yml` へコピーしてから編集します。既存の実設定は上書きしません。`hosts.example.yml` は初期状態の参照用です。実設定を書いた後にサンプルで上書きしないでください。

表2: inventory/hosts.yml の編集箇所

| 設定 | 入れる値 |
|---|---|
| `ansible_host`（各ホスト） | **現在SSHで到達できるIPまたは名前**。将来のLAN IPではない |
| `ansible_user` | SSHユーザー。root、またはsudo可能な管理ユーザー |
| `ansible_port` | SSHポート。既定22 |
| `ansible_ssh_private_key_file` | このPCの秘密鍵パス。秘密鍵そのものを書かない |
| `event_server_ip` | G3から接続できるサーバーの固定公開IPv4。SSH接続先と別指定 |
| `event_server_admin_cidrs` | このPCからサーバーへのSSHが実際に出る送信元IP `/32` 等 |
| `event_server_wan` | サーバーのインターネット向けIF名。例 `ens3` |
| `event_links` | G3の内蔵LAN・USB-LAN・携帯USBの対応。MACまたはUSBの`ID_PATH`で指定 |
| `event_gateway_admin_cidrs` | 管理用 `.50.10/32` と、構築中のこのPCの実際の送信元IP `/32` |
| `event_guest_mode` | 参加者機器がルーターなら `router`、APなら `ap` |

接続先ごとにユーザー・鍵・ポートが異なる場合は、ホスト直下に書いて共通値を上書きできます。SSHのProxyJump等は `ansible_ssh_common_args` に指定できます。実機情報は今は未確定なので、IP・MAC・USB識別子を捏造して埋めていません。サンプルの予約アドレスや `REPLACE_...` は実適用前の検査で拒否します。

FWが許可するSSHポートは、SSHセッションの接続先ポートから検出します。NAT等で外側のポートとsshdのポートが違う場合も、sshd側を使います。ローカル適用の場合だけ `event_ssh_port`（既定22）を指定できます。初版のSSH管理元CIDRはIPv4です。

G3のネットワークは `systemd-networkd` が担当します。携帯USBのMACが変わる場合に備えて、USBの物理経路 `ID_PATH` を推奨します。**その場合はケーブルを挿すUSBポートを固定します。** `.link`によるIF名変更は再起動で反映します。

## SSHを準備した後の実行

OSインストールとSSHの有効化は各マシンで済ませます。このPCから鍵でログインでき、管理ユーザーがsudoできる状態が入口です。sudoがパスワード式なら以下のコマンドに `--ask-become-pass` を加えます。パスワードはYAMLへ平文保存しません。

以下はこのREADMEと同じディレクトリを作業場所にして実行します。「後お願い」と依頼された際の作業順序は [HANDOFF.md](HANDOFF.md) にまとめています。

```sh
# Pythonが無い最小インストールの場合だけ実行
scripts/manage.sh bootstrap

# SSH・sudo・Debianの版・IF/MAC/USB識別子を読み取り確認
scripts/manage.sh connect

# 接続確認結果に合わせて inventory/hosts.yml を編集後、認証情報を一度だけ生成
scripts/init-secrets.sh

# Gitクローン時に固定パッケージを取得。ローカルに同梱済みなら再検証
scripts/prepare.sh

# 先にサーバー、次にG3の設定配置
scripts/manage.sh server
scripts/manage.sh gateway

# G3のネットワーク切替と再起動。SSH再接続後に確認して確定
scripts/manage.sh activate
```

`server.yml` はサーバーのサービスとFWを適用します。クラウド側のセキュリティグループでもUDP 443と管理用SSHを許可してください。VM作成・クラウド側FW・課金管理はこのAnsibleの対象外です。

`gateway.yml` はパッケージ・設定を配置しますが、稼働中のネットワーク管理サービスを止めたり、新しいFWを有効化したりしません。再適用もまずこの段階から行います。`site.yml` はこの2つを順に実行し、G3の再起動は含みません。

`activate-gateway.yml` は既存のNetworkManager／ifupdownを次回起動時に停止するよう設定し、networkd・FW・VPNを有効化して再起動します。**その後180秒以内に元のSSH接続先へ戻り、FW・DNS・ルートガード・VPNのIPv4設定を確認できた場合に確定**します。確定されなければ起動から360秒後に元のネットワーク設定・サービス有効状態を復元して再起動します。最初の切替前に採ったスナップショットへの復元で、OS全体のロールバックではありません。

### G3へのSSHを切替後も維持する

既存有線LANをDJ側にする場合、サンプルの `keep_dhcp: true` により、イベント用固定アドレスと**構築中のLANから取得するDHCPアドレスを併用**します。自宅ルーター側でG3のMACにDHCP予約を設定すると、SSH接続先を維持しやすくなります。G3へSSHしているこのPCのIPも `event_gateway_admin_cidrs` に含めてください。PlaybookはSSHセッションの送信元が許可範囲に入るか検査します。

**`keep_dhcp: true` の間はDJ側のDHCPサーバーを停止**し、自宅LANへ別のDHCPサーバーを持ち込まないようにします。会場へ移す前に、管理PCを固定IP `.50.10` で接続できることを確認し、`keep_dhcp: false` にして再配置・有効化すると、DJ側のDHCP配布が始まります。参加者側は別NICなので、AP方式のDHCPとは独立しています。

別の有線管理アダプターを使う場合は、`event_links` に `role: management` のリンクを追加できます。このリンクはmqvpnの経路に入りません。無線を管理専用にする場合の認証移行は初版では自動化していません。

切替でIPが変わった場合、すぐに同じPlaybookを連打せず、ロールバックの再起動を待って元の接続先を確認します。実機の電源断・起動不能・SSH設定自体の故障まではネットワーク復元で救えません。初回は画面とキーボードを手元に置いて試します。

## 会場Wi-Fiを予備として設定する場合

`event_links` に `role: venue` の無線IFを追加し、`event_venue_enabled: true` とSSIDを設定します。WPA-PSKならパスワードも設定し、オープンSSIDなら省略します。

```yaml
event_venue_enabled: true
event_venue_ssid: "会場のSSID"
# event_venue_psk: "パスワード"  # Vault等で管理。オープンSSIDなら省略
```

通常の `mobile` プロファイルにはこのIFを含めません。退避するときだけG3で実行します。

```sh
sudo event-profile venue
sudo event-profile mobile
```

切替はVPNの再接続を伴います。キャプティブポータルのログインやUDP疎通は別途現地確認が必要です。再起動後も選択中のプロファイルを使いますが、Ansibleの再適用はinventoryの通常方針に合わせてmobileへ戻します。

## 管理画面と利用者LANの分離

G3はLANからTUNへの転送だけを許可し、携帯WAN・会場WANへの直接転送を許可しません。さらにRFC1918・リンクローカル・CGNAT等を宛先とする転送を、VPN経由でも拒否します。測定した管理IPがこれらの外なら `event_extra_blocked_v4` に追加します。これにより `web.setting` の名前を隠すだけに頼らず、809SH管理IPの直指定も遮断します。G3自身からの管理は可能です。

**参加者ルーター/AP自身の管理画面は別途、その機器側で遮断してください。** 同じ無線LAN内の通信はG3を通らず、G3のFWだけでは管理画面や端末間通信を遮断できません。ゲストSSID・管理元制限・クライアント分離の対応を機種ごとに確認します。809SHのWi-Fiも不要なら停止し、利用者がG3を迂回して直接接続できないようにします。

参加者とDJ・VJは別NIC・別サブネットです。DJ・VJ間はスイッチ内で通信でき、VPN停止時もローカル通信を維持できます。各スイッチの同じLAN内通信をG3が検査する構成ではありません。

FWは専用の `inet event_network` テーブルだけをトランザクションで置き換えます。ホストの全ルールをflushしません。ただし他のFWが別チェーンで通信をdropすれば、こちらのacceptより優先して遮断されます。新規の専用Debianを前提に、既存FWがあれば確認して統合します。上流mqvpnのサーバーユニットはNATの二重管理を避けるため停止し、専用 `event-vpn` を使います。

## 帯域と復旧

参加者下りはguestlanの送信側、参加者上りはTUNへの送信側で制御します。上りの分類はNAT前のパケットマークを使います。IFやTUNが作り直された場合、タイマーがルート・QoSを再設定します。G3自身の管理通信は利用者用ポリシールートへ入れません。

下りはG3に届くまでに携帯帯域を消費しています。下り8Mbpsという設定だけで、無線区間の混雑時にDJ用帯域を保証できるわけではありません。弱い回線1本でも出演者の再生と制限後の参加者通信を運べるよう、現地で値を決めます。値を変更したらG3の設定配置と有効化を行います。

```sh
sudo event-diagnose
sudo systemctl restart event-vpn
sudo journalctl -u event-vpn -n 100 --no-pager
```

`Restart=always` で異常終了後に再起動しますが、端末側のUSBテザリングを再度ONにする操作やSIMのPIN解除は代行できません。画面消灯中の通信、給電、発熱、USB抜き差し、停電復帰は実機で試します。

## 認証情報と固定バージョン

`secrets/` にはPSK・専用CA・サーバー証明書を作ります。CA秘密鍵はこのPCだけに保管し、G3にはCA証明書だけを配置します。システム全体の信頼ストアは変更しません。サーバー証明書は90日有効です。`ServerName=vpn.event.internal` と専用CAで検証するため、この名前を外部DNSへ登録する必要はありません。

秘密の配置タスクは `no_log` と `diff: false` を使います。`init-secrets.sh` は再実行で鍵を変更しません。`secrets/` と実inventoryは公開Gitへ入れず、必要ならAnsible Vaultでinventoryの秘密変数を暗号化してください。SSH秘密鍵を接続先へコピーする必要はありません。

固定debはこのローカル作業コピーの `artifacts/` にありますが、Gitには含めません。Gitで管理するSHA256 manifestを使い、クローン後は `scripts/prepare.sh` で取得します。導入時に接続先でもSHA256を確認します。APT依存パッケージの導入には接続先からDebianミラーへの通信が必要です。当日の復旧は既存サービス・保存済み設定を使い、OS再インストールまで完全オフラインにする仕組みではありません。

## 検証

実行方法と結果の範囲は [VALIDATION.md](VALIDATION.md) に記載しています。Docker試験は仮想NICによるLinux通信の検証です。40台分のWi-Fi電波、地下会場の携帯網、Pixel 6・809SHのUSBドライバーや発熱、物理再起動後のUSB認識は再現できません。

当日は1080p固定で実動画を流し、参加者側の大量通信と片回線断を重ねて試験します。実機の合否条件は、再生停止・バッファ量、片回線時の継続、管理画面遮断、再起動後の復帰です。

## ライセンス

この設定一式の独自部分はApache-2.0です。適用範囲と第三者ソフトウェアの扱いは [リポジトリのライセンス説明](../docs/LICENSING.md)、全文は [LICENSE](../LICENSE)、帰属情報は [NOTICE](../NOTICE) を参照してください。
