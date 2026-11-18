"""Bridge-side global request rate limiter (architecture doc section 6.7).

The architecture requires a global limit of 30 requests per second on the
bridge (the per-session 20 req/s limit belongs to the MCP server).  The
limiter is a token bucket:

* ``per_second`` tokens are refilled per second (default 30);
* at most ``burst`` tokens are stored (default 30, i.e. one second of traffic);
* every ``/rpc`` request must take one token *before* a game-thread job is
  queued, so a rejected request can never produce an editor side effect.

Rejection is reported through the existing error model
(``RATE_LIMITED`` -> JSON-RPC -32012 / HTTP 429 / ``retryable=true``); see
``rpc.handle_request``.

The bucket is thread safe: HTTP worker threads call :meth:`try_acquire`
concurrently.  ``time.monotonic`` is used so wall-clock changes cannot create
or destroy tokens.
"""

import threading
import time

DEFAULT_RATE_PER_SECOND = 30
DEFAULT_RATE_BURST = 30


class RateLimiter(object):
    """Thread-safe token bucket shared by every HTTP worker thread."""

    __slots__ = (
        "enabled",
        "per_second",
        "burst",
        "_tokens",
        "_updated",
        "_clock",
        "_lock",
        "accepted",
        "rejected",
    )

    def __init__(
        self,
        per_second=DEFAULT_RATE_PER_SECOND,
        burst=DEFAULT_RATE_BURST,
        enabled=True,
        clock=time.monotonic,
    ):
        self.per_second = float(per_second)
        self.burst = float(max(1, int(burst)))
        # ``per_second <= 0`` also disables the limiter so an operator can turn
        # it off from either the JSON file or a single environment variable.
        self.enabled = bool(enabled) and self.per_second > 0.0
        self._clock = clock
        self._tokens = self.burst
        self._updated = self._clock()
        self._lock = threading.Lock()
        self.accepted = 0
        self.rejected = 0

    @classmethod
    def from_settings(cls, settings):
        """Build a limiter from a :class:`uemcp_bridge.settings.Settings`."""
        if settings is None:
            return cls()
        return cls(
            per_second=getattr(settings, "rate_limit_per_second", DEFAULT_RATE_PER_SECOND),
            burst=getattr(settings, "rate_limit_burst", DEFAULT_RATE_BURST),
            enabled=getattr(settings, "rate_limit_enabled", True),
        )

    def try_acquire(self):
        """Consume one token.

        Returns ``(allowed, retry_after_seconds)``.  ``retry_after_seconds`` is
        ``0.0`` when the request is allowed and the time until the next token
        otherwise.
        """
        with self._lock:
            if not self.enabled:
                self.accepted += 1
                return (True, 0.0)

            now = self._clock()
            elapsed = now - self._updated
            if elapsed > 0.0:
                self._tokens = min(self.burst, self._tokens + elapsed * self.per_second)
                self._updated = now

            if self._tokens >= 1.0:
                self._tokens -= 1.0
                self.accepted += 1
                return (True, 0.0)

            self.rejected += 1
            # Guard against a zero/negative rate (already disabled above) and
            # keep the value finite for JSON serialization.
            wait = (1.0 - self._tokens) / self.per_second
            return (False, max(0.0, wait))

    def reset(self):
        """Refill the bucket (used by tests and by a manual restart)."""
        with self._lock:
            self._tokens = self.burst
            self._updated = self._clock()
            self.accepted = 0
            self.rejected = 0

    def snapshot(self):
        """JSON-safe view for ``/health``."""
        with self._lock:
            return {
                "enabled": self.enabled,
                "perSecond": self.per_second,
                "burst": self.burst,
                "available": round(self._tokens, 3),
                "accepted": self.accepted,
                "rejected": self.rejected,
            }
