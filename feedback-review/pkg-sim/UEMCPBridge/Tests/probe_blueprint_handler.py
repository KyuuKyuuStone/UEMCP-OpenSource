r"""Probe #4: call the real blueprint.query handler inside the editor.

Verifies that the Asset Registry fallback actually produces parentClass /
generatedClass / graphs on a real Blueprint, and that the empty-success guard
no longer fires when tags are available.

Run headless:
  UnrealEditor-Cmd.exe <uproject> -run=pythonscript -script=<this file> -unattended -nop4 -nosplash -nullrhi
Result: %TEMP%\uemcp_bp_handler.json
"""

import json
import os
import sys
import tempfile
import traceback

PLUGIN_PY = os.environ.get(
    "UEMCP_PLUGIN_PY",
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "Content", "Python",
    ),
)
OUT = os.environ.get("UEMCP_BP_PROBE_OUT") or os.path.join(
    tempfile.gettempdir(), "uemcp_bp_handler.json"
)

TARGETS = [
    "/Game/StarterContent/Blueprints/Blueprint_CeilingLight",
    "/Game/StarterContent/Blueprints/Blueprint_Effect_Fire",
]

results = {"plugin_py": PLUGIN_PY, "cases": []}


class _Settings(object):
    allow_write = False
    allow_console = False
    allow_exec = False
    request_timeout_ms = 30000
    search_timeout_ms = 20000
    console_allowlist = ()


class _Server(object):
    settings = _Settings()


def run_case(module, path):
    case = {"blueprintPath": path}
    try:
        outcome = module.handle(
            _Server(),
            {
                "action": "query",
                "blueprintPath": path,
                "include": ["parent", "variables", "graphs", "compileState"],
            },
        )
        case["ok"] = True
        case["data"] = outcome.data
        case["warnings"] = outcome.warnings
    except Exception as exc:  # noqa: BLE001 - RpcError carries the contract code
        case["ok"] = False
        case["error"] = "%s: %s" % (exc.__class__.__name__, str(exc)[:300])
        for attr in ("code", "details"):
            if hasattr(exc, attr):
                case[attr] = getattr(exc, attr)
    return case


def main():
    if PLUGIN_PY not in sys.path:
        sys.path.insert(0, PLUGIN_PY)
    import uemcp_bridge.handlers.blueprints as module

    for path in TARGETS:
        results["cases"].append(run_case(module, path))

    with open(OUT, "w", encoding="utf-8") as handle:
        json.dump(results, handle, ensure_ascii=False, indent=2, default=str)
    try:
        import unreal

        unreal.log("[UEMCP] bp handler probe written to %s" % OUT)
    except Exception:
        pass


try:
    main()
except Exception as exc:  # noqa: BLE001
    results["fatal"] = "%s: %s" % (exc.__class__.__name__, exc)
    results["traceback"] = traceback.format_exc()
    with open(OUT, "w", encoding="utf-8") as handle:
        json.dump(results, handle, ensure_ascii=False, indent=2, default=str)
