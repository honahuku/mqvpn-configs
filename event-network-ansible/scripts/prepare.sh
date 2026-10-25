#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
version=0.18.0
mkdir -p artifacts
python3 - "$version" <<'PY'
import hashlib, json, pathlib, sys, urllib.request
version = sys.argv[1]
base = f'https://github.com/mp0rta/mqvpn/releases/download/v{version}/'
name = f'mqvpn_{version}_amd64.deb'
sums = urllib.request.urlopen(base + 'SHA256SUMS', timeout=60).read().decode()
matches = [line.split()[0] for line in sums.splitlines()
           if len(line.split()) == 2 and line.split()[1].lstrip('*./') == name]
if len(matches) != 1:
    raise SystemExit('Expected exactly one package checksum')
lock = pathlib.Path('artifacts/manifest.json')
if lock.exists():
    previous = json.loads(lock.read_text())
    if previous['version'] != version or previous['sha256'] != matches[0]:
        raise SystemExit('Release differs from existing lock; inspect before updating')
dest = pathlib.Path('artifacts') / name
if not dest.exists() or hashlib.sha256(dest.read_bytes()).hexdigest() != matches[0]:
    data = urllib.request.urlopen(base + name, timeout=120).read()
    if hashlib.sha256(data).hexdigest() != matches[0]:
        raise SystemExit('SHA256 mismatch')
    dest.write_bytes(data)
manifest = {'version': version, 'sha256': matches[0], 'url': base + name}
pathlib.Path('artifacts/manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(f'Pinned {name}: {matches[0]}')
PY
