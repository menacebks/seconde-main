"""
Market Belgique - lancement local (et sur Railway).
    python server.py   puis ouvrir http://localhost:8000
Sur PythonAnywhere, ce fichier n'est pas utilisé : c'est app.py (variable `application`).
"""
import os
from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

import app

PORT = int(os.environ.get("PORT", 8000))


class ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True


class Handler(WSGIRequestHandler):
    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args), flush=True)


if __name__ == "__main__":
    print(f"Market Belgique en ligne : http://localhost:{PORT}  (données : {app.DATA_DIR})", flush=True)
    if os.environ.get("ADMIN_PASSWORD"):
        print(f"Administration : http://localhost:{PORT}/admin.html  (mot de passe : variable ADMIN_PASSWORD)", flush=True)
    else:
        print(f"Administration : http://localhost:{PORT}/admin.html  (mot de passe dans {app.ADMIN_PASSWORD_FILE})", flush=True)
    app.purger_si_besoin(force=True)
    make_server("0.0.0.0", PORT, app.application, server_class=ThreadingWSGIServer, handler_class=Handler).serve_forever()
