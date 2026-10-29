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

ReceiveBeginPlay: registers the menu key actions (OwlAdminToggle = Shift+O, OwlPlayerToggle =
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

HUD tab: HudOn (1/0 per menu_defs.HUD_ITEMS), HudText (per HUD_TEXTS) and HudVer replicate.
The relay's OwlServerHudSet (hud_server) writes them; BeginPlay loads the OwlHud save into them
on the server. On every machine with a screen, the tick (while the overlay is up) sets the
overlay's texts and shows each part that is on whenever HudVer passes HudSeen, and keeps the
players-online count (GameState.PlayerArray) current while that part is on.

Server Restart tab (restart_ctrl): RsVals (menu_defs.RS_LIMITS order) and RsVer replicate; the
relay's OwlServerRsSet writes them and BeginPlay loads the OwlRestart save into them. Once a
second the server's tick works out the seconds to the next restart (the daily time on the
server's clock, or a manual countdown) into the replicated RsLeft (-1 = no banner), and raises
RsBeep at each warning that is on. Every screen shows the countdown over the alert banner while
RsLeft >= 0 and plays the chosen sound on each new RsBeep. Owl Admin never restarts the server.

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
for _m in ("oa_config", "menu_defs", "menu_shell", "ce_panel", "restart_ctrl", "kits_ctrl"):
    sys.modules.pop(_m, None)
import oa_config as MOD
import menu_defs as D
import restart_ctrl
import kits_ctrl
from ce_panel import _Ctx

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
                               ("SettingsVersion", bel.get_basic_type_by_name("int"), True),
                               ("LooksOn", bel.get_basic_type_by_name("bool"), True)] + \
                              [("Live_" + sid, bel.get_basic_type_by_name("real"), True) for sid in D.LIVE]:
    bel.add_member_variable(bp_obj, var, vtype)
    if replicated:
        bel.set_blueprint_variable_replication(bp_obj, var, REPL)
# the HUD tab's values (hud_server writes them, the server loads them at BeginPlay); HudSeen is
# this machine's: the HudVer its HUD last showed
ints_t = bel.get_array_type(bel.get_basic_type_by_name("int"))
for var, vtype, replicated in (("HudOn", ints_t, True), ("HudText", strings_t, True),
                               ("HudVer", bel.get_basic_type_by_name("int"), True),
                               ("HudSeen", bel.get_basic_type_by_name("int"), False)):
    bel.add_member_variable(bp_obj, var, vtype)
    bel.set_blueprint_variable_replication(bp_obj, var, REPL if replicated else
                                           unreal.BlueprintVariableReplication.NONE)
HUD_SG_CLS = MOD.full(PKG, MOD.HUD_SAVEGAME) + "_C"
assert unreal.load_object(None, HUD_SG_CLS), "run 08_savegame.py first: no " + HUD_SG_CLS
# the Server Restart tab's (restart_ctrl): its values, the countdown, the banner and sound
for var, vtype, replicated in restart_ctrl.variables(bel):
    bel.add_member_variable(bp_obj, var, vtype)
    bel.set_blueprint_variable_replication(bp_obj, var, REPL if replicated else
                                           unreal.BlueprintVariableReplication.NONE)
RS_SG_CLS = MOD.full(PKG, MOD.RESTART_SAVEGAME) + "_C"
assert unreal.load_object(None, RS_SG_CLS), "run 08_savegame.py first: no " + RS_SG_CLS
# Kits (kits_ctrl): what is in each kit, for every player's menu
for var, vtype, replicated in kits_ctrl.variables(bel):
    bel.add_member_variable(bp_obj, var, vtype)
    bel.set_blueprint_variable_replication(bp_obj, var, REPL if replicated else
                                           unreal.BlueprintVariableReplication.NONE)
