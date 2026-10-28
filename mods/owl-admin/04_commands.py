"""owl-admin step 04: the console commands -- one DataActorCommand class each (rows in 05):

    dc OwlAdmin                  (client)  open/close the admin menu; its login page shows
                                           until admin mode is unlocked. Shift+O does the same.
    dc OwlLogin <password>       (server)  check the password; right -> unlock admin mode
    dc OwlLogout                 (server)  lock admin mode again (the menu's Lock button)
    dc OwlSetPassword <password> (server, Conan admins only)  set or replace the Owl Admin
                                           password, mark it set for every client, unlock the caller
    dc OwlApply <value> x N      (server, admin mode only)  the admin menu's APPLY: one value per
                                           menu_defs.SETTINGS entry; saved (OwlAdminSettings slot)
                                           and handed to the controller, which pushes the LIVE ones
                                           into Conan's server settings

The admin menu does NOT use OwlLogin / OwlSetPassword: anything typed or run as a console
command is written to the log ("Cmd: dc OwlLogin <password>"), so the menu sends passwords
through the relay's server RPCs instead (10). These two stay as a console fallback (a
forgotten password: a Conan admin sets a new one), and they do log what is typed. The shared
server-side logic is oa_auth. Passwords here are one word: the command line is split on
spaces and only the first word is used.

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
for _m in ("oa_config", "menu_defs", "oa_auth"):
    sys.modules.pop(_m, None)
import oa_config as MOD
import menu_defs as D
from oa_auth import Auth

assert not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor(), \
    "Play-in-Editor is running -- stop Play first"

PKG = MOD.resolve_pkg()
CTRL_CLS = MOD.full(PKG, MOD.CONTROLLER) + "_C"
SG_CLS = MOD.full(PKG, MOD.SAVEGAME) + "_C"
SETTINGS_SG_CLS = MOD.full(PKG, MOD.SETTINGS_SAVEGAME) + "_C"
for c in (CTRL_CLS, SG_CLS, SETTINGS_SG_CLS):
    assert unreal.load_object(None, c), "build 02 and 08 first: no " + c

DAC = "/Script/ConanSandbox.DataActorCommand"
GUIMC = "/Script/ConanSandbox.GUIModuleController"
GS = "/Script/Engine.GameplayStatics"
KSL = "/Script/Engine.KismetSystemLibrary"
KML = "/Script/Engine.KismetMathLibrary"
PSTATE = "/Script/Engine.PlayerState"


def auth(g, ev):
    return Auth(g, CTRL_CLS, SG_CLS, MOD.SAVE_SLOT, (ev, "CallingPlayerController"))


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
    a = auth(g, ev)
    bHas = has_param(g, ev, (0, 0))
    a.message(bHas, "else", "Type the password after the command: dc OwlLogin <password>", (600, 600))
    first = g.array_get(ev, "Parameters", 0, (600, 300), elem_cat="string")
    a.check_password(bHas, "then", (first, "Output"), (600, 0))


# ---------------------------------------------------------------- dc OwlLogout (server)
def logout(g, ev):
    a = auth(g, ev)
    done = a.set_pending_and_call(ev, "then", "OwlLockPending", (300, 0))
    a.message(done, "then", "Admin mode locked.", (1300, 0))


# ---------------------------------------------------------------- dc OwlSetPassword <password> (server)
def set_password(g, ev):
    a = auth(g, ev)
    bHas = has_param(g, ev, (0, 0))
    a.message(bHas, "else", "Type the new password after the command (one word): dc OwlSetPassword <password>",
              (600, 600))
    first = g.array_get(ev, "Parameters", 0, (600, 300), elem_cat="string")
    a.store_password(bHas, "then", (first, "Output"), (600, 0))


# ---------------------------------------------------------------- dc OwlApply <value> x N (server)
def apply_settings(g, ev):
    """Only for players in admin mode (UnlockedPlayers, checked here on the server: the command
    row can't require Conan admin, since Owl admins needn't be). Exactly one value per setting."""
    a = auth(g, ev)
    bIn, gac = a.require_unlocked(ev, "then", (0, 0))
    n = g.array_len(ev, "Parameters", (800, 250), elem_cat="string")
    eq = g.call("EqualEqual_IntInt", KML, pos=(1050, 250))
    g.wire(n, "ReturnValue", eq, "A", exec=False)
    g.typed_input(eq, "B", str(len(D.SETTINGS)), "int")
    bN = g.branch(pos=(1050, 0))
    g.wire(bIn, "then", bN, "execute")
    g.wire(eq, "ReturnValue", bN, "Condition", exec=False)
    a.message(bN, "else", "Settings not applied: the menu and the server are on different Owl Admin "
                          "versions (expected %d values)." % len(D.SETTINGS), (1300, 700))
    crt = g.call("CreateSaveGameObject", GS, pos=(1300, 0))
    cp = crt.pin("SaveGameClass").typed("class", ir.obj_path("/Script/Engine.SaveGame"), direction="EGPD_Input")
    cp.set("PinType.bIsUObjectWrapper", "True")
    cp.set("DefaultObject", '"%s"' % SETTINGS_SG_CLS)
    crt.pin("ReturnValue").typed("object", ir.obj_path(SETTINGS_SG_CLS), direction="EGPD_Output")
    g.wire(bN, "then", crt, "execute")
    ss = g.var_set("Settings", "string", pos=(1600, 0), parent=SETTINGS_SG_CLS)
    ss.pin("Settings").set("PinType.ContainerType", "Array")
    g.wire(crt, "ReturnValue", ss, "self", exec=False)
    g.wire(ev, "Parameters", ss, "Settings", exec=False)
    g.wire(crt, "then", ss, "execute")
    sav = g.call("SaveGameToSlot", GS, pos=(1900, 0))
    g.typed_input(sav, "SlotName", MOD.SETTINGS_SLOT, "string")
    g.typed_input(sav, "UserIndex", "0", "int")
    g.wire(crt, "ReturnValue", sav, "SaveGameObject", exec=False)
    g.wire(ss, "then", sav, "execute")
    # hand the values to the controller: it keeps them (replicated) and pushes the LIVE ones
    sp = g.var_set("PendingSettings", "string", pos=(2200, 0), parent=CTRL_CLS)
    sp.pin("PendingSettings").set("PinType.ContainerType", "Array")
    g.wire(gac, "ReturnValue", sp, "self", exec=False)
    g.wire(ev, "Parameters", sp, "PendingSettings", exec=False)
    g.wire(sav, "then", sp, "execute")
    call = g.call("OwlSettingsPending", CTRL_CLS, pos=(2500, 0))
    g.wire(gac, "ReturnValue", call, "self", exec=False)
    g.wire(sp, "then", call, "execute")
    a.message(call, "then", "Restrictions applied and saved on the server.", (2800, 0))


BUILDERS = {"OwlAdmin": open_menu, "OwlLogin": login, "OwlLogout": logout, "OwlSetPassword": set_password,
            "OwlApply": apply_settings}
for cmd, cls, *_flags in MOD.COMMANDS:
    build_command(cls, BUILDERS[cmd])
print("BUILD OK: owl-admin v%d -> %d commands%s" % (
    MOD.VERSION, len(MOD.COMMANDS), "  [DRY RUN -- not shippable]" if PKG != MOD.OUTPUT_PKG else ""))
