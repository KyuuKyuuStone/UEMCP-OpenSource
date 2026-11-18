# -*- coding: utf-8 -*-
"""ZM 证据抽查（只读）。口径复刻 ZM 组自述的 verify_reflection.py 三件事：
path 存在、该行非空、该行文本含 token。仅读取，不写任何工程文件。
"""
import io
import os
import sys

ROOT = r"C:\UE5_P\5.4\ZMCPP_54"

# 抽查样本：覆盖 README / 运行时 health / 像素差 / C++ 源码 / 会话日志 / ini / svn 笔记 / 插件 py handler
SPOT = [
    ("E-001", "1.1 Bridge 只绑回环地址", r"Plugins\UEMCPBridge\README.md", 108, "127.0.0.1"),
    ("E-007", "1.2 实测端口 18790", r"Saved\UEMCP\bridge-health.json", 1, "18790"),
    ("E-015", "1.4 场景 3：开闸 8s 像素差 8.004", r"Saved\UEMCP\spillwayfix\pixel_diff_cross.json", 38, "8.004"),
    ("E-023", "P0-1 崩溃现象 0x0 访问违例", r"Saved\UEMCP\floodpeak\bugs.md", 71, "EXCEPTION_ACCESS_VIOLATION"),
    ("E-025", "P0-1 崩溃点 GetPeakModelId 未判空", r"Plugins\ZS_WebAPI\Source\ZS_WebAPI\Private\CommonAPI\FloodCmdHandler.cpp", 48, "GetPeakModelId"),
    ("E-034", "P0-4 探针 valueIsNone=true", r"Saved\UEMCP\floodpeak\session.log", 52, "valueIsNone"),
    ("E-044", "P2-1 BFS 节点预算硬编码", r"Plugins\UEMCPBridge\Content\Python\uemcp_bridge\handlers\assets.py", 19, "_MAX_BFS_NODES"),
    ("E-047", "P2-4 cook 目录已含 /Game/Sequence", r"Config\DefaultGame.ini", 98, "/Game/Sequence"),
    ("E-078", "5.7 工作副本 modified 1866 条", r"Saved\UEMCP\svn\06_notes.txt", 33, "1866"),
    ("E-081", "5.7 svn log 鉴权失败", r"Saved\UEMCP\svn\06_notes.txt", 67, "E170013"),
]


def check_one(relpath, lineno, token):
    path = os.path.join(ROOT, relpath)
    if not os.path.isfile(path):
        return "FAIL", "path not found"
    with io.open(path, encoding="utf-8", errors="replace") as fh:
        lines = fh.read().splitlines()
    if lineno < 1 or lineno > len(lines):
        return "FAIL", "line %d out of range (file has %d lines)" % (lineno, len(lines))
    text = lines[lineno - 1]
    if not text.strip():
        return "FAIL", "line empty"
    if token.lower() not in text.lower():
        return "FAIL", "token %r not in line: %s" % (token, text[:160])
    return "PASS", "line %d: %s" % (lineno, text[:160])


def main():
    npass = 0
    for eid, claim, relpath, lineno, token in SPOT:
        status, detail = check_one(relpath, lineno, token)
        npass += status == "PASS"
        print("SPOT|%s|%s|%s|%d|%s|%s" % (eid, status, claim, lineno, token, detail))
    print("SPOT_SUMMARY|checked=%d|pass=%d|fail=%d" % (len(SPOT), npass, len(SPOT) - npass))
    return 0 if npass == len(SPOT) else 2


if __name__ == "__main__":
    sys.exit(main())
