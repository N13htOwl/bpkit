"""owl-admin step 02: BP_OwlAdminController : ModController -- puts WBP_OwlAlerts on screen
while the local player has a character, and holds who has unlocked admin mode.

Conan auto-spawns every ModController subclass on play, but BEFORE the player exists
(docs/CONAN-NOTES.md "Persistent mod logic"), so the widget is driven from Tick. During
character creation the PlayerController has NO pawn of its own (the body on screen is a
preview actor seen through a CameraActor; GetPlayerPawn returns a SpectatorPawn; verified in
PIE 2026-10-26), so "the PC's own pawn is valid" is the gate:

ReceiveTick:
    HasAuthority?                    -> yes: every PlayerController not in RelayOwners gets a
                                        BP_OwlRelay (10) spawned with it as Owner -- the admin
                                        menu sends passwords through it as RPCs
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
the admin menu shows its "set admin password" page instead of the login page. Then it loads
the applied menu settings (the OwlAdminSettings save) into the replicated AppliedSettings and
re-applies the LIVE ones that aren't kept in ServerSettings.ini.

Applied settings: `dc OwlApply` (04, the menu's APPLY) saves the values, sets PendingSettings
and calls OwlSettingsPending here: AppliedSettings = PendingSettings, every LIVE setting
(menu_defs.LIVE) is pushed into BP_ServerSettings, and the real values are read back into the
replicated Live_<id> variables. SettingsVersion (replicated) goes up after each load or apply,
and open admin menus reload their controls when it changes.

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
for _m in ("oa_config", "menu_defs"):
    sys.modules.pop(_m, None)
import oa_config as MOD
import menu_defs as D

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
REPL = unreal.BlueprintVariableReplication.REPLICATED
# the per-player relay (10 fills it in): created here if missing so the spawn below can name it
RELAY_CLS = MOD.full(PKG, MOD.RELAY) + "_C"
if not unreal.load_object(None, RELAY_CLS):
    _relay, _ = bp.scratch_blueprint(pkg=PKG, name=MOD.RELAY, parent=unreal.Actor)
    bel.compile_blueprint(_relay)
    unreal.EditorAssetLibrary.save_asset("%s/%s" % (PKG, MOD.RELAY))
assert unreal.load_object(None, RELAY_CLS), "could not create " + RELAY_CLS
actor_t = bel.get_object_reference_type(unreal.Actor.static_class())
bel.add_member_variable(bp_obj, "RelayOwners", bel.get_array_type(actor_t))   # server: players given a relay
strings_t = bel.get_array_type(bel.get_basic_type_by_name("string"))
for var, vtype, replicated in [("AppliedSettings", strings_t, True),     # the saved menu values
                               ("PendingSettings", strings_t, False),    # server-only hand-off from OwlApply
                               ("SettingsVersion", bel.get_basic_type_by_name("int"), True)] + \
                              [("Live_" + sid, bel.get_basic_type_by_name("real"), True) for sid in D.LIVE]:
    bel.add_member_variable(bp_obj, var, vtype)
    if replicated:
        bel.set_blueprint_variable_replication(bp_obj, var, REPL)
print("controller BP:", FULL)


def widget_var(pos):
    return g.var_get("AlertsWidget", "object", ir.obj_path(USERWIDGET), pos=pos)


g = ir.Graph("EventGraph")
tick = g.event("ReceiveTick", pos=(0, 0))

dds = g.call("IsDedicatedServer", KSL, pos=(0, 200))
bDds = g.branch(pos=(300, 0))

# Server first: give every PlayerController without one a relay (10), owned by that player so
# their menu can call its Run-on-Server events. RelayOwners remembers who has one.
tAuth = g.call("HasAuthority", "/Script/Engine.Actor", pos=(-1800, 200))
bTickAuth = g.branch(pos=(-1800, 0))
g.wire(tick, "then", bTickAuth, "execute")
g.wire(tAuth, "ReturnValue", bTickAuth, "Condition", exec=False)
pcs = g.get_all_actors("/Script/Engine.PlayerController", pos=(-1550, 0))
g.wire(bTickAuth, "then", pcs, "execute")
each = g.foreach("/Script/Engine.Actor", pos=(-1250, 0))
g.wire(pcs, "then", each, "Exec")
g.wire(pcs, "OutActors", each, "Array", exec=False)
owners = g.array_var("RelayOwners", pos=(-1000, 300), elem_cat="object", elem_sub=ir.obj_path("/Script/Engine.Actor"))
known = g.array_fn("Array_Contains", pos=(-750, 300), elem_cat="object", elem_sub=ir.obj_path("/Script/Engine.Actor"))
g.array_item_pin(known, "ItemToFind", "object", ir.obj_path("/Script/Engine.Actor"))
g.wire(owners, "RelayOwners", known, "TargetArray", exec=False)
g.wire(each, "Array Element", known, "ItemToFind", exec=False)
bKnown = g.branch(pos=(-750, 0))
g.wire(each, "LoopBody", bKnown, "execute")
g.wire(known, "ReturnValue", bKnown, "Condition", exec=False)
spawn = g.node("K2Node_SpawnActorFromClass", [], base="SpawnActor", pos=(-500, 100))
sc = spawn.pin("Class").typed("class", ir.obj_path("/Script/Engine.Actor"), direction="EGPD_Input")
sc.set("DefaultObject", '"%s"' % RELAY_CLS)
xf = g.call("MakeTransform", "/Script/Engine.KismetMathLibrary", pos=(-750, 450))   # a relay has no body
g.wire(xf, "ReturnValue", spawn, "SpawnTransform", exec=False)
g.wire(each, "Array Element", spawn, "Owner", exec=False)
g.wire(bKnown, "else", spawn, "execute")
remember = g.array_fn("Array_Add", pos=(-200, 100), elem_cat="object", elem_sub=ir.obj_path("/Script/Engine.Actor"))
g.array_item_pin(remember, "NewItem", "object", ir.obj_path("/Script/Engine.Actor"))
g.wire(g.array_var("RelayOwners", pos=(-450, 400), elem_cat="object", elem_sub=ir.obj_path("/Script/Engine.Actor")),
       "RelayOwners", remember, "TargetArray", exec=False)
g.wire(each, "Array Element", remember, "NewItem", exec=False)
g.wire(spawn, "then", remember, "execute")
g.wire(each, "Completed", bDds, "execute")
g.wire(bTickAuth, "else", bDds, "execute")
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

# ---------------------------------------------------------------- applied settings (server side)
# AppliedSettings: one string per menu_defs.SETTINGS entry (the values `dc OwlApply` saved),
# replicated so every admin menu shows them. The LIVE ones are pushed into Conan's server
# settings, then read back into Live_<id> so menus show what is really in effect (and the
# server's own values before anything was ever applied). SettingsVersion goes up after every
# load/apply: an open menu reloads its controls when it changes.
KSTR = "/Script/Engine.KismetStringLibrary"
KML = "/Script/Engine.KismetMathLibrary"
SS_CLS = MOD.SERVER_SETTINGS_CLS
SETTINGS_SG_CLS = MOD.full(PKG, MOD.SETTINGS_SAVEGAME) + "_C"
assert unreal.load_object(None, SETTINGS_SG_CLS), "run 08_savegame.py first: no " + SETTINGS_SG_CLS
N_SETTINGS = len(D.SETTINGS)
BY_ID = {st["id"]: st for st in D.SETTINGS}


def server_settings(entries, pos):
    """GetActorOfClass(BP_ServerSettings) + IsValid branch, entered from each (node, exec pin)
    in entries. Returns (actor node, branch)."""
    gac = g.call("GetActorOfClass", GS, pos=pos)
    ap = gac.pin("ActorClass").typed("class", ir.obj_path("/Script/Engine.Actor"), direction="EGPD_Input")
    ap.set("PinType.bIsUObjectWrapper", "True")
    ap.set("DefaultObject", '"%s"' % SS_CLS)
    gac.pin("ReturnValue").typed("object", ir.obj_path(SS_CLS), direction="EGPD_Output")
    for prev, prev_pin in entries:
        g.wire(prev, prev_pin, gac, "execute")
    ok = g.call("IsValid", KSL, pos=(pos[0] + 250, pos[1] + 200))
    g.wire(gac, "ReturnValue", ok, "Object", exec=False)
    b = g.branch(pos=(pos[0] + 300, pos[1]))
    g.wire(gac, "then", b, "execute")
    g.wire(ok, "ReturnValue", b, "Condition", exec=False)
    return gac, b


def applied_value(sid, pos):
    """FClamp(StringToDouble(AppliedSettings[index]), min, max) -- pure."""
    lo, hi = D.bounds(BY_ID[sid])
    arr = g.array_var("AppliedSettings", pos=pos, elem_cat="string")
    item = g.array_get(arr, "AppliedSettings", D.index(sid), (pos[0] + 200, pos[1]), elem_cat="string")
    num = g.call("Conv_StringToDouble", KSTR, pos=(pos[0] + 400, pos[1]))
    g.wire(item, "Output", num, "InString", exec=False)
    clamp = g.call("FClamp", KML, pos=(pos[0] + 650, pos[1]))
    g.wire(num, "ReturnValue", clamp, "Value", exec=False)
    g.typed_input(clamp, "Min", str(float(lo)), "real")
    g.typed_input(clamp, "Max", str(float(hi)), "real")
    return clamp


def push_live(prev, prev_pin, kinds, pos):
    """Put the applied LIVE values (of the given kinds: "ini", "bp") into the server settings.
    Returns the last exec node."""
    x, y = pos
    ss, ok = server_settings([(prev, prev_pin)], (x, y))
    prev, prev_pin = ok, "then"
    x += 700
    for sid, (key, how) in D.LIVE.items():
        if how not in kinds:
            continue
        v = applied_value(sid, (x - 300, y + 300))
        if how == "ini":                     # native setter: applies now, writes ServerSettings.ini
            n = g.call("SetServerSetting", "/Script/ConanSandbox.ServerSettings", pos=(x + 500, y))
            g.typed_input(n, "serverSetting", key, "string")
            g.wire(v, "ReturnValue", n, "value", exec=False)
        else:                                # a variable on BP_ServerSettings
            n = g.var_set(key, "real", pos=(x + 500, y), parent=SS_CLS)
            g.wire(v, "ReturnValue", n, key, exec=False)
        g.wire(ss, "ReturnValue", n, "self", exec=False)
        g.wire(prev, prev_pin, n, "execute")
        prev, prev_pin = n, "then"
        x += 900
    return prev, prev_pin


def read_live(entries, pos):
    """Live_<id> = the server settings' real values; then SettingsVersion += 1."""
    x, y = pos
    ss, ok = server_settings(entries, (x, y))
    prev, prev_pin = ok, "then"
    x += 700
    for sid, (key, how) in D.LIVE.items():
        if how == "ini":
            get = g.call("GetServerSetting", "/Script/ConanSandbox.ServerSettings", pos=(x, y))
            g.typed_input(get, "serverSetting", key, "string")
            g.wire(prev, prev_pin, get, "execute")
            prev, prev_pin, src, src_pin = get, "then", get, "value"
        else:
            src = g.var_get(key, "real", parent=SS_CLS, pos=(x, y + 250))
            src_pin = key
        g.wire(ss, "ReturnValue", src, "self", exec=False)
        st = g.var_set("Live_" + sid, "real", pos=(x + 300, y))
        g.wire(src, src_pin, st, "Live_" + sid, exec=False)
        g.wire(prev, prev_pin, st, "execute")
        prev, prev_pin = st, "then"
        x += 650
    add = g.call("Add_IntInt", KML, pos=(x, y + 200))
    g.wire(g.var_get("SettingsVersion", "int", pos=(x - 250, y + 200)), "SettingsVersion", add, "A", exec=False)
    g.typed_input(add, "B", "1", "int")
    ver = g.var_set("SettingsVersion", "int", pos=(x + 250, y))
    g.wire(add, "ReturnValue", ver, "SettingsVersion", exec=False)
    g.wire(prev, prev_pin, ver, "execute")
    # the server-settings-missing branch still bumps the version (menus then show the saved values)
    g.wire(ok, "else", ver, "execute")
    return ver


