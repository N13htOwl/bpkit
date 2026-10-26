"""owl-admin step 09: the controller's ModDataTableOperations override -- the game tables the
mod merges into at mod init (the base ModController calls it on every instance, server and
clients, before the GUI modules load):

    MergeDataTables(CustomConsoleCommandsDataTable, DT_OwlAdmin_Commands)   `dc Owl*` (05)
    MergeDataTables(DT_UIModuleTable, DT_OwlAdmin_UIModules)                 both menus (06)

MergeDataTables is BlueprintProtected -- it resolves ONLY inside this override (CONAN-NOTES
"Custom console commands"). Recipe as in mounted-followers/02_manager.py: editor-made
override, the merges pasted as one chained set with the tables as quoted DefaultObject refs,
then live-wire entry -> first merge. (The menu key actions are registered from 02's BeginPlay:
GetInputSettings / AddActionMapping are dropped when pasted into this override graph.)

Run with Play STOPPED, last (after 02, 05 and 06):  python ue_run.py mods/owl-admin/09_register.py
"""
import sys
for _m in list(sys.modules):
    if _m == "bpkit" or _m.startswith("bpkit."):
        sys.modules.pop(_m, None)
import unreal
import os
import re
from bpkit import bridge as bp, ir, config as _cfg
sys.path.insert(0, os.path.join(_cfg.REPO_ROOT, "mods", "owl-admin"))
sys.modules.pop("oa_config", None)
import oa_config as MOD

assert not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor(), \
    "Play-in-Editor is running -- stop Play first"

PKG = MOD.resolve_pkg()
PATH = "%s/%s" % (PKG, MOD.CONTROLLER)
FULL = MOD.full(PKG, MOD.CONTROLLER)
DTAB = "/Script/Engine.DataTable"
OPFN = "ModDataTableOperations"


def obj_of(pkg_path):
    return "%s.%s" % (pkg_path, pkg_path.rsplit("/", 1)[1])


MERGES = [(obj_of(MOD.CUSTOM_CMD_TABLE), MOD.full(PKG, MOD.CMD_TABLE)),
          (obj_of(MOD.GAME_UI_MODULE_TABLE), MOD.full(PKG, MOD.UI_MODULE_TABLE))]
for _into, ours in MERGES:
    assert unreal.load_asset(ours.split(".")[0]), "run 05 + 06 first: no " + ours
bp_obj = unreal.EditorAssetLibrary.load_asset(PATH)
assert bp_obj, "run 02_controller.py first"

bp_ptr, op_gptr = bp.create_function_override(bp_obj, OPFN, unreal.ModController.static_class().get_path_name())
og = ir.Graph(OPFN)
chain = []
for i, (into, ours) in enumerate(MERGES):
    merge = og.node("K2Node_CallFunction", ['FunctionReference=(MemberName="MergeDataTables",bSelfContext=True)'],
                    base="CallFunction", pos=(560 + i * 400, 0))
    for pin, obj in (("MergeIntoDataTable", into), ("ToBeAddedDataTable", ours)):
        p = merge.pin(pin).typed("object", ir.obj_path(DTAB), direction="EGPD_Input")
        p.set("DefaultObject", '"%s"' % obj)
    chain.append(merge)
for a, b in zip(chain, chain[1:]):
    og.wire(a, "then", b, "execute")

text = og.render()
authored = text.count("Begin Object Class=")
op_res = bp.inject(FULL, text, graph_name=OPFN, compile=False, save=False)
assert op_res.get("pasted") == authored and not op_res.get("dropped_links"), "override set dropped: %r" % op_res
nodes = [(bp.export_nodes([n]), n) for n in bp.graph_nodes(op_gptr)]
entry = next(n for t, n in nodes if "K2Node_FunctionEntry" in t.splitlines()[0])
first = next(n for t, n in nodes if "K2Node_CallFunction" in t.splitlines()[0] and MERGES[0][1] in t)
assert bp.connect_pins(bp.find_pin(entry, "then", 1), bp.find_pin(first, "execute", 0)), "entry->merge wire failed"
bp.mark_structurally_modified(bp_ptr)
unreal.BlueprintEditorLibrary.compile_blueprint(bp_obj)

op_txt = bp.export_nodes(bp.graph_nodes(op_gptr))
problems = []
if not all(a in op_txt and b in op_txt for a, b in MERGES):
    problems.append("table refs missing")
if "bOrphanedPin=True" in op_txt:
    problems.append("orphaned pins")
if "bHasCompilerMessage=True" in op_txt:
    problems.append("compiler messages: %s" % sorted(set(re.findall(r'ErrorMsg="([^"]*)"', op_txt))))
assert not problems, "override not clean: %s\n%s" % (problems, op_txt)
assert unreal.EditorAssetLibrary.save_asset(PATH), "save failed"
for into, ours in MERGES:
    print("override: merges %s into %s" % (ours.rsplit(".", 1)[1], into.rsplit(".", 1)[1]))
print("BUILD OK: owl-admin v%d -> %s:%s%s" % (
    MOD.VERSION, FULL, OPFN, "  [DRY RUN -- not shippable]" if PKG != MOD.OUTPUT_PKG else ""))
