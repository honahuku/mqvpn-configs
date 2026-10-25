#!/bin/sh
set -eu
export PATH="$HOME/.local/bin:$PATH"
cd "$(dirname "$0")/.."
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
export ANSIBLE_LOCAL_TEMP="$tmp/local"
export ANSIBLE_HOME="$tmp/ansible"
export XDG_CACHE_HOME="$tmp/cache"
yamllint -c .yamllint .
ansible-lint --offline
for play in bootstrap connect server gateway activate-gateway site; do
    ansible-playbook -i inventory/hosts.example.yml "$play.yml" --syntax-check
done
python3 - <<'PY'
import ast
from pathlib import Path
import subprocess
for file in Path('.').rglob('*.py'):
    ast.parse(file.read_text(), filename=str(file))
for file in Path('scripts').glob('*.sh'):
    subprocess.run(['sh', '-n', str(file)], check=True)
subprocess.run(['bash', '-n', 'tests/namespace-setup.sh'], check=True)
print('Python and shell syntax passed')
PY
