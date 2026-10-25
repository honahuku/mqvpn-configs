#!/usr/bin/env python3
"""Cold SSH provisioning and Ansible-driven reboot/reconnect from a third host."""
import io
import json
import os
import pathlib
import subprocess
import tarfile
import tempfile
import time

root = pathlib.Path(__file__).resolve().parents[1]
prefix = 'evssh-' + str(int(time.time()))
image = 'mqvpn-event-debian13:lab'
server, gateway, control = [prefix + '-' + n for n in ['server', 'gateway', 'control']]
wan, lan = prefix + '-wan', prefix + '-lan'
env = dict(os.environ)
config = tempfile.TemporaryDirectory(prefix='event-ssh-docker-')
pathlib.Path(config.name, 'config.json').write_text('{}')
env['DOCKER_CONFIG'] = config.name
passed = False
report = {'prefix': prefix, 'passed': False}


def d(*args, data=None, check=True, timeout=360):
    r = subprocess.run(['docker', *args], input=data, capture_output=True, env=env, timeout=timeout)
    if check and r.returncode:
        raise RuntimeError(r.stderr.decode(errors='replace')[-2000:] + r.stdout.decode(errors='replace')[-10000:])
    return r.stdout


def sh(host, text, **kwargs):
    return d('exec', host, 'bash', '-euo', 'pipefail', '-c', text, **kwargs)


