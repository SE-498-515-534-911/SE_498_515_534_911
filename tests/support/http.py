"""A small browser-like HTTP client for system tests against a live server.

Keeps cookies, sends the CSRF token like the WBMME pages do, and returns
status, headers and body, so tests can check things a browser would see
(for example that the session cookie is HttpOnly).
"""
import http.cookiejar
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import uuid


class Response:
    def __init__(self, status, headers, body):
        self.status, self.headers, self.body = status, headers, body

    def json(self):
        return json.loads(self.body or b'{}')

    @property
    def text(self):
        return self.body.decode('utf-8', 'replace')

    def set_cookie(self, name):
        """The raw Set-Cookie header for ``name``, or ''."""
        return next((h for h in self.headers.get_all('Set-Cookie') or [] if h.startswith(name + '=')), '')


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Browser:
    def __init__(self, base_url, follow_redirects=True):
        self.base = base_url.rstrip('/')
        self.jar = http.cookiejar.CookieJar()
        handlers = [urllib.request.HTTPCookieProcessor(self.jar)]
        if not follow_redirects:
            handlers.append(_NoRedirect())
        self.opener = urllib.request.build_opener(*handlers)

    def cookie(self, name):
        return next((c.value for c in self.jar if c.name == name), None)

    def request(self, method, path, data=None, content_type=None):
        req = urllib.request.Request(self.base + path, data=data, method=method)
        req.add_header('Referer', self.base + '/')
        if content_type:
            req.add_header('Content-Type', content_type)
        if method != 'GET' and self.cookie('csrftoken'):
            req.add_header('X-CSRFToken', self.cookie('csrftoken'))
        try:
            with self.opener.open(req, timeout=120) as response:
                return Response(response.status, response.headers, response.read())
        except urllib.error.HTTPError as exc:
            return Response(exc.code, exc.headers, exc.read())

    def get(self, path):
        return self.request('GET', path)

    def post_json(self, path, body):
        return self.request('POST', path, json.dumps(body).encode(), 'application/json')

    def submit_form(self, path, fields):
        """GET the page (for the CSRF token), then POST the form like a browser does."""
        page = self.get(path)
        token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page.text)
        data = dict(fields, csrfmiddlewaretoken=token.group(1) if token else '')
        return self.request('POST', path, urllib.parse.urlencode(data).encode(),
                            'application/x-www-form-urlencoded')

    def upload(self, name, content, content_type='text/csv'):
        boundary = uuid.uuid4().hex
        body = (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\n'
            f'Content-Type: {content_type}\r\n\r\n'
        ).encode() + content + f'\r\n--{boundary}--\r\n'.encode()
        return self.request('POST', '/api/upload', body, f'multipart/form-data; boundary={boundary}')

    def api_login(self, username, password):
        self.get('/accounts/login/')
        return self.post_json('/api/auth/login', {'username': username, 'password': password})
