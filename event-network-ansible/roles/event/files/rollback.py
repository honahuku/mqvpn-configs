#!/usr/bin/python3
"""Restore the pre-deployment network if SSH activation is not committed."""
import json
import pathlib
import shutil
import subprocess
import sys

base = pathlib.Path('/var/lib/event-network/rollback')
pending = pathlib.Path('/var/lib/event-network/activation-pending')
services = ['NetworkManager.service', 'networking.service', 'dnsmasq.service',
            'systemd-networkd.service', 'event-vpn.service', 'event-dns.service',
            'event-policy.timer', 'event-qos.timer', 'event-firewall.service']
paths = ['/etc/systemd/network', '/etc/network/interfaces', '/etc/network/interfaces.d']


def run(*args, **kwargs):
    return subprocess.run(args, text=True, capture_output=True, **kwargs)


if sys.argv[1] == 'snapshot':
    if (base / 'state.json').exists():
        sys.exit(0)
    base.mkdir(parents=True, mode=0o700, exist_ok=True)
    state = {'services': {}, 'paths': {}}
    for service in services:
        state['services'][service] = run('systemctl', 'is-enabled', service).stdout.strip()
    for name in paths:
        source = pathlib.Path(name)
        state['paths'][name] = source.exists()
        if source.exists():
            target = base / name.lstrip('/')
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.is_dir():
                shutil.copytree(source, target, symlinks=True)
            else:
                shutil.copy2(source, target, follow_symlinks=False)
    firewall = run('nft', 'list', 'table', 'inet', 'event_network')
    (base / 'firewall.nft').write_text(firewall.stdout if firewall.returncode == 0 else '')
    (base / 'state.json').write_text(json.dumps(state, indent=2))
elif sys.argv[1] == 'commit':
    pending.unlink(missing_ok=True)
    run('systemctl', 'disable', '--now', 'event-rollback.timer', check=True)
elif sys.argv[1] == 'restore':
    if not pending.exists():
        sys.exit(0)
    state = json.loads((base / 'state.json').read_text())
    for service in services:
        if service.startswith('event-'):
            run('systemctl', 'stop', service)
    run('nft', 'delete', 'table', 'inet', 'event_network')
    if (base / 'firewall.nft').read_text():
        run('nft', '-f', str(base / 'firewall.nft'), check=True)
    for name, existed in state['paths'].items():
        target = pathlib.Path(name)
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink(missing_ok=True)
        if existed:
            source = base / name.lstrip('/')
            if source.is_dir():
                shutil.copytree(source, target, symlinks=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target, follow_symlinks=False)
    for service, enabled in state['services'].items():
        run('systemctl', 'unmask', service)
        if enabled in ['enabled', 'enabled-runtime']:
            run('systemctl', 'enable', service)
        elif enabled == 'masked':
            run('systemctl', 'mask', service)
        else:
            run('systemctl', 'disable', service)
    pathlib.Path('/etc/sysctl.d/80-event-network.conf').unlink(missing_ok=True)
    pending.unlink()
    run('systemctl', 'disable', 'event-rollback.timer')
    run('systemctl', 'daemon-reload')
    # A reboot also restores pre-deployment link names and clears policy routes/tc.
    run('systemctl', 'reboot', check=True)
else:
    raise SystemExit('snapshot|commit|restore')
