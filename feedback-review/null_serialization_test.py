# Offline read-only verification: serialization.to_jsonable None preservation.
# ZM P0-4 / PROB-008 bridge-side check (feedback md:78 "确认 TMap 序列化对空对象的处理").
# Loads serialization.py standalone: no package import, no unreal, no editor launch.
import importlib.util
import json
import sys

SER = r"C:\UE5_P\5.4\UEMCP\UEMCPBridge\Content\Python\uemcp_bridge\serialization.py"
spec = importlib.util.spec_from_file_location("serialization_standalone", SER)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
tj = mod.to_jsonable

print("python:", sys.version.split()[0])
print("source:", SER)
print("unreal_available:", mod.unreal is not None, "(expected False offline)")

cases = [
    ("none_scalar", None),
    ("tmap_null_value", {"ZM库区洪水推演01": None}),
    ("dict_mixed", {"a": 1, "b": None, "c": "x"}),
    ("list_with_none", [1, None, "x"]),
    ("nested_null", {"controllers": {"k1": None, "k2": {"deep": None}}}),
]
for name, val in cases:
    out = tj(val)
    print("CASE %s: input=%r -> to_jsonable=%r -> json=%s"
          % (name, val, out, json.dumps(out, ensure_ascii=False)))

assert tj(None) is None
d = tj({"ZM库区洪水推演01": None})
assert d == {"ZM库区洪水推演01": None}, d
assert "ZM库区洪水推演01" in d and d["ZM库区洪水推演01"] is None
assert json.dumps(d, ensure_ascii=False) == '{"ZM库区洪水推演01": null}'
n = tj({"controllers": {"k1": None, "k2": {"deep": None}}})
assert n["controllers"]["k1"] is None and n["controllers"]["k2"]["deep"] is None
assert tj([1, None, "x"]) == [1, None, "x"]

print("ALL_ASSERTIONS_PASS")
print("VERDICT: to_jsonable preserves None values and their dict keys; JSON emits null (key NOT dropped).")
print("SCOPE_NOTE: UE TMap<FString,TWeakObjectPtr<...>> null-weak-pointer iteration requires live editor -> undecided;")
print("            nullController:true marker targets getList (ZS_WebAPI-side) -> out of bridge scope.")
