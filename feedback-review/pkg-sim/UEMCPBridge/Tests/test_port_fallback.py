"""Port fallback self-check (no editor required).

Occupies 127.0.0.1:18778 with a plain listening socket, then starts a real
BridgeServer (stub ``unreal`` + synchronous dispatcher + temporary HOME) and
asserts that it binds 18779 instead of sharing 18778.

Exit code 0 = PASS, 1 = FAIL.  Exit code 2 = environment issue (18779 also
occupied by an unrelated process).
"""

import json
import os
import socket
import sys
import tempfile
import time
import urllib.request

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(TESTS_DIR)
PYTHON_DIR = os.path.join(PLUGIN_DIR, "Content", "Python")

HOME_DIR = tempfile.mkdtemp(prefix="uemcp_port_home_")
PROJECT_DIR = tempfile.mkdtemp(prefix="uemcp_port_project_")
STUB_DIR = tempfile.mkdtemp(prefix="uemcp_port_stub_")

os.environ["USERPROFILE"] = HOME_DIR
os.environ["HOME"] = HOME_DIR
os.environ.pop("UEMCP_BRIDGE_PORT", None)
os.environ.pop("UEMCP_BRIDGE_TOKEN_FILE", None)

with open(os.path.join(STUB_DIR, "unreal.py"), "w", encoding="utf-8") as handle:
    handle.write(
        "class Paths:\n"
        "    @staticmethod\n"
        "    def project_dir():\n"
        "        return %r\n"
        "    @staticmethod\n"
        "    def project_saved_dir():\n"
        "        return %r\n"
        "class SystemLibrary:\n"
        "    @staticmethod\n"
        "    def get_engine_version():\n"
        "        return '5.4.4-stub'\n"
        "    @staticmethod\n"
        "    def is_editor():\n"
        "        return True\n"
        "class AssetRegistryHelpers:\n"
        "    pass\n"
        "def register_slate_post_tick_callback(fn):\n"
        "    return 1\n"
        "def unregister_slate_post_tick_callback(handle):\n"
        "    pass\n"
        "def register_python_shutdown_callback(fn):\n"
        "    pass\n"
        "def log(message):\n"
        "    pass\n"
        "def log_error(message):\n"
        "    pass\n"
        % (PROJECT_DIR + os.sep, PROJECT_DIR + os.sep)
    )

sys.path.insert(0, STUB_DIR)
sys.path.insert(0, PYTHON_DIR)

from uemcp_bridge.dispatcher import SynchronousDispatcher  # noqa: E402
from uemcp_bridge.server import BridgeServer  # noqa: E402


def _port_free(port):
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        try:
            probe.close()
        except OSError:
            pass


def main():
    if not _port_free(18779):
        print("PORT_FALLBACK_RESULT SKIP: 18779 is already occupied in this environment")
        return 2

    blocker = None
    if _port_free(18778):
        blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # A socket that was just closed (the probe above, or the previous test
        # in a suite run) can keep the port reserved for a few milliseconds on
        # Windows; retry briefly instead of failing on a transient bind error.
        bound = False
        for _attempt in range(20):
            try:
                blocker.bind(("127.0.0.1", 18778))
                blocker.listen(1)
                bound = True
                break
            except OSError:
                time.sleep(0.05)
        if not bound:
            try:
                blocker.close()
            except OSError:
                pass
            blocker = None
            if _port_free(18778):
                print("PORT_FALLBACK_RESULT FAIL: cannot occupy 127.0.0.1:18778")
                return 1
            # Something else grabbed the port in the meantime: that is the
            # production scenario, keep going with the external listener.
            print("BLOCKER already present on 127.0.0.1:18778 (reusing it)")
        else:
            print("BLOCKER created on 127.0.0.1:18778")
    else:
        # A real editor (or another bridge) already owns 18778.  That is the
        # production scenario we want to exercise; reuse the existing
        # listener instead of failing or killing the process.
        print("BLOCKER already present on 127.0.0.1:18778 (reusing it)")

    try:
        server = BridgeServer.instance()
        started = server.start(dispatcher=SynchronousDispatcher())
        if not started:
            print("PORT_FALLBACK_RESULT FAIL: bridge did not start")
            return 1

        try:
            print("BRIDGE_BOUND port=%d" % server.port)
            if server.port != 18779:
                print(
                    "PORT_FALLBACK_RESULT FAIL: expected 18779, got %d" % server.port
                )
                return 1
            url = "http://127.0.0.1:%d/health" % server.port
            with urllib.request.urlopen(url, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if payload.get("app") != "uemcp-bridge":
                print("PORT_FALLBACK_RESULT FAIL: bad /health %r" % payload)
                return 1
            print("HEALTH port=%d ok=%s" % (payload.get("port"), payload.get("ok")))
            print("PORT_FALLBACK_RESULT PASS")
            return 0
        finally:
            server.stop()
    finally:
        if blocker is not None:
            try:
                blocker.close()
            except OSError:
                pass


if __name__ == "__main__":
    sys.exit(main())