KITS_SG_CLS = MOD.full(PKG, MOD.KITS_SAVEGAME) + "_C"
assert unreal.load_object(None, KITS_SG_CLS), "run 08_savegame.py first: no " + KITS_SG_CLS
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
# then the Server Restart countdown (restart_ctrl), once a second
_rs = _Ctx(g, None, None, None)
_rs.exits = [(each, "Completed")]
restart_ctrl.server_tick(_rs, y=-14000)
for e, ep in _rs.exits:
    g.wire(e, ep, bDds, "execute")
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

# HUD tab, on every machine with a screen, while the overlay is up: when HudVer moved past what
# this HUD last showed, set the texts and show each part that is on (a text part also needs text);
# then, every tick, the players-online count while it's on.
TEXTBLOCK = "/Script/UMG.TextBlock"
KMLc = "/Script/Engine.KismetMathLibrary"
KTXTc = "/Script/Engine.KismetTextLibrary"
HUD_PARTS = {"alert": ("AlertOutline", "AlertText"), "notice": ("Notice1Outline", "Notice1Text"),
             "restrict": ("Notice2Outline", "Notice2Text"), "players": ("HudPlayers", None),
             "hint": ("HudHint", None)}
assert [k for k, _l, _d, _n in D.HUD_ITEMS] == list(HUD_PARTS), "HUD_PARTS out of step with menu_defs.HUD_ITEMS"
WAS = "AsWBP Owl Alerts"
hx, hy = 2200, 6500
wcast = g.cast(WIDGET_CLS, pos=(hx, hy))
g.wire(widget_var((hx - 250, hy + 200)), "AlertsWidget", wcast, "Object", exec=False)
g.wire(show, "then", wcast, "execute")


def hud_item(arr, k, cat, pos):
    a = g.array_var(arr, pos=pos, elem_cat=cat)
    return g.array_get(a, arr, k, (pos[0] + 200, pos[1]), elem_cat=cat)


def part(name, cls, pos):
    n = g.var_get(name, "object", ir.obj_path(cls), parent=WIDGET_CLS, pos=pos)
    g.wire(wcast, WAS, n, "self", exec=False)
    return n


vneq = g.call("NotEqual_IntInt", KMLc, pos=(hx + 300, hy + 250))
g.wire(g.var_get("HudVer", "int", pos=(hx + 100, hy + 250)), "HudVer", vneq, "A", exec=False)
g.wire(g.var_get("HudSeen", "int", pos=(hx + 100, hy + 400)), "HudSeen", vneq, "B", exec=False)
bNew = g.branch(pos=(hx + 300, hy))
g.wire(wcast, "then", bNew, "execute")
g.wire(vneq, "ReturnValue", bNew, "Condition", exec=False)
seen = g.var_set("HudSeen", "int", pos=(hx + 600, hy))
g.wire(g.var_get("HudVer", "int", pos=(hx + 450, hy + 250)), "HudVer", seen, "HudSeen", exec=False)
g.wire(bNew, "then", seen, "execute")
exits = [(seen, "then")]          # every (node, exec pin) the next node is entered from


def chain(node, pin="execute"):
    global exits
    for e, ep in exits:
        g.wire(e, ep, node, pin)
    exits = [(node, "then")]


