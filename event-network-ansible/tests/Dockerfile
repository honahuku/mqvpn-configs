FROM debian:13-slim
ENV DEBIAN_FRONTEND=noninteractive container=docker
RUN apt-get update && apt-get install -y --no-install-recommends \
    ansible-core ca-certificates curl openssl systemd systemd-sysv dbus \
    iproute2 nftables iptables dnsmasq-base network-manager wpasupplicant \
    python3 python3-apt python3-venv python3-yaml sudo procps iputils-ping \
    ethtool iw tcpdump iperf3 netcat-openbsd xz-utils jq udev \
    && apt-get clean && rm -rf /var/lib/apt/lists/* \
    && systemctl mask getty.target console-getty.service systemd-logind.service
STOPSIGNAL SIGRTMIN+3
CMD ["/sbin/init"]
