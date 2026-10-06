from http.server import HTTPServer, BaseHTTPRequestHandler
import subprocess, base64, urllib.parse, sys

class Relay(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path
        if path == '/ping':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'pong from mac sandbox')
            return
        q = urllib.parse.urlparse(path).query
        if q:
            try:
                cmd = base64.b64decode(q).decode()
                r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
                out = r.stdout + r.stderr
            except Exception as e:
                out = str(e)
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(out.encode())
        else:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'relay ok')

    def log_message(self, *a):
        pass

port = int(sys.argv[1]) if len(sys.argv) > 1 else 18765
print(f'RELAY_READY:{port}', flush=True)
HTTPServer(('127.0.0.1', port), Relay).serve_forever()
