#!/usr/bin/python3
"""Send a DHCPDISCOVER, then request the offer; requires an isolated netns."""
import json
import os
import random
import socket
import struct
import sys
import time

iface = sys.argv[1]
mac = bytes.fromhex(open(f'/sys/class/net/{iface}/address').read().strip().replace(':', ''))
xid = random.getrandbits(32)
bootp = struct.pack('!BBBBIHH4s4s4s4s16s64s128s', 1, 1, 6, 0, xid, 0, 0x8000,
                    b'\0' * 4, b'\0' * 4, b'\0' * 4, b'\0' * 4,
                    mac + b'\0' * 10, b'\0' * 64, b'\0' * 128)
s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(0x0800))
s.bind((iface, 0))
s.settimeout(1)


def send(options):
    dhcp = (bootp + b'\x63\x82\x53\x63' + options + b'\xff').ljust(300, b'\0')
    udp = struct.pack('!HHHH', 68, 67, 8 + len(dhcp), 0) + dhcp
    ip = struct.pack('!BBHHHBBH4s4s', 0x45, 0, 20 + len(udp), 0, 0, 64, 17, 0,
                     b'\0' * 4, b'\xff' * 4)
    words = struct.unpack('!10H', ip)
    total = sum(words)
    total = (total & 65535) + (total >> 16)
    total = (total & 65535) + (total >> 16)
    ip = ip[:10] + struct.pack('!H', (~total) & 65535) + ip[12:]
    s.send(b'\xff' * 6 + mac + b'\x08\x00' + ip + udp)


def receive(kind):
    until = time.monotonic() + 15
    while time.monotonic() < until:
        try:
            packet = s.recv(4096)
        except TimeoutError:
            continue
        if len(packet) < 282 or packet[23] != 17:
            continue
        pos = 14 + ((packet[14] & 15) * 4)
        if struct.unpack('!H', packet[pos + 2:pos + 4])[0] != 68:
            continue
        body = packet[pos + 8:]
        if struct.unpack('!I', body[4:8])[0] != xid:
            continue
        opts = {}
        off = 240
        while off < len(body) and body[off] != 255:
            key = body[off]
            off += 1
            if key == 0:
                continue
            length = body[off]
            opts[key] = body[off + 1:off + 1 + length]
            off += length + 1
        if opts.get(53) == bytes([kind]):
            return body[16:20], opts
    raise SystemExit('No matching DHCP response')


send(b'\x35\x01\x01\x37\x03\x01\x03\x06')
address, options = receive(2)
send(b'\x35\x01\x03\x32\x04' + address + b'\x36\x04' + options[54])
address, options = receive(5)
print(json.dumps({'address': socket.inet_ntoa(address), 'router': socket.inet_ntoa(options[3][:4]),
                  'dns': socket.inet_ntoa(options[6][:4])}))
