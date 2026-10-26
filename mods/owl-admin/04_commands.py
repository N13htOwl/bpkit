"""owl-admin step 04: the console commands -- one DataActorCommand class each (rows in 05):

    dc OwlAdmin                  (client)  open/close the admin menu; its login page shows
                                           until admin mode is unlocked. Shift+U does the same.
    dc OwlLogin <password>       (server)  check the password; right -> unlock admin mode
    dc OwlLogout                 (server)  lock admin mode again (the menu's Lock button)
    dc OwlSetPassword <password> (server, Conan admins only)  set the Owl Admin password

Login/logout/set-password run ON THE SERVER: the password is read from the server's
SaveGame (08) and never sent to clients, and unlocking writes the server-owned, replicated
UnlockedPlayers list on the controller (02) -- via PendingPlayer + OwlUnlockPending, since
the list belongs to the controller. Results come back as a Conan message box on the caller's
screen (ClientShowMessageBox is a client RPC). Passwords are one word: the command line is
split on spaces and only the first word is used.

OwlAdmin: GetGUIModuleController -> GetModule(OwlAdminMenu) valid? no -> LoadModules (the
merged row landed after the controller loaded its modules); then ToggleModule.

Run with Play STOPPED, after 02, 03 and 08:  python ue_run.py mods/owl-admin/04_commands.py
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
CTRL_CLS = MOD.full(PKG, MOD.CONTROLLER) + "_C"
SG_CLS = MOD.full(PKG, MOD.SAVEGAME) + "_C"
for c in (CTRL_CLS, SG_CLS):
    assert unreal.load_object(None, c), "build 02 and 08 first: no " + c

DAC = "/Script/ConanSandbox.DataActorCommand"
GUIMC = "/Script/ConanSandbox.GUIModuleController"
CPC = "/Script/ConanSandbox.ConanPlayerController"
GS = "/Script/Engine.GameplayStatics"
KSL = "/Script/Engine.KismetSystemLibrary"
KML = "/Script/Engine.KismetMathLibrary"
KSTR = "/Script/Engine.KismetStringLibrary"
KTXT = "/Script/Engine.KismetTextLibrary"
PSTATE = "/Script/Engine.PlayerState"
SG_CAST = "AsBP Owl Admin Save"
TITLE = "Owl Admin"


# ---------------------------------------------------------------- shared pieces
def message(g, ev, prev, prev_pin, text, pos):
    """Conan message box on the CALLING player's screen (ClientShowMessageBox is a client RPC)."""
    t = g.call("Conv_StringToText", KTXT, pos=(pos[0], pos[1] + 200))
    g.typed_input(t, "InString", text, "string")
    title = g.call("Conv_StringToText", KTXT, pos=(pos[0], pos[1] + 350))
    g.typed_input(title, "InString", TITLE, "string")
    box = g.call("ClientShowMessageBox", CPC, pos=pos)
    g.wire(ev, "CallingPlayerController", box, "self", exec=False)
    g.wire(title, "ReturnValue", box, "Title", exec=False)
    g.wire(t, "ReturnValue", box, "Message", exec=False)
    g.wire(prev, prev_pin, box, "execute")
    return box


def has_param(g, ev, pos):
    """Branch on Parameters having at least one word."""
    n = g.array_len(ev, "Parameters", (pos[0], pos[1] + 250), elem_cat="string")
    gt = g.call("Greater_IntInt", KML, pos=(pos[0] + 250, pos[1] + 250))
    g.wire(n, "ReturnValue", gt, "A", exec=False)
    g.typed_input(gt, "B", "0", "int")
    b = g.branch(pos=(pos[0] + 250, pos[1]))
    g.wire(ev, "then", b, "execute")
    g.wire(gt, "ReturnValue", b, "Condition", exec=False)
    return b


