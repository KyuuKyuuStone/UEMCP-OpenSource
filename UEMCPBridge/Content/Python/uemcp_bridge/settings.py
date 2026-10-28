"""Bridge configuration.

Precedence (architecture doc section 4.4): environment > project settings JSON >
defaults.  The project settings file lives at
``<Project>/Saved/UEMCP/bridge-settings.json``.
"""

import json
import os
from pathlib import Path

PLUGIN_VERSION = "0.1.0"
BRIDGE_PROTOCOL = 1

DEFAULT_PORT = 18778
FALLBACK_PORTS = tuple(range(18779, 18789))

DEFAULT_MAX_QUEUE_SIZE = 64
DEFAULT_REQUEST_TIMEOUT_MS = 30000
DEFAULT_SEARCH_TIMEOUT_MS = 20000
# Bridge-wide request limit (architecture section 6.7: 30 req/s globally).
# Set rateLimitPerSecond to 0 (or rateLimitEnabled to false) to turn it off.
DEFAULT_RATE_LIMIT_ENABLED = True
DEFAULT_RATE_LIMIT_PER_SECOND = 30
DEFAULT_RATE_LIMIT_BURST = 30
# Single source of truth for the console allowlist (architecture section
# 5.8, 11 entries).  Keep this list authoritative; shared/ docs must mirror it.
DEFAULT_CONSOLE_ALLOWLIST = (
    "stat",
    "show",
    "r.",
    "sg.",
    "viewmode",
    "log",
    "help",
    "dumpticks",
    "obj",
    "memreport",
    "camera",
)

_TRUE_VALUES = ("1", "true", "yes", "on")
_FALSE_VALUES = ("0", "false", "no", "off")


def _as_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in _TRUE_VALUES:
        return True
    if text in _FALSE_VALUES:
        return False
    return default


def _as_int(value, default, minimum=None, maximum=None):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    if minimum is not None and number < minimum:
        return default
    if maximum is not None and number > maximum:
        return default
    return number


