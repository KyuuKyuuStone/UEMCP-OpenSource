r"""Probe #3: can the Asset Registry expose Blueprint parent class / other tags?

Run headless:
  UnrealEditor-Cmd.exe <uproject> -run=pythonscript -script=<this file> -unattended -nop4 -nosplash -nullrhi
Result: %TEMP%\uemcp_bp_probe3.json
"""

import json
import os
import tempfile
import traceback

OUT = os.environ.get("UEMCP_BP_PROBE_OUT") or os.path.join(
    tempfile.gettempdir(), "uemcp_bp_probe3.json"
)

TARGETS = [
    "/Game/StarterContent/Blueprints/Blueprint_CeilingLight",
    "/Game/StarterContent/Blueprints/Blueprint_Effect_Fire",
]
results = {"targets": {}, "probes": {}}


def attempt(fn):
    try:
        return {"ok": True, "value": repr(fn())[:300]}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": "%s: %s" % (exc.__class__.__name__, str(exc)[:300])}


def main():
    import unreal

    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    results["registry_class"] = attempt(lambda: registry.get_class().get_name())

    for path in TARGETS:
        entry = {}
        pkg = path
        name = path.rsplit("/", 1)[1]
        data = None
        got = attempt(
            lambda p=pkg, n=name: registry.get_assets_by_package_name(p)
        )
        entry["get_assets_by_package_name"] = got
        try:
            assets = registry.get_assets_by_package_name(pkg)
            for candidate in assets or []:
                if str(candidate.asset_name) == name:
                    data = candidate
                    break
            if data is None and assets:
                data = assets[0]
        except Exception:
            data = None

        if data is not None:
            entry["asset_data"] = {
                "asset_name": attempt(lambda: str(data.asset_name)),
                "package_name": attempt(lambda: str(data.package_name)),
                "asset_class": attempt(lambda: str(data.asset_class)),
                "tags_and_values": attempt(lambda: dict(data.get_tags_and_values())),
                "tag_keys": attempt(lambda: list(dict(data.get_tags_and_values()).keys())),
            }
            for tag in ("ParentClass", "GeneratedClass", "BlueprintType", "NativeParentClass", "IsBlueprint"):
                entry["tag_%s" % tag] = attempt(lambda t=tag: str(data.get_tag_value(t)))
        results["targets"][path] = entry

    with open(OUT, "w", encoding="utf-8") as handle:
        json.dump(results, handle, ensure_ascii=False, indent=2)
    unreal.log("[UEMCP] bp probe3 written to %s" % OUT)


try:
    main()
except Exception as exc:  # noqa: BLE001
    results["fatal"] = "%s: %s" % (exc.__class__.__name__, exc)
    results["traceback"] = traceback.format_exc()
    with open(OUT, "w", encoding="utf-8") as handle:
        json.dump(results, handle, ensure_ascii=False, indent=2)
