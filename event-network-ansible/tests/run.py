#!/usr/bin/env python3
"""Build isolated Debian 13 hosts and exercise the actual playbooks and VPN.

No host networking or host filesystem mounts. Only this run's containers/network
are removed. --keep retains them on success; failure always retains evidence.
"""
import argparse
import io
import json
import os
import pathlib
import subprocess
import tarfile
import tempfile
import time

args = argparse.ArgumentParser()
args.add_argument('--keep', action='store_true')
options = args.parse_args()
root = pathlib.Path(__file__).resolve().parents[1]
prefix = f'evtest-{int(time.time())}'
image = 'mqvpn-event-debian13:lab'
network = prefix + '-wan'
server, gateway, internet = [prefix + '-' + n for n in ['server', 'gateway', 'internet']]
results = []
env = dict(os.environ)
config = tempfile.TemporaryDirectory(prefix='event-docker-')
pathlib.Path(config.name, 'config.json').write_text('{}\n')
# Anonymous public pulls do not depend on Windows credential-helper PATH.
env['DOCKER_CONFIG'] = config.name


def docker(*argv, data=None, timeout=240, check=True):
    result = subprocess.run(['docker', *argv], input=data, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, env=env, timeout=timeout)
    if check and result.returncode:
        raise RuntimeError(f'docker {argv[:3]} failed:\n{result.stdout.decode(errors="replace")[-10000:]}')
    return result


def shell(host, command, **kwargs):
    return docker('exec', host, 'bash', '-euo', 'pipefail', '-c', command, **kwargs)


def note(name, detail='passed'):
    print(f'PASS {name}: {detail}', flush=True)
    results.append({'test': name, 'detail': detail})


def wait_tunnel():
    for _ in range(40):
        r = shell(gateway, "ip -4 -o addr show dev mqvpn0 | grep -q ' inet '", check=False)
        if r.returncode == 0:
            time.sleep(3)  # policy/qos reconcile timers
            return
        time.sleep(1)
    raise RuntimeError(shell(gateway, 'journalctl -u event-vpn -n 40 --no-pager').stdout.decode())


def curl(namespace='dj', success=True):
    r = shell(gateway, f'ip netns exec {namespace} curl -fsS --max-time 10 http://198.18.77.30:8080/', check=False)
    assert (r.returncode == 0) == success, r.stdout.decode()
    return r


def play(host, file, inventory, extra='', zero=False):
    r = shell(host, f'cd /bundle; ansible-playbook -i {inventory} {file} {extra}', timeout=360)
    text = r.stdout.decode()
    if zero:
        recap = text.split('PLAY RECAP')[-1]
        assert 'changed=0 ' in recap, recap
    return text


def bundle():
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w') as tar:
        for directory in ['roles', 'scripts', 'tests']:
            for file in (root / directory).rglob('*'):
                if file.is_file() and 'results' not in file.parts and '__pycache__' not in file.parts:
                    tar.add(file, arcname=str(file.relative_to(root)))
        for file in list(root.glob('*.yml')) + list(root.glob('*.cfg')):
            tar.add(file, arcname=file.name)
        for file in ['manifest.json', 'mqvpn_0.18.0_amd64.deb']:
            tar.add(root / 'artifacts' / file, arcname='artifacts/' + file)
    return stream.getvalue()


