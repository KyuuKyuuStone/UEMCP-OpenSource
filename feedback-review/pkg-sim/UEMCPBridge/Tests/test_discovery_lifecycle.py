"""Regression test for DEFECT-5: discovery file lifecycle (no editor).

Covers:
* normal ``stop()`` removes both discovery files;
* stale files (dead PID) are removed on the next start;
* an unremovable file can be marked ``stale``;
* ``atexit`` fallback is registered.
"""

import json
import os
import sys
import tempfile

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(TESTS_DIR)
PYTHON_DIR = os.path.join(PLUGIN_DIR, "Content", "Python")

HOME_DIR = tempfile.mkdtemp(prefix="uemcp_disc_home_")
PROJECT_DIR = tempfile.mkdtemp(prefix="uemcp_disc_project_")
STUB_DIR = tempfile.mkdtemp(prefix="uemcp_disc_stub_")

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

from uemcp_bridge import discovery  # noqa: E402
from uemcp_bridge.dispatcher import SynchronousDispatcher  # noqa: E402
from uemcp_bridge.server import BridgeServer  # noqa: E402


def _read(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def main():
    failures = []
    project_file = discovery.project_file_path(PROJECT_DIR)
    latest_file = discovery.latest_file_path()

    if not discovery.pid_alive(os.getpid()):
        failures.append("pid_alive(current process) returned False")

    server = BridgeServer.instance()
    if not server.start(dispatcher=SynchronousDispatcher()):
        print("DISCOVERY_RESULT FAIL: bridge did not start")
        return 1

    try:
        if not os.path.isfile(project_file):
            failures.append("project discovery file missing after start")
        if not os.path.isfile(latest_file):
            failures.append("latest discovery file missing after start")
        if not server._atexit_registered:
            failures.append("atexit fallback was not registered")
        if os.path.isfile(project_file):
            record = _read(project_file)
            if record.get("pid") != os.getpid():
                failures.append("discovery pid mismatch: %r" % record.get("pid"))
            print("DISCOVERY_STARTED port=%s pid=%s schema=%s" % (
                record.get("port"), record.get("pid"), record.get("schemaVersion")))

        # mark_stale must add explicit flags for unremovable files.
        marked = discovery.mark_stale(server._record, "test_cleanup_failure")
        if not marked:
            failures.append("mark_stale did not touch any file")
        else:
            record = _read(project_file)
            if not record.get("stale") or record.get("staleReason") != "test_cleanup_failure":
                failures.append("stale flags missing: %r" % record)
            else:
                print("MARK_STALE ok reason=%s" % record.get("staleReason"))
    finally:
        server.stop()

    if os.path.isfile(project_file):
        failures.append("project discovery file still exists after stop")
    if os.path.isfile(latest_file):
        failures.append("latest discovery file still exists after stop")
    if not os.path.isfile(project_file) and not os.path.isfile(latest_file):
        print("DISCOVERY_STOP_CLEANUP ok")

    # Stale cleanup on next start: dead PID file must be removed.
    stale_payload = {
        "schemaVersion": 1,
        "pid": 999999,
        "token": "dead-token",
        "projectDir": discovery.normalize_project_dir(PROJECT_DIR),
        "port": 18778,
    }
    discovery.write_json_atomic(project_file, stale_payload)
    discovery.write_json_atomic(latest_file, stale_payload)
    removed = discovery.cleanup_stale(PROJECT_DIR)
    if os.path.isfile(project_file) or os.path.isfile(latest_file):
        failures.append("stale discovery files were not removed")
    else:
        print("STALE_CLEANUP ok removed=%d" % len(removed))

    if failures:
        for failure in failures:
            print("FAIL: %s" % failure)
        print("DISCOVERY_RESULT FAIL")
        return 1
    print("DISCOVERY_RESULT PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
