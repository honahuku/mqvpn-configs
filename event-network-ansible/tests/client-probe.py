#!/usr/bin/python3
import concurrent.futures
import http.client
import json
import socket
import struct
import sys
import time

mode = sys.argv[1]
if mode == 'dns':
    name, resolver = sys.argv[2:]
    question = b''.join(bytes([len(x)]) + x.encode() for x in name.split('.')) + b'\0\x00\x01\x00\x01'
    packet = b'\x13\x37\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00' + question
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(3)
    s.sendto(packet, (resolver, 53))
    result = s.recv(4096)
    assert result[:2] == b'\x13\x37' and result[3] & 15 == 0, result
    print(socket.inet_ntoa(result[-4:]))
elif mode == 'forty':
    def fetch(index):
        ip = f'192.168.60.{100 + index}'
        c = http.client.HTTPConnection('198.18.77.30', 8080, timeout=20, source_address=(ip, 0))
        c.request('GET', '/')
        response = c.getresponse()
        assert response.status == 200
        assert len(response.read()) == 64
        c.close()
        return ip
    with concurrent.futures.ThreadPoolExecutor(max_workers=40) as pool:
        print(json.dumps(list(pool.map(fetch, range(40)))))
elif mode == 'rate':
    c = http.client.HTTPConnection('198.18.77.30', 8080, timeout=45)
    start = time.monotonic()
    if sys.argv[2] == 'down':
        c.request('GET', '/blob')
        r = c.getresponse()
        data = r.read()
        assert r.status == 200 and len(data) == 4 * 1024 * 1024
        elapsed = time.monotonic() - start
        assert elapsed > 2.5, f'Guest downstream cap not effective: {elapsed}'
    else:
        c.request('POST', '/', body=b'x' * 512 * 1024)
        r = c.getresponse()
        assert r.status == 200 and r.read() == b'OK'
        elapsed = time.monotonic() - start
        assert elapsed > 2, f'Guest upstream cap not effective: {elapsed}'
    print(json.dumps({'direction': sys.argv[2], 'seconds': round(elapsed, 3)}))
