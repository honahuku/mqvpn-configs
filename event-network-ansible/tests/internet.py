#!/usr/bin/python3
"""Deterministic HTTP and DNS endpoints inside the isolated Docker lab."""
import http.server
import socket
import struct
import threading
import ssl
import subprocess


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        data = b'x' * (4 * 1024 * 1024 if self.path == '/blob' else 64)
        self.send_response(200)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        self.rfile.read(int(self.headers.get('Content-Length', 0)))
        self.send_response(200)
        self.send_header('Content-Length', '2')
        self.end_headers()
        self.wfile.write(b'OK')

    def log_message(self, *args):
        pass


def dns():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(('0.0.0.0', 53))
    while True:
        data, peer = s.recvfrom(4096)
        offset = 12
        while data[offset]:
            offset += data[offset] + 1
        end = offset + 5
        answer = b'\xc0\x0c' + struct.pack('!HHIH', 1, 1, 10, 4) + socket.inet_aton('198.18.77.30')
        reply = data[:2] + b'\x81\x80\x00\x01\x00\x01\x00\x00\x00\x00' + data[12:end] + answer
        s.sendto(reply, peer)


class Server(http.server.ThreadingHTTPServer):
    request_queue_size = 128


class Server6(Server):
    address_family = socket.AF_INET6


subprocess.run(['openssl', 'req', '-x509', '-newkey', 'ec', '-pkeyopt',
                'ec_paramgen_curve:prime256v1', '-nodes', '-keyout', '/tmp/web.key',
                '-out', '/tmp/web.crt', '-days', '1', '-subj', '/CN=LabWeb'],
               check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain('/tmp/web.crt', '/tmp/web.key')
for server in [Server(('0.0.0.0', 443), Handler), Server6(('::', 8443), Handler)]:
    server.socket = context.wrap_socket(server.socket, server_side=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
threading.Thread(target=dns, daemon=True).start()
Server(('0.0.0.0', 8080), Handler).serve_forever()
