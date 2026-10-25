# この構築一式を後から扱うエージェントへ

- 最初にREADME.md、HANDOFF.md、VALIDATION.mdと実inventoryを読む。
- コントローラーはこのPC。対象はSSH先のDebian 13サーバーとG3。Docker検証結果を実機での成功と扱わない。
- 機器選定は未確定。TP-LinkとBUFFALOを候補に追加しない。
- 適用を依頼されたら接続・構成確認から進め、失敗したタスクの原因を修正して再適用する。接続先・鍵・MAC・USBポートを推測しない。
- gateway.ymlは配置、activate-gateway.ymlはネットワーク切替と再起動。元のSSH経路、管理元CIDR、DHCP維持を確認してから切り替える。
- 秘密鍵・PSK・秘密変数をツール出力やレポートに出さない。生成済みsecretsを再生成しない。
- 実機適用後に実機の確認結果を追記する。Notionの編集は依頼がある場合だけ行う。
- このPCに追加導入したものとDocker内だけに導入したものを区別して報告する。