ok = False
try:
    print(f'Lab prefix: {prefix}', flush=True)
    docker('build', '-t', image, str(root / 'tests'), timeout=600)
    docker('network', 'create', '--subnet', '198.18.77.0/24', network)
    for name, ip in [(server, '198.18.77.10'), (gateway, '198.18.77.20')]:
        docker('run', '-d', '--name', name, '--network', network, '--ip', ip,
               '--privileged', '--cgroupns=private', '--tmpfs', '/run', '--tmpfs', '/run/lock', image)
        shell(name, 'mkdir -p /bundle /dev/net; test -e /dev/net/tun || mknod /dev/net/tun c 10 200')
    data = bundle()
    for host in [server, gateway]:
        docker('exec', '-i', host, 'tar', '-xf', '-', '-C', '/bundle', data=data)
    shell(server, 'cd /bundle; chmod +x scripts/*.sh; scripts/init-secrets.sh')
    secret_tar = docker('exec', server, 'tar', '-cf', '-', '-C', '/bundle', 'secrets').stdout
    docker('exec', '-i', gateway, 'tar', '-xf', '-', '-C', '/bundle', data=secret_tar)
    shell(gateway, 'bash /bundle/tests/namespace-setup.sh')
    make_inventory = r'''
import json, subprocess, yaml
mac={x['ifname']:x['address'] for x in json.loads(subprocess.check_output(['ip','-j','link']))}
base={'ansible_connection':'local','ansible_user':'root','event_server_ip':'198.18.77.10',
      'event_dns':['198.18.77.30'],'event_server_admin_cidrs':['198.18.77.0/24']}
entries=[]
for n,role,address,metric in [('djlan','performer',None,0),('guestlan','guest',None,0),
                              ('povo','mobile','198.18.77.20/24',100),('softbank','mobile','198.18.77.21/24',200)]:
    e={'name':n,'role':role,'mac':mac[n]}
    if address:e.update(address=address,gateway='198.18.77.1',metric=metric)
    entries.append(e)
inventory={'all':{'vars':base,'children':{
 'gateways':{'hosts':{'g3':{'event_links':entries}}},
 'vpn_servers':{'hosts':{'exit':{'event_server_wan':'eth0'}}}}}}
open('/bundle/tests/lab.yml','w').write(yaml.safe_dump(inventory))
'''
    docker('exec', '-i', gateway, 'python3', '-', data=make_inventory.encode())
    inventory = docker('exec', gateway, 'cat', '/bundle/tests/lab.yml').stdout
    docker('exec', '-i', server, 'tee', '/bundle/tests/lab.yml', data=inventory)
    play(server, 'server.yml', 'tests/lab.yml')
    play(gateway, 'gateway.yml', 'tests/lab.yml')
    note('Debian 13 real server/gateway playbook apply')
    play(server, 'server.yml', 'tests/lab.yml', zero=True)
    play(gateway, 'gateway.yml', 'tests/lab.yml', zero=True)
    note('second apply is idempotent on both hosts', 'changed=0')
    # Activation without a machine reboot: kernel/USB boot lifecycle is a hardware test.
    shell(gateway, '/usr/local/lib/event-network/activate; sysctl -p /etc/sysctl.d/80-event-network.conf; '
          'systemctl stop systemd-networkd-wait-online.service || true; '
          'systemctl start event-firewall systemd-networkd event-policy.timer event-qos.timer event-dns event-vpn')
    wait_tunnel()
    shell(gateway, '/usr/local/lib/event-network/rollback commit')
    docker('run', '-d', '--name', internet, '--network', network, '--ip', '198.18.77.30',
           '--privileged', image, 'sleep', 'infinity')
    docker('exec', '-i', internet, 'tee', '/internet.py', data=(root / 'tests/internet.py').read_bytes())
    docker('exec', '-d', internet, 'python3', '/internet.py')
    time.sleep(1)
    curl('dj')
    curl('guest')
    note('performer LAN and NAT-router guest LAN traverse real TLS-verified VPN')
    paths = shell(server, "printf '%s\n' '{\"cmd\":\"get_status\"}' | nc -w 2 127.0.0.1 9090").stdout.decode()
    assert paths.count('path_id') >= 2, paths
    note('two active transport paths', 'server get_status reports two path IDs')
    for direction in ['down', 'up']:
        r = shell(gateway, f'ip netns exec guest python3 /bundle/tests/client-probe.py rate {direction}', timeout=60)
        note(f'guest {direction} shaping', r.stdout.decode().strip())
    # Measure the guest egress limiter independently of VPN congestion control.
    shell(gateway, 'ip netns exec router iperf3 -s -D -p 5201')
    r = shell(gateway, 'iperf3 -c 192.168.60.2 -p 5201 -u -b 30M -l 1200 -t 6 -J', timeout=30)
    bps = json.loads(r.stdout)['end']['sum_received']['bits_per_second']
    assert 5_000_000 < bps < 9_500_000, bps
    note('8Mbps guest egress cap under offered 30Mbps UDP load', f'{bps / 1e6:.3f} Mbps received')
    # Normal users cannot enter any management service on the gateway or upstream.
    for namespace in ['dj', 'guest', 'router']:
        target = '192.168.50.1' if namespace == 'dj' else '192.168.60.1'
        for port in [22, 9090]:
            r = shell(gateway, f'ip netns exec {namespace} nc -z -w 1 {target} {port}', check=False)
            assert r.returncode != 0, f'{namespace} can reach management port {port}'
    note('management services blocked from performer and guest clients')
    # The upstream management IP is reachable from the trusted gateway itself.
    shell(internet, 'ip addr add 192.168.128.1/32 dev eth0')
    shell(gateway, 'ip route add 192.168.128.1/32 dev povo')
    shell(gateway, 'curl -fsS --max-time 3 http://192.168.128.1:8080/')
    shell(gateway, 'curl -kfsS --max-time 3 https://192.168.128.1/')
    for namespace in ['dj', 'guest']:
        r = shell(gateway, f'ip netns exec {namespace} curl -fsS --max-time 2 http://192.168.128.1:8080/', check=False)
        assert r.returncode != 0
        r = shell(gateway, f'ip netns exec {namespace} curl -kfsS --max-time 2 https://192.168.128.1/', check=False)
        assert r.returncode != 0
    note('upstream management IP blocked for clients, reachable by gateway admin')
    shell(internet, 'sysctl -w net.ipv6.conf.eth0.disable_ipv6=0; ip -6 addr add fd77::30/64 dev eth0')
    shell(gateway, 'sysctl -w net.ipv6.conf.povo.disable_ipv6=0; ip -6 addr add fd77::20/64 dev povo; '
          'ip -6 addr add fd50::1/64 dev djlan; ip -n dj -6 addr add fd50::100/64 dev eth0; '
          'ip -n dj -6 route add default via fd50::1')
    time.sleep(2)
    shell(gateway, "curl --noproxy '*' -kfsS --max-time 3 https://[fd77::30]:8443/")
    r = shell(gateway, "ip netns exec dj curl --noproxy '*' -kfsS --max-time 2 https://[fd77::30]:8443/", check=False)
    assert r.returncode != 0
    note('IPv6 upstream management reachable by gateway, blocked from LAN')
    r = shell(gateway, 'ip netns exec dj python3 /bundle/tests/client-probe.py dns test.event 192.168.50.1')
    assert '198.18.77.30' in r.stdout.decode()
    note('LAN DNS resolution through VPN')
    # Loss of one outer path must not require a new VPN configuration.
    shell(gateway, "nft add table inet fault_inject; nft 'add chain inet fault_inject out { type filter hook output priority -20; policy accept; }'; "
          "nft 'add rule inet fault_inject out oifname povo udp dport 443 drop'")
    time.sleep(4)
    curl('dj')
    shell(gateway, 'nft delete table inet fault_inject')
    note('primary transport failure continues over second path')
    shell(gateway, 'systemctl stop event-vpn; /usr/local/lib/event-network/policy')
    curl('dj', success=False)
    curl('guest', success=False)
    for namespace in ['dj', 'guest']:
        r = shell(gateway, f'ip netns exec {namespace} curl -kfsS --max-time 2 https://192.168.128.1/', check=False)
        assert r.returncode != 0
    r = shell(gateway, 'ip netns exec dj python3 /bundle/tests/client-probe.py dns uncached.outage.event 192.168.50.1', check=False)
    assert r.returncode != 0
    note('VPN stopped: no cellular bypass for either LAN or uncached DNS')
    shell(gateway, 'systemctl start event-vpn')
    wait_tunnel()
    curl('dj')
    shell(gateway, 'tc class show dev mqvpn0 | grep -q "htb 1:20"')
    note('tunnel recreation recovers routes and QoS automatically')
    # Explicit AP mode enables the larger participant DHCP pool.
    play(gateway, 'gateway.yml', 'tests/lab.yml', '-e event_guest_mode=ap')
    shell(gateway, 'systemctl restart event-dns')
    dhcp = shell(gateway, 'ip netns exec router python3 /bundle/tests/dhcp-probe.py eth0').stdout.decode()
    lease = json.loads(dhcp)
    assert lease['address'].startswith('192.168.60.') and lease['router'] == '192.168.60.1', dhcp
    note('AP mode DHCP offer and ACK', dhcp.strip())
    shell(gateway, 'for n in $(seq 101 139); do ip -n router addr add 192.168.60.$n/24 dev eth0; done')
    r = shell(gateway, 'ip netns exec router python3 /bundle/tests/client-probe.py forty', timeout=60)
    assert len(json.loads(r.stdout)) == 40
    note('40 source IPv4 clients with concurrent HTTP connections')
    # A bad trust store must not silently disable certificate verification.
    shell(gateway, 'cp /etc/mqvpn/ca.crt /tmp/good-ca.crt; '
          'openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -nodes '
          '-keyout /tmp/wrong-ca.key -out /etc/mqvpn/ca.crt -days 1 -subj /CN=WrongCA >/dev/null 2>&1; '
          'systemctl restart event-vpn')
    time.sleep(5)
    r = shell(gateway, "ip -4 -o addr show dev mqvpn0 | grep -q ' inet '", check=False)
    assert r.returncode != 0
    shell(gateway, 'cp /tmp/good-ca.crt /etc/mqvpn/ca.crt; systemctl restart event-vpn')
    wait_tunnel()
    curl('dj')
    note('wrong CA rejected; restoring CA recovers VPN')
    # Exercise actual SSH transport from a separate LAN network namespace.
    shell(gateway, 'mkdir -p /root/.ssh; ssh-keygen -q -t ed25519 -N "" -f /tmp/lab-key; '
          'cat /tmp/lab-key.pub >> /root/.ssh/authorized_keys; chmod 700 /root/.ssh; '
          'chmod 600 /root/.ssh/authorized_keys; systemctl start ssh')
    ssh_inventory = inventory.decode().replace('ansible_connection: local', 'ansible_connection: ssh')
    ssh_inventory += ''
    transform = r'''
import yaml
p='/bundle/tests/lab.yml'
r=yaml.safe_load(open(p))
r['all']['vars'].update(ansible_connection='ssh', ansible_ssh_private_key_file='/tmp/lab-key',
    ansible_ssh_common_args='-b 192.168.50.10 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null')
r['all']['children']['gateways']['hosts']['g3'].update(ansible_host='192.168.50.1',event_guest_mode='ap')
open('/bundle/tests/ssh.yml','w').write(yaml.safe_dump(r))
'''
    docker('exec', '-i', gateway, 'python3', '-', data=transform.encode())
    r = shell(gateway, 'cd /bundle; ip netns exec dj ansible-playbook -i tests/ssh.yml gateway.yml', timeout=360)
    assert 'changed=0 ' in r.stdout.decode().split('PLAY RECAP')[-1], r.stdout.decode()[-5000:]
    note('SSH apply from an isolated LAN controller namespace preserves access and is idempotent')
    public_key = docker('exec', gateway, 'cat', '/tmp/lab-key.pub').stdout
    shell(server, 'mkdir -p /root/.ssh; chmod 700 /root/.ssh; systemctl start ssh')
    docker('exec', '-i', server, 'tee', '/root/.ssh/authorized_keys', data=public_key)
    shell(server, 'chmod 600 /root/.ssh/authorized_keys')
    server_ssh = r'''
import yaml
r=yaml.safe_load(open('/bundle/tests/ssh.yml'))
r['all']['vars']['ansible_ssh_common_args']='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'
r['all']['children']['vpn_servers']['hosts']['exit']['ansible_host']='198.18.77.10'
open('/bundle/tests/ssh-server.yml','w').write(yaml.safe_dump(r))
'''
    docker('exec', '-i', gateway, 'python3', '-', data=server_ssh.encode())
    play(gateway, 'server.yml', 'tests/ssh-server.yml', zero=True)
    note('server playbook over SSH is idempotent')
    # Negative configuration tests run before network mutation.
    r = shell(gateway, "cd /bundle; ansible-playbook -i tests/lab.yml gateway.yml -e event_guest_net=192.168.50.0/24", check=False)
    assert r.returncode != 0 and b'overlap' in r.stdout
    note('overlapping subnet configuration rejected')
    r = shell(gateway, 'cd /bundle; ansible-playbook -i tests/lab.yml gateway.yml '
              "-e '{\"event_artifact\":{\"version\":\"0.18.0\",\"sha256\":\"" + '0' * 64 + "\"}}'", check=False)
    assert r.returncode != 0 and b'Reject altered package' in r.stdout
    note('incorrect pinned package checksum rejected')
    # Bootstrap management DHCP must not introduce a second DHCP server on a home LAN.
    transform = r'''
import yaml
r=yaml.safe_load(open('/bundle/tests/lab.yml'))
for entry in r['all']['children']['gateways']['hosts']['g3']['event_links']:
    if entry['role']=='performer':entry['keep_dhcp']=True
open('/bundle/tests/bootstrap-lan.yml','w').write(yaml.safe_dump(r))
'''
    docker('exec', '-i', gateway, 'python3', '-', data=transform.encode())
    play(gateway, 'gateway.yml', 'tests/bootstrap-lan.yml')
    shell(gateway, "! grep -q 'dhcp-range=set:dj' /etc/event-network/dnsmasq.conf")
    note('keep_dhcp management mode does not serve DHCP on existing performer/home LAN')
    # Real restore path: reboot ends a systemd container; Docker restarts it below.
    shell(gateway, 'touch /var/lib/event-network/activation-pending; systemctl start --no-block event-rollback.service')
    for _ in range(45):
        status = docker('inspect', '-f', '{{.State.Status}}', gateway).stdout.decode().strip()
        if status == 'exited':
            break
        time.sleep(1)
    assert status == 'exited', 'rollback did not reboot the container'
    docker('start', gateway)
    shell(gateway, 'test ! -f /var/lib/event-network/activation-pending; '
          'test ! -f /etc/systemd/network/10-event-povo.network; '
          'test "$(systemctl is-enabled NetworkManager.service)" = enabled; '
          '! systemctl is-enabled --quiet event-vpn.service')
    note('unconfirmed activation restores original network files/services and reboots')
    ok = True
finally:
    out = root / 'tests/results'
    out.mkdir(exist_ok=True)
    (out / 'latest.json').write_text(json.dumps({'prefix': prefix, 'passed': ok, 'checks': results}, indent=2) + '\n')
    if ok and not options.keep:
        for host in [gateway, server, internet]:
            docker('rm', '-f', host, check=False)
        docker('network', 'rm', network, check=False)
    else:
        print(f'Containers retained for inspection: {prefix}', flush=True)
    config.cleanup()