def set_applied(src, src_pin, pos):
    n = g.var_set("AppliedSettings", "string", pos=pos)
    n.pin("AppliedSettings").set("PinType.ContainerType", "Array")
    g.wire(src, src_pin, n, "AppliedSettings", exec=False)
    return n


# OwlSettingsPending (called by `dc OwlApply` after it set PendingSettings and saved them):
# AppliedSettings = PendingSettings -> push every LIVE value -> read them back
apEv = g.custom_event("OwlSettingsPending", pos=(0, 2600))
apSet = set_applied(g.array_var("PendingSettings", pos=(0, 2800), elem_cat="string"), "PendingSettings", (300, 2600))
g.wire(apEv, "then", apSet, "execute")
last, last_pin = push_live(apSet, "then", ("ini", "bp"), (600, 2600))
read_live([(last, last_pin)], (600 + 700 + 900 * len(D.LIVE), 2600))

# BeginPlay, server, after PasswordIsSet: load the saved settings. The "ini" ones are already
# in effect (SetServerSetting wrote them to ServerSettings.ini); the "bp" ones are re-applied.
# No save, an unreadable one, or one from a menu with a different number of settings -> just
# read the live values.
y = 3600
sdse = g.call("DoesSaveGameExist", GS, pos=(2200, 1800))
g.typed_input(sdse, "SlotName", MOD.SETTINGS_SLOT, "string")
g.typed_input(sdse, "UserIndex", "0", "int")
g.wire(setPw, "then", sdse, "execute")
bSave = g.branch(pos=(2500, 1800))
g.wire(sdse, "then", bSave, "execute")
g.wire(sdse, "ReturnValue", bSave, "Condition", exec=False)
sload = g.call("LoadGameFromSlot", GS, pos=(0, y))
g.typed_input(sload, "SlotName", MOD.SETTINGS_SLOT, "string")
g.typed_input(sload, "UserIndex", "0", "int")
g.wire(bSave, "then", sload, "execute")
scast = g.cast(SETTINGS_SG_CLS, pos=(300, y))
g.wire(sload, "ReturnValue", scast, "Object", exec=False)
g.wire(sload, "then", scast, "execute")
saved = g.array_var("Settings", pos=(300, y + 250), elem_cat="string", parent=SETTINGS_SG_CLS)
g.wire(scast, "AsBP Owl Settings Save", saved, "self", exec=False)
bgSet = set_applied(saved, "Settings", (600, y))
g.wire(scast, "then", bgSet, "execute")
slen = g.array_len(g.array_var("AppliedSettings", pos=(600, y + 250), elem_cat="string"), "AppliedSettings",
                   (850, y + 250), elem_cat="string")
