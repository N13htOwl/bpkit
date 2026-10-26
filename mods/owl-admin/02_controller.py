"""owl-admin step 02: BP_OwlAdminController : ModController -- puts WBP_OwlAlerts on screen
while the local player has a character.

Conan auto-spawns every ModController subclass on play, but BEFORE the player exists
(docs/CONAN-NOTES.md "Persistent mod logic"), so the widget is driven from Tick. During
character creation the PlayerController has NO pawn of its own (the body on screen is a
preview actor seen through a CameraActor; GetPlayerPawn returns a SpectatorPawn; verified in
PIE 2026-10-26), so "the PC's own pawn is valid" is the gate:

ReceiveTick:
    IsDedicatedServer?               -> yes: nothing (no screen)
    IsValid(GetPlayerController(0))? -> no: try again next tick
    Sequence [1]: Left Shift held AND U pressed this frame -> ExecuteConsoleCommand("dc OwlAdmin")
                  (the console command keeps its RequireAdmin check, so non-admins get nothing)
    Sequence [0]:
    IsValid(AlertsWidget)?
      no  -> IsValid(PC.K2_GetPawn)? -> yes: CreateWidget(WBP_OwlAlerts, PC)
                                            -> AlertsWidget -> AddToViewport(ZOrder)
      yes -> (show/hide, below)
    show/hide (also right after creation, so it never flashes over a menu):
      IsValid(PC.K2_GetPawn) AND NOT PC.bShowMouseCursor -> HitTestInvisible, else Collapsed
      (no pawn: death / respawn screens. Cursor shown: one of Conan's full-screen menus is
      open -- sampled in PIE 2026-10-26, bShowMouseCursor tracked every Followers /
      inventory / journal open+close exactly, ~100 samples)

CDO: OwlVersion stamped (tell a stale spawned class from the current build), always
relevant (else the controller never exists on MP clients), per-frame tick (the Left Shift+U
hotkey is a one-frame key edge; each tick is a few cheap reads).

ModDataTableOperations override: merges DT_OwlAdmin_Commands (05) into the game's console
command table so `dc OwlAdmin` works (04), then DT_OwlAdmin_UIModules (06) into
DT_UIModuleTable so the admin menu (03) is a GUIModule.

Run with Play STOPPED, after 01, 05 and 06:  python ue_run.py mods/owl-admin/02_controller.py
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
UWIDGET = "/Script/UMG.Widget"
SLATEVIS = ir.enum_path("/Script/UMG.ESlateVisibility")
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

gpc = g.call("GetPlayerController", GS, pos=(300, 200))
g.typed_input(gpc, "PlayerIndex", "0", "int")
pcValid = g.call("IsValid", KSL, pos=(600, 200))
g.wire(gpc, "ReturnValue", pcValid, "Object", exec=False)
bPc = g.branch(pos=(600, 0))
g.wire(bDds, "else", bPc, "execute")
g.wire(pcValid, "ReturnValue", bPc, "Condition", exec=False)

# PC valid -> Sequence: [0] the alerts overlay, [1] the Left Shift+U menu hotkey
seq = g.node("K2Node_ExecutionSequence", [], base="ExecutionSequence", pos=(750, 0))
seq.pin("execute").typed("exec", direction="EGPD_Input")
seq.pin("then_0").typed("exec", direction="EGPD_Output")
seq.pin("then_1").typed("exec", direction="EGPD_Output")
g.wire(bPc, "then", seq, "execute")

wValid = g.call("IsValid", KSL, pos=(900, 200))
g.wire(widget_var((700, 320)), "AlertsWidget", wValid, "Object", exec=False)
bUp = g.branch(pos=(900, 0))
g.wire(seq, "then_0", bUp, "execute")

# Hotkey: Left Shift held + U pressed this frame -> run `dc OwlAdmin` as this player. Going
# through the console command (not ToggleModule directly) keeps the row's RequireAdmin check,
# so non-admins get nothing. Polled per frame (tick interval 0 below): WasInputKeyJustPressed
# is a one-frame edge and a 0.1 s tick would miss quick taps.
KEY = ir.struct_path("/Script/InputCore.Key")
PCLS = "/Script/Engine.PlayerController"
shift = g.call("IsInputKeyDown", PCLS, pos=(1000, -700))
g.typed_input(shift, "Key", MOD.MENU_HOTKEY[0], "struct", KEY)
g.wire(gpc, "ReturnValue", shift, "self", exec=False)
ukey = g.call("WasInputKeyJustPressed", PCLS, pos=(1000, -550))
g.typed_input(ukey, "Key", MOD.MENU_HOTKEY[1], "struct", KEY)
g.wire(gpc, "ReturnValue", ukey, "self", exec=False)
both = g.call("BooleanAND", "/Script/Engine.KismetMathLibrary", pos=(1250, -650))
g.wire(shift, "ReturnValue", both, "A", exec=False)
g.wire(ukey, "ReturnValue", both, "B", exec=False)
bKey = g.branch(pos=(1450, -800))
g.wire(seq, "then_1", bKey, "execute")
g.wire(both, "ReturnValue", bKey, "Condition", exec=False)
dc = g.call("ExecuteConsoleCommand", KSL, pos=(1700, -800))
g.typed_input(dc, "Command", "dc " + MOD.CMD_NAME, "string")
g.wire(gpc, "ReturnValue", dc, "SpecificPlayer", exec=False)
g.wire(bKey, "then", dc, "execute")
g.wire(wValid, "ReturnValue", bUp, "Condition", exec=False)

# one pure "player has a character" test, read by both the create and the show/hide branch.
# The PC's OWN pawn: GameplayStatics.GetPlayerPawn is GetPawnOrSpectator, and during character
# creation it returns a SpectatorPawn (verified in PIE), so it can't tell creation from play.
gpp = g.call("K2_GetPawn", "/Script/Engine.Controller", pos=(1100, 400))
g.wire(gpc, "ReturnValue", gpp, "self", exec=False)
pawnValid = g.call("IsValid", KSL, pos=(1350, 400))
g.wire(gpp, "ReturnValue", pawnValid, "Object", exec=False)

# not created yet: create it only once the player has a character
bPawnNew = g.branch(pos=(1200, -200))
g.wire(bUp, "else", bPawnNew, "execute")
g.wire(pawnValid, "ReturnValue", bPawnNew, "Condition", exec=False)
crt = g.create_widget(WIDGET_CLS, pos=(1500, -200))
g.wire(bPawnNew, "then", crt, "execute")
g.wire(gpc, "ReturnValue", crt, "OwningPlayer", exec=False)
store = g.var_set("AlertsWidget", "object", ir.obj_path(USERWIDGET), pos=(1800, -200))
g.wire(crt, "then", store, "execute")
g.wire(crt, "ReturnValue", store, "AlertsWidget", exec=False)
atv = g.call("AddToViewport", USERWIDGET, pos=(2100, -200))
g.typed_input(atv, "ZOrder", str(ZORDER), "int")
g.wire(store, "then", atv, "execute")
g.wire(widget_var((1900, -20)), "AlertsWidget", atv, "self", exec=False)

# show/hide: visible only while the player has a character AND no menu has the cursor up.
# Entered from the already-created branch and straight after creation.
bPawnVis = g.branch(pos=(1200, 200))
g.wire(bUp, "then", bPawnVis, "execute")
g.wire(atv, "then", bPawnVis, "execute")
g.wire(pawnValid, "ReturnValue", bPawnVis, "Condition", exec=False)
cursor = g.var_get("bShowMouseCursor", "bool", parent="/Script/Engine.PlayerController", pos=(1300, 500))
g.wire(gpc, "ReturnValue", cursor, "self", exec=False)
bMenu = g.branch(pos=(1500, 100))
g.wire(bPawnVis, "then", bMenu, "execute")
g.wire(cursor, "bShowMouseCursor", bMenu, "Condition", exec=False)


def set_vis(vis, pos):
    sv = g.call("SetVisibility", UWIDGET, pos=pos)
    g.typed_input(sv, "InVisibility", vis, "byte", SLATEVIS)
    g.wire(widget_var((pos[0] - 200, pos[1] + 80)), "AlertsWidget", sv, "self", exec=False)
    return sv


show = set_vis("HitTestInvisible", (1800, 0))
hide = set_vis("Collapsed", (1800, 300))
g.wire(bMenu, "else", show, "execute")      # character, no menu
g.wire(bMenu, "then", hide, "execute")      # a menu has the cursor up
g.wire(bPawnVis, "else", hide, "execute")   # no character

rep = build.build_graph(FULL, g)
assert rep["ok"], "controller graph not clean: %r" % rep

# Register `dc OwlAdmin`: merge DT_OwlAdmin_Commands into the game's console-command table.
# MergeDataTables is BlueprintProtected -- it resolves ONLY inside the ModDataTableOperations
# override, which the base ModController calls at mod-init on every instance (CONAN-NOTES
# "Custom console commands"). Same recipe as mounted-followers/02_manager.py: editor-made
# override, merge pasted with the tables as quoted DefaultObject refs, then live-wire entry->merge.
# Second merge: the OwlAdminMenu row (06) into DT_UIModuleTable, so the menu is a GUIModule.
DTAB = "/Script/Engine.DataTable"
OPFN = "ModDataTableOperations"


def obj_of(pkg_path):
    return "%s.%s" % (pkg_path, pkg_path.rsplit("/", 1)[1])


MERGES = [(obj_of(MOD.CUSTOM_CMD_TABLE), MOD.full(PKG, MOD.CMD_TABLE)),             # `dc OwlAdmin`
          (obj_of(MOD.GAME_UI_MODULE_TABLE), MOD.full(PKG, MOD.UI_MODULE_TABLE))]  # OwlAdminMenu module
for _into, ours in MERGES:
    assert unreal.load_asset(ours.split(".")[0]), "run 05 + 06 first: no " + ours
bp_ptr, op_gptr = bp.create_function_override(bp_obj, OPFN, unreal.ModController.static_class().get_path_name())
og = ir.Graph(OPFN)
prev = None
for i, (into, ours) in enumerate(MERGES):
    merge = og.node("K2Node_CallFunction", ['FunctionReference=(MemberName="MergeDataTables",bSelfContext=True)'],
                    base="CallFunction", pos=(560 + i * 400, 0))
    for pin, obj in (("MergeIntoDataTable", into), ("ToBeAddedDataTable", ours)):
        p = merge.pin(pin).typed("object", ir.obj_path(DTAB), direction="EGPD_Input")
        p.set("DefaultObject", '"%s"' % obj)
    if prev:
        og.wire(prev, "then", merge, "execute")
    prev = merge
op_res = bp.inject(FULL, og.render(), graph_name=OPFN, compile=False, save=False)
assert op_res.get("pasted") == len(MERGES) and not op_res.get("dropped_links"), "merge chain dropped: %r" % op_res
nodes = [(bp.export_nodes([n]), n) for n in bp.graph_nodes(op_gptr)]
entry = next(n for t, n in nodes if "K2Node_FunctionEntry" in t.splitlines()[0])
first = next(n for t, n in nodes if "K2Node_CallFunction" in t.splitlines()[0] and MERGES[0][1] in t)
assert bp.connect_pins(bp.find_pin(entry, "then", 1), bp.find_pin(first, "execute", 0)), "entry->merge wire failed"
bp.mark_structurally_modified(bp_ptr)
bel.compile_blueprint(bp_obj)
op_txt = bp.export_nodes(bp.graph_nodes(op_gptr))
assert all(a in op_txt and b in op_txt for a, b in MERGES) and "bOrphanedPin=True" not in op_txt, \
    "override not clean:\n" + op_txt
for into, ours in MERGES:
    print("override: %s merges %s into %s" % (OPFN, ours.rsplit(".", 1)[1], into.rsplit(".", 1)[1]))

# CDO defaults (class-level, so every spawned instance carries them)
gen = unreal.load_object(None, FULL + "_C")
assert gen, "no generated class after compile: " + FULL + "_C"
cdo = unreal.get_default_object(gen)
cdo.set_editor_property("OwlVersion", MOD.VERSION)
cdo.set_editor_property("always_relevant", True)
tk = cdo.get_editor_property("primary_actor_tick")
tk.set_editor_property("tick_interval", 0.0)   # every frame: the hotkey is a one-frame edge
cdo.set_editor_property("primary_actor_tick", tk)
assert unreal.EditorAssetLibrary.save_asset(PATH), "save failed"
print("CDO: OwlVersion=%d always_relevant=%s tick_interval=%.1f" % (
    cdo.get_editor_property("OwlVersion"), cdo.get_editor_property("always_relevant"),
    cdo.get_editor_property("primary_actor_tick").get_editor_property("tick_interval")))
print("BUILD OK: owl-admin v%d -> %s%s" % (
    MOD.VERSION, FULL, "  [DRY RUN -- not shippable]" if PKG != MOD.OUTPUT_PKG else ""))
