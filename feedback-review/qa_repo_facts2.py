# -*- coding: utf-8 -*-
"""固化仓内代码引文事实 #2（只读）：CMD 3.4/3.5/3.13 与 probe 前提相关行。"""
import io
import os

WS = r"C:\UE5_P\5.4\UEMCP"
B = os.path.join(WS, "UEMCPBridge", "Content", "Python", "uemcp_bridge")


def rd(p):
    with io.open(p, "r", encoding="utf-8", errors="replace") as f:
        return f.read().splitlines()


def sl(tag, lines, a, b):
    print("%s %s:%d-%d" % (tag, os.path.relpath(lines and tag or "", WS), a, b))
    for i in range(a, min(len(lines), b) + 1):
        print("  %4d| %s" % (i, lines[i - 1][:150]))


pe = rd(os.path.join(B, "handlers", "python_exec.py"))
print("PYTHON_EXEC 30-45 + 88-98:")
sl("px", pe, 30, 45)
sl("px", pe, 88, 98)

rp = rd(os.path.join(B, "rpc.py"))
print("RPC_PY 30-44 + 100-140 + queue结构:")
sl("rpc", rp, 30, 44)
sl("rpc", rp, 100, 140)
q = [i + 1 for i, l in enumerate(rp) if "queue" in l.lower() or "Queue" in l]
print("RPC_QUEUE_LINES|%s" % q[:12])

vp = rd(os.path.join(B, "handlers", "viewport.py"))
print("VIEWPORT 40-46 + headless 606-618 + force_game_view 区域:")
sl("vp", vp, 40, 46)
sl("vp", vp, 606, 618)
g = [i + 1 for i, l in enumerate(vp) if "force_game_view" in l]
t = [i + 1 for i, l in enumerate(vp) if "TakeHighResScreenshot" in l or "PixelStreaming" in l]
print("VIEWPORT_FORCE_GAME_VIEW_LINES|%s" % g)
print("VIEWPORT_PIXELSTREAM_LINES|%s" % t[:10])

sv = rd(os.path.join(B, "server.py"))
print("SERVER_LOG 128-146:")
sl("sv", sv, 128, 146)

pr = rd(os.path.join(WS, "UEMCPBridge", "Tests", "probe_ue57.py"))
print("PROBE_UE57 pixel_streaming_mode 区域:")
h = [i + 1 for i, l in enumerate(pr) if "pixel_streaming" in l.lower()]
print("PROBE_PS_LINES|%s" % h)
if h:
    a = h[0]
    sl("pr", pr, a, a + 12)

tc = rd(os.path.join(WS, "uemcp", "packages", "server", "src", "tools", "pythonExec.ts"))
print("PYTHON_EXEC_TS 40-80:")
sl("ts", tc, 40, 80)
dsp = rd(os.path.join(B, "dispatcher.py"))
print("DISPATCHER 96-106:")
sl("dsp", dsp, 96, 106)
er = rd(os.path.join(B, "errors.py"))
bb = [i + 1 for i, l in enumerate(er) if "BRIDGE_BUSY" in l]
print("ERRORS_BRIDGE_BUSY_LINES|%s" % bb)
pe = rd(os.path.join(B, "handlers", "python_exec.py"))
tm = [i + 1 for i, l in enumerate(pe) if "timedOut" in l or "timeoutMs" in l]
print("PYTHON_EXEC_TIMEOUT_LINES|%s" % tm)

rdm = rd(os.path.join(WS, "UEMCPBridge", "README.md"))
print("README_MENTIONS L169-172 / L219-221 / L30,L34:")
sl("rm", rdm, 169, 172)
sl("rm", rdm, 219, 221)
sl("rm", rdm, 30, 34)
print("FACTS2_DONE")