x = hx + 900
for k, (key, (box, txt)) in enumerate(HUD_PARTS.items()):
    on = g.call("EqualEqual_IntInt", KMLc, pos=(x, hy + 450))
    g.wire(hud_item("HudOn", k, "int", (x - 400, hy + 450)), "Output", on, "A", exec=False)
    g.typed_input(on, "B", "1", "int")
    cond = on
    if txt:
        text = hud_item("HudText", k, "string", (x - 400, hy + 750))
        tt = g.call("Conv_StringToText", KTXTc, pos=(x, hy + 750))
        g.wire(text, "Output", tt, "InString", exec=False)
        st = g.call("SetText", TEXTBLOCK, pos=(x, hy))
        g.wire(part(txt, TEXTBLOCK, (x - 200, hy + 900)), txt, st, "self", exec=False)
        g.wire(tt, "ReturnValue", st, "InText", exec=False)
        chain(st)
        ln = g.call("Len", "/Script/Engine.KismetStringLibrary", pos=(x + 200, hy + 750))
        g.wire(text, "Output", ln, "S", exec=False)
        has_text = g.call("Greater_IntInt", KMLc, pos=(x + 400, hy + 750))
        g.wire(ln, "ReturnValue", has_text, "A", exec=False)
        g.typed_input(has_text, "B", "0", "int")
        cond = g.call("BooleanAND", KMLc, pos=(x + 600, hy + 600))
        g.wire(on, "ReturnValue", cond, "A", exec=False)
        g.wire(has_text, "ReturnValue", cond, "B", exec=False)
    b = g.branch(pos=(x + 300, hy))
    chain(b)
    g.wire(cond, "ReturnValue", b, "Condition", exec=False)
    ends = []
    for j, (pin, vis) in enumerate((("then", "HitTestInvisible"), ("else", "Collapsed"))):
        sv = g.call("SetVisibility", UWIDGET, pos=(x + 600, hy + 300 * j))
        g.typed_input(sv, "InVisibility", vis, "byte", SLATEVIS)
        g.wire(part(box, UWIDGET, (x + 400, hy + 1050 + 150 * j)), box, sv, "self", exec=False)
        g.wire(b, pin, sv, "execute")
        ends.append((sv, "then"))
    exits = ends                  # the next part is entered from both visibility setters
    x += 1300

# every tick (a new version or not): the players-online count, while that part is on
exits += [(bNew, "else")]
pon = g.call("EqualEqual_IntInt", KMLc, pos=(x, hy + 450))
g.wire(hud_item("HudOn", [k for k, _l, _d, _n in D.HUD_ITEMS].index("players"), "int", (x - 400, hy + 450)),
       "Output", pon, "A", exec=False)
g.typed_input(pon, "B", "1", "int")
bp_on = g.branch(pos=(x + 300, hy))
chain(bp_on)
g.wire(pon, "ReturnValue", bp_on, "Condition", exec=False)
gstate = g.call("GetGameState", GS, pos=(x + 300, hy + 600))
players = g.array_var("PlayerArray", pos=(x + 550, hy + 600), elem_cat="object", elem_sub=ir.obj_path(PSTATE),
                      parent="/Script/Engine.GameStateBase")
g.wire(gstate, "ReturnValue", players, "self", exec=False)
pcount = g.array_len(players, "PlayerArray", (x + 800, hy + 600), elem_cat="object", elem_sub=ir.obj_path(PSTATE))
pstr = g.call("Conv_IntToString", "/Script/Engine.KismetStringLibrary", pos=(x + 1000, hy + 600))
g.wire(pcount, "ReturnValue", pstr, "InInt", exec=False)
ptxt = g.call("Conv_StringToText", KTXTc, pos=(x + 1200, hy + 600))
g.wire(pstr, "ReturnValue", ptxt, "InString", exec=False)
pset = g.call("SetText", TEXTBLOCK, pos=(x + 600, hy))
g.wire(part("HudPlayersText", TEXTBLOCK, (x + 400, hy + 300)), "HudPlayersText", pset, "self", exec=False)
g.wire(ptxt, "ReturnValue", pset, "InText", exec=False)
g.wire(bp_on, "then", pset, "execute")

# Server Restart (restart_ctrl): the countdown over the alert banner while the overlay is up; the
# warning sound whether it's up or hidden (a menu open), so nobody misses it
_rs = _Ctx(g, None, None, None)
_rs.exits = [(pset, "then"), (bp_on, "else")]
restart_ctrl.banner(_rs, wcast, WAS, WIDGET_CLS, y=hy + 3000)
_rs.exits += [(hide, "then")]
restart_ctrl.sound(_rs, y=hy + 5000)

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

# Menu keys: register the input actions the module rows (06) toggle on -- Shift+O / Shift+I.
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
PAD_FROM = 72         # a save made before "owltm" (v1.3) holds 72 values; newer settings get their defaults
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


