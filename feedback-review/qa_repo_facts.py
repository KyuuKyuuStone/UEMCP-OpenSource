# -*- coding: utf-8 -*-
"""固化仓内代码/文档事实（只读），作为覆盖映射与冒烟矩阵的日志支撑。"""
import hashlib
import io
import os

WS = r"C:\UE5_P\5.4\UEMCP"


def rd(rel):
    with io.open(os.path.join(WS, rel), "r", encoding="utf-8", errors="replace") as f:
        return f.read().splitlines()


def sha(rel):
    with open(os.path.join(WS, rel), "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def sl(lines, a, b):
    for i in range(max(1, a), min(len(lines), b) + 1):
        print("  %4d| %s" % (i, lines[i - 1]))


print("REPO_FACTS RUN 2026-11-17 by QA (只读; HEAD 工作区)")

up = rd(os.path.join("UEMCPBridge", "UEMCPBridge.uplugin"))
print("UPLUGIN|VersionName=%s|sha256=%s" % (
    [l for l in up[:8] if "VersionName" in l][0].strip(), sha(os.path.join("UEMCPBridge", "UEMCPBridge.uplugin"))))

rpy = rd(r"UEMCPBridge\Content\Python\uemcp_bridge\rpc.py")
print("RPC_PY|sha256=%s|注册块 45-70:" % sha(r"UEMCPBridge\Content\Python\uemcp_bridge\rpc.py"))
sl(rpy, 45, 70)

rp = rd("UEMCPBridge\\README.md")
print("README|sha256=%s|lines=%d" % (sha("UEMCPBridge\\README.md"), len(rp)))
print("README_L29| %s" % rp[28])
m5 = [i + 1 for i, l in enumerate(rp) if l.startswith("| `ue_")]
print("README_S5_TOOL_ROWS|count=%d|lines=%s" % (len(m5), m5))
s102 = [i + 1 for i, l in enumerate(rp) if ("check_" in l or "test_" in l) and i > 195 and i < 240]
print("README_S102_CHECK_ROWS|count=%d|lines=%s" % (len(s102), s102))
for ln in (207, 208, 209, 234, 235, 236, 243, 244, 245, 246, 247):
    if ln <= len(rp):
        print("README_L%d| %s" % (ln, rp[ln - 1][:160]))

sv = rd(r"UEMCPBridge\Content\Python\uemcp_bridge\server.py")
print("SERVER_PY|/health 555-578:")
sl(sv, 555, 578)

ty = rd(r"uemcp\packages\shared\src\types.ts")
print("TYPES_TS|AuditRecord 66-92:")
sl(ty, 66, 92)

au = rd(r"uemcp\packages\server\src\audit.ts")
print("AUDIT_TS|1-32:")
sl(au, 1, 32)

sm = rd(r"UEMCPBridge\Tests\SMOKE-REAL-ENGINE.md")
print("SMOKE_DOC|L73 8-RPC 行:")
for i, l in enumerate(sm):
    if l.startswith("8 个 RPC"):
        print("  %4d| %s" % (i + 1, l[:400]))
        break

tests = sorted(os.listdir(os.path.join(WS, "UEMCPBridge", "Tests")))
print("TESTS_DIR|%s" % tests)
print("REPO_FACTS_DONE")
