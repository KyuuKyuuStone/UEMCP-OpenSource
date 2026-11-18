"""GameThreadDispatcher meta/queuedMs/cancellation self-check (no editor required).

Covers: measured queuedMs via a fake clock, timeout -> cancelled -> dropped on
the next tick without executing or occupying the pending slot, expired-before-
execution jobs, the Pending poll lifecycle (complete / cancelled / deadline),
shutdown drain, queue-full DispatcherBusy, DispatcherTimeout.timeout_ms, and
SynchronousDispatcher meta compatibility.
"""

import os
import sys
import threading
import time
import types

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(TESTS_DIR)
PYTHON_DIR = os.path.join(PLUGIN_DIR, "Content", "Python")

# Minimal unreal stub: the dispatcher only needs tick/shutdown registration.
_stub = types.ModuleType("unreal")
_stub.register_slate_post_tick_callback = lambda fn: 1
_stub.unregister_slate_post_tick_callback = lambda handle: None
_stub.register_python_shutdown_callback = lambda fn: None
sys.modules["unreal"] = _stub

sys.path.insert(0, PYTHON_DIR)

from uemcp_bridge import dispatcher as dispatcher_mod  # noqa: E402
from uemcp_bridge.dispatcher import (  # noqa: E402
    DispatcherBusy,
    DispatcherTimeout,
    Done,
    GameThreadDispatcher,
    Pending,
    SynchronousDispatcher,
)


