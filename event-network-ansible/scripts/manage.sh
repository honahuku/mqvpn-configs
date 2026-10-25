#!/bin/sh
set -eu
export PATH="$HOME/.local/bin:$PATH"
cd "$(dirname "$0")/.."
inventory=${EVENT_INVENTORY:-inventory/hosts.yml}
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
export ANSIBLE_LOCAL_TEMP="${ANSIBLE_LOCAL_TEMP:-$tmp/local}"
export ANSIBLE_HOME="${ANSIBLE_HOME:-$tmp/ansible}"
action=${1:-}
[ "$#" -gt 0 ] && shift
case "$action" in
    bootstrap) playbook=bootstrap.yml ;;
    connect) playbook=connect.yml ;;
    server) playbook=server.yml ;;
    gateway) playbook=gateway.yml ;;
    activate) playbook=activate-gateway.yml ;;
    *) echo 'Usage: scripts/manage.sh bootstrap|connect|server|gateway|activate [ansible options]' >&2; exit 2 ;;
esac
ansible-playbook -i "$inventory" "$playbook" "$@"
