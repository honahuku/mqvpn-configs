#!/bin/bash
set -euo pipefail
test -f /.dockerenv
systemctl stop NetworkManager.service || true
mkdir -p /dev/net
test -e /dev/net/tun || mknod /dev/net/tun c 10 200
ip link set eth0 name povo
ip link add softbank link povo type macvlan mode bridge
ip link set softbank address 02:00:00:77:00:21
ip addr add 198.18.77.21/24 dev softbank
ip link set softbank up
ip route add default via 198.18.77.1 dev softbank metric 200
attach() {
    ns=$1 link=$2 addr=$3 gw=$4
    ip netns add "$ns"
    ip -n "$ns" link set lo up
    ip link add "$link" type veth peer name eth0 netns "$ns"
    ip link set "$link" up
    ip -n "$ns" link set eth0 up
    ip -n "$ns" addr add "$addr" dev eth0
    ip -n "$ns" route add default via "$gw"
}
attach dj djlan 192.168.50.100/24 192.168.50.1
ip -n dj addr add 192.168.50.10/24 dev eth0
attach router guestlan 192.168.60.2/24 192.168.60.1
ip -n router addr add 192.168.60.100/24 dev eth0
ip netns add guest
ip -n guest link set lo up
ip -n router link add lan type veth peer name eth0 netns guest
ip -n router addr add 192.168.70.1/24 dev lan
ip -n router link set lan up
ip -n guest addr add 192.168.70.100/24 dev eth0
ip -n guest link set eth0 up
ip -n guest route add default via 192.168.70.1
ip netns exec router sysctl -w net.ipv4.ip_forward=1
ip netns exec router iptables -t nat -A POSTROUTING -s 192.168.70.0/24 -o eth0 -j MASQUERADE
