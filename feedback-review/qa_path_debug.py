# -*- coding: utf-8 -*-
import io
import os
import sys

targets = [
    r"C:",
    r"C:\UE5_P",
    r"C:\UE5_P\5.4",
    r"C:\UE5_P\5.4\ZMCPP_54",
    r"C:\UE5_P\5.4\ZMCPP_54\Plugins",
    r"C:\UE5_P\5.4\ZMCPP_54\Plugins\UEMCPBridge",
    r"C:\UE5_P\5.4\ZMCPP_54\Plugins\UEMCPBridge\README.md",
    r"C:\UE5_P\5.4\ZMCPP_54\Saved\UEMCP\bridge-health.json",
    r"C:\UE5_P\5.4\ZMCPP_54\Saved\UEMCP\svn\06_notes.txt",
]
for q in targets:
    print("EXISTS|%r|isdir=%s|isfile=%s" % (q, os.path.isdir(q), os.path.isfile(q)))

try:
    names = os.listdir(r"C:\UE5_P\5.4\ZMCPP_54\Plugins\UEMCPBridge")
    print("LISTDIR_OK|%d|%s" % (len(names), names[:6]))
except Exception as exc:
    print("LISTDIR_ERR|%r" % exc)

try:
    names = os.listdir(r"C:\UE5_P\5.4\ZMCPP_54\Saved\UEMCP")
    print("LISTDIR_SAVED_OK|%d|%s" % (len(names), names[:10]))
except Exception as exc:
    print("LISTDIR_SAVED_ERR|%r" % exc)

try:
    with io.open(r"C:\UE5_P\5.4\ZMCPP_54\Plugins\UEMCPBridge\README.md", "rb") as fh:
        head = fh.readline()
    print("OPEN_OK|%r" % head[:60])
except Exception as exc:
    print("OPEN_ERR|%r" % exc)

print("CWD|%s" % os.getcwd())
print("SYS|winver=%s" % sys.getwindowsversion())
