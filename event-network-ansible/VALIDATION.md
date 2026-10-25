# Debian 13構築の検証結果

実施日: 2026-10-25（日本時間）。実サーバー・G3には未適用です。

## 目的

このPCからSSHでサーバーとG3を構築し、失敗時に原因を修正して再適用できることを検証します。VPN経由の転送、LAN分離、回線断時の動作、ネットワーク切替後のSSH再接続を対象にします。

## 方法

Docker内にsystemdで起動するDebian 13環境を用意し、同梱のPlaybookと固定mqvpnパッケージを適用しました。サーバー、G3、通信先、別のSSHコントローラーを仮想NIC・network namespaceで接続しました。テスト用の鍵・CA・PSKは検証環境内だけで生成し、実運用の認証情報と共有していません。

- Debian 13.7、mqvpn 0.18.0 amd64、コンテナ内Ansible core 2.19.11。
- カーネルはDockerホストと共有する `6.18.33.2-microsoft-standard-WSL2`。
- 使用イメージ: `mqvpn-event-debian13:lab`、ID `sha256:95a3312765f601594893da91255e3e16ce5e290fed4407b3680eb8eb3dea3622`。
- Debianベースイメージdigest: `sha256:62bd423aeee912639ca8ee681c2b762cb3e25137e0a92b20be455898a9f034ad`。
- 静的検査はこのPCの既存yamllint、ansible-lint、ansible-playbookを使用。

再実行する場合は、このディレクトリで次を実行します。Dockerの特権コンテナを作成しますが、ホストのネットワーク名前空間やホストファイルシステムをマウントしません。試験中に実機用inventoryを使いません。

```sh
scripts/prepare.sh
scripts/check.sh
docker build -t mqvpn-event-debian13:lab -f tests/Dockerfile .
python3 tests/run.py
python3 tests/ssh-activation.py
```

試験に成功すると、その試験のコンテナとネットワークを削除します。失敗時は調査用に残し、出力された接頭辞で識別します。`tests/run.py --keep` は成功時も残します。再実行の結果は `tests/results/` に出力します。今回の結果のスナップショットは `tests/evidence/2026-10-25/` に保存してあり、再実行では更新されません。Dockerの認証ヘルパーに依存しないよう、試験スクリプトは一時的な匿名Docker設定を使います。

SSH再起動試験では、コンテナ再起動時に仮想NICを復元する試験専用ユニットを使います。またコンテナはカーネルboot IDを共有するため、再起動判定だけPID 1の開始時刻へ置き換えます。実機Playbookの既定値はカーネルboot IDです。

## 結果

### 3回線を通常利用する設定の追加検証

`tests/profiles.yml` はネットワークやサービスを変更せず、本番と同じプロファイル選択タスクと設定テンプレートを使います。3回線の `auto`、会場未設定時の2回線の `auto`、携帯のみ・会場のみの選択、不明なプロファイルと無効な会場プロファイルの拒否を検査します。実行コマンドは `ansible-playbook -i localhost, tests/profiles.yml` です。

今回の実行は `ok=31 changed=0 failed=0 rescued=2` でした。`rescued=2` は不正入力の拒否を期待したテストです。3本の実トランスポート接続・断復帰は今回未実行です。以下のDocker結果は、この変更前の携帯2回線構成の証跡として保持します。実機への適用前に、3回線の接続と各回線の断復帰を検証します。

### 変更前のDocker検証

静的検査はyamllint、ansible-lint、6 Playbookのsyntax-check、Python・shell構文検査が成功しました。出力は [lint.txt](tests/evidence/2026-10-25/lint.txt) です。 既存の実行ラッパーにより、ansible-lintからPATH追加の警告が1件出ます。呼び出す3ツールはいずれも同じ既存venvへのシンボリックリンクであり、そのvenvのパスが追加されています。検査ルールの失敗・警告は0件です。

表1: 統合試験23項目の結果（[生データ](tests/evidence/2026-10-25/latest.json)）

