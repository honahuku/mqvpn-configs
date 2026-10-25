# ライセンスと配布範囲

## このリポジトリに適用するライセンス

本リポジトリ独自のPlaybook、スクリプト、設定、文書には **Apache-2.0** を適用します。権利者表記は `Copyright (c) 2026 honahuku` です。[LICENSE](../LICENSE) に英語の原文を、[NOTICE](../NOTICE) に帰属情報を置きます。第三者の文面やバイナリまで、このライセンスへ変更するものではありません。

mqvpnがApache-2.0であることだけを理由に、独立した設定一式をApache-2.0にする義務はありません。[Apache-2.0第1条は分離可能な著作物をDerivative Worksの定義から除外し、第4条は元の条件を守ったうえで追加・変更部分に別の条件を付けることを認めています](https://www.apache.org/licenses/LICENSE-2.0)。独自部分にMITを選ぶ余地もあります。

今回はmqvpnの設定例・サービス定義を参考にしたテンプレートも扱うため、上流と同じApache-2.0にそろえます。同ライセンスには[第3条の明示的な特許ライセンス許諾](https://www.apache.org/licenses/LICENSE-2.0)もあります。Apache-2.0に統一しても、上流の著作権・NOTICEや、依存ライブラリ固有の表示を省略できるわけではありません。

## mqvpn 0.18.0と同梱ライブラリ

対象は[公式v0.18.0](https://github.com/mp0rta/mqvpn/releases/tag/v0.18.0)、対応するソースcommitは `14e98987b3d5cbdc25c114923db1114996f7aa1a` です。ローカルのdebは `mqvpn_0.18.0_amd64.deb`、SHA256は `eca43217805f1e26863c6c855c23fe1b245680129a4ed4b4a6b21ae2ed89fdd4` です。版とハッシュは [manifest.json](../event-network-ansible/artifacts/manifest.json) で固定します。

次の文面は、そのdeb内の `/usr/share/doc/mqvpn/` から改変せず保存しています。

表1: 固定debに含まれる権利表記

| 対象 | ライセンス・保存先 |
|---|---|
| mqvpn | [Apache-2.0全文](../licenses/mqvpn-0.18.0/LICENSE)、[元のNOTICE](../licenses/mqvpn-0.18.0/NOTICE) |
| xquic | [Apache-2.0全文](../licenses/mqvpn-0.18.0/third-party/xquic.txt) |
| lwIP | [BSD-3-Clause・著作権表示](../licenses/mqvpn-0.18.0/third-party/lwip.txt) |
| BoringSSL | [パッケージ同梱の複数のライセンス・著作権表示](../licenses/mqvpn-0.18.0/third-party/boringssl.txt) |

このdeb同梱のBoringSSL文書にはApache-2.0全文と、TLSテスト用サポートコードのGo BSDライセンスが収録されています。後者については、コンパイルされたlibcrypto・libsslには含まれず、リンク済みバイナリの配布ではそのライセンスは発動しない旨が文書に記載されています。ここでは文書を抜粋せず全文保持します。

上流のNOTICEにはWindows用Wintunヘッダーへの言及もあります。NOTICEを削らず保存し、その参照先に対応する [WintunのMITライセンス](../licenses/mqvpn-0.18.0/third-party/wintun.txt) も上流v0.18.0の `third_party/wintun/LICENSE` から保存しています。Linuxの構築手順はWintunをインストールしません。これらの著作権表示の権利者は元の文面のままです。

mqvpnの実装ソースやバイナリはGitに含めず、取得スクリプトで公式debをダウンロードします。サーバーへはそのdebを改変せず導入し、パッケージのライセンス文書を削除しません。設定テンプレートの変更が上流のバイナリを改変することはありません。

## Ansible・OS・検査ツール

Playbookは `ansible.builtin` モジュールを呼び出し、スクリプトはインストール済みのコマンドやPython標準ライブラリを使います。このリポジトリにはAnsibleモジュール本体、Pythonライブラリ本体、OSパッケージ本体をコピーしていません。独立した設定やコマンド呼び出しと、それらの実装コードの配布を区別します。

表2: 依存ソフトウェアの扱い

| 対象 | ライセンス確認・リポジトリでの扱い |
|---|---|
| ansible-core | [上流COPYINGはGPLv3](https://github.com/ansible/ansible/blob/devel/COPYING)。外部コマンドとして実行し、実装を同梱しない |
| ansible-lint・yamllint | [ansible-lint COPYING](https://github.com/ansible/ansible-lint/blob/main/COPYING)、[yamllint LICENSE](https://github.com/adrienverge/yamllint/blob/master/LICENSE) はGPLv3。コントローラーで実行する検査ツールで、実装を同梱しない |
| Python・PyYAML・Jinja等 | 各プロジェクトのライセンスが適用される。PythonスクリプトやPlaybookから使用し、ライブラリの実装を同梱しない |
| systemd・dnsmasq・nftables・iproute2・OpenSSL・wpa_supplicant等 | Debianのパッケージとして導入する。GPL・LGPL・BSD・Apache等が混在するため、導入先の `/usr/share/doc/<package>/copyright` と同梱文書を保持する |
| Docker・Debianコンテナ | Dockerfileと検証コードだけをGit管理する。イメージ・レイヤー・OSパッケージは配布しない |

[GPLv3第2条は未改変プログラムの実行を認め、実行結果にGPLが適用されるかは結果そのものの内容によると定めています](https://www.gnu.org/licenses/gpl-3.0.html#section2)。AnsibleやGPLツールを実行するだけで、この独立した設定リポジトリ全体をGPLにするものとは扱いません。将来、モジュール・プラグインの実装をコピー・改変する場合は、この判断をそのまま使わず、そのコードに適用される条件を確認します。

## Gitとローカル配布物の境界

Gitでは設定サンプルとハッシュ固定manifest、第三者の権利表記を管理し、実inventory・秘密情報・deb・ZIP・検証ログを除外します。Gitのライセンスファイルだけで、バイナリ再配布に必要な表示が自動でそろうと考えないでください。

今回移動したローカルZIPには、mqvpn debに加えて、このリポジトリのLICENSE・NOTICE・本書・`licenses/` を含めます。deb単体を改変せず渡す場合も、その中の `/usr/share/doc/mqvpn/` の文書を保持します。展開した実行ファイルだけを渡す場合は、mqvpnと各同梱ライブラリのライセンス・NOTICEを別途同梱する必要があります。

Dockerイメージや構築済みOSを将来配布する場合は、同梱された全パッケージを対象に、ライセンス表示に加えGPL等の対応ソース提供条件も確認します。このGitリポジトリのApache-2.0だけで、イメージ全体を再許諾することはできません。

調査範囲は2026-10-25時点のmqvpn 0.18.0公式debと、このリポジトリに保存する設定・文書・検証コードです。mqvpnの更新や依存実装の同梱を始める場合は、保存済み文面・ハッシュ・配布条件を再確認します。
