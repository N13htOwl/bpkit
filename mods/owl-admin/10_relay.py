"""owl-admin step 10: BP_OwlRelay -- one per player, spawned by the controller (02) on the
server with that player's PlayerController as Owner. It is how the admin menu (03) sends a
password to the server without a console command: anything run as a console command is
written to the log ("Cmd: dc OwlLogin <password>"), an RPC's arguments are not.

    OwlServerLogin(Password)        Run on Server, reliable: check it -> unlock the owner
    OwlServerSetPassword(Password)  Run on Server, reliable: Conan admins only -> save it, mark it
                                    set for every client, unlock the owner

A client may only call Run-on-Server events on actors its own connection owns, which is why
each player has their own relay (owned = only relevant to that player, too). The checks are
oa_auth, the same as the console commands (04); the caller is the relay's owner.

Tick (server, 1 s): the owner is gone (player left) -> destroy the relay.

Run with Play STOPPED, after 02 (which creates the empty asset so it can spawn it) and 08:
    python ue_run.py mods/owl-admin/10_relay.py
"""
import sys
for _m in list(sys.modules):
    if _m == "bpkit" or _m.startswith("bpkit."):
        sys.modules.pop(_m, None)
import ctypes
import unreal
import os
from bpkit import bridge as bp, ir, build, config as _cfg
sys.path.insert(0, os.path.join(_cfg.REPO_ROOT, "mods", "owl-admin"))
for _m in ("oa_config", "oa_auth"):
    sys.modules.pop(_m, None)
import oa_config as MOD
from oa_auth import Auth

assert not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor(), \
    "Play-in-Editor is running -- stop Play first"

PKG = MOD.resolve_pkg()
PATH = "%s/%s" % (PKG, MOD.RELAY)
FULL = MOD.full(PKG, MOD.RELAY)
CTRL_CLS = MOD.full(PKG, MOD.CONTROLLER) + "_C"
SG_CLS = MOD.full(PKG, MOD.SAVEGAME) + "_C"
for c in (CTRL_CLS, SG_CLS):
    assert unreal.load_object(None, c), "build 02 and 08 first: no " + c

ACTOR = "/Script/Engine.Actor"
CPC = "/Script/ConanSandbox.ConanPlayerController"
KSL = "/Script/Engine.KismetSystemLibrary"
KML = "/Script/Engine.KismetMathLibrary"
KSTR = "/Script/Engine.KismetStringLibrary"
# K2Node_CustomEvent "Replicates: Run on Server, Reliable" = FUNC_Net | FUNC_NetReliable | FUNC_NetServer
RUN_ON_SERVER = 0x200000 | 0x80 | 0x40
EVENTS = ("OwlServerLogin", "OwlServerSetPassword")

bel = unreal.BlueprintEditorLibrary
bp_obj, _ = bp.scratch_blueprint(pkg=PKG, name=MOD.RELAY, parent=unreal.Actor)

g = ir.Graph("EventGraph")


def server_event(name, y):
    """The RPC: custom event with a Password string, then the owner as a ConanPlayerController."""
    ce = g.custom_event(name, pos=(0, y))
    ce.set("FunctionFlags", str(RUN_ON_SERVER))
    ce.set('CustomProperties UserDefinedPin (PinName="Password",PinType=(PinCategory="string"),'
           'DesiredPinDirection=EGPD_Output)')
    owner = g.call("GetOwner", ACTOR, pos=(0, y + 250))
    cast = g.cast(CPC, pos=(300, y))
    g.wire(owner, "ReturnValue", cast, "Object", exec=False)
    g.wire(ce, "then", cast, "execute")
    a = Auth(g, CTRL_CLS, SG_CLS, MOD.SAVE_SLOT, (cast, "AsConan Player Controller"))
    # an empty box sends an empty string: say so instead of checking it
    ln = g.call("Len", KSTR, pos=(600, y + 250))
    g.wire(ce, "Password", ln, "S", exec=False)
    gt = g.call("Greater_IntInt", KML, pos=(850, y + 250))
    g.wire(ln, "ReturnValue", gt, "A", exec=False)
    g.typed_input(gt, "B", "0", "int")
    bAny = g.branch(pos=(850, y))
    g.wire(cast, "then", bAny, "execute")
    g.wire(gt, "ReturnValue", bAny, "Condition", exec=False)
    a.message(bAny, "else", "Type a password first.", (1100, y + 700))
    return ce, a, bAny