def set_pending_and_call(g, ev, prev, prev_pin, event, pos):
    """controller = GetActorOfClass(BP_OwlAdminController); controller.PendingPlayer =
    caller's PlayerState; controller.<event>(). Returns the call node (exec out "then")."""
    x, y = pos
    gac = g.call("GetActorOfClass", GS, pos=(x, y))
    ap = gac.pin("ActorClass").typed("class", ir.obj_path("/Script/Engine.Actor"), direction="EGPD_Input")
    ap.set("PinType.bIsUObjectWrapper", "True")
    ap.set("DefaultObject", '"%s"' % CTRL_CLS)
    g.wire(prev, prev_pin, gac, "execute")
    # GetActorOfClass already returns the controller's type (a cast is flagged as redundant);
    # the controller always exists once the mod is loaded, so no validity branch here
    gac.pin("ReturnValue").typed("object", ir.obj_path(CTRL_CLS), direction="EGPD_Output")
    ps = g.var_get("PlayerState", "object", ir.obj_path(PSTATE), parent="/Script/Engine.Controller",
                   pos=(x + 300, y + 250))
    g.wire(ev, "CallingPlayerController", ps, "self", exec=False)
    sp = g.var_set("PendingPlayer", "object", ir.obj_path(PSTATE), pos=(x + 600, y), parent=CTRL_CLS)
    g.wire(gac, "ReturnValue", sp, "self", exec=False)
    g.wire(ps, "PlayerState", sp, "PendingPlayer", exec=False)
    g.wire(gac, "then", sp, "execute")
    call = g.call(event, CTRL_CLS, pos=(x + 900, y))
    g.wire(gac, "ReturnValue", call, "self", exec=False)
    g.wire(sp, "then", call, "execute")
    return call


def build_command(name, graph_fn):
    full = MOD.full(PKG, name)
    bp_obj, _ = bp.scratch_blueprint(pkg=PKG, name=name, parent=unreal.DataActorCommand)
    g = ir.Graph("EventGraph")
    ev = g.event("DoCommand", parent=DAC, pos=(0, 0))
    graph_fn(g, ev)
    rep = build.build_graph(full, g)
    assert rep["ok"], "%s graph not clean: %r" % (name, {k: rep[k] for k in (
        "dropped_nodes", "dropped_links", "orphans", "wildcards", "errors")})
    unreal.BlueprintEditorLibrary.remove_unused_variables(bp_obj)
    unreal.BlueprintEditorLibrary.compile_blueprint(bp_obj)
    assert unreal.EditorAssetLibrary.save_asset("%s/%s" % (PKG, name)), "save failed: " + name
    print("BUILD OK: %s" % full)


# ---------------------------------------------------------------- dc OwlAdmin (client)
def open_menu(g, ev):
    gmc = g.call("GetGUIModuleController", GUIMC, pos=(0, 250))
    gm = g.call("GetModule", GUIMC, pos=(300, 0))      # not pure: an exec node
    g.typed_input(gm, "Name", MOD.MENU_MODULE, "name")
    g.wire(ev, "then", gm, "execute")
    g.wire(gmc, "ReturnValue", gm, "self", exec=False)
    valid = g.call("IsValid", KSL, pos=(550, 250))
    g.wire(gm, "ReturnValue", valid, "Object", exec=False)
    b = g.branch(pos=(600, 0))
    g.wire(gm, "then", b, "execute")
    g.wire(valid, "ReturnValue", b, "Condition", exec=False)
    load = g.call("LoadModules", GUIMC, pos=(700, 150))
    g.wire(b, "else", load, "execute")
    g.wire(gmc, "ReturnValue", load, "self", exec=False)
    tgl = g.call("ToggleModule", GUIMC, pos=(1000, 0))
    g.typed_input(tgl, "ModuleName", MOD.MENU_MODULE, "name")
    g.wire(b, "then", tgl, "execute")
    g.wire(load, "then", tgl, "execute")
    g.wire(gmc, "ReturnValue", tgl, "self", exec=False)


