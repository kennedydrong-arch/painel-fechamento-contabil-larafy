# -*- coding: utf-8 -*-
"""Sobe o painel no navegador. O painel le um arquivo JSON por fetch,
e isso o navegador so permite via http:// - abrir o index.html direto
pelo Windows nao funciona.

    py servir.py            -> http://127.0.0.1:8099
"""
import http.server
import os
import socketserver
import sys
import webbrowser

PORTA = int(sys.argv[1]) if len(sys.argv) > 1 else 8099
os.chdir(os.path.dirname(os.path.abspath(__file__)))


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *a):
        pass


with socketserver.TCPServer(("127.0.0.1", PORTA), Handler) as s:
    url = "http://127.0.0.1:%d/" % PORTA
    print("Painel no ar: " + url)
    print("Para parar: Ctrl+C")
    webbrowser.open(url)
    s.serve_forever()
