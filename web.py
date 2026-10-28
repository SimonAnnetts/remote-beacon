"""Minimal authenticated HTTP server and JSON API for the beacon.

route() is plain request -> response logic so it can be tested without
sockets; serve() wraps it in an asyncio server.

Security: the interface is protected by HTTP Basic auth with web_password
(any username). That is only as safe as the network, since Basic auth over
plain HTTP is sent unencrypted: keep it on a trusted LAN, never expose it to
the internet. The server refuses all requests until a password is configured.
"""
import asyncio
import binascii
import json

import clock
import config

_MAX_BODY = 2048
_MAX_HEADERS = 32
_TIMEOUT_S = 15

_JSON = "application/json"


def _same(a, b):
    """Compare strings without exiting early on the first difference."""
    if len(a) != len(b):
        return False
    diff = 0
    for x, y in zip(a, b):
        diff |= ord(x) ^ ord(y)
    return diff == 0


def authorized(headers, password):
    if not password:
        return False
    value = headers.get("authorization", "")
    if not value.startswith("Basic "):
        return False
    try:
        userpass = binascii.a2b_base64(value[6:]).decode()
    except Exception:
        return False
    return _same(userpass.partition(":")[2], password)


def _json(code, obj):
    return code, _JSON, json.dumps(obj).encode()


def route(beacon, net, method, path, headers, body):
    """Return (status code, content type, body bytes)."""
    password = beacon.cfg["web_password"]
    if not password:
        return 503, "text/plain", b"Set web_password in config.json first"
    if not authorized(headers, password):
        return 401, "text/plain", b"Authentication required"

    if method == "GET" and path == "/":
        try:
            with open("index.html", "rb") as f:
                return 200, "text/html", f.read()
        except OSError:
            return 500, "text/plain", b"index.html missing"
    if method == "GET" and path == "/api/status":
        status = beacon.status()
        status["net"] = net
        status["clock"] = clock.status()
        return _json(200, status)
    if method == "GET" and path == "/api/config":
        return _json(200, config.public(beacon.current_config()))
    if method == "POST" and path == "/api/config":
        try:
            update = json.loads(body)
            if not isinstance(update, dict):
                raise ValueError("expected a JSON object")
            new = config.merge(beacon.current_config(), update)
        except (ValueError, KeyError, TypeError, AttributeError) as e:
            return _json(400, {"error": str(e)})
        beacon.request_config(new)
        return _json(200, {"ok": True})
    if method == "POST" and path == "/api/tx":
        try:
            beacon.request_tx(json.loads(body)["band"])
        except (ValueError, KeyError, TypeError) as e:
            return _json(400, {"error": str(e)})
        return _json(200, {"ok": True})
    if method == "POST" and path == "/api/stop":
        beacon.emergency_stop()
        return _json(200, {"ok": True})
    return 404, "text/plain", b"Not found"


_REASONS = {200: "OK", 400: "Bad Request", 401: "Unauthorized", 404: "Not Found",
            413: "Payload Too Large", 500: "Server Error", 503: "Service Unavailable"}


async def _respond(writer, code, ctype, body):
    head = "HTTP/1.0 %d %s\r\nContent-Type: %s\r\nContent-Length: %d\r\n" % (
        code, _REASONS.get(code, "Error"), ctype, len(body))
    if code == 401:
        head += 'WWW-Authenticate: Basic realm="remote-beacon"\r\n'
    head += "Cache-Control: no-store\r\nConnection: close\r\n\r\n"
    writer.write(head.encode())
    writer.write(body)
    await writer.drain()


async def _handle(reader, writer, beacon, net):
    try:
        request = (await asyncio.wait_for(reader.readline(), _TIMEOUT_S)).decode()
        parts = request.split()
        if len(parts) < 2:
            return
        headers = {}
        for _ in range(_MAX_HEADERS):
            line = (await asyncio.wait_for(reader.readline(), _TIMEOUT_S)).decode()
            if line in ("\r\n", "\n", ""):
                break
            name, _, value = line.partition(":")
            headers[name.strip().lower()] = value.strip()
        length = int(headers.get("content-length", "0") or "0")
        if length > _MAX_BODY:
            await _respond(writer, 413, "text/plain", b"Too large")
            return
        body = await asyncio.wait_for(reader.readexactly(length), _TIMEOUT_S) if length else b""
        code, ctype, out = route(beacon, net, parts[0], parts[1].split("?")[0],
                                 headers, body)
        await _respond(writer, code, ctype, out)
    except Exception as e:  # a bad client must never take the server down
        print("web:", repr(e))
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


async def serve(beacon, net, port=80):
    await asyncio.start_server(
        lambda r, w: _handle(r, w, beacon, net), "0.0.0.0", port)
    while True:
        await asyncio.sleep(3600)
