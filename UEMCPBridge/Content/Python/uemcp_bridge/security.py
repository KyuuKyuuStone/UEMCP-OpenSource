"""Loopback, Host/Origin and token checks (architecture doc section 6.2)."""

import base64
import hmac
import secrets

_LOOPBACK_PEERS = frozenset({"127.0.0.1", "::1", "::ffff:127.0.0.1"})
_ALLOWED_HOSTS = frozenset({"127.0.0.1", "localhost"})


def generate_token():
    """32 random bytes as unpadded base64url (43 characters)."""
    raw = secrets.token_bytes(32)
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def token_matches(expected, supplied):
    if not expected or not supplied:
        return False
    try:
        return hmac.compare_digest(str(expected), str(supplied))
    except Exception:
        return False


def is_loopback_peer(peer_address):
    if not peer_address:
        return False
    value = str(peer_address).strip("[]")
    return value in _LOOPBACK_PEERS


def valid_host(host_header, port):
    """Only ``127.0.0.1[:port]`` / ``localhost[:port]`` are accepted."""
    if not host_header:
        return False
    header = str(host_header).strip()
    if header.startswith("["):
        return False  # IPv6 Host headers are not used by the bridge.
    host, separator, port_text = header.partition(":")
    if host.lower() not in _ALLOWED_HOSTS:
        return False
    if separator:
        try:
            host_port = int(port_text)
        except ValueError:
            return False
        if host_port != int(port):
            return False
    return True


def valid_origin(origin, port):
    """``Origin`` is optional; when present it must be loopback or ``null``."""
    if origin is None:
        return True
    value = str(origin).strip()
    if value == "" or value.lower() == "null":
        return True
    lowered = value.lower()
    for scheme in ("http://", "https://"):
        if lowered.startswith(scheme):
            remainder = value[len(scheme):]
            host, separator, port_text = remainder.partition(":")
            if host.lower() not in _ALLOWED_HOSTS:
                return False
            if separator:
                try:
                    host_port = int(port_text.split("/", 1)[0])
                except ValueError:
                    return False
                return host_port == int(port)
            return True
    return False
