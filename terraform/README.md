# mqvpn-serversのTerraform初期設定

対象は既存のGCPプロジェクト `mqvpn-servers`、番号 `601341793638` です。プロジェクトIDと番号はユーザーから提示された値です。GCPへはまだ認証・接続していません。各設定の `google_project` data sourceが実際の番号を読み、期待値と異なる場合は処理を止めます。

この段階の管理対象はstate用バケットと必要APIです。VM、外部IP、VPC、ファイアウォール、サービスアカウントは、サーバー構成を決めた後に追加します。OS内は既存の[Ansible](../event-network-ansible/README.md)が担当します。

## 構築を分ける理由

`bootstrap/` はstate用GCSバケットとStorage API、`project/` はCompute Engine・IAM APIを管理します。存在しないバケットへstateを保存しようとすると初回の初期化ができないため、先にbootstrapをローカルstateで構築し、その後にGCSへ移行します。

表1: stateの保存先

| 設定 | バケット | prefix |
|---|---|---|
| bootstrap | `mqvpn-servers-tfstate-601341793638` | `mqvpn-servers/bootstrap` |
| project | 同上 | `mqvpn-servers/project` |

バケットは東京の `ASIA-NORTHEAST1`、公開アクセス禁止、均一なIAMアクセス制御、Object Versioning、soft delete保持期間604800秒を指定します。保存・操作・履歴にはGCSの料金がかかります。バケットのロケーションは作成後に変更できないため、初回適用前に場所を確認してください。[Cloud Storageのstate保存](https://cloud.google.com/docs/terraform/resource-management/store-state)

`force_destroy = false`、`deletion_policy = "PREVENT"`、`prevent_destroy = true` でTerraform経由の削除を抑止します。これらはコンソールや他の管理者による削除を禁止するIAM設定ではありません。プロジェクトAPIは設定を外しても無効化しない方針です。

## 認証と事前条件

ローカル実行にはGoogle Cloud CLIとADCを使います。サービスアカウントのJSON鍵は作成せず、認証情報をリポジトリへ保存しません。[Google推奨のTerraform認証](https://cloud.google.com/docs/terraform/authentication)

認証コマンドとプロジェクト番号の確認は、[初回構築手順](../docs/gcp-terraform-setup.md#前提と認証)にまとめています。

課金先の紐付けと、Service Usage・Cloud Resource Manager APIの利用可否はコンソールで確認します。初回構築者には、プロジェクト参照、API有効化、バケット作成・設定変更の権限が必要です。GCS backendの使用者には、対象バケットのオブジェクトを読み書きしてロックを扱える権限が必要です。権限不足の場合はエラーに含まれる操作を確認し、対象を限定して追加します。[GCS backendの認証・権限](https://developer.hashicorp.com/terraform/language/backend/gcs)

## 初回適用の順序

init・plan・apply、state移行、ログ保存の実行コマンドは、[初回構築手順](../docs/gcp-terraform-setup.md)を参照してください。

1. Terraformのprovider lockを各設定へ保存し、検査を完了する。
2. `bootstrap/` をローカルstateで初期化し、planがStorage APIとstate用バケットだけを対象にすることを確認して適用する。
3. 出力されたバケット名を `bootstrap/backend.hcl` と照合する。
4. `bootstrap/backend.tf.example` を同じディレクトリの `backend.tf` として新規配置し、`bootstrap/backend.hcl` を使って既存stateをGCSへ移行する。元のローカルstateと移行時のバックアップは、移行を確認するまで保持する。
5. `project/` を `project/backend.hcl` で初期化し、API設定をplan・適用する。

両方の設定を同時に適用しないでください。bootstrapのバケット作成とstate移行が完了してからprojectへ進みます。バケット名が既存の他者のものと衝突する場合は、新しい名前と両方のbackend設定をそろえてから進めます。

`bootstrap/backend.tf` は初回移行後だけ存在するローカル設定としてGitから除外します。`project/` にはGCS backend宣言を常に置くため、新しい作業コピーでも明示的なbackend初期化が必要です。クローン直後にbootstrapを実行する場合は、すでに構築済みか確認し、構築済みなら先にGCS backend設定を配置します。空のローカルstateで既存バケットを再作成しようとしないでください。

## バージョンと検査

Google providerは `8.8.1`、Terraformの下限は `1.17.0` です。CIはTerraform `1.17.0`、既存のローカル環境と同じTFLint `0.64.0` に固定します。Google providerの依存lockはTerraform初期化で生成し、`.terraform.lock.hcl` としてGit管理します。手書きのチェックサムは使いません。

[検査CI](../.github/workflows/terraform.yml)はbootstrap・projectそれぞれでfmt、backend未接続の初期化、validate、TFLintを実行します。GCPの認証情報を使わず、plan・applyも実行しません。初回CIは生成したprovider lockをartifactへ保存します。取得したlockを確認して各ディレクトリへ保存し、以降の変更とともにコミットします。

ローカルで実行可能な静的検査は、リポジトリ直下から次のように指定します。

```sh
tflint --chdir=terraform/bootstrap --config=../.tflint.hcl
tflint --chdir=terraform/project --config=../.tflint.hcl
yamllint .github/workflows/terraform.yml
```

state、plan、実tfvars、認証情報、実行ログはGit管理しません。CIのfmt・validateが未実行なら、その状態を検査成功として扱わないでください。
