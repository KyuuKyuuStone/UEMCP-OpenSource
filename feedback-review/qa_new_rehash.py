# -*- coding: utf-8 -*-
"""NEW 目录 3 文件复算哈希（只读，访问面=已读文件），对比 layer23 留档值。"""
import hashlib
import time

FILES = {
    r"C:\UE5_P\5.4\ZMCPP_54_NEW\Plugins\ZS_WebAPI\Source\ZS_WebAPI\Private\CommonAPI\FloodCmdHandler.cpp": "d4f58853",
    r"C:\UE5_P\5.4\ZMCPP_54_NEW\Plugins\ZS_Flood\Source\ZS_Flood\Private\FloodPeak.cpp": "b5dc7ecf",
    r"C:\UE5_P\5.4\ZMCPP_54_NEW\Config\DefaultGame.ini": "c5b56128",
}

print("NEW_REHASH RUN 2026-11-17 %s by QA (只读; 仅限已抽查过的 3 文件)" % time.strftime("%H:%M:%S"))
for p, prefix in FILES.items():
    try:
        data = open(p, "rb").read()
        h = hashlib.sha256(data).hexdigest()
        st = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(__import__("os").stat(p).st_mtime))
        state = "UNCHANGED" if h.startswith(prefix) else "CHANGED_SINCE_READ"
        print("REHASH|%s|%s|sha256=%s|size=%d|mtime=%s" % (p, state, h, len(data), st))
    except OSError as exc:
        print("REHASH|%s|ERROR|%r" % (p, exc))
