#!/bin/sh
set -eu
cat /etc/os-release
ip -br link
ip -4 -br address
ip -4 route
for p in /sys/class/net/*; do
    echo "### ${p##*/}"
    udevadm info --query=property --path="$p" | sed -n '/^ID_PATH=/p;/^ID_NET_DRIVER=/p;/^ID_SERIAL=/p'
    ethtool -P "${p##*/}" 2>/dev/null || true
done
printf '\nRecord each WAN gateway/management subnet and check subnet overlap.\n'