def pad_settings(prev, prev_pin, pos):
    """A save from before the newest settings (PAD_FROM values or more) gets their defaults
    appended, so it still loads. Returns the (node, exec pin) exits."""
    exits = [(prev, prev_pin)]
    x, y = pos
    for k in range(PAD_FROM, N_SETTINGS):
        st = D.SETTINGS[k]
        ln = g.array_len(g.array_var("AppliedSettings", pos=(x, y + 250), elem_cat="string"), "AppliedSettings",
                         (x + 150, y + 250), elem_cat="string")
        eq = g.call("EqualEqual_IntInt", KML, pos=(x + 300, y + 250))
        g.wire(ln, "ReturnValue", eq, "A", exec=False)
        g.typed_input(eq, "B", str(k), "int")
        b = g.branch(pos=(x + 300, y))
        for e, ep in exits:
            g.wire(e, ep, b, "execute")
        g.wire(eq, "ReturnValue", b, "Condition", exec=False)
        add = g.array_fn("Array_Add", pos=(x + 600, y), elem_cat="string")
        g.wire(g.array_var("AppliedSettings", pos=(x + 450, y + 250), elem_cat="string"), "AppliedSettings", add,
               "TargetArray", exec=False)
        g.array_item_pin(add, "NewItem", "string")
        default = ("1" if st["default"] else "0") if st["type"] == "toggle" else "%g" % st["default"]
        g.typed_input(add, "NewItem", default, "string")
        g.wire(b, "then", add, "execute")
        exits = [(b, "else"), (add, "then")]
        x += 900
    return exits


def update_looks(entries, pos):
    """LooksOn = the "owltm" setting (Owl Transmog and Animal Masks shown), true while the settings
    don't hold it. Entered from each (node, exec pin) in entries; returns the exits."""
    x, y = pos
    k = D.index("owltm")
    ln = g.array_len(g.array_var("AppliedSettings", pos=(x, y + 250), elem_cat="string"), "AppliedSettings",
                     (x + 150, y + 250), elem_cat="string")
    has = g.call("Greater_IntInt", KML, pos=(x + 300, y + 250))
    g.wire(ln, "ReturnValue", has, "A", exec=False)
    g.typed_input(has, "B", str(k), "int")
    b = g.branch(pos=(x + 300, y))
    for e, ep in entries:
        g.wire(e, ep, b, "execute")
    g.wire(has, "ReturnValue", b, "Condition", exec=False)
    on = g.call("GreaterEqual_DoubleDouble", KML, pos=(x + 1000, y + 250))
    g.wire(applied_value("owltm", (x + 300, y + 450)), "ReturnValue", on, "A", exec=False)
    g.typed_input(on, "B", "0.5", "real")
    s1 = g.var_set("LooksOn", "bool", pos=(x + 1300, y))
    g.wire(on, "ReturnValue", s1, "LooksOn", exec=False)
    g.wire(b, "then", s1, "execute")
    s2 = g.var_set("LooksOn", "bool", pos=(x + 1300, y + 300))
    s2.pin("LooksOn").literal("true")
    g.wire(b, "else", s2, "execute")
    return [(s1, "then"), (s2, "then")]


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
update_looks([(read_live([(last, last_pin)], (600 + 700 + 900 * len(D.LIVE), 2600)), "then")],
             (600 + 1400 + 900 * len(D.LIVE), 2600))

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
for e, ep in pad_settings(bgSet, "then", (600, y - 700)):
    g.wire(e, ep, bLen, "execute")
g.wire(seq, "ReturnValue", bLen, "Condition", exec=False)
last, last_pin = push_live(bLen, "then", ("bp",), (1400, y))
loaded = read_live([(last, last_pin), (bSave, "else"), (scast, "CastFailed"), (bLen, "else")], (1400, y + 900))
looks_set = update_looks([(loaded, "then")], (1400, y + 1500))