try:
    print(prefix, flush=True)
    d('network', 'create', '--subnet', '198.18.80.0/24', wan)
    d('network', 'create', '--subnet', '198.18.81.0/24', '--gateway', '198.18.81.254', lan)
    for host, ip in [(server, '198.18.80.10'), (gateway, '198.18.80.20')]:
        d('run', '-d', '--name', host, '--restart', 'always', '--network', wan, '--ip', ip,
          '--privileged', '--cgroupns=private', '--tmpfs', '/run', '--tmpfs', '/run/lock', image)
    d('network', 'connect', '--ip', '198.18.81.1', lan, gateway)
    d('run', '-d', '--name', control, '--network', wan, '--ip', '198.18.80.40', image, 'sleep', 'infinity')
    d('network', 'connect', '--ip', '198.18.81.10', lan, control)
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w') as tar:
        for directory in ['roles', 'scripts']:
            for f in (root / directory).rglob('*'):
                if f.is_file():
                    tar.add(f, arcname=str(f.relative_to(root)))
        for f in list(root.glob('*.yml')) + list(root.glob('*.cfg')):
            tar.add(f, arcname=f.name)
        for name in ['manifest.json', 'mqvpn_0.18.0_amd64.deb']:
            tar.add(root / 'artifacts' / name, arcname='artifacts/' + name)
    sh(control, 'mkdir -p /bundle; ssh-keygen -q -t ed25519 -N "" -f /tmp/controller-key')
    d('exec', '-i', control, 'tar', '-xf', '-', '-C', '/bundle', data=stream.getvalue())
    sh(control, 'cd /bundle; chmod +x scripts/*.sh; scripts/init-secrets.sh')
    public = d('exec', control, 'cat', '/tmp/controller-key.pub')
    for host in [server, gateway]:
        # This is the fixture's equivalent of the user enabling SSH first.
        sh(host, 'apt-get update -qq; DEBIAN_FRONTEND=noninteractive apt-get install -y -qq openssh-server >/dev/null; '
           'mkdir -p /root/.ssh /dev/net; chmod 700 /root/.ssh; '
           'test -e /dev/net/tun || mknod /dev/net/tun c 10 200')
        d('exec', '-i', host, 'tee', '/root/.ssh/authorized_keys', data=public)
        sh(host, 'chmod 600 /root/.ssh/authorized_keys; systemctl start ssh')
    devices = json.loads(sh(gateway, 'ip -j link'))
    mac = {x['ifname']: x['address'] for x in devices}
    # Recreate the lab's virtual hardware every boot. Real G3 devices persist in hardware.
    fixture = f'''#!/bin/bash
set -euo pipefail
for path in /sys/class/net/*; do
 n=${{path##*/}}
 if ip -4 -o addr show dev "$n" | grep -q 'inet 198.18.80.20/'; then
  ip link set "$n" down
  ip link set "$n" address {mac['eth0']}
  if [ "$n" != povo ]; then ip link set "$n" name povo; fi
  ip link set povo up
 elif ip -4 -o addr show dev "$n" | grep -q 'inet 198.18.81.1/'; then
  ip link set "$n" down
  ip link set "$n" address {mac['eth1']}
  if [ "$n" != djlan ]; then ip link set "$n" name djlan; fi
  ip link set djlan up
 fi
done
ip route replace default via 198.18.80.1 dev povo metric 999
if ! ip link show softbank >/dev/null 2>&1; then
 ip link add softbank link povo type macvlan mode bridge
 ip link set softbank address 02:00:00:80:00:21
 ip link set softbank up
fi
if ! ip link show guestlan >/dev/null 2>&1; then
 ip link add guestlan type dummy
 ip link set guestlan address 02:00:00:81:00:60
 ip link set guestlan up
fi
'''
    d('exec', '-i', gateway, 'tee', '/usr/local/sbin/lab-nics', data=fixture.encode())
    unit = b'''[Unit]
Description=Recreate virtual lab NICs after container restart
DefaultDependencies=no
After=systemd-udevd.service
Before=network-pre.target systemd-networkd.service event-firewall.service
[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/sbin/lab-nics
[Install]
WantedBy=sysinit.target
'''
    d('exec', '-i', gateway, 'tee', '/etc/systemd/system/lab-nics.service', data=unit)
    sh(gateway, 'chmod +x /usr/local/sbin/lab-nics; systemctl daemon-reload; systemctl enable --now lab-nics')
    inventory = {'all': {'vars': {
        'ansible_connection': 'ssh', 'ansible_user': 'root',
        'ansible_ssh_private_key_file': '/tmp/controller-key',
        'ansible_ssh_common_args': '-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null',
        'event_server_ip': '198.18.80.10', 'event_server_admin_cidrs': ['198.18.80.40/32'],
        'event_performer_cidr': '198.18.81.1/24', 'event_performer_net': '198.18.81.0/24',
        'event_gateway_admin_cidrs': ['198.18.81.10/32'],
        # Container restart does not change the host kernel boot ID.
        'event_boot_time_command': "awk '{print $22}' /proc/1/stat",
    }, 'children': {
        'vpn_servers': {'hosts': {'exit': {'ansible_host': '198.18.80.10', 'event_server_wan': 'eth0'}}},
        'gateways': {'hosts': {'g3': {'ansible_host': '198.18.81.1', 'event_links': [
            {'name': 'povo', 'role': 'mobile', 'mac': mac['eth0'], 'address': '198.18.80.20/24', 'gateway': '198.18.80.1', 'metric': 100},
            {'name': 'softbank', 'role': 'mobile', 'mac': '02:00:00:80:00:21', 'address': '198.18.80.21/24', 'gateway': '198.18.80.1', 'metric': 200},
            {'name': 'djlan', 'role': 'performer', 'mac': mac['eth1']},
            {'name': 'guestlan', 'role': 'guest', 'mac': '02:00:00:81:00:60'},
        ]}}},
    }}}
    d('exec', '-i', control, 'tee', '/bundle/inventory.json', data=json.dumps(inventory).encode())
    log = sh(control, 'cd /bundle; ansible-playbook -i inventory.json site.yml')
    print('PASS cold provisioning of both targets over SSH', flush=True)
    activation = sh(control, 'cd /bundle; ansible-playbook -i inventory.json activate-gateway.yml')
    print(activation.decode()[-3500:], flush=True)
    sh(gateway, 'test ! -f /var/lib/event-network/activation-pending; '
       'systemctl is-active event-vpn event-firewall event-dns; '
       'test "$(systemctl is-enabled event-rollback.timer)" = disabled')
    print('PASS remote reboot, SSH reconnect, VPN checks, and activation commit', flush=True)
    passed = True
    report['passed'] = True
    report['activation_recap'] = activation.decode().split('PLAY RECAP')[-1].strip()
finally:
    out = root / 'tests/results'
    out.mkdir(exist_ok=True)
    (out / 'ssh-activation.json').write_text(json.dumps(report, indent=2) + '\n')
    if passed:
        for host in [gateway, server, control]:
            d('rm', '-f', host, check=False)
        for name in [lan, wan]:
            d('network', 'rm', name, check=False)
    else:
        print('Retained for debugging: ' + prefix, flush=True)
    config.cleanup()
