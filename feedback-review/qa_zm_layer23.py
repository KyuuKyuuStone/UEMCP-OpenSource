# -*- coding: utf-8 -*-
"""ZM 层②+③核验（全部只读）。
层②：证据索引中指向 Plugins/UEMCPBridge/** 的 31 条引文 → 对照本仓库 HEAD，
      区分 命中 / 版本漂移（token 在但行号不同）/ HEAD缺失。
层③：NEW 目录源码文件抽查 ≤3（主管建议 FloodPeak.cpp / FloodCmdHandler.cpp + 自选 DefaultGame.ini），
      每文件记录 SHA256 + 读取时间戳；文件锁/不存在 → 记无法核验并跳过。
另：环境变更证据（旧根不存在 / NEW 内 Saved\\UEMCP 是否存在）。
"""
import hashlib
import io
import os
import re
import sys
import time

REPO = r"C:\UE5_P\5.4\UEMCP"
BRIDGE = os.path.join(REPO, "UEMCPBridge")
DESK = r"C:\Users\Administrator\Desktop\UEMCP遇到的问题\ZM项目组——UEMCP_使用反馈"
NEW = r"C:\UE5_P\5.4\ZMCPP_54_NEW"
OLD = r"C:\UE5_P\5.4\ZMCPP_54"


def now():
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


def sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest().lower()


def read_lines(path):
    with io.open(path, encoding="utf-8", errors="replace") as f:
        return f.read().splitlines()


def load_index():
    idx = {}
    with io.open(os.path.join(DESK, "证据索引.md"), encoding="utf-8") as f:
        for m in re.finditer(r"^\|\s*(E-\d{3})\s*\|\s*([^|]+?)\s*\|\s*([^:]+):(\d+)\s*\|\s*([^|]+?)\s*\|",
                             f.read(), re.M):
            idx[m.group(1)] = {"claim": m.group(2), "path": m.group(3).strip().replace("\\", "/"),
                               "lineno": int(m.group(4)), "token": m.group(5).strip()}
    return idx


def check_ptr(base, relpath, lineno, token):
    """返回 (状态, 详情)。base 下相对路径。"""
    path = os.path.join(base, relpath.replace("/", os.sep))
    if not os.path.isfile(path):
        return "ABSENT_FILE", path
    try:
        lines = read_lines(path)
    except OSError as exc:
        return "LOCKED_OR_ERR", "%r" % exc
    hit = token.lower() in (lines[lineno - 1].lower() if 0 < lineno <= len(lines) else "")
    if hit:
        return "MATCH", "%s:%d" % (relpath, lineno)
    found = [i + 1 for i, ln in enumerate(lines) if token.lower() in ln.lower()]
    if found:
        return "TOKEN_DRIFT", "token 在 HEAD 行 %s（对方引 %d 行）" % (found[:6], lineno)
    return "TOKEN_ABSENT", "token 在该文件 HEAD 版本 0 命中（文件 %d 行）" % len(lines)


def main():
    idx = load_index()

    # ---------- 版本基线 ----------
    upl = os.path.join(BRIDGE, "UEMCPBridge.uplugin")
    m = re.search(r'"VersionName"\s*:\s*"([^"]+)"', open(upl, encoding="utf-8").read())
    print("REPO_HEAD_PLUGINVERSION|%s|对方环境=0.1.4" % (m.group(1) if m else "?"))
    print("REPO_README_SHA256|%s" % sha256(os.path.join(BRIDGE, "README.md")))

    # ---------- 层② ----------
    stats = {}
    for eid in sorted(idx):
        rec = idx[eid]
        if not rec["path"].startswith("Plugins/UEMCPBridge/"):
            continue
        rel = rec["path"][len("Plugins/UEMCPBridge/"):]
        status, detail = check_ptr(BRIDGE, rel, rec["lineno"], rec["token"])
        stats[status] = stats.get(status, 0) + 1
        print("L2|%s|%s|%s|%d|%s|%s" % (eid, status, rec["path"], rec["lineno"], rec["token"], detail))
    print("L2_SUMMARY|%s" % stats)

    # ---------- 环境变更 ----------
    print("ENV|OLD_ZMCPP_54_exists=%s (%s)" % (os.path.exists(OLD), "os error 2 若 False"))
    print("ENV|NEW_exists=%s" % os.path.isdir(NEW))
    print("ENV|NEW_Saved_UEMCP_exists=%s" % os.path.isdir(os.path.join(NEW, "Saved", "UEMCP")))

    # ---------- 层③ ----------
    targets = [
        ("E-025/E-029/E-039", "Plugins/ZS_WebAPI/Source/ZS_WebAPI/Private/CommonAPI/FloodCmdHandler.cpp",
         [(48, "GetPeakModelId"), (86, "AddUniqueDynamic"), (96, "SendMessage(ResponseMsg)")]),
        ("E-046", "Plugins/ZS_Flood/Source/ZS_Flood/Private/FloodPeak.cpp",
         [(34, "SetCameraFollow_Implementation")]),
        ("E-047", "Config/DefaultGame.ini", [(98, "/Game/Sequence")]),
    ]
    for eids, rel, checks in targets:
        path = os.path.join(NEW, rel.replace("/", os.sep))
        stamp = now()
        if not os.path.isfile(path):
            print("L3|%s|%s|ABSENT_FILE|read_attempt=%s" % (eids, rel, stamp))
            continue
        try:
            digest = sha256(path)
            lines = read_lines(path)
        except OSError as exc:
            print("L3|%s|%s|LOCKED_OR_ERR|%r|read_attempt=%s" % (eids, rel, exc, stamp))
            continue
        print("L3|%s|%s|READ_OK|sha256=%s|lines=%d|read_time=%s" % (eids, rel, digest, len(lines), stamp))
        for lineno, token in checks:
            text = lines[lineno - 1] if 0 < lineno <= len(lines) else ""
            hit = token.lower() in text.lower()
            near = [i + 1 for i, ln in enumerate(lines) if token.lower() in ln.lower()][:6]
            note = "MATCH" if hit else ("DRIFT->%s" % near if near else "TOKEN_ABSENT")
            print("L3_CHECK|%s|%s:%d|%s|%s|%s" % (eids, rel, lineno, token, note, text.strip()[:90]))
    print("L3_DISCLAIMER|迁移后目录 ZMCPP_54_NEW（ak.uproject），非反馈时点原始证据环境，内容可能已变更；引文不符记『迁移后内容已变更』而非『反馈不实』")
    return 0


if __name__ == "__main__":
    sys.exit(main())