# BeginPlay, server, after the settings: the HUD tab's save into HudOn / HudText, if it holds one
# value per item; else the defaults stay (everything off). HudVer goes up either way, so every
# client's HUD shows what the server has.
HUD_N, HUD_T = len(D.HUD_ITEMS), len(D.HUD_TEXTS)
y = 4800
hdse = g.call("DoesSaveGameExist", GS, pos=(0, y))
g.typed_input(hdse, "SlotName", MOD.HUD_SLOT, "string")
g.typed_input(hdse, "UserIndex", "0", "int")
for _e, _ep in looks_set:
    g.wire(_e, _ep, hdse, "execute")
bHud = g.branch(pos=(250, y))
g.wire(hdse, "then", bHud, "execute")
g.wire(hdse, "ReturnValue", bHud, "Condition", exec=False)
hload = g.call("LoadGameFromSlot", GS, pos=(500, y))
g.typed_input(hload, "SlotName", MOD.HUD_SLOT, "string")
g.typed_input(hload, "UserIndex", "0", "int")
g.wire(bHud, "then", hload, "execute")
hcast = g.cast(HUD_SG_CLS, pos=(800, y))
g.wire(hload, "ReturnValue", hcast, "Object", exec=False)
g.wire(hload, "then", hcast, "execute")
HAS = "AsBP Owl Hud Save"
sizes_ok = None
for k, (field, cat, n) in enumerate((("On", "int", HUD_N), ("Text", "string", HUD_T))):
    a = g.array_var(field, pos=(800, y + 300 + 150 * k), elem_cat=cat, parent=HUD_SG_CLS)
    g.wire(hcast, HAS, a, "self", exec=False)
    ln = g.array_len(a, field, (1050, y + 300 + 150 * k), elem_cat=cat)
    eq = g.call("EqualEqual_IntInt", KML, pos=(1300, y + 300 + 150 * k))
    g.wire(ln, "ReturnValue", eq, "A", exec=False)
    g.typed_input(eq, "B", str(n), "int")
    if sizes_ok is None:
        sizes_ok = eq
    else:
        both = g.call("BooleanAND", KML, pos=(1550, y + 400))
        g.wire(sizes_ok, "ReturnValue", both, "A", exec=False)
        g.wire(eq, "ReturnValue", both, "B", exec=False)
        sizes_ok = both
bSizes = g.branch(pos=(1100, y))
g.wire(hcast, "then", bSizes, "execute")
g.wire(sizes_ok, "ReturnValue", bSizes, "Condition", exec=False)
prev, prev_pin = bSizes, "then"
for k, (var, field, cat) in enumerate((("HudOn", "On", "int"), ("HudText", "Text", "string"))):
    st = g.var_set(var, cat, pos=(1800 + 300 * k, y))
    st.pin(var).set("PinType.ContainerType", "Array")
    src = g.array_var(field, pos=(1800 + 300 * k, y + 600), elem_cat=cat, parent=HUD_SG_CLS)
    g.wire(hcast, HAS, src, "self", exec=False)
    g.wire(src, field, st, var, exec=False)
    g.wire(prev, prev_pin, st, "execute")
    prev, prev_pin = st, "then"
hinc = g.call("Add_IntInt", KML, pos=(2450, y + 250))
g.wire(g.var_get("HudVer", "int", pos=(2250, y + 250)), "HudVer", hinc, "A", exec=False)
g.typed_input(hinc, "B", "1", "int")
hver = g.var_set("HudVer", "int", pos=(2500, y))
g.wire(hinc, "ReturnValue", hver, "HudVer", exec=False)
for e, ep in ((prev, prev_pin), (bHud, "else"), (hcast, "CastFailed"), (bSizes, "else")):
    g.wire(e, ep, hver, "execute")