class _FakeTime(object):
    """Deterministic monotonic clock; only dispatcher_mod.time is rebound."""

    def __init__(self):
        self.now = 1000.0

    def monotonic(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


_CLOCK = _FakeTime()


def _wait_queue(d, count=1, timeout=2.0):
    end = time.monotonic() + timeout
    while d._queue.qsize() < count:
        if time.monotonic() > end:
            raise AssertionError("queue never reached %d job(s)" % count)
        time.sleep(0.005)


def _run_call(d, fn, timeout_s, meta=None):
    holder = {}

    def worker():
        try:
            holder["result"] = d.call(fn, timeout_s, meta=meta)
        except BaseException as exc:  # noqa: BLE001 - record any failure
            holder["error"] = exc

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    return thread, holder


def _expect_timeout(failures, label, holder, message_part, timeout_ms):
    exc = holder.get("error")
    if not isinstance(exc, DispatcherTimeout):
        failures.append("%s: expected DispatcherTimeout, got %r" % (label, exc))
        return
    if message_part not in str(exc):
        failures.append("%s: message %r lacks %r" % (label, str(exc), message_part))
    if exc.timeout_ms != timeout_ms:
        failures.append(
            "%s: timeout_ms=%r, expected %r" % (label, exc.timeout_ms, timeout_ms)
        )


def check_queued_ms(failures):
    d = GameThreadDispatcher()
    try:
        executed = []
        meta = {}
        thread, holder = _run_call(
            d, lambda: executed.append(1) or "ok", 5.0, meta=meta
        )
        _wait_queue(d)
        _CLOCK.advance(0.25)
        d._on_tick(0.016)
        thread.join(2.0)
        if holder.get("result") != "ok" or not executed:
            failures.append("queued_ms: job did not execute: %r" % holder)
        if meta.get("queuedMs") != 250:
            failures.append("queued_ms: queuedMs=%r, expected 250" % meta.get("queuedMs"))
        # Backward compatibility: call() without meta still works.
        thread2, holder2 = _run_call(d, lambda: "no-meta", 5.0)
        _wait_queue(d)
        d._on_tick(0.016)
        thread2.join(2.0)
        if holder2.get("result") != "no-meta":
            failures.append("queued_ms: no-meta call failed: %r" % holder2)
        print("QUEUED_MS queuedMs=%s no_meta=ok" % meta.get("queuedMs"))
    finally:
        d.shutdown()


def check_timeout_cancel(failures):
    d = GameThreadDispatcher()
    try:
        executed = []
        meta = {}
        thread, holder = _run_call(
            d, lambda: executed.append(1) or "late", 0.05, meta=meta
        )
        _wait_queue(d)
        thread.join(2.0)  # real-time wait expires; no tick happened
        _expect_timeout(failures, "timeout_cancel", holder, "timed out", 50)
        if meta.get("queuedMs") is not None:
            failures.append(
                "timeout_cancel: queuedMs=%r before dequeue, expected None"
                % meta.get("queuedMs")
            )
        d._on_tick(0.016)  # cancelled job must be dropped, not executed
        if executed:
            failures.append("timeout_cancel: cancelled job executed")
        if not d._queue.empty() or d._pending is not None:
            failures.append("timeout_cancel: queue/pending not released")
        print("TIMEOUT_CANCEL dropped=ok queuedMs=%s" % meta.get("queuedMs"))
    finally:
        d.shutdown()


def check_expired(failures):
    d = GameThreadDispatcher()
    try:
        executed = []
        thread, holder = _run_call(d, lambda: executed.append(1) or "late", 0.2)
        _wait_queue(d)
        _CLOCK.advance(1.0)  # deadline passes while still queued
        d._on_tick(0.016)
        thread.join(2.0)
        _expect_timeout(failures, "expired", holder, "expired before execution", 200)
        if executed:
            failures.append("expired: expired job executed")
        print("EXPIRED_BEFORE_EXECUTION ok")
    finally:
        d.shutdown()


def check_pending_cancel(failures):
    d = GameThreadDispatcher()
    try:
        polls = []

        def poll():
            polls.append(1)
            return None

        thread, holder = _run_call(d, lambda: Pending(poll), 0.05)
        _wait_queue(d)
        d._on_tick(0.016)  # fn returns Pending -> registered
        thread.join(2.0)  # caller times out while pending
        _expect_timeout(failures, "pending_cancel", holder, "timed out", 50)
        if d._pending is None:
            failures.append("pending_cancel: pending released before next tick")
        d._on_tick(0.016)  # next tick must release the cancelled pending
        if d._pending is not None:
            failures.append("pending_cancel: pending not released on next tick")
        if polls:
            failures.append("pending_cancel: poll ran for a cancelled job")
        print("PENDING_CANCEL released_on_next_tick=ok polls=%d" % len(polls))
    finally:
        d.shutdown()


def check_pending_complete(failures):
    d = GameThreadDispatcher()
    try:
        polls = []

        def poll():
            polls.append(1)
            if len(polls) >= 2:
                return Done("val")
            return None

        meta = {}
        thread, holder = _run_call(d, lambda: Pending(poll), 5.0, meta=meta)
        _wait_queue(d)
        _CLOCK.advance(0.25)
        d._on_tick(0.016)  # register pending
        d._on_tick(0.016)  # poll -> None
        d._on_tick(0.016)  # poll -> Done
        thread.join(2.0)
        if holder.get("result") != "val":
            failures.append("pending_complete: result=%r" % holder)
        if len(polls) != 2:
            failures.append("pending_complete: polls=%d, expected 2" % len(polls))
        if meta.get("queuedMs") != 250:
            failures.append(
                "pending_complete: queuedMs=%r, expected 250" % meta.get("queuedMs")
            )
        if d._pending is not None:
            failures.append("pending_complete: pending not cleared")
        print("PENDING_COMPLETE result=val polls=%d queuedMs=%s" % (len(polls), meta.get("queuedMs")))
    finally:
        d.shutdown()


def check_pending_deadline(failures):
    d = GameThreadDispatcher()
    try:
        thread, holder = _run_call(d, lambda: Pending(lambda: None), 0.1)
        _wait_queue(d)
        d._on_tick(0.016)  # register pending
        _CLOCK.advance(1.0)
        d._on_tick(0.016)  # polling deadline exceeded
        thread.join(2.0)
        _expect_timeout(failures, "pending_deadline", holder, "timed out while polling", 100)
        if d._pending is not None:
            failures.append("pending_deadline: pending not cleared")
        print("PENDING_DEADLINE ok")
    finally:
        d.shutdown()


def check_shutdown_drain(failures):
    d = GameThreadDispatcher()
    threads = []
    holders = []
    try:
        for _ in range(2):
            thread, holder = _run_call(d, lambda: "never", 5.0)
            threads.append(thread)
            holders.append(holder)
        _wait_queue(d, count=2)
        d.shutdown()
        for thread in threads:
            thread.join(2.0)
        for index, holder in enumerate(holders):
            _expect_timeout(
                failures, "shutdown_drain[%d]" % index, holder, "bridge shutting down", 5000
            )
        if not d._queue.empty():
            failures.append("shutdown_drain: queue not drained")
        try:
            d.call(lambda: "x", 1.0)
            failures.append("shutdown_drain: call after shutdown did not raise")
        except DispatcherBusy:
            pass
        d.shutdown()  # idempotent
        print("SHUTDOWN_DRAIN ok")
    finally:
        d.shutdown()


def check_shutdown_pending(failures):
    d = GameThreadDispatcher()
    try:
        thread, holder = _run_call(d, lambda: Pending(lambda: None), 5.0)
        _wait_queue(d)
        d._on_tick(0.016)
        d.shutdown()
        thread.join(2.0)
        _expect_timeout(failures, "shutdown_pending", holder, "bridge shutting down", 5000)
        if d._pending is not None:
            failures.append("shutdown_pending: pending not cleared")
        print("SHUTDOWN_PENDING ok")
    finally:
        d.shutdown()


def check_queue_full(failures):
    d = GameThreadDispatcher(max_queue=1)
    try:
        thread, holder = _run_call(d, lambda: "first", 5.0)
        _wait_queue(d)
        try:
            d.call(lambda: "second", 0.2)
            failures.append("queue_full: second call did not raise")
        except DispatcherBusy as exc:
            if "queue is full" not in str(exc):
                failures.append("queue_full: unexpected message %r" % str(exc))
        d._on_tick(0.016)
        thread.join(2.0)
        if holder.get("result") != "first":
            failures.append("queue_full: first job lost: %r" % holder)
        print("QUEUE_FULL ok")
    finally:
        d.shutdown()


def check_sync_dispatcher(failures):
    d = SynchronousDispatcher()
    meta = {}
    if d.call(lambda: "sync", 1.0, meta=meta) != "sync":
        failures.append("sync: result mismatch")
    if meta.get("queuedMs") != 0:
        failures.append("sync: queuedMs=%r, expected 0" % meta.get("queuedMs"))
    if d.call(lambda: "two-arg", 1.0) != "two-arg":
        failures.append("sync: two-arg call failed")
    d.shutdown()
    try:
        d.call(lambda: "x", 1.0)
        failures.append("sync: call after shutdown did not raise")
    except DispatcherBusy:
        pass
    print("SYNC_DISPATCHER queuedMs=0 two_arg=ok shutdown_gate=ok")


def main():
    failures = []
    real_time = dispatcher_mod.time
    dispatcher_mod.time = _CLOCK
    try:
        check_queued_ms(failures)
        check_timeout_cancel(failures)
        check_expired(failures)
        check_pending_cancel(failures)
        check_pending_complete(failures)
        check_pending_deadline(failures)
        check_shutdown_drain(failures)
        check_shutdown_pending(failures)
        check_queue_full(failures)
        check_sync_dispatcher(failures)
    finally:
        dispatcher_mod.time = real_time
    for item in failures:
        print("FAIL: %s" % item)
    if failures:
        print("DISPATCHER_META_RESULT FAIL (%d)" % len(failures))
        return 1
    print("DISPATCHER_META_RESULT PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
