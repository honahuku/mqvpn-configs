import ipaddress
import json
import re
import sys

c = json.load(sys.stdin)


def require(ok, message):
    if not ok:
        raise SystemExit(message)


server = ipaddress.IPv4Address(c['server'])
require(not any(server in ipaddress.ip_network(n) for n in
                ['192.0.2.0/24', '198.51.100.0/24', '203.0.113.0/24']),
        'Replace example/documentation server IPv4 address')
for n in c['blocked'] + c['admins']:
    ipaddress.IPv4Network(n, strict=False)
for a in c['dns']:
    ipaddress.IPv4Address(a)
require(c['dns'], 'At least one DNS server is required')
require(40 <= int(c['flows']) <= 4096, 'TCP flow limit must be 40..4096')
if c['gateway']:
    nets = [ipaddress.IPv4Network(n) for n in c['nets']]
    require(all(not a.overlaps(b) for i, a in enumerate(nets) for b in nets[i + 1:]),
            'Performer, guest transit, guest router LAN, and VPN networks must not overlap')
    require(all(n.prefixlen == 24 for n in nets[:3]), 'LAN DHCP implementation requires /24 LANs')
    for i, value in enumerate(c['addresses']):
        addr = ipaddress.IPv4Interface(value)
        require(addr.network == nets[i], 'LAN address/subnet mismatch')
        require(1 <= int(str(addr.ip).split('.')[-1]) <= 99, 'Reserve gateway address below DHCP pool')
    router = ipaddress.IPv4Address(c['router'])
    require(router in nets[1] and router != ipaddress.IPv4Interface(c['addresses'][1]).ip,
            'Guest router WAN address must be distinct and inside guest transit subnet')
    for entry in c['links']:
        for address in entry.get('extra_addresses', []):
            ipaddress.IPv4Interface(address)
        require(re.fullmatch(r'[A-Za-z0-9_-]{1,15}', entry['name']), 'Unsafe interface name')
        require(0 < int(entry.get('metric', 100)) < 65536, 'Invalid route metric')
print('Configuration address and overlap validation passed')