# then the Server Restart tab's save into RsVals, if it holds one value per entry (else the
# defaults stay: no daily restart). RsVer goes up either way, so open admin pages reload.
y = 5800
_rs = _Ctx(g, None, None, None)
_rs.exits = [(hver, "then")]
rdse = g.call("DoesSaveGameExist", GS, pos=(0, y + 300))
g.typed_input(rdse, "SlotName", MOD.RESTART_SLOT, "string")
g.typed_input(rdse, "UserIndex", "0", "int")
_rs.go(rdse)
bRs = _rs.branch((rdse, "ReturnValue"), (250, y))
_rs.exits = [(bRs, "then")]
rload = g.call("LoadGameFromSlot", GS, pos=(500, y))
g.typed_input(rload, "SlotName", MOD.RESTART_SLOT, "string")
g.typed_input(rload, "UserIndex", "0", "int")
_rs.go(rload)
rcast = g.cast(RS_SG_CLS, pos=(800, y))
g.wire(rload, "ReturnValue", rcast, "Object", exec=False)
_rs.go(rcast)
RAS = "AsBP Owl Restart Save"
rvals = g.array_var("Vals", pos=(800, y + 300), elem_cat="int", parent=RS_SG_CLS)
g.wire(rcast, RAS, rvals, "self", exec=False)
rlen = g.array_len(rvals, "Vals", (1050, y + 300), elem_cat="int")
bRsLen = _rs.branch(_rs.fn("EqualEqual_IntInt", KML, {"A": (rlen, "ReturnValue"), "B": (str(len(D.RS_LIMITS)), "int")},
                           (1300, y + 300)), (1300, y))
_rs.exits = [(bRsLen, "then")]
rset = g.var_set("RsVals", "int", pos=(1600, y))
rset.pin("RsVals").set("PinType.ContainerType", "Array")
rsrc = g.array_var("Vals", pos=(1400, y + 500), elem_cat="int", parent=RS_SG_CLS)
g.wire(rcast, RAS, rsrc, "self", exec=False)
g.wire(rsrc, "Vals", rset, "RsVals", exec=False)
_rs.go(rset)
_rs.exits += [(bRs, "else"), (rcast, "CastFailed"), (bRsLen, "else")]
_rs.bump("RsVer", (1900, y))
# then the kits (the OwlKits save into the Kit* arrays)
kits_ctrl.load(_rs, KITS_SG_CLS, y + 1000)

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
# the HUD tab's defaults: one value per item (the tick reads them by index), all off, no text;
# HudSeen -1 so a new HUD always loads once
cdo.set_editor_property("HudOn", [0] * len(D.HUD_ITEMS))
cdo.set_editor_property("HudText", [""] * len(D.HUD_TEXTS))
cdo.set_editor_property("HudSeen", -1)
restart_ctrl.defaults(cdo)       # no daily restart; RsLeft / RsBeepSeen / RsClock -1
cdo.set_editor_property("LooksOn", True)   # Owl Transmog and Animal Masks shown until the settings say no
kits_ctrl.defaults(cdo)          # Kit 1 / 2 / 3, no items
cdo.set_editor_property("always_relevant", True)
tk = cdo.get_editor_property("primary_actor_tick")
tk.set_editor_property("tick_interval", 0.1)
cdo.set_editor_property("primary_actor_tick", tk)
assert unreal.EditorAssetLibrary.save_asset(PATH), "save failed"
assert list(cdo.get_editor_property("HudOn")) == [0] * len(D.HUD_ITEMS), "HudOn default didn't stick"
print("CDO: OwlVersion=%d HudOn=%s always_relevant=%s tick_interval=%.1f" % (
    cdo.get_editor_property("OwlVersion"), list(cdo.get_editor_property("HudOn")),
    cdo.get_editor_property("always_relevant"),
    cdo.get_editor_property("primary_actor_tick").get_editor_property("tick_interval")))
print("BUILD OK: owl-admin v%d -> %s%s" % (
    MOD.VERSION, FULL, "  [DRY RUN -- not shippable]" if PKG != MOD.OUTPUT_PKG else ""))