| 対象 | 結果 |
|---|---|
| Debian上でのサーバー・G3への適用、2回目の適用 | 成功。両ホストの2回目は `changed=0` |
| 専用CAで検証したVPN、DJ側・NATルーター配下参加者側の通信 | 成功。2本のトランスポート経路が有効 |
| 参加者の上り・下り制御 | 成功。30MbpsのUDP投入に対して下り8Mbps設定の受信は7.731Mbps（単回測定） |
| G3のSSH・API、上流管理IPへの利用者アクセス遮断 | 成功。G3自身からの上流管理IP到達は維持 |
| IPv6の上流管理IPへの利用者アクセス遮断 | 成功。G3自身からは到達 |
| VPN経由DNS、片回線断での継続 | 成功 |
| VPN停止時の両LAN・未キャッシュDNSの直接WAN迂回防止 | 成功 |
| VPN再接続後の経路・QoS再設定 | 成功 |
| AP方式DHCP | DHCP Offer・ACK、アドレス・GW・DNSオプションが成功 |
| 40送信元IPv4によるHTTP同時接続 | 成功 |
| 間違ったCAと正しいCAへの復帰 | 接続拒否後、正しいCAで回復 |
| 別namespaceからのSSHによる両端再適用 | 成功。再適用後もSSH到達、`changed=0` |
| 重複サブネット・不正なdeb SHA256 | 適用を拒否 |
| `keep_dhcp: true` の構築中管理LAN | DJ側DHCPサーバー設定を生成しない |
| 未確定の有効化からの復元 | 元のネットワークファイル・サービス有効状態へ復元して再起動 |

別の初期状態の2ホストへ、第三のコントローラーからSSHで `site.yml` と `activate-gateway.yml` を実行した試験も成功しました。Ansibleによる再起動、SSH再接続、VPN・FW等の確認、ロールバック解除まで完了しています。最終recapは `g3: ok=5 changed=3 unreachable=0 failed=0` です（[生データ](tests/evidence/2026-10-25/ssh-activation.json)）。

追加の仮想環境試験では、SSHポート2222への適用後も同ポートで再接続できました。また会場予備プロファイルでvenue IFだけにUDPソケットを作成してTUN IPv4を取得し、mobileへ戻すとpovo・softbankの2 IFで再接続しました。オープンSSIDの設定は `key_mgmt=NONE` でした。これらは手動の補助試験で、上記23項目には含みません。

## 考察と適用範囲

ソフトウェアの構築・転送・分離・再適用・SSH再起動経路を、このDocker構成の範囲で検証できています。40送信元の試験はLinux上のIP別同時通信です。40台の実無線端末による接続容量や電波品質を示しません。7.731Mbpsは帯域制御の動作確認用の単回測定であり、G3やmqvpnの最大処理能力を示しません。

USB NIC、Pixel 6、809SH、実際のWi-Fi認証・キャプティブポータル、携帯網の輻輳、ネイティブDebianカーネルでの物理再起動は対象外です。参加者ルーター/APの管理画面と同一L2端末間の通信は、その機器の設定が必要です。`keep_dhcp` は生成設定の検査であり、自宅の実DHCPサーバーとの共存試験ではありません。

## 結論

この一式は、実機のSSH・NIC・管理元IPを記入して構築を開始できる状態です。Docker試験を実会場の性能保証とは扱いません。

## 実機適用時の確認

[HANDOFF.md](HANDOFF.md) の順で、まず接続確認・実inventoryの作成、次にサーバー適用、G3配置・有効化を行います。実機では1080p再生と参加者通信、片回線断、管理画面遮断、USB抜き差し・電源復帰を試します。

## このPCへの追加導入

**ホストに新しくインストールしたツールはありません。** 既存のAnsible関連ツール、Python、OpenSSL、Dockerを使用しました。Debianの検証依存パッケージはDocker内だけに導入し、一覧は [tests/Dockerfile](tests/Dockerfile) に残しています。検証コンテナ・ネットワークは削除し、再現用Dockerイメージは保持しています。固定mqvpn debはこの一式の `artifacts/` に同梱し、このPCにはインストールしていません。
