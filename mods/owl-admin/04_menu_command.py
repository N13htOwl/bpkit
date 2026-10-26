"""owl-admin step 04: BP_OwlAdminMenuCommand : DataActorCommand -- the `dc OwlAdmin` handler.
Runs on the CLIENT (the row sets RunOnClient; the menu is local UI).

DoCommand:
    ctrl = GetGUIModuleController
    IsValid(ctrl.GetModule(OwlAdminMenu))?  -> no: ctrl.LoadModules   (picks up the merged row)
    ctrl.ToggleModule(OwlAdminMenu)          -> opens the menu (or closes it if already open)

The module (06's row, merged by 02) makes Conan's GUIModuleController own the window: it
shows the cursor, routes input, hides the shortcut bar, and Esc / the Close button (03)
close it. LoadModules is needed when the merge lands after the controller first loaded its
modules (seen in PIE 2026-10-26: row merged, GetModule None until LoadModules; the HUD
modules stayed active across the reload).

Run with Play STOPPED, after 03:  python ue_run.py mods/owl-admin/04_menu_command.py
"""
import sys
for _m in list(sys.modules):
    if _m == "bpkit" or _m.startswith("bpkit."):
        sys.modules.pop(_m, None)
import unreal
import os
from bpkit import bridge as bp, ir, build, config as _cfg
sys.path.insert(0, os.path.join(_cfg.REPO_ROOT, "mods", "owl-admin"))
sys.modules.pop("oa_config", None)
import oa_config as MOD

assert not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor(), \
    "Play-in-Editor is running -- stop Play first"

PKG = MOD.resolve_pkg()
PATH = "%s/%s" % (PKG, MOD.MENU_CMD)
FULL = MOD.full(PKG, MOD.MENU_CMD)

DAC = "/Script/ConanSandbox.DataActorCommand"
GUIMC = "/Script/ConanSandbox.GUIModuleController"
KSL = "/Script/Engine.KismetSystemLibrary"

bel = unreal.BlueprintEditorLibrary
bp_obj, _ = bp.scratch_blueprint(pkg=PKG, name=MOD.MENU_CMD, parent=unreal.DataActorCommand)
print("command BP:", FULL)

g = ir.Graph("EventGraph")
ev = g.event("DoCommand", parent=DAC, pos=(0, 0))
gmc = g.call("GetGUIModuleController", GUIMC, pos=(0, 250))

gm = g.call("GetModule", GUIMC, pos=(300, 0))      # not pure: an exec node
g.typed_input(gm, "Name", MOD.MENU_MODULE, "name")
g.wire(ev, "then", gm, "execute")
g.wire(gmc, "ReturnValue", gm, "self", exec=False)
valid = g.call("IsValid", KSL, pos=(550, 250))
g.wire(gm, "ReturnValue", valid, "Object", exec=False)
bReg = g.branch(pos=(600, 0))
g.wire(gm, "then", bReg, "execute")
g.wire(valid, "ReturnValue", bReg, "Condition", exec=False)

load = g.call("LoadModules", GUIMC, pos=(700, 150))
g.wire(bReg, "else", load, "execute")
g.wire(gmc, "ReturnValue", load, "self", exec=False)

tgl = g.call("ToggleModule", GUIMC, pos=(1000, 0))
g.typed_input(tgl, "ModuleName", MOD.MENU_MODULE, "name")
g.wire(bReg, "then", tgl, "execute")
g.wire(load, "then", tgl, "execute")
g.wire(gmc, "ReturnValue", tgl, "self", exec=False)

rep = build.build_graph(FULL, g)
assert rep["ok"], "command graph not clean: %r" % {k: rep[k] for k in ("dropped_nodes", "dropped_links", "orphans", "wildcards", "errors")}
bel.remove_unused_variables(bp_obj)     # v5 draft's MenuWidget var, if present
bel.compile_blueprint(bp_obj)
assert unreal.load_object(None, FULL + "_C"), "no generated class"
assert unreal.EditorAssetLibrary.save_asset(PATH), "save failed"
print("BUILD OK: owl-admin v%d -> %s%s" % (
    MOD.VERSION, FULL, "  [DRY RUN -- not shippable]" if PKG != MOD.OUTPUT_PKG else ""))
