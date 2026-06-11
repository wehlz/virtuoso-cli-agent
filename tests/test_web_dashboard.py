import threading

from http.server import ThreadingHTTPServer

from core.web_dashboard import make_handler


def test_dashboard_status_endpoint():
    handler = make_handler()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        import requests

        res = requests.get(f"http://127.0.0.1:{port}/api/status", timeout=5)
        assert res.status_code == 200
        data = res.json()
        assert "backend" in data
        assert "model" in data
    finally:
        httpd.shutdown()
