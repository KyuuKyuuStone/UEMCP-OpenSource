# -*- coding: utf-8 -*-
"""证据环境变更探测（只读）：固化 ZMCPP_54→ZMCPP_54_NEW 的磁盘事实。"""
import os
import time


def probe(path):
    try:
        st = os.stat(path)
        mt = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime))
        kind = "DIR" if os.path.isdir(path) else "FILE"
        return "EXISTS|%s|%s|mtime=%s" % (path, kind, mt)
    except OSError as exc:
        return "ABSENT|%s|%r" % (path, exc)


def main():
    print("ENV_PROBE RUN 2026-11-17 by QA (只读; os.stat)")
    roots = [
        r"C:\UE5_P\5.4\ZMCPP_54",
        r"C:\UE5_P\5.4\ZMCPP_54_NEW",
        r"C:\UE5_P\5.4\ZMCPP_54_NEW\Saved\UEMCP",
        r"C:\UE5_P\5.4\ZMCPP_54_NEW\Plugins\UEMCPBridge\README.md",
        r"C:\UE5_P\5.4\ZMCPP_54_NEW\Plugins\ZS_WebAPI\Source\ZS_WebAPI\Private\CommonAPI\FloodCmdHandler.cpp",
        r"C:\UE5_P\5.4\ZMCPP_54_NEW\Plugins\ZS_Flood\Source\ZS_Flood\Private\FloodPeak.cpp",
        r"C:\UE5_P\5.4\ZMCPP_54_NEW\Config\DefaultGame.ini",
        r"C:\UE5_P\5.4\ZMCPP_54_NEW\Saved\Logs",
        r"C:\UE5_P\5.4\ZMCPP_54_NEW\Saved\AutoScreenshot.png",
        r"C:\UE5_P\5.4\ZMCPP_54_NEW\ak.uproject",
    ]
    for p in roots:
        print("ENV|" + probe(p))

    # 反馈原件目录只读确认（应全部存在，无被移动）
    desk = r"C:\Users\Administrator\Desktop\UEMCP遇到的问题"
    print("DESK_ROOT|" + probe(desk))
    print("CMD_FEEDBACK_ROOT|" + probe(os.path.join(desk, "CMD构建发布组_UEMCP反馈")))
    print("ZM_FEEDBACK_ROOT|" + probe(os.path.join(desk, "ZM项目组——UEMCP_使用反馈")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