class Settings(object):
    """Immutable snapshot of the bridge configuration."""

    __slots__ = (
        "port",
        "allow_write",
        "allow_exec",
        "allow_console",
        "console_allowlist",
        "max_queue_size",
        "request_timeout_ms",
        "search_timeout_ms",
        "rate_limit_enabled",
        "rate_limit_per_second",
        "rate_limit_burst",
        "token_override",
        "source",
    )

    def __init__(
        self,
        port=DEFAULT_PORT,
        allow_write=False,
        allow_exec=False,
        allow_console=False,
        console_allowlist=DEFAULT_CONSOLE_ALLOWLIST,
        max_queue_size=DEFAULT_MAX_QUEUE_SIZE,
        request_timeout_ms=DEFAULT_REQUEST_TIMEOUT_MS,
        search_timeout_ms=DEFAULT_SEARCH_TIMEOUT_MS,
        rate_limit_enabled=DEFAULT_RATE_LIMIT_ENABLED,
        rate_limit_per_second=DEFAULT_RATE_LIMIT_PER_SECOND,
        rate_limit_burst=DEFAULT_RATE_LIMIT_BURST,
        token_override=None,
        source="defaults",
    ):
        self.port = port
        self.allow_write = bool(allow_write)
        self.allow_exec = bool(allow_exec)
        self.allow_console = bool(allow_console)
        self.console_allowlist = tuple(console_allowlist)
        self.max_queue_size = max_queue_size
        self.request_timeout_ms = request_timeout_ms
        self.search_timeout_ms = search_timeout_ms
        self.rate_limit_enabled = bool(rate_limit_enabled)
        self.rate_limit_per_second = rate_limit_per_second
        self.rate_limit_burst = rate_limit_burst
        self.token_override = token_override
        self.source = source

    @classmethod
    def load(cls, project_dir):
        data = {}
        source = "defaults"
        settings_path = Path(project_dir) / "Saved" / "UEMCP" / "bridge-settings.json"
        if settings_path.is_file():
            try:
                with open(settings_path, "r", encoding="utf-8") as handle:
                    loaded = json.load(handle)
                if isinstance(loaded, dict):
                    data = loaded
                    source = str(settings_path)
            except Exception:
                # A malformed settings file must never prevent the bridge from
                # starting; fall back to defaults and let the caller log it.
                data = {}

        def pick(key, env_key, default):
            if env_key in os.environ:
                return os.environ[env_key]
            return data.get(key, default)

        port = _as_int(pick("port", "UEMCP_BRIDGE_PORT", DEFAULT_PORT), DEFAULT_PORT, 0, 65535)

        allow_write = _as_bool(
            pick("allowWrite", "UEMCP_BRIDGE_ALLOW_WRITE", False), False
        )
        allow_exec = _as_bool(
            pick("allowExec", "UEMCP_BRIDGE_ALLOW_EXEC", False), False
        )
        allow_console = _as_bool(
            pick("allowConsole", "UEMCP_BRIDGE_ALLOW_CONSOLE", False), False
        )

        allowlist = data.get("consoleAllowlist", DEFAULT_CONSOLE_ALLOWLIST)
        if not isinstance(allowlist, (list, tuple)):
            allowlist = DEFAULT_CONSOLE_ALLOWLIST
        allowlist = tuple(str(item) for item in allowlist if str(item))

        max_queue_size = _as_int(
            pick("maxQueueSize", "UEMCP_BRIDGE_MAX_QUEUE_SIZE", DEFAULT_MAX_QUEUE_SIZE),
            DEFAULT_MAX_QUEUE_SIZE,
            1,
            4096,
        )
        request_timeout_ms = _as_int(
            pick("requestTimeoutMs", "UEMCP_BRIDGE_REQUEST_TIMEOUT_MS", DEFAULT_REQUEST_TIMEOUT_MS),
            DEFAULT_REQUEST_TIMEOUT_MS,
            1000,
            120000,
        )
        search_timeout_ms = _as_int(
            data.get("searchTimeoutMs", DEFAULT_SEARCH_TIMEOUT_MS),
            DEFAULT_SEARCH_TIMEOUT_MS,
            1000,
            120000,
        )

        # A value of 0 disables the limiter (equivalent to rateLimitEnabled
        # false) so either knob can turn it off from the settings file or the
        # environment.
        rate_limit_per_second = _as_int(
            pick(
                "rateLimitPerSecond",
                "UEMCP_BRIDGE_RATE_LIMIT_PER_SECOND",
                DEFAULT_RATE_LIMIT_PER_SECOND,
            ),
            DEFAULT_RATE_LIMIT_PER_SECOND,
            0,
            10000,
        )
        rate_limit_burst = _as_int(
            pick(
                "rateLimitBurst",
                "UEMCP_BRIDGE_RATE_LIMIT_BURST",
                rate_limit_per_second or DEFAULT_RATE_LIMIT_BURST,
            ),
            rate_limit_per_second or DEFAULT_RATE_LIMIT_BURST,
            1,
            10000,
        )
        rate_limit_enabled = _as_bool(
            pick(
                "rateLimitEnabled",
                "UEMCP_BRIDGE_RATE_LIMIT_ENABLED",
                DEFAULT_RATE_LIMIT_ENABLED,
            ),
            DEFAULT_RATE_LIMIT_ENABLED,
        )

        token_override = None
        token_file = os.environ.get("UEMCP_BRIDGE_TOKEN_FILE")
        if token_file:
            try:
                with open(token_file, "r", encoding="utf-8") as handle:
                    candidate = handle.read().strip()
                if candidate:
                    token_override = candidate
            except Exception:
                token_override = None

        return cls(
            port=port,
            allow_write=allow_write,
            allow_exec=allow_exec,
            allow_console=allow_console,
            console_allowlist=allowlist,
            max_queue_size=max_queue_size,
            request_timeout_ms=request_timeout_ms,
            search_timeout_ms=search_timeout_ms,
            rate_limit_enabled=rate_limit_enabled,
            rate_limit_per_second=rate_limit_per_second,
            rate_limit_burst=rate_limit_burst,
            token_override=token_override,
            source=source,
        )

    def policy_snapshot(self):
        """Bridge-side policy snapshot used by ``editor.status``."""
        if self.allow_write:
            mode = "standard"
        else:
            mode = "read-only"
        return {
            "mode": mode,
            "write": self.allow_write,
            "exec": self.allow_exec,
            "destructive": False,
        }
