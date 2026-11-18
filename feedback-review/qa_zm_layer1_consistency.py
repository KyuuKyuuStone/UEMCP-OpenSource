# -*- coding: utf-8 -*-
"""ZM 层①：反馈包内部一致性核验（只读，不写反馈目录）。
交叉核对：UEMCP使用反馈.md ↔ 证据索引.md ↔ findings.json ↔ 00_checks.txt ↔ 05_evidence_check.txt
外加：桌面落盘文件的 SHA256 与 00_checks.txt [5] 记录值比对。
"""
import hashlib
import io
import json
import os
import re

DESK = r"C:\Users\Administrator\Desktop\UEMCP遇到的问题\ZM项目组——UEMCP_使用反馈"
AI = os.path.join(DESK, "UEMCP_AI_REVIEW")

def sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest().upper()

def line(tag, msg):
    print("%s|%s" % (tag, msg))

def main():
    # ---------- 解析证据索引.md ----------
    idx = {}
    with io.open(os.path.join(DESK, "证据索引.md"), encoding="utf-8") as f:
        for m in re.finditer(r"^\|\s*(E-\d{3})\s*\|\s*([^|]+?)\s*\|\s*([^:]+):(\d+)\s*\|\s*([^|]+?)\s*\|",
                             f.read(), re.M):
        # 每行: 编号/断言/path:line/token
            idx[m.group(1)] = {"claim": m.group(2), "path": m.group(3).strip(),
                               "lineno": int(m.group(4)), "token": m.group(5).strip()}
    line("IDX_PARSE", "rows=%d expect=82 %s" % (len(idx), "OK" if len(idx) == 82 else "MISMATCH"))

    # ---------- 解析 00_checks.txt [1] PASS 列表 ----------
    with io.open(os.path.join(DESK, "00_checks.txt"), encoding="utf-8") as f:
        chk = f.read()
    pass_rows = {k: (p, int(n)) for k, p, n in re.findall(r"PASS (E-\d{3}) (\S+):(\d+)", chk)}
    mism = []
    for eid, (p, ln) in pass_rows.items():
        if eid not in idx:
            mism.append("%s not in 证据索引" % eid)
        elif idx[eid]["path"].replace("\\", "/") != p or idx[eid]["lineno"] != ln:
            mism.append("%s idx=%s:%d vs checks=%s:%d" % (eid, idx[eid]["path"], idx[eid]["lineno"], p, ln))
    line("IDX_VS_CHECKS", "checks_rows=%d mismatch=%d %s" % (len(pass_rows), len(mism), mism if mism else "ALL CONSISTENT"))

    # ---------- findings.json ↔ 证据索引：同 path:line 的 token 对齐 ----------
    with io.open(os.path.join(AI, "findings.json"), encoding="utf-8") as f:
        findings = json.load(f)["findings"]
    kinds = {}
    for fd in findings:
        kinds[fd["kind"]] = kinds.get(fd["kind"], 0) + 1
    line("FINDINGS_COUNT", "total=%d kinds=%s expect_total=28 %s"
         % (len(findings), kinds, "OK" if len(findings) == 28 else "MISMATCH"))

    ev_to_finding = {}
    for fd in findings:
        p, ln = fd["evidence"].rsplit(":", 1)
        ev_to_finding[(p.replace("\\", "/"), int(ln))] = fd["id"]
    overlap = [(eid, v["path"].replace("\\", "/"), v["lineno"], ev_to_finding[(v["path"].replace("\\", "/"), v["lineno"])])
               for eid, v in idx.items()
               if (v["path"].replace("\\", "/"), v["lineno"]) in ev_to_finding]
    line("FINDINGS_VS_IDX", "finding_evidence=%d idx_rows=%d overlap_same_pointer=%d (两表口径独立，允许不等)"
         % (len(findings), len(idx), len(overlap)))

    # ---------- 05_evidence_check.txt ↔ findings.json 逐条对齐 ----------
    with io.open(os.path.join(AI, "05_evidence_check.txt"), encoding="utf-8") as f:
        ec = f.read()
    ec_rows = re.findall(r"PASS (PROB|IMP|POS)-(\d{3}) status=(\w+) evidence=(\S+)", ec)
    ec_map = {"%s-%s" % (k, n): (st, ev) for k, n, st, ev in ec_rows}
    bad = []
    for fd in findings:
        got = ec_map.get(fd["id"])
        if not got:
            bad.append("%s missing in 05" % fd["id"])
        elif got[0] != fd["status"] or got[1].replace("\\", "/") != fd["evidence"].replace("\\", "/"):
            bad.append("%s 05=(%s,%s) json=(%s,%s)" % (fd["id"], got[0], got[1], fd["status"], fd["evidence"]))
    line("FINDINGS_VS_05", "rows=%d mismatch=%d %s" % (len(ec_map), len(bad), bad if bad else "ALL CONSISTENT"))

    # ---------- 正文 id 覆盖（13 PROB + 8 IMP，含 7 POS 段） ----------
    with io.open(os.path.join(DESK, "UEMCP使用反馈.md"), encoding="utf-8") as f:
        body = f.read()
    prob_ids = ["PROB-%03d" % i for i in range(1, 14)]
    imp_ids = ["IMP-%03d" % i for i in range(1, 9)]
    pos_ids = ["POS-%03d" % i for i in range(1, 8)]
    miss = [i for i in prob_ids + imp_ids if i not in body]
    pos_in_json = [fd["id"] for fd in findings if fd["kind"] == "positive"]
    line("BODY_ID_COVERAGE", "prob+imp_missing=%s pos_ids_in_json=%s pos_markers_in_body=%d (正文用【POS-00x】标题)"
         % (miss if miss else "NONE", len(pos_in_json), sum(1 for i in pos_ids if i in body)))

    # ---------- 桌面文件 SHA256 vs 00_checks [5] 记录 ----------
    recorded = {name: (ws, desk) for name, ws, desk in
                re.findall(r"(UEMCP使用反馈\.md|证据索引\.md) \| ws=([0-9A-F]{64}) \| desk=([0-9A-F]{64})", chk)}
    for name, (ws_h, desk_h) in recorded.items():
        cur = sha256(os.path.join(DESK, name))
        line("DESK_SHA256", "%s recorded(ws==desk)=%s current=%s %s"
             % (name, desk_h[:16] + "…", cur[:16] + "…",
                "MATCH" if cur == desk_h and ws_h == desk_h else "MISMATCH(文件在自检后被改动或记录两值不等)"))

    # ---------- 证据索引引用的 Saved/UEMCP 运行时文件在桌面包内是否留档 ----------
    runtime_paths = sorted({v["path"] for v in idx.values() if v["path"].replace("\\", "/").startswith("Saved/UEMCP")})
    line("RUNTIME_EVIDENCE", "distinct_runtime_paths=%d (桌面包内无留档→本机已全部不可复核，见环境变更节)" % len(runtime_paths))
    for p in runtime_paths:
        print("  RUNTIME_PATH|%s" % p)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