# OwlServerLogin(Password): the same check as `dc OwlLogin`
ce, a, ok = server_event("OwlServerLogin", 0)
a.check_password(ok, "then", (ce, "Password"), (1100, 0))

# OwlServerSetPassword(Password): Conan admins only (the console command's RequireAdmin row flag)
ce, a, ok = server_event("OwlServerSetPassword", 2000)
adm = g.call("IsAdmin", CPC, pos=(1100, 2250))
g.wire(a.caller[0], a.caller[1], adm, "self", exec=False)
bAdm = g.branch(pos=(1100, 2000))
g.wire(ok, "then", bAdm, "execute")
g.wire(adm, "ReturnValue", bAdm, "Condition", exec=False)
a.message(bAdm, "else", "Only a Conan admin can set the Owl Admin password.", (1400, 2700))
a.store_password(bAdm, "then", (ce, "Password"), (1400, 2000))

# Tick, server only: the owning player left -> remove the relay
tick = g.event("ReceiveTick", parent=ACTOR, pos=(0, 4000))
auth = g.call("HasAuthority", ACTOR, pos=(0, 4250))
bAuth = g.branch(pos=(300, 4000))
g.wire(tick, "then", bAuth, "execute")
g.wire(auth, "ReturnValue", bAuth, "Condition", exec=False)
alive = g.call("IsValid", KSL, pos=(550, 4250))
g.wire(g.call("GetOwner", ACTOR, pos=(300, 4250)), "ReturnValue", alive, "Object", exec=False)
bAlive = g.branch(pos=(600, 4000))
g.wire(bAuth, "then", bAlive, "execute")
g.wire(alive, "ReturnValue", bAlive, "Condition", exec=False)
die = g.call("K2_DestroyActor", ACTOR, pos=(900, 4100))
g.wire(bAlive, "else", die, "execute")

# Clear + compile first, or a rebuild renames the pasted events (see 02)
bel.compile_blueprint(bp_obj)
_bp_ptr, _g_ptr = bp.find_graph(FULL, "EventGraph")
bp.clear_graph(_bp_ptr, _g_ptr)
bp.mark_structurally_modified(_bp_ptr)
bel.compile_blueprint(bp_obj)

rep = build.build_graph(FULL, g)
assert rep["ok"], "relay graph not clean: %r" % {k: rep[k] for k in ("dropped_nodes", "dropped_links", "orphans",
                                                                     "wildcards", "errors")}
# the events must exist under their own names AND compile as server RPCs (INTERNALS §10:
# EFunctionFlags at 0xd0 of the UFunction in this build)
for fn in EVENTS:
    f = unreal.find_object(None, FULL + "_C:" + fn)
    assert f, "custom event %s missing after build (renamed on paste?)" % fn
    flags = ctypes.c_uint32.from_address(bp.obj_addr(f) + 0xd0).value
    assert flags & RUN_ON_SERVER == RUN_ON_SERVER, "%s is not Run on Server: flags 0x%08x" % (fn, flags)
    print("%s: Run on Server, reliable (flags 0x%08x)" % (fn, flags))

gen = unreal.load_object(None, FULL + "_C")
cdo = unreal.get_default_object(gen)
cdo.set_editor_property("replicates", True)
cdo.set_editor_property("only_relevant_to_owner", True)
tk = cdo.get_editor_property("primary_actor_tick")
tk.set_editor_property("tick_interval", 1.0)
cdo.set_editor_property("primary_actor_tick", tk)
assert unreal.EditorAssetLibrary.save_asset(PATH), "save failed"
print("CDO: replicates=%s only_relevant_to_owner=%s" % (cdo.get_editor_property("replicates"),
                                                        cdo.get_editor_property("only_relevant_to_owner")))
print("BUILD OK: owl-admin v%d -> %s%s" % (
    MOD.VERSION, FULL, "  [DRY RUN -- not shippable]" if PKG != MOD.OUTPUT_PKG else ""))
