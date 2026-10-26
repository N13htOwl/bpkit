"""owl-admin step 02: BP_OwlAdminController : ModController -- puts WBP_OwlAlerts on screen.

Conan auto-spawns every ModController subclass on play, but BEFORE the player exists
(docs/CONAN-NOTES.md "Persistent mod logic"), so the widget is created on Tick, guarded:

ReceiveTick:
    IsDedicatedServer?            -> yes: nothing (no screen)
    IsValid(AlertsWidget)?        -> yes: nothing (already up; the steady-state cost)
    IsValid(GetPlayerController(0))? -> no: try again next tick
    CreateWidget(WBP_OwlAlerts, OwningPlayer=PC) -> AlertsWidget -> AddToViewport(ZOrder)

CDO: OwlVersion stamped (tell a stale spawned class from the current build), always
relevant (else the controller never exists on MP clients), 0.5 s tick (it only polls).

Run with Play STOPPED, after 01:  python ue_run.py mods/owl-admin/02_controller.py
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
PATH = "%s/%s" % (PKG, MOD.CONTROLLER)
FULL = MOD.full(PKG, MOD.CONTROLLER)
WIDGET_CLS = MOD.full(PKG, MOD.ALERTS_WBP) + "_C"
assert unreal.load_object(None, WIDGET_CLS), "run 01_alerts_widget.py first: no " + WIDGET_CLS

GS = "/Script/Engine.GameplayStatics"
KSL = "/Script/Engine.KismetSystemLibrary"
USERWIDGET = "/Script/UMG.UserWidget"
ZORDER = 1000           # above Conan's game HUD

# edit in place (reuse if present): delete+recreate leaves a stale redirector that blocks
# recreate, and an orphaned ModController class keeps auto-spawning (CONAN-NOTES §Packaging)
bel = unreal.BlueprintEditorLibrary
bp_obj, _ = bp.scratch_blueprint(pkg=PKG, name=MOD.CONTROLLER, parent=unreal.ModController)
bel.add_member_variable(bp_obj, "AlertsWidget",
                        bel.get_object_reference_type(unreal.UserWidget.static_class()))
bel.add_member_variable(bp_obj, "OwlVersion", bel.get_basic_type_by_name("int"))
print("controller BP:", FULL)


def widget_var(pos):
    return g.var_get("AlertsWidget", "object", ir.obj_path(USERWIDGET), pos=pos)


g = ir.Graph("EventGraph")
tick = g.event("ReceiveTick", pos=(0, 0))

dds = g.call("IsDedicatedServer", KSL, pos=(0, 200))
bDds = g.branch(pos=(300, 0))
g.wire(tick, "then", bDds, "execute")
g.wire(dds, "ReturnValue", bDds, "Condition", exec=False)

wValid = g.call("IsValid", KSL, pos=(300, 200))
g.wire(widget_var((100, 320)), "AlertsWidget", wValid, "Object", exec=False)
bUp = g.branch(pos=(600, 0))
g.wire(bDds, "else", bUp, "execute")
g.wire(wValid, "ReturnValue", bUp, "Condition", exec=False)

gpc = g.call("GetPlayerController", GS, pos=(600, 200))
g.typed_input(gpc, "PlayerIndex", "0", "int")
pcValid = g.call("IsValid", KSL, pos=(900, 200))
g.wire(gpc, "ReturnValue", pcValid, "Object", exec=False)
bPc = g.branch(pos=(900, 0))
g.wire(bUp, "else", bPc, "execute")
g.wire(pcValid, "ReturnValue", bPc, "Condition", exec=False)

crt = g.create_widget(WIDGET_CLS, pos=(1200, 0))
g.wire(bPc, "then", crt, "execute")
g.wire(gpc, "ReturnValue", crt, "OwningPlayer", exec=False)
store = g.var_set("AlertsWidget", "object", ir.obj_path(USERWIDGET), pos=(1500, 0))
g.wire(crt, "then", store, "execute")
g.wire(crt, "ReturnValue", store, "AlertsWidget", exec=False)
atv = g.call("AddToViewport", USERWIDGET, pos=(1800, 0))
g.typed_input(atv, "ZOrder", str(ZORDER), "int")
g.wire(store, "then", atv, "execute")
g.wire(widget_var((1600, 200)), "AlertsWidget", atv, "self", exec=False)

rep = build.build_graph(FULL, g)
assert rep["ok"], "controller graph not clean: %r" % rep

# CDO defaults (class-level, so every spawned instance carries them)
gen = unreal.load_object(None, FULL + "_C")
assert gen, "no generated class after compile: " + FULL + "_C"
cdo = unreal.get_default_object(gen)
cdo.set_editor_property("OwlVersion", MOD.VERSION)
cdo.set_editor_property("always_relevant", True)
tk = cdo.get_editor_property("primary_actor_tick")
tk.set_editor_property("tick_interval", 0.5)
cdo.set_editor_property("primary_actor_tick", tk)
assert unreal.EditorAssetLibrary.save_asset(PATH), "save failed"
print("CDO: OwlVersion=%d always_relevant=%s tick_interval=%.1f" % (
    cdo.get_editor_property("OwlVersion"), cdo.get_editor_property("always_relevant"),
    cdo.get_editor_property("primary_actor_tick").get_editor_property("tick_interval")))
print("BUILD OK: owl-admin v%d -> %s%s" % (
    MOD.VERSION, FULL, "  [DRY RUN -- not shippable]" if PKG != MOD.OUTPUT_PKG else ""))
