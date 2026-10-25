# GCPのTerraform初回構築手順

対象は `mqvpn-servers`（プロジェクト番号 `601341793638`）です。構成・権限・state保存先の説明は [Terraform設定のREADME](../terraform/README.md) を参照してください。

この手順は本人が実行します。各コマンドが成功したことを確認してから次へ進み、失敗した場合はその時点で止めてください。初回はbootstrapの適用、bootstrapのstate移行、projectの適用の順です。

## 前提と認証

Terraform設定を含むworktreeで、同じBash端末を使います。Terraformは `1.17.0` 以上、`2.0.0` 未満が必要です。ログ記録にはutil-linuxの `script` を使います。

Google Cloud CLIが未導入なら、[公式手順](https://cloud.google.com/sdk/docs/install)に沿って導入します。ADCが未設定の場合は、次を実行してください。

```bash
gcloud auth login
gcloud projects describe mqvpn-servers --format='yaml(projectId,projectNumber,lifecycleState)'
gcloud auth application-default login
gcloud auth application-default set-quota-project mqvpn-servers
```

表示されたプロジェクト番号が `601341793638` であることを確認します。CLIのログインとADCは別の認証設定です。認証情報やトークンをリポジトリへ保存する必要はありません。[Terraformの認証](https://cloud.google.com/docs/terraform/authentication)

## ログ保存先の準備

設定を含むworktree内から実行します。新しい試行ごとに保存先を作り、以前のplan・ログを上書きしません。

```bash
cd "$(git rev-parse --show-toplevel)/terraform"
umask 077
mkdir -p logs
export MQVPN_TF_RUN_DIR="$(mktemp -d "$PWD/logs/run.XXXXXXXX")"
printf 'ログ保存先: %s\n' "$MQVPN_TF_RUN_DIR"

git rev-parse HEAD > "$MQVPN_TF_RUN_DIR/source-commit.txt"
git status --short > "$MQVPN_TF_RUN_DIR/source-status.txt"
script -qefc 'terraform version' "$MQVPN_TF_RUN_DIR/version.log"
```

以降も、この端末での実行が前提です。`script -e` は子コマンドの終了状態を返し、ログ末尾にも終了コードを残します。標準出力と標準エラーは画面にも表示され、同じログへ保存されます。

`logs/` はGit管理対象外です。planやログには機密情報が含まれる可能性があるため、公開リポジトリへ追加しないでください。

## bootstrapのinit・検証・plan

バケットがまだ存在しない初回は、ローカルstateで構築します。すでに構築済みの場合は、後述の「構築済み環境を別の作業コピーで使う場合」を先に確認してください。

```bash
cd bootstrap
pwd > "$MQVPN_TF_RUN_DIR/bootstrap.cwd.txt"

script -qefc 'terraform init -input=false -no-color' "$MQVPN_TF_RUN_DIR/bootstrap-init.log"
script -qefc 'terraform fmt -check' "$MQVPN_TF_RUN_DIR/bootstrap-fmt.log"
script -qefc 'terraform validate -no-color' "$MQVPN_TF_RUN_DIR/bootstrap-validate.log"
script -qefc 'terraform plan -no-color -out="$MQVPN_TF_RUN_DIR/bootstrap.tfplan"' "$MQVPN_TF_RUN_DIR/bootstrap-plan.log"
```

planの管理対象が `google_project_service.storage` と `google_storage_bucket.terraform_state` であることを確認します。バケット名は `mqvpn-servers-tfstate-601341793638`、ロケーションは `ASIA-NORTHEAST1` です。意図しない削除・置換や別プロジェクトへの変更があれば、適用せず確認します。

## bootstrapのapply

planを確認した後、このブロックだけを実行します。保存済みplanを渡すapplyは、追加の承認プロンプトなしで適用します。[保存済みplanの適用](https://developer.hashicorp.com/terraform/cli/commands/apply)

```bash
script -qefc 'terraform apply -no-color "$MQVPN_TF_RUN_DIR/bootstrap.tfplan"' "$MQVPN_TF_RUN_DIR/bootstrap-apply.log"
```

## bootstrapのstateをGCSへ移行

バケット作成の成功と、出力されたバケット名が `backend.hcl` と一致することを確認してから進みます。初回は `backend.tf.example` を `backend.tf` として配置します。すでに `backend.tf` がある場合は上書きせず、内容と移行状況を確認してください。

```bash
cp -n backend.tf.example backend.tf
script -qefc 'terraform init -migrate-state -backend-config=backend.hcl -no-color' "$MQVPN_TF_RUN_DIR/bootstrap-migrate.log"
script -qefc 'terraform state list' "$MQVPN_TF_RUN_DIR/bootstrap-state-list.log"
```

stateコピーの確認では、移行元・移行先を読んでから `yes` と答えます。移行先のprefixは `mqvpn-servers/bootstrap` です。移行後のstate一覧に、bootstrapで管理するAPIとバケットが表示されることを確認します。元のローカルstateとバックアップは保持してください。[state移行の指定](https://developer.hashicorp.com/terraform/cli/commands/init)

## projectのinit・検証・plan

bootstrapのstate移行まで完了したら進みます。

```bash
cd ../project
pwd > "$MQVPN_TF_RUN_DIR/project.cwd.txt"

script -qefc 'terraform init -backend-config=backend.hcl -input=false -no-color' "$MQVPN_TF_RUN_DIR/project-init.log"
script -qefc 'terraform fmt -check' "$MQVPN_TF_RUN_DIR/project-fmt.log"
script -qefc 'terraform validate -no-color' "$MQVPN_TF_RUN_DIR/project-validate.log"
script -qefc 'terraform plan -no-color -out="$MQVPN_TF_RUN_DIR/project.tfplan"' "$MQVPN_TF_RUN_DIR/project-plan.log"
```

stateのprefixは `mqvpn-servers/project` です。この段階のplan対象は、Compute Engine APIとIAM APIの設定です。対象が期待どおりであることを確認します。

## projectのapply

確認した保存済みplanを適用します。

```bash
script -qefc 'terraform apply -no-color "$MQVPN_TF_RUN_DIR/project.tfplan"' "$MQVPN_TF_RUN_DIR/project-apply.log"
```

各設定の `.terraform.lock.hcl` はGit管理します。state・実tfvars・plan・ログ・認証情報は追加しません。

## 失敗・再試行時

失敗したコマンドのログと終了コードを確認し、それより後の処理は実行しません。再試行には新しいログ保存先を作ります。applyが途中まで進んだ場合は、元のplanをそのまま再実行せず、現在のstateからplanを作り直してください。過去のplanとログは保持します。

実行後にログ保存先と、どの段階まで進んだかを伝えれば、Coding Agentsがログを読み、設定修正や次の手順の確認を行えます。認証情報の貼り付けは不要です。

## 構築済み環境を別の作業コピーで使う場合

既存のGCS stateを使います。bootstrapの新規構築を繰り返さないでください。

`bootstrap/` で `backend.tf.example` を `backend.tf` として配置し、通常の `terraform init -backend-config=backend.hcl` で既存stateへ接続します。これは新しい作業コピーでの接続であり、初回のローカルstate移行用の `-migrate-state` は付けません。ローカルstateがすでにある場合は、上書きや移行を始めず、その由来を確認します。

project側も、既存の `project/backend.hcl` を使って初期化します。planに既存リソースの予期しない新規作成・削除・置換が現れた場合は、適用前にbackendのバケットとprefixを確認してください。
