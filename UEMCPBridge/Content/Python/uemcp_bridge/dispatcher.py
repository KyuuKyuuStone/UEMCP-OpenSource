"""Game-thread dispatcher (architecture doc section 2.6).

HTTP worker threads may never touch ``unreal`` directly.  Every job is queued
and executed from a Slate post-tick callback.  A job may return a
:class:`Pending` object when it needs several ticks to finish (for example a
high-resolution screenshot task), which keeps the game thread responsive.
"""

import queue
import threading
import time

try:
    import unreal  # type: ignore
except Exception:  # pragma: no cover - only absent outside the editor
    unreal = None


class DispatcherBusy(Exception):
    """Queue is full."""


class DispatcherTimeout(Exception):
    """The job did not finish before the caller's timeout."""


class Pending(object):
    """Returned by a job that needs additional ticks.

    ``poll`` is called once per tick.  It returns ``None`` while the job is
    still running, a :class:`Done` value when finished, or raises an exception.
    """

    __slots__ = ("poll",)

    def __init__(self, poll):
        self.poll = poll


class Done(object):
    __slots__ = ("value",)

    def __init__(self, value):
        self.value = value


class _Job(object):
    __slots__ = ("fn", "done", "result", "error", "cancelled", "deadline")

    def __init__(self, fn, deadline):
        self.fn = fn
        self.done = threading.Event()
        self.result = None
        self.error = None
        self.cancelled = False
        self.deadline = deadline


class GameThreadDispatcher(object):
    """Single queue, one job per Slate tick."""

    def __init__(self, max_queue=64):
        if unreal is None:
            raise RuntimeError("unreal module is not available")
        self._queue = queue.Queue(maxsize=max_queue)
        self._pending = None
        self._pending_poll = None
        self._lock = threading.Lock()
        self._shutting_down = False
        self._tick_handle = unreal.register_slate_post_tick_callback(self._on_tick)
        try:
            unreal.register_python_shutdown_callback(self.shutdown)
        except Exception:
            pass

    # -- HTTP-thread side -------------------------------------------------

    def call(self, fn, timeout_s):
        if self._shutting_down:
            raise DispatcherBusy("dispatcher is shutting down")
        deadline = time.monotonic() + max(0.1, float(timeout_s))
        job = _Job(fn, deadline)
        try:
            self._queue.put(job, timeout=0.5)
        except queue.Full:
            raise DispatcherBusy("game-thread queue is full")
        if not job.done.wait(timeout_s):
            job.cancelled = True
            raise DispatcherTimeout(
                "game-thread job timed out after %.1fs" % float(timeout_s)
            )
        if job.error is not None:
            raise job.error
        return job.result

    # -- Game-thread side -------------------------------------------------

    def _on_tick(self, _delta_seconds):
        if self._shutting_down:
            return
        if self._pending is not None:
            self._continue_pending()
            return
        try:
            job = self._queue.get_nowait()
        except queue.Empty:
            return

        if job.cancelled:
            job.done.set()
            return

        if time.monotonic() > job.deadline:
            job.error = DispatcherTimeout("job expired before execution")
            job.done.set()
            return

        try:
            result = job.fn()
        except BaseException as exc:  # noqa: BLE001 - forward to HTTP thread
            job.error = exc
            job.done.set()
            return

        if isinstance(result, Pending):
            job.result = None
            self._pending = job
            self._pending_poll = result.poll
            return

        job.result = result
        job.done.set()

    def _continue_pending(self):
        job = self._pending
        poll = self._pending_poll
        if job.cancelled:
            self._pending = None
            self._pending_poll = None
            job.done.set()
            return
        if time.monotonic() > job.deadline:
            self._pending = None
            self._pending_poll = None
            job.error = DispatcherTimeout("job timed out while polling")
            job.done.set()
            return
        try:
            outcome = poll()
        except BaseException as exc:  # noqa: BLE001
            self._pending = None
            self._pending_poll = None
            job.error = exc
            job.done.set()
            return

        if isinstance(outcome, Done):
            self._pending = None
            self._pending_poll = None
            job.result = outcome.value
            job.done.set()

    def shutdown(self):
        if self._shutting_down:
            return
        self._shutting_down = True
        if self._pending is not None:
            try:
                self._pending.error = DispatcherTimeout("bridge shutting down")
            except Exception:
                pass
            self._pending.done.set()
            self._pending = None
            self._pending_poll = None
        while True:
            try:
                job = self._queue.get_nowait()
            except queue.Empty:
                break
            job.error = DispatcherTimeout("bridge shutting down")
            job.done.set()
        handle = self._tick_handle
        self._tick_handle = None
        if handle is not None and unreal is not None:
            try:
                unreal.unregister_slate_post_tick_callback(handle)
            except Exception:
                pass


class SynchronousDispatcher(object):
    """Test-only dispatcher used by the headless smoke script.

    It executes jobs on the calling thread and must never be used inside the
    editor (production always uses :class:`GameThreadDispatcher`).
    """

    def __init__(self):
        self._shutting_down = False

    def call(self, fn, timeout_s):
        if self._shutting_down:
            raise DispatcherBusy("dispatcher is shutting down")
        return fn()

    def shutdown(self):
        self._shutting_down = True
