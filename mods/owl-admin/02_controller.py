"""owl-admin step 02: BP_OwlAdminController : ModController -- puts WBP_OwlAlerts on screen
while the local player has a character, and holds who has unlocked admin mode.

Conan auto-spawns every ModController subclass on play, but BEFORE the player exists
(docs/CONAN-NOTES.md "Persistent mod logic"), so the widget is driven from Tick. During
character creation the PlayerController has NO pawn of its own (the body on screen is a
preview actor seen through a CameraActor; GetPlayerPawn returns a SpectatorPawn; verified in
PIE 2026-10-26), so "the PC's own pawn is valid" is the gate:

ReceiveTick:
    IsDedicatedServer?               -> yes: nothing (no screen)
    IsValid(GetPlayerController(0))? -> no: try again next tick
    IsValid(AlertsWidget)?
      no  -> IsValid(PC.K2_GetPawn)? -> yes: CreateWidget(WBP_OwlAlerts, PC)
                                            -> AlertsWidget -> AddToViewport(ZOrder)
      yes -> (show/hide, below)
    show/hide (also right after creation, so it never flashes over a menu):
      IsValid(PC.K2_GetPawn) AND NOT PC.bShowMouseCursor -> HitTestInvisible, else Collapsed
      (no pawn: death / respawn screens. Cursor shown: one of Conan's full-screen menus is
      open -- sampled in PIE 2026-10-26, bShowMouseCursor tracked every Followers /
      inventory / journal open+close exactly, ~100 samples)

Admin mode (the Owl Admin login): UnlockedPlayers is a REPLICATED array of PlayerStates,
written only on the server by the OwlLogin / OwlLogout commands (04), which run on the
server: they set PendingPlayer and call OwlUnlockPending / OwlLockPending here. Every client
sees the list (the controller is always relevant) and the admin menu (03) shows its settings
only while the owning player's PlayerState is in it. A client can't add itself: the array
is server-owned and replicates one way.

CDO: OwlVersion stamped (tell a stale spawned class from the current build), always
relevant (else the controller never exists on MP clients, and neither would the unlocked
list), 0.1 s tick (a menu opening hides the overlay within a tenth of a second).

ReceiveBeginPlay: registers the menu key actions (OwlAdminToggle = Shift+U, OwlPlayerToggle =
Shift+I) that the UI module rows (06) name as their ToggleActionName; then, on the server,
sets the replicated PasswordIsSet from whether the password save exists. While it's false
the admin menu shows its "set admin password" page instead of the login page.

The ModDataTableOperations override (table merges) is step 09.

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
PSTATE = "/Script/Engine.PlayerState"
ps_type = bel.get_object_reference_type(unreal.PlayerState.static_class())
bel.add_member_variable(bp_obj, "UnlockedPlayers", bel.get_array_type(ps_type))
bel.set_blueprint_variable_replication(bp_obj, "UnlockedPlayers", unreal.BlueprintVariableReplication.REPLICATED)
bel.add_member_variable(bp_obj, "PendingPlayer", ps_type)    # server-only hand-off from the commands
bel.add_member_variable(bp_obj, "PasswordIsSet", bel.get_basic_type_by_name("bool"))
bel.set_blueprint_variable_replication(bp_obj, "PasswordIsSet", unreal.BlueprintVariableReplication.REPLICATED)
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

wValid = g.call("IsValid", KSL, pos=(900, 200))
g.wire(widget_var((700, 320)), "AlertsWidget", wValid, "Object", exec=False)
bUp = g.branch(pos=(900, 0))
g.wire(bPc, "then", bUp, "execute")
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

# Admin mode list, server side (called by the OwlLogin / OwlLogout commands after they set
# PendingPlayer). AddUnique / RemoveItem on the replicated array; clients get the change.
for i, (event, fn) in enumerate((("OwlUnlockPending", "Array_AddUnique"), ("OwlLockPending", "Array_RemoveItem"))):
    y = 1000 + i * 300
    ev = g.custom_event(event, pos=(0, y))
    arr = g.array_var("UnlockedPlayers", pos=(250, y + 120), elem_cat="object", elem_sub=ir.obj_path(PSTATE))
    op = g.array_fn(fn, pos=(500, y), elem_cat="object", elem_sub=ir.obj_path(PSTATE))
    g.array_item_pin(op, "NewItem" if fn == "Array_AddUnique" else "Item", "object", ir.obj_path(PSTATE))
    g.wire(ev, "then", op, "execute")
    g.wire(arr, "UnlockedPlayers", op, "TargetArray", exec=False)
    g.wire(g.var_get("PendingPlayer", "object", ir.obj_path(PSTATE), pos=(250, y + 220)), "PendingPlayer",
           op, "NewItem" if fn == "Array_AddUnique" else "Item", exec=False)

# Menu keys: register the input actions the module rows (06) toggle on -- Shift+U / Shift+I.
# AddActionMapping is an AddUnique on the in-memory input settings (never saved to an ini) and
# rebuilds every PlayerInput's key map; PlayerInputs created later read it anyway. Done at
# BeginPlay because these calls are dropped when pasted into the ModDataTableOperations
# override graph (09), though they paste fine here.
ISET = "/Script/Engine.InputSettings"
bgn = g.event("ReceiveBeginPlay", pos=(0, 1800))
settings = g.call("GetInputSettings", ISET, pos=(250, 2000))
prev = bgn
KEYMAP = "/Script/Engine.InputActionKeyMapping"
for i, (action, key) in enumerate(MOD.ACTIONS):
    # KeyMapping is a const-ref struct param: it must be WIRED (a typed default is rejected)
    mk = g.node("K2Node_MakeStruct", ["StructType=\"/Script/CoreUObject.ScriptStruct'%s'\"" % KEYMAP],
                base="MakeStruct", pos=(500 + i * 400, 2050))
    g.typed_input(mk, "ActionName", action, "name")
    g.typed_input(mk, "bShift", "true", "bool")
    g.typed_input(mk, "Key", key, "struct", ir.struct_path("/Script/InputCore.Key"))
    mk.pin("InputActionKeyMapping").typed("struct", ir.struct_path(KEYMAP), direction="EGPD_Output")
    add = g.call("AddActionMapping", ISET, pos=(500 + i * 400, 1800))
    g.wire(mk, "InputActionKeyMapping", add, "KeyMapping", exec=False)
    g.wire(settings, "ReturnValue", add, "self", exec=False)
    g.wire(prev, "then", add, "execute")
    prev = add

# First-time setup: PasswordIsSet (replicated) tells every client's admin menu whether to show
# the login page or the "set admin password" page. Only the server can see the save, so the
# server reads it here; OwlPasswordSetPending (called by OwlSetPassword, 04) flips it on later.
auth = g.call("HasAuthority", "/Script/Engine.Actor", pos=(1300, 2050))
bAuth = g.branch(pos=(1300, 1800))
g.wire(prev, "then", bAuth, "execute")
g.wire(auth, "ReturnValue", bAuth, "Condition", exec=False)
dse = g.call("DoesSaveGameExist", GS, pos=(1600, 1800))       # impure: in the exec chain
g.typed_input(dse, "SlotName", MOD.SAVE_SLOT, "string")
g.typed_input(dse, "UserIndex", "0", "int")
g.wire(bAuth, "then", dse, "execute")
setPw = g.var_set("PasswordIsSet", "bool", pos=(1900, 1800))
g.wire(dse, "then", setPw, "execute")
g.wire(dse, "ReturnValue", setPw, "PasswordIsSet", exec=False)
pwEv = g.custom_event("OwlPasswordSetPending", pos=(0, 1600))
pwOn = g.var_set("PasswordIsSet", "bool", pos=(300, 1600))
pwOn.pin("PasswordIsSet").literal("true")
g.wire(pwEv, "then", pwOn, "execute")

# Clear + compile first: a rebuild pastes OwlUnlockPending/OwlLockPending while the compiled class
# still has functions of those names, and the editor renames the pasted events to "CustomEvent",
# breaking the commands' calls (seen on the second build, 2026-10-26).
bel.compile_blueprint(bp_obj)
_bp_ptr, _g_ptr = bp.find_graph(FULL, "EventGraph")
bp.clear_graph(_bp_ptr, _g_ptr)
bp.mark_structurally_modified(_bp_ptr)
bel.compile_blueprint(bp_obj)

rep = build.build_graph(FULL, g)
for fn in ("OwlUnlockPending", "OwlLockPending", "OwlPasswordSetPending"):
    assert unreal.find_object(None, FULL + "_C:" + fn), "custom event %s missing after build (renamed on paste?)" % fn
if not rep["ok"] and not (rep["dropped_nodes"] or rep["dropped_links"] or rep["orphans"] or rep["wildcards"]):
    # A pasted Make struct carries a benign "Override pins have been removed ... This note will go
    # away after you resave the asset" note (also filtered as benign in mods/forthvm/test_vm.py).
    # Accept the build only if that note is the sole message on every flagged node.
    import re
    msgs = {}
    for n in bp.graph_nodes(bp.find_graph(FULL, "EventGraph")[1]):
        t = bp.export_nodes([n])
        if "bHasCompilerMessage=True" in t:
            msgs[re.search(r'Name="([^"]+)"', t).group(1)] = re.findall(r'ErrorMsg="([^"]*)"', t)
    benign = all(k.startswith("K2Node_MakeStruct") and m and all("Override pins have been removed" in x for x in m)
                 for k, m in msgs.items())
    print("compiler notes: %s -> %s" % (sorted(msgs), "benign Make-struct resave notes" if benign else "REAL ERRORS"))
    rep["ok"] = benign and sorted(msgs) == sorted(rep["errors"])
assert rep["ok"], "controller graph not clean: %r" % rep

# CDO defaults (class-level, so every spawned instance carries them)
gen = unreal.load_object(None, FULL + "_C")
assert gen, "no generated class after compile: " + FULL + "_C"
cdo = unreal.get_default_object(gen)
cdo.set_editor_property("OwlVersion", MOD.VERSION)
cdo.set_editor_property("always_relevant", True)
tk = cdo.get_editor_property("primary_actor_tick")
tk.set_editor_property("tick_interval", 0.1)
cdo.set_editor_property("primary_actor_tick", tk)
assert unreal.EditorAssetLibrary.save_asset(PATH), "save failed"
print("CDO: OwlVersion=%d always_relevant=%s tick_interval=%.1f" % (
    cdo.get_editor_property("OwlVersion"), cdo.get_editor_property("always_relevant"),
    cdo.get_editor_property("primary_actor_tick").get_editor_property("tick_interval")))
print("BUILD OK: owl-admin v%d -> %s%s" % (
    MOD.VERSION, FULL, "  [DRY RUN -- not shippable]" if PKG != MOD.OUTPUT_PKG else ""))
