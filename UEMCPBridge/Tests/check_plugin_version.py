"""Plugin version drift guard (no editor required).

``pluginVersion`` used to stay at 0.1.0 across releases, so installing a new
build could not be told apart from the old one.  This check fails whenever the
descriptor and the runtime constant disagree:

* ``UEMCPBridge.uplugin`` ``VersionName`` == ``settings.PLUGIN_VERSION``;
* ``Version`` is a positive integer (monotonic build counter);
* ``/health``'s ``pluginVersion`` (``BridgeServer.health_payload``) reports the
  same value.

Exit code 0 = PASS, 1 = FAIL.
"""

import json
import os
import sys
import tempfile

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(TESTS_DIR)
PYTHON_DIR = os.path.join(PLUGIN_DIR, "Content", "Python")
UPLUGIN_PATH = os.path.join(PLUGIN_DIR, "UEMCPBridge.uplugin")

if PYTHON_DIR not in sys.path:
    sys.path.insert(0, PYTHON_DIR)

from uemcp_bridge import settings  # noqa: E402


def main():
    failures = []
    with open(UPLUGIN_PATH, "r", encoding="utf-8") as handle:
        descriptor = json.load(handle)

    version_name = str(descriptor.get("VersionName", ""))
    version_code = descriptor.get("Version")
    runtime_version = str(settings.PLUGIN_VERSION)

    if version_name != runtime_version:
        failures.append(
            "VersionName %r != settings.PLUGIN_VERSION %r "
            "(bump both in the same change)" % (version_name, runtime_version)
        )
    if not isinstance(version_code, int) or version_code <= 0:
        failures.append("uplugin Version must be a positive integer, got %r" % (version_code,))

    health_version = None
    try:
        from uemcp_bridge import server as server_module  # noqa: E402

        class _DummyServer(object):
            ue_version = "0.0.0-test"
            port = 18778
            project_dir = tempfile.mkdtemp(prefix="uemcp_version_")
            project_file = "test.uproject"
            started_at = "1970-01-01T00:00:00Z"
            capabilities = {}
            rate_limiter = None
            settings = None

        payload = server_module.BridgeServer.health_payload(_DummyServer())
        health_version = str(payload.get("pluginVersion"))
        if health_version != runtime_version:
            failures.append(
                "/health pluginVersion %r != settings.PLUGIN_VERSION %r"
                % (health_version, runtime_version)
            )
    except Exception as exc:  # noqa: BLE001 - report, do not crash
        failures.append("cannot build /health payload: %s" % exc)

    print(
        "uplugin VersionName=%r Version=%r runtime=%r health=%r"
        % (version_name, version_code, runtime_version, health_version)
    )
    if failures:
        for failure in failures:
            print("FAIL: %s" % failure)
        print("PLUGIN_VERSION_RESULT FAIL")
        return 1
    print("PLUGIN_VERSION_RESULT PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
