# QA script (task 0faacf99): CMD 3.8 coverage scan + feedback zero-write manifest.
# READ-ONLY on repo/Tests/ and Desktop feedback dirs. Prints to stdout for log capture.
import hashlib
import json
import re
import sys
import time
from pathlib import Path

REPO = Path(r"C:\UE5_P\5.4\UEMCP")
TESTS = REPO / "UEMCPBridge" / "Tests"
LOGS = REPO / "feedback-review" / "logs"
DESK = Path(r"C:\Users\Administrator\Desktop\UEMCP遇到的问题")

METHODS = [
    "bridge.ping", "bridge.capabilities", "editor.status", "actor.query",
    "actor.edit", "level.control", "asset.search", "material.params",
    "viewport.capture", "console.command", "python.exec", "blueprint.query",
    "pie.control", "object.reflect", "object.call", "log.query",
]

# SMOKE L73 eight read-only RPCs (pinned in qa-repo-facts-20261117.log)
SMOKE8 = {
    "bridge.ping", "bridge.capabilities", "editor.status", "actor.query",
    "asset.search", "level.control", "material.params", "viewport.capture",
}

# method -> handler module name (rpc.py:51-68 HANDLERS mapping, read 2026-11-17).
# bridge.ping/capabilities are inline functions in rpc.py (no handler module).
MOD_OF = {
    "editor.status": "status", "actor.query": "actors", "actor.edit": "actors",
    "level.control": "levels", "asset.search": "assets", "material.params": "materials",
    "viewport.capture": "viewport", "console.command": "console",
    "python.exec": "python_exec", "blueprint.query": "blueprints",
    "pie.control": "pie", "object.reflect": "objects", "object.call": "objects",
    "log.query": "logs",
}


def imports_mod(body: str, mod: str) -> bool:
    for line in body.splitlines():
        if "import" in line and re.search(r"(?<![a-z0-9_])" + mod + r"(?![a-z0-9_])", line):
            return True
    return False


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def part1_coverage():
    print("=" * 20, "PART1 CMD3.8 COVERAGE SCAN (v2)", "=" * 20)
    tests = sorted(p for p in TESTS.glob("*.py") if re.match(r"^(check_|test_)", p.name))
    print(f"OFFLINE_TEST_COUNT: {len(tests)}")
    bodies = {p.name: p.read_text(encoding="utf-8", errors="replace") for p in tests}
    # audit column from collect recompute (CMD env 0.1.0/0.1.4), JSON line format
    rpc_log = LOGS / "qa-collect-recompute-20261117.log"
    audit_counts = {}
    for line in rpc_log.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("RPCMETHOD_DIST|"):
            audit_counts = json.loads(line.split("|", 1)[1])
    print(f"AUDIT_DIST_PARSED: {audit_counts}")
    print("NOTE selfcheck Y = method-string literal [..] or handler-module import (..)"
          " per rpc.py:51-68; audit_cnt from CMD 0.1.0/0.1.4 history, 0.1.5=0 records")
    empty3 = []
    for meth in METHODS:
        str_refs = sorted(n for n, b in bodies.items() if meth in b)
        mod = MOD_OF.get(meth)
        mod_only = sorted(n for n, b in bodies.items()
                          if mod and meth not in b and imports_mod(b, mod))
        smoke = "Y" if meth in SMOKE8 else "-"
        acount = audit_counts.get(meth, 0)
        covered = bool(str_refs or mod_only)
        all3empty = (not covered and smoke == "-" and acount == 0)
        if all3empty:
            empty3.append(meth)
        print(f"METHOD[{meth}] selfcheck={'Y' if covered else 'N'} str={str_refs}"
              f" mod_only={mod_only} smoke8={smoke} audit_cnt={acount}"
              f" {'ALL3_EMPTY' if all3empty else ''}")
    print(f"PART1_SUMMARY all3_empty={empty3}")


def part2_manifest():
    print("=" * 20, "PART2 FEEDBACK ZERO-WRITE MANIFEST (v2)", "=" * 20)
    print(f"NOW: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("QA_FIRST_TOUCH_ZM: 2026-11-17 09:24 (qa-zm-spotcheck header)")
    # baselines: 6 CMD files parsed live from qa-hash-check-20261117.log (recorded_sha= fields),
    # 2 ZM files from qa-zm-layer1 log (sha 1c9bf345.../e1d0e489..., prefix compare here)
    base = {}
    hc = (LOGS / "qa-hash-check-20261117.log").read_text(encoding="utf-8", errors="replace")
    for line in hc.splitlines():
        if "HASH_MATCH" in line:
            parts = line.split("|")
            name = parts[0].replace("\\", "/")
            sha = [p for p in parts if p.startswith("recorded_sha=")][0].split("=", 1)[1]
            base["CMD构建发布组_UEMCP反馈/" + name] = sha
    base["ZM项目组——UEMCP_使用反馈/UEMCP使用反馈.md"] = "1c9bf345"
    base["ZM项目组——UEMCP_使用反馈/证据索引.md"] = "e1d0e489"
    print(f"BASELINE_KEYS: {sorted(base.keys())}")
    roots = [DESK / "CMD构建发布组_UEMCP反馈", DESK / "ZM项目组——UEMCP_使用反馈"]
    n = 0
    mismatch = 0
    for root in roots:
        for p in sorted(root.rglob("*")):
            if p.is_dir():
                continue
            n += 1
            rel = str(p.relative_to(DESK)).replace("\\", "/")
            st = p.stat()
            h = sha256(p)
            tag = "NO_BASELINE"
            if rel in base and base[rel]:
                tag = "BASELINE_MATCH" if h.startswith(base[rel]) else "BASELINE_MISMATCH!"
                if tag.endswith("!"):
                    mismatch += 1
            mt = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime))
            pre_qa = "PRE_QA_READ" if st.st_mtime < time.mktime(time.strptime("2026-11-17 09:24:00", "%Y-%m-%d %H:%M:%S")) else "AFTER!"
            print(f"FILE[{rel}] size={st.st_size} mtime={mt} {pre_qa} sha256={h} {tag}")
    print(f"PART2_SUMMARY files={n} baseline_mismatch={mismatch}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    part1_coverage()
    part2_manifest()
