
import os
import ssl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.parse import urlsplit

from django.core.servers.basehttp import WSGIRequestHandler, ThreadedWSGIServer
from django.contrib.staticfiles.handlers import StaticFilesHandler
from django.core.wsgi import get_wsgi_application


HTTPS_PORT = 8000
HTTP_PORT = 8001


class HTTPSWSGIServer(ThreadedWSGIServer):
    def __init__(self, address, handler_class):
        super().__init__(address, handler_class)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(
            os.path.join(os.environ["TEMP"], "wbmme-localhost.crt"),
            os.path.join(os.environ["TEMP"], "wbmme-localhost.key"),
        )
        self.socket = context.wrap_socket(self.socket, server_side=True)


class RedirectHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.redirect_to_https()

    def do_HEAD(self):
        self.redirect_to_https()

    def do_POST(self):
        self.redirect_to_https()

    def do_PUT(self):
        self.redirect_to_https()

    def do_PATCH(self):
        self.redirect_to_https()

    def do_DELETE(self):
        self.redirect_to_https()

    def do_OPTIONS(self):
        self.redirect_to_https()

    def redirect_to_https(self):
        path = urlsplit(self.path).path
        query = urlsplit(self.path).query
        destination = f"https://127.0.0.1:{HTTPS_PORT}{path}"
        if query:
            destination += f"?{query}"
        self.send_response(308)
        self.send_header("Location", destination)
        self.end_headers()

    def log_message(self, format, *args):
        print(f"HTTP redirect: {args[0]}")


if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    application = get_wsgi_application()

    https_server = HTTPSWSGIServer(
        ("127.0.0.1", HTTPS_PORT), WSGIRequestHandler
    )
    https_server.set_app(StaticFilesHandler(application))

    http_server = ThreadingHTTPServer(
        ("127.0.0.1", HTTP_PORT), RedirectHandler
    )

    Thread(target=http_server.serve_forever, daemon=True).start()
    print(f"HTTP redirects:  http://127.0.0.1:{HTTP_PORT}/")
    print(f"HTTPS server:    https://127.0.0.1:{HTTPS_PORT}/")

    try:
        https_server.serve_forever()
    except KeyboardInterrupt:
        print("\nServers stopped.")
    finally:
        http_server.shutdown()
        http_server.server_close()
        https_server.server_close()
