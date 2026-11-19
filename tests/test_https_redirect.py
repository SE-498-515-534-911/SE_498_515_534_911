import pytest
from run_https_dev import RedirectHandler


class FakeHandler:
    def __init__(self,path):
        self.path=path
        self.status=None
        self.headers={}
        self.error=None
    def redirect_to_https(self):
        RedirectHandler.redirect_to_https(self)

    def send_error(self,status,message):
        self.error=(status,message)

    def send_response(self,status):
        self.status=status

    def send_header(self,name,value):
        self.headers[name]=value

    def end_headers(self):
        pass


@pytest.mark.parametrize("method",[
    "do_GET","do_HEAD","do_POST","do_PUT",
    "do_PATCH","do_DELETE","do_OPTIONS"
])
def test_redirect_methods(method):
    handler=FakeHandler("/dashboard")
    getattr(RedirectHandler,method)(handler)

    assert handler.status==308
    assert handler.headers["Location"]=="https://127.0.0.1:8000/dashboard"


def test_query_string_preserved():
    handler=FakeHandler("/search?q=hello world")
    RedirectHandler.redirect_to_https(handler)

    assert "q=hello%20world" in handler.headers["Location"]


def test_special_characters_encoded():
    handler=FakeHandler("/hello world")
    RedirectHandler.redirect_to_https(handler)

    assert handler.headers["Location"].endswith("/hello%20world")


def test_control_characters_rejected():
    handler=FakeHandler("/test\x01")
    RedirectHandler.redirect_to_https(handler)

    assert handler.error[0]==400
    assert handler.status is None


def test_redirect_without_query():
    handler=FakeHandler("/")
    RedirectHandler.redirect_to_https(handler)

    assert handler.headers["Location"]=="https://127.0.0.1:8000/"