# ---------------------------------------------------------------- dc OwlLogin <password> (server)
def login(g, ev):
    bHas = has_param(g, ev, (0, 0))
    message(g, ev, bHas, "else", "Type the password after the command: dc OwlLogin <password>", (600, 600))
    dse = g.call("DoesSaveGameExist", GS, pos=(600, 0))
    g.typed_input(dse, "SlotName", MOD.SAVE_SLOT, "string")
    g.typed_input(dse, "UserIndex", "0", "int")
    g.wire(bHas, "then", dse, "execute")
    bSet = g.branch(pos=(850, 0))
    g.wire(dse, "then", bSet, "execute")
    g.wire(dse, "ReturnValue", bSet, "Condition", exec=False)
    no_pw = "No Owl Admin password is set yet. A Conan admin sets one with: dc OwlSetPassword <password>"
    message(g, ev, bSet, "else", no_pw, (1100, 600))
    load = g.call("LoadGameFromSlot", GS, pos=(1100, 0))
    g.typed_input(load, "SlotName", MOD.SAVE_SLOT, "string")
    g.typed_input(load, "UserIndex", "0", "int")
    g.wire(bSet, "then", load, "execute")
    cast = g.cast(SG_CLS, pos=(1400, 0))
    g.wire(load, "ReturnValue", cast, "Object", exec=False)
    g.wire(load, "then", cast, "execute")
    message(g, ev, cast, "CastFailed", no_pw, (1700, 900))
    pw = g.var_get("Password", "string", parent=SG_CLS, pos=(1400, 300))
    g.wire(cast, SG_CAST, pw, "self", exec=False)
    first = g.array_get(ev, "Parameters", 0, (1400, 450), elem_cat="string")
    eq = g.call("EqualEqual_StrStr", KSTR, pos=(1700, 300))     # case-sensitive compare
    g.wire(first, "Output", eq, "A", exec=False)
    g.wire(pw, "Password", eq, "B", exec=False)
    bOk = g.branch(pos=(1700, 0))
    g.wire(cast, "then", bOk, "execute")
    g.wire(eq, "ReturnValue", bOk, "Condition", exec=False)
    message(g, ev, bOk, "else", "Wrong password.", (2000, 600))
    done = set_pending_and_call(g, ev, bOk, "then", "OwlUnlockPending", (2000, 0))
    message(g, ev, done, "then", "Admin mode unlocked. Press Shift+U to open the admin menu.", (3000, 0))


# ---------------------------------------------------------------- dc OwlLogout (server)
def logout(g, ev):
    done = set_pending_and_call(g, ev, ev, "then", "OwlLockPending", (300, 0))
    message(g, ev, done, "then", "Admin mode locked.", (1300, 0))


# ---------------------------------------------------------------- dc OwlSetPassword <password> (server)
def set_password(g, ev):
    bHas = has_param(g, ev, (0, 0))
    message(g, ev, bHas, "else", "Type the new password after the command (one word): dc OwlSetPassword <password>",
            (600, 600))
    crt = g.call("CreateSaveGameObject", GS, pos=(600, 0))
    cp = crt.pin("SaveGameClass").typed("class", ir.obj_path("/Script/Engine.SaveGame"), direction="EGPD_Input")
    cp.set("PinType.bIsUObjectWrapper", "True")
    cp.set("DefaultObject", '"%s"' % SG_CLS)
    # CreateSaveGameObject narrows ReturnValue to the class passed (as in mounted-followers 04)
    crt.pin("ReturnValue").typed("object", ir.obj_path(SG_CLS), direction="EGPD_Output")
    g.wire(bHas, "then", crt, "execute")
    first = g.array_get(ev, "Parameters", 0, (600, 300), elem_cat="string")
    sp = g.var_set("Password", "string", pos=(900, 0), parent=SG_CLS)
    g.wire(crt, "ReturnValue", sp, "self", exec=False)
    g.wire(first, "Output", sp, "Password", exec=False)
    g.wire(crt, "then", sp, "execute")
    sav = g.call("SaveGameToSlot", GS, pos=(1200, 0))
    g.typed_input(sav, "SlotName", MOD.SAVE_SLOT, "string")
    g.typed_input(sav, "UserIndex", "0", "int")
    g.wire(crt, "ReturnValue", sav, "SaveGameObject", exec=False)
    g.wire(sp, "then", sav, "execute")
    message(g, ev, sav, "then", "Owl Admin password set. Players unlock admin mode with: dc OwlLogin <password>",
            (1500, 0))


BUILDERS = {"OwlAdmin": open_menu, "OwlLogin": login, "OwlLogout": logout, "OwlSetPassword": set_password}
for cmd, cls, *_flags in MOD.COMMANDS:
    build_command(cls, BUILDERS[cmd])
print("BUILD OK: owl-admin v%d -> %d commands%s" % (
    MOD.VERSION, len(MOD.COMMANDS), "  [DRY RUN -- not shippable]" if PKG != MOD.OUTPUT_PKG else ""))
