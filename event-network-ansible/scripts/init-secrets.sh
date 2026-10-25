#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
name=${1:-vpn.event.internal}
case "$name" in ''|*[!a-zA-Z0-9.-]*) echo 'Invalid TLS DNS name' >&2; exit 1;; esac
umask 077
mkdir -p secrets
# A partial directory is an error, never silently rotate a working key or CA.
if [ -e secrets/auth-key ]; then
    openssl verify -CAfile secrets/ca.crt secrets/server.crt >/dev/null
    openssl x509 -in secrets/server.crt -checkhost "$name" -noout >/dev/null
    echo 'Existing credentials retained.'
    exit 0
fi
if [ -n "$(ls -A secrets)" ]; then echo 'Nonempty secrets directory; inspect it first.' >&2; exit 1; fi
openssl rand -base64 32 > secrets/auth-key
openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -nodes \
    -keyout secrets/ca.key -out secrets/ca.crt -days 365 \
    -subj '/CN=Event mqvpn private CA' \
    -addext 'basicConstraints=critical,CA:TRUE' -addext 'keyUsage=critical,keyCertSign,cRLSign'
openssl req -new -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -nodes \
    -keyout secrets/server.key -out secrets/server.csr -subj "/CN=$name"
cat > secrets/server.ext <<EOF
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature
extendedKeyUsage=serverAuth
subjectAltName=DNS:$name
EOF
openssl x509 -req -in secrets/server.csr -CA secrets/ca.crt -CAkey secrets/ca.key \
    -CAcreateserial -out secrets/server.crt -days 90 -extfile secrets/server.ext
openssl verify -CAfile secrets/ca.crt secrets/server.crt
echo 'Credentials created under secrets/ (private; back up separately).'
