"""Inject ``EngineVersion`` into ``UEMCPBridge.uplugin`` for packaging.

The checked-in plugin descriptor does not pin an engine version so the same
source tree loads in any UE5 editor (5.4, 5.7, ...).  Distribution builds that
want an explicit version should stamp it with this script instead of editing
the file by hand:

    python UEMCPBridge/Tools/stamp_uplugin.py --engine-root "C:\\Program Files\\Epic Games\\UE_5.7" --out dist/UEMCPBridge.uplugin

    python UEMCPBridge/Tools/stamp_uplugin.py --engine 5.7.4 --inplace

Standard library only (the plugin must never grow a third-party dependency).
"""

import argparse
import json
import re
import sys
from pathlib import Path

DEFAULT_UPLUGIN = Path(__file__).resolve().parent.parent / "UEMCPBridge.uplugin"

_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


def engine_version_from_install(engine_root):
    """Read ``Engine/Build/Build.version`` and return ``"Major.Minor.Patch"``."""
    build_version = Path(engine_root).resolve() / "Engine" / "Build" / "Build.version"
    if not build_version.is_file():
        raise ValueError("Build.version not found: %s" % build_version)
    with open(build_version, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    try:
        return "%d.%d.%d" % (
            int(data["MajorVersion"]),
            int(data["MinorVersion"]),
            int(data.get("PatchVersion", 0)),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Build.version is missing version fields: %s" % exc)


def stamp_descriptor(descriptor, engine_version):
    """Return a copy of ``descriptor`` with ``EngineVersion`` set."""
    if not isinstance(descriptor, dict):
        raise ValueError("plugin descriptor must be a JSON object")
    if not isinstance(engine_version, str) or not _VERSION_RE.match(engine_version):
        raise ValueError("engine version must look like '5.7.4', got %r" % (engine_version,))
    stamped = dict(descriptor)
    stamped["EngineVersion"] = engine_version
    return stamped


def load_descriptor(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def dump_descriptor(descriptor):
    return json.dumps(descriptor, ensure_ascii=False, indent="\t") + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--engine", help="engine version to stamp, e.g. 5.7.4")
    source.add_argument(
        "--engine-root",
        help="engine install root; the version is read from Engine/Build/Build.version",
    )
    parser.add_argument("--in", dest="input_path", default=str(DEFAULT_UPLUGIN))
    parser.add_argument("--out", dest="output_path", help="write the stamped file here")
    parser.add_argument(
        "--inplace",
        action="store_true",
        help="overwrite --in (refused when the source is the repository descriptor "
        "unless --force is also given)",
    )
    parser.add_argument("--force", action="store_true", help="allow --inplace on the repo file")
    args = parser.parse_args(argv)

    try:
        if args.engine:
            engine_version = args.engine
        elif args.engine_root:
            engine_version = engine_version_from_install(args.engine_root)
        else:
            parser.error("one of --engine or --engine-root is required")

        input_path = Path(args.input_path).resolve()
        descriptor = load_descriptor(input_path)
        stamped = stamp_descriptor(descriptor, engine_version)
        payload = dump_descriptor(stamped)

        if args.inplace:
            if input_path == DEFAULT_UPLUGIN.resolve() and not args.force:
                parser.error(
                    "--inplace on the repository descriptor would re-pin the engine "
                    "version; use --out <path> (or --force)"
                )
            target = input_path
        elif args.output_path:
            target = Path(args.output_path).resolve()
        else:
            sys.stdout.write(payload)
            return 0

        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(payload)
        print("STAMPED %s EngineVersion=%s" % (target, engine_version))
        return 0
    except (OSError, ValueError) as exc:
        sys.stderr.write("stamp_uplugin: %s\n" % exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