seq = g.call("EqualEqual_IntInt", KML, pos=(1100, y + 250))
g.wire(slen, "ReturnValue", seq, "A", exec=False)
g.typed_input(seq, "B", str(N_SETTINGS), "int")
bLen = g.branch(pos=(1100, y))
g.wire(bgSet, "then", bLen, "execute")
g.wire(seq, "ReturnValue", bLen, "Condition", exec=False)
last, last_pin = push_live(bLen, "then", ("bp",), (1400, y))
read_live([(last, last_pin), (bSave, "else"), (scast, "CastFailed"), (bLen, "else")], (1400, y + 900))

# Clear + compile first: a rebuild pastes OwlUnlockPending/OwlLockPending while the compiled class
# still has functions of those names, and the editor renames the pasted events to "CustomEvent",
# breaking the commands' calls (seen on the second build, 2026-10-26).
bel.compile_blueprint(bp_obj)
_bp_ptr, _g_ptr = bp.find_graph(FULL, "EventGraph")
bp.clear_graph(_bp_ptr, _g_ptr)
bp.mark_structurally_modified(_bp_ptr)
bel.compile_blueprint(bp_obj)

rep = build.build_graph(FULL, g)
for fn in ("OwlUnlockPending", "OwlLockPending", "OwlPasswordSetPending", "OwlSettingsPending"):
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
