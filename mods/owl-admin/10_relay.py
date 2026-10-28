"""owl-admin step 10: BP_OwlRelay -- one per player, spawned by the controller (02) on the
server with that player's PlayerController as Owner. It is how the admin menu (03) sends a
password to the server without a console command: anything run as a console command is
written to the log ("Cmd: dc OwlLogin <password>"), an RPC's arguments are not.

    OwlServerLogin(Password)        Run on Server, reliable: check it -> unlock the owner
    OwlServerSetPassword(Password)  Run on Server, reliable: Conan admins only -> save it, mark it
                                    set for every client, unlock the owner

A client may only call Run-on-Server events on actors its own connection owns, which is why
each player has their own relay. The checks are oa_auth, the same as the console commands
(04); the caller is the relay's owner.

Transmog (the player menu's tab, 07): TmLook (replicated: everyone sees every look) and the
owner-only TmOutfitNames / TmOutfitLooks, sent by OwlClientTm (Run on owning Client; TmClientVer
goes up on arrival so the open menu reloads). BeginPlay (server) loads them from the owner's
OwlTransmog_<net id> save; OwlServerTmApply(Look) and OwlServerTmSaveOutfit(Name, Look)
(Run on Server) change and save them. Every player sees every look, so the relay is always
relevant (not only to its owner) and carries TmPawn, its player's character (other players'
controllers don't exist on a client). The outfits stay private: they aren't replicated, only
sent to the owner. OwlServerTmRequest asks for them again (the owner's client, once, in case
the BeginPlay send arrived before its relay existed there).

Tick (0.1 s):
    server: the owner is gone (player left) -> destroy the relay; else TmPawn = the owner's pawn
    owner's client: the first time, OwlServerTmRequest
    every machine with a screen: show TmLook on TmPawn. The character's real layout
        (BasePlayerChar_C.CharacterLayout, which the game saves and equipment changes) is broken
        apart and made again with each picked slot's item id in its CharacterMeshLayout member
        (menu_defs.TM_LAYOUT), and that copy goes to the customization component's
        ToggleCharacterLayoutOverride. The game resolves it like worn gear (male/female mesh,
        hidden hair, tucked legs), never saves it, and it doesn't change stats. A picked slot's
        dye is cleared (the real item's dye would tint the transmog piece). Redone only when
        the result changes (TmApplied: the pawn + the ten mesh ids); an empty look turns it off.
        The live layout is only ever read: writing to it rewrites the player's character.

Character editor (the admin menu's Characters tab, 03): the OwlServerCe* / OwlClientCe* events
and their Ce* / Sv* variables come from ce_server.py (see its docstring).

Bug reports (the player menu's Bug Report tab, 07; the admin menu's Bug Reports tab, 03): the
OwlServerBug* / OwlClientBug* events and their Bug* / SvBug* variables come from bug_server.py.

The HUD tab (03): OwlServerHudSet / OwlClientHudSaved and their Hud* / SvHud* variables come
from hud_server.py. It writes the controller's (02) replicated HudOn / HudText / HudVer, so 02
must have them: build 02 before this.

The Server Restart tab (03): OwlServerRsSet / OwlServerRsCount / OwlClientRsSaved and their
Rs* / SvRs* variables come from restart_server.py; they write the controller's Rs* (02 again).

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
for _m in ("oa_config", "oa_auth", "menu_defs", "ce_server", "bug_server", "hud_server", "restart_server"):
    sys.modules.pop(_m, None)
import types
import oa_config as MOD
import menu_defs as D
import ce_server
import bug_server
import hud_server
import restart_server
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
# K2Node_CustomEvent "Replicates: Run on Server, Reliable" = FUNC_Net | FUNC_NetReliable | FUNC_NetServer;
# "Run on owning Client, Reliable" = FUNC_Net | FUNC_NetReliable | FUNC_NetClient
RUN_ON_SERVER = 0x200000 | 0x80 | 0x40
RUN_ON_OWNING_CLIENT = 0x1000000 | 0x80 | 0x40
EVENTS = {"OwlServerLogin": RUN_ON_SERVER, "OwlServerSetPassword": RUN_ON_SERVER, "OwlServerTmApply": RUN_ON_SERVER,
          "OwlServerTmSaveOutfit": RUN_ON_SERVER, "OwlServerTmRequest": RUN_ON_SERVER,
          "OwlClientTm": RUN_ON_OWNING_CLIENT}

TM_SG_CLS = MOD.full(PKG, MOD.TM_SAVEGAME) + "_C"
for c in (TM_SG_CLS, MOD.full(PKG, MOD.CE_SAVEGAME) + "_C", MOD.full(PKG, MOD.ECON_SAVEGAME) + "_C",
          MOD.full(PKG, MOD.BUG_SAVEGAME) + "_C", MOD.full(PKG, MOD.HUD_SAVEGAME) + "_C",
          MOD.full(PKG, MOD.RESTART_SAVEGAME) + "_C"):
    assert unreal.load_object(None, c), "build 08 first: no " + c
assert unreal.get_default_object(unreal.load_object(None, CTRL_CLS)).get_editor_property("HudVer") is not None, \
    "rebuild 02 first: the controller has no HudVer"
assert unreal.get_default_object(unreal.load_object(None, CTRL_CLS)).get_editor_property("RsVer") is not None, \
    "rebuild 02 first: the controller has no RsVer"

bel = unreal.BlueprintEditorLibrary
bp_obj, _ = bp.scratch_blueprint(pkg=PKG, name=MOD.RELAY, parent=unreal.Actor)
# transmog state. TmLook + TmPawn replicate to every player (the relay is always relevant);
# the outfits are the owner's alone, so they don't replicate: OwlClientTm sends them to the owner
strings_t = bel.get_array_type(bel.get_basic_type_by_name("string"))
REPL = unreal.BlueprintVariableReplication
for var, vtype, repl in (("TmLook", strings_t, REPL.REPLICATED),
                         ("TmPawn", bel.get_object_reference_type(unreal.Pawn.static_class()), REPL.REPLICATED),
                         ("TmOutfitNames", strings_t, REPL.NONE), ("TmOutfitLooks", strings_t, REPL.NONE),
                         ("TmClientVer", bel.get_basic_type_by_name("int"), REPL.NONE),  # + 1 per OwlClientTm
                         ("TmAsked", bel.get_basic_type_by_name("bool"), REPL.NONE),     # sent OwlServerTmRequest
                         # what this machine last showed on TmPawn
                         ("TmApplied", bel.get_basic_type_by_name("string"), REPL.NONE),
                         ("TmOn", bel.get_basic_type_by_name("bool"), REPL.NONE)):
    bel.add_member_variable(bp_obj, var, vtype)
    bel.set_blueprint_variable_replication(bp_obj, var, repl)
# character editor (ce_server): the owner's copy the admin panel reads + the server's scratch values
CE_VARS = ce_server.variables(unreal, bel, unreal.load_object(None, MOD.full(PKG, MOD.CE_SAVEGAME) + "_C"))
# bug reports (bug_server): the same, for the Bug Report / Bug Reports tabs
CE_VARS += bug_server.variables(unreal, bel, unreal.load_object(None, MOD.full(PKG, MOD.BUG_SAVEGAME) + "_C"))
# the HUD tab (hud_server)
CE_VARS += hud_server.variables(unreal, bel)
# the Server Restart tab (restart_server)
CE_VARS += restart_server.variables(unreal, bel)
for var, vtype in CE_VARS:
    bel.add_member_variable(bp_obj, var, vtype)
    bel.set_blueprint_variable_replication(bp_obj, var, REPL.NONE)

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

# ---------------------------------------------------------------- transmog (player menu, 07)
# TmLook: 5 item row names, one per menu_defs.TM_SLOTS slot ("" = worn gear). TmOutfitNames +
# TmOutfitLooks (5 row names per outfit, flattened). Saved per player in OwlTransmog_<net id>;
# they reach the owner by OwlClientTm; TmClientVer goes up on arrival so the open menu reloads.
TM_ARRAYS = (("TmLook", "Look"), ("TmOutfitNames", "OutfitNames"), ("TmOutfitLooks", "OutfitLooks"))
N_SLOTS = len(D.TM_SLOTS)


def strings(name, pos, parent=None):
    return g.array_var(name, pos=pos, elem_cat="string", parent=parent)


def set_strings(name, src, src_pin, pos):
    n = g.var_set(name, "string", pos=pos)
    n.pin(name).set("PinType.ContainerType", "Array")
    g.wire(src, src_pin, n, name, exec=False)
    return n


def owner_pc(prev, prev_pin, pos):
    """GetOwner -> cast to ConanPlayerController (exec). Returns the cast node."""
    owner = g.call("GetOwner", ACTOR, pos=(pos[0], pos[1] + 250))
    cast = g.cast(CPC, pos=pos)
    g.wire(owner, "ReturnValue", cast, "Object", exec=False)
    g.wire(prev, prev_pin, cast, "execute")
    return cast


def save_slot(cast, pos, prefix=MOD.TM_SLOT_PREFIX):
    """prefix + the net id of cast's ConanPlayerController, ':' and '/' made file-name safe
    (pure). In Play-in-Editor the id ends "-Context_<n>" and n goes up every session; that tail is
    dropped so a save survives a Play restart (real Steam ids have no such tail)."""
    nid = g.call("GetPlayerNetId", CPC, pos=pos)
    g.wire(cast, "AsConan Player Controller", nid, "self", exec=False)
    sp = g.call("Split", KSTR, pos=(pos[0], pos[1] + 200))
    g.wire(nid, "ReturnValue", sp, "SourceString", exec=False)
    g.typed_input(sp, "InStr", "-Context_", "string")
    stem = g.call("SelectString", KML, pos=(pos[0] + 250, pos[1] + 200))
    g.wire(sp, "LeftS", stem, "A", exec=False)
    g.wire(nid, "ReturnValue", stem, "B", exec=False)
    g.wire(sp, "ReturnValue", stem, "bPickA", exec=False)
    prev = (stem, "ReturnValue")
    for i, ch in enumerate((":", "/", "\\")):
        rep = g.call("Replace", KSTR, pos=(pos[0] + 250 * (i + 1), pos[1]))
        g.wire(prev[0], prev[1], rep, "SourceString", exec=False)
        g.typed_input(rep, "From", ch, "string")
        g.typed_input(rep, "To", "_", "string")
        prev = (rep, "ReturnValue")
    cat = g.call("Concat_StrStr", KSTR, pos=(pos[0] + 1000, pos[1]))
    g.typed_input(cat, "A", prefix, "string")
    g.wire(prev[0], prev[1], cat, "B", exec=False)
    return cat


SELF_CALLS = []


def self_call(name, pos):
    """Call one of this blueprint's own events on self (the unwired target). Its function isn't on
    the class until the graph compiles, so this node drops on paste; it is pasted again after."""
    c = g.call(name, FULL + "_C", pos=pos)
    c.pin("execute").typed("exec", direction="EGPD_Input")
    c.pin("then").typed("exec", direction="EGPD_Output")
    SELF_CALLS.append(c)
    return c


def send(entries, pos):
    """Server -> owner: OwlClientTm(TmLook, TmOutfitNames, TmOutfitLooks), entered from each (node, exec pin)."""
    c = self_call("OwlClientTm", pos)
    for i, (mine, param) in enumerate((("TmLook", "Look"), ("TmOutfitNames", "Names"), ("TmOutfitLooks", "Looks"))):
        c.pin(param).typed("string", direction="EGPD_Input", container="Array", ref=True, const=True)
        g.wire(strings(mine, (pos[0] - 250, pos[1] + 200 + 150 * i)), mine, c, param, exec=False)
    for e, ep in entries:
        g.wire(e, ep, c, "execute")
    return c


def save_tm(entries, cast, pos):
    """Write TmLook / TmOutfitNames / TmOutfitLooks to the owner's save slot, then send them to the owner."""
    x, y = pos
    crt = g.call("CreateSaveGameObject", GS_, pos=(x, y))
    cp = crt.pin("SaveGameClass").typed("class", ir.obj_path("/Script/Engine.SaveGame"), direction="EGPD_Input")
    cp.set("PinType.bIsUObjectWrapper", "True")
    cp.set("DefaultObject", '"%s"' % TM_SG_CLS)
    crt.pin("ReturnValue").typed("object", ir.obj_path(TM_SG_CLS), direction="EGPD_Output")
    for e, ep in entries:
        g.wire(e, ep, crt, "execute")
    prev = crt
    for i, (mine, saved) in enumerate(TM_ARRAYS):
        st = g.var_set(saved, "string", pos=(x + 300 * (i + 1), y), parent=TM_SG_CLS)
        st.pin(saved).set("PinType.ContainerType", "Array")
        g.wire(crt, "ReturnValue", st, "self", exec=False)
        g.wire(strings(mine, (x + 300 * (i + 1), y + 250)), mine, st, saved, exec=False)
        g.wire(prev, "then", st, "execute")
        prev = st
    sav = g.call("SaveGameToSlot", GS_, pos=(x + 1300, y))
    g.wire(save_slot(cast, (x + 300, y + 450)), "ReturnValue", sav, "SlotName", exec=False)
    g.typed_input(sav, "UserIndex", "0", "int")
    g.wire(crt, "ReturnValue", sav, "SaveGameObject", exec=False)
    g.wire(prev, "then", sav, "execute")
    return send([(sav, "then")], (x + 1600, y))


def len_is(arr_node, arr_pin, n, pos, op="EqualEqual_IntInt"):
    ln = g.array_len(arr_node, arr_pin, pos, elem_cat="string")
    cmp_ = g.call(op, KML, pos=(pos[0] + 250, pos[1]))
    g.wire(ln, "ReturnValue", cmp_, "A", exec=False)
    g.typed_input(cmp_, "B", str(n), "int")
    return cmp_


GS_ = "/Script/Engine.GameplayStatics"

# BeginPlay, server: load the owner's saved look and outfits
bgn = g.event("ReceiveBeginPlay", parent=ACTOR, pos=(0, 6000))
ha = g.call("HasAuthority", ACTOR, pos=(0, 6250))
bHa = g.branch(pos=(300, 6000))
g.wire(bgn, "then", bHa, "execute")
g.wire(ha, "ReturnValue", bHa, "Condition", exec=False)
bc = owner_pc(bHa, "then", (600, 6000))
dse = g.call("DoesSaveGameExist", GS_, pos=(900, 6000))
g.wire(save_slot(bc, (600, 6500)), "ReturnValue", dse, "SlotName", exec=False)
g.typed_input(dse, "UserIndex", "0", "int")
g.wire(bc, "then", dse, "execute")
bEx = g.branch(pos=(1200, 6000))
g.wire(dse, "then", bEx, "execute")
g.wire(dse, "ReturnValue", bEx, "Condition", exec=False)
load = g.call("LoadGameFromSlot", GS_, pos=(1500, 6000))
g.wire(save_slot(bc, (1500, 6800)), "ReturnValue", load, "SlotName", exec=False)
g.typed_input(load, "UserIndex", "0", "int")
g.wire(bEx, "then", load, "execute")
sc = g.cast(TM_SG_CLS, pos=(1800, 6000))
g.wire(load, "ReturnValue", sc, "Object", exec=False)
g.wire(load, "then", sc, "execute")
prev = sc
for i, (mine, saved) in enumerate(TM_ARRAYS):
    src = strings(saved, (2100 + 300 * i, 6250), parent=TM_SG_CLS)
    g.wire(sc, "AsBP Owl Transmog Save", src, "self", exec=False)
    st = set_strings(mine, src, saved, (2100 + 300 * i, 6000))
    g.wire(prev, "then", st, "execute")
    prev = st
send([(prev, "then"), (bEx, "else"), (sc, "CastFailed")], (3200, 6000))


def tm_event(name, pins, y, flags=None):
    """A Run-on-Server (default) transmog event with the given (name, category, is_array) params."""
    ce = g.custom_event(name, pos=(0, y))
    ce.set("FunctionFlags", str(flags or RUN_ON_SERVER))
    for pn, cat, arr in pins:
        ce.set('CustomProperties UserDefinedPin (PinName="%s",PinType=(PinCategory="%s"%s),'
               'DesiredPinDirection=EGPD_Output)' % (pn, cat,
                                                      # arrays: const ref, or the compiler says
                                                      # "No value will be returned by reference"
                                                      ",ContainerType=Array,bIsReference=True,bIsConst=True"
                                                      if arr else ""))
    return ce


# OwlServerTmApply(Look): exactly one entry per slot -> TmLook, save
ce = tm_event("OwlServerTmApply", [("Look", "string", True)], 7500)
ac = owner_pc(ce, "then", (300, 7500))
bOk = g.branch(pos=(600, 7500))
g.wire(ac, "then", bOk, "execute")
g.wire(len_is(ce, "Look", N_SLOTS, (300, 7800)), "ReturnValue", bOk, "Condition", exec=False)
sl = set_strings("TmLook", ce, "Look", (900, 7500))
g.wire(bOk, "then", sl, "execute")
save_tm([(sl, "then")], ac, (1200, 7500))

# OwlServerTmSaveOutfit(Name, Look): same name -> overwrite it; else add if there's room
ce = tm_event("OwlServerTmSaveOutfit", [("Name", "string", False), ("Look", "string", True)], 9000)
oc = owner_pc(ce, "then", (300, 9000))
oa = Auth(g, CTRL_CLS, SG_CLS, MOD.SAVE_SLOT, (oc, "AsConan Player Controller"))
nameLen = g.call("Len", KSTR, pos=(300, 9450))
g.wire(ce, "Name", nameLen, "S", exec=False)
named = g.call("Greater_IntInt", KML, pos=(550, 9450))
g.wire(nameLen, "ReturnValue", named, "A", exec=False)
g.typed_input(named, "B", "0", "int")
both = g.call("BooleanAND", KML, pos=(800, 9300))
g.wire(named, "ReturnValue", both, "A", exec=False)
g.wire(len_is(ce, "Look", N_SLOTS, (550, 9300)), "ReturnValue", both, "B", exec=False)
bValid = g.branch(pos=(800, 9000))
g.wire(oc, "then", bValid, "execute")
g.wire(both, "ReturnValue", bValid, "Condition", exec=False)
find = g.array_fn("Array_Find", pos=(1100, 9300), elem_cat="string")
g.array_item_pin(find, "ItemToFind", "string")
find.pin("ReturnValue").typed("int", direction="EGPD_Output")
g.wire(strings("TmOutfitNames", (850, 9500)), "TmOutfitNames", find, "TargetArray", exec=False)
g.wire(ce, "Name", find, "ItemToFind", exec=False)
known = g.call("GreaterEqual_IntInt", KML, pos=(1350, 9300))
g.wire(find, "ReturnValue", known, "A", exec=False)
g.typed_input(known, "B", "0", "int")
bKnown = g.branch(pos=(1350, 9000))
g.wire(bValid, "then", bKnown, "execute")
g.wire(known, "ReturnValue", bKnown, "Condition", exec=False)
# overwrite: TmOutfitLooks[idx*N + k] = Look[k]
base = g.call("Multiply_IntInt", KML, pos=(1600, 9500))
g.wire(find, "ReturnValue", base, "A", exec=False)
g.typed_input(base, "B", str(N_SLOTS), "int")
prev, prev_pin = bKnown, "then"
for k in range(N_SLOTS):
    at = g.call("Add_IntInt", KML, pos=(1900 + 300 * k, 9500))
    g.wire(base, "ReturnValue", at, "A", exec=False)
    g.typed_input(at, "B", str(k), "int")
    item = g.array_get(ce, "Look", k, (1900 + 300 * k, 9650), elem_cat="string")
    st = g.array_fn("Array_Set", pos=(1900 + 300 * k, 9000), elem_cat="string")
    g.array_item_pin(st, "Item", "string")
    g.wire(strings("TmOutfitLooks", (1900 + 300 * k, 9350)), "TmOutfitLooks", st, "TargetArray", exec=False)
    g.wire(at, "ReturnValue", st, "Index", exec=False)
    g.wire(item, "Output", st, "Item", exec=False)
    g.wire(prev, prev_pin, st, "execute")
    prev, prev_pin = st, "then"
overwritten = (prev, prev_pin)
# new: room left?
bRoom = g.branch(pos=(1600, 10000))
g.wire(bKnown, "else", bRoom, "execute")
g.wire(len_is(strings("TmOutfitNames", (1350, 10250)), "TmOutfitNames", MOD.TM_MAX_OUTFITS, (1600, 10250),
              op="Less_IntInt"), "ReturnValue", bRoom, "Condition", exec=False)
addName = g.array_fn("Array_Add", pos=(1900, 10000), elem_cat="string")
g.array_item_pin(addName, "NewItem", "string")
g.wire(strings("TmOutfitNames", (1900, 10250)), "TmOutfitNames", addName, "TargetArray", exec=False)
g.wire(ce, "Name", addName, "NewItem", exec=False)
g.wire(bRoom, "then", addName, "execute")
addLook = g.array_fn("Array_Append", pos=(2200, 10000), elem_cat="string")
sa = addLook.pin("SourceArray")
sa.dir = "EGPD_Input"
sa.typed("string", container="Array", ref=True, const=True)
g.wire(strings("TmOutfitLooks", (2200, 10250)), "TmOutfitLooks", addLook, "TargetArray", exec=False)
g.wire(ce, "Look", addLook, "SourceArray", exec=False)
g.wire(addName, "then", addLook, "execute")
oa.message(bRoom, "else", "You have %d saved outfits. Save over one by typing its name." % MOD.TM_MAX_OUTFITS,
           (1900, 10600))
save_tm([overwritten, (addLook, "then")], oc, (3600, 9000))

# OwlServerTmRequest(): the owner's client asks for its look + outfits (once, from Tick)
ce = tm_event("OwlServerTmRequest", [], 11000)
send([(ce, "then")], (500, 11000))

# OwlClientTm(Look, Names, Looks), run on the owning client: store them, TmClientVer + 1 (the menu
# reloads when it changes). TmLook is set too, so the menu never reads it before replication.
ce = tm_event("OwlClientTm", [("Look", "string", True), ("Names", "string", True), ("Looks", "string", True)],
              12000, flags=RUN_ON_OWNING_CLIENT)
prev = ce
for i, (mine, param) in enumerate((("TmLook", "Look"), ("TmOutfitNames", "Names"), ("TmOutfitLooks", "Looks"))):
    st = set_strings(mine, ce, param, (400 + 300 * i, 12000))
    g.wire(prev, "then", st, "execute")
    prev = st
inc = g.call("Add_IntInt", KML, pos=(1300, 12200))
g.wire(g.var_get("TmClientVer", "int", pos=(1100, 12200)), "TmClientVer", inc, "A", exec=False)
g.typed_input(inc, "B", "1", "int")
setVer = g.var_set("TmClientVer", "int", pos=(1500, 12000))
g.wire(inc, "ReturnValue", setVer, "TmClientVer", exec=False)
g.wire(prev, "then", setVer, "execute")

# Tick, server: the owning player left -> remove the relay; else TmPawn = their character
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
CONTROLLER = "/Script/Engine.Controller"
PAWN = "/Script/Engine.Pawn"
pcCast = g.cast(CONTROLLER, pos=(900, 3800))
pcCast.pin("Object").typed("object", ir.obj_path(ACTOR), direction="EGPD_Input")
owner = g.call("GetOwner", ACTOR, pos=(700, 3950))
owner.pin("ReturnValue").typed("object", ir.obj_path(ACTOR), direction="EGPD_Output")
g.wire(owner, "ReturnValue", pcCast, "Object", exec=False)
g.wire(bAlive, "then", pcCast, "execute")
getPawn = g.call("K2_GetPawn", CONTROLLER, pos=(1150, 3950))
g.wire(pcCast, "AsController", getPawn, "self", exec=False)
setPawn = g.var_set("TmPawn", "object", ir.obj_path(PAWN), pos=(1400, 3800))
g.wire(getPawn, "ReturnValue", setPawn, "TmPawn", exec=False)
g.wire(pcCast, "then", setPawn, "execute")

# Tick, every machine with a screen: show TmLook on TmPawn (see the docstring)
CHAR_CLS = "/Game/Characters/BasePlayerChar.BasePlayerChar_C"
CCC = "/Script/ConanSandbox.CharacterCustomizationComponent"
CS = "/Script/ConanSandbox."
LAYOUT, MESHL = CS + "CharacterLayout", CS + "CharacterMeshLayout"
LAYOUT_MEMBERS = (("MeshLayout", MESHL), ("TextureLayout", CS + "CharacterTextureLayout"),
                  ("TintLayout", CS + "CharacterTintLayout"), ("ArmourDyeParams", CS + "CharacterArmourDyeParams"),
                  ("BoolParams", CS + "CharacterBoolParameters"), ("IntParams", CS + "CharacterIntParameters"),
                  ("ScalarParams", CS + "CharacterScalarParameters"), ("EnumParams", CS + "CharacterEnumParameters"))
MESH_MEMBERS = ("Helmet", "Hair", "FacialHair", "Head", "Forearms", "Hands", "UpperBody", "LowerBody", "Legs", "Feet")
picked_member = {D.TM_LAYOUT[k][1]: i for i, (k, _l, _loc) in enumerate(D.TM_SLOTS)}
Y = 14000


def struct_node(kind, spath, pos):
    """K2Node_BreakStruct / K2Node_MakeStruct of a native struct; its struct pin is named after the struct."""
    hdr = ['StructType="%s"' % ir.struct_path(spath)] + (["bMadeAfterOverridePinRemoval=True"] if kind == "Make" else [])
    n = g.node("K2Node_%sStruct" % kind, hdr, base=kind + "Struct", pos=pos)
    n.pin(spath.split(".")[-1]).typed("struct", ir.struct_path(spath),
                                      direction="EGPD_Input" if kind == "Break" else "EGPD_Output")
    return n


def toggle(prev, prev_pin, enable, layout_src, pos):
    """The pawn's CharacterCustomizationComponent -> ToggleCharacterLayoutOverride(enable, layout),
    deferred (the game's own way), never forced."""
    gc = g.call("GetComponentByClass", ACTOR, pos=(pos[0], pos[1] + 250))
    g.wire(pawnCast, "AsBase Player Char", gc, "self", exec=False)
    cp = gc.pin("ComponentClass").typed("class", ir.obj_path("/Script/Engine.ActorComponent"), direction="EGPD_Input")
    cp.set("DefaultObject", '"%s"' % CCC)
    gc.pin("ReturnValue").typed("object", ir.obj_path(CCC), direction="EGPD_Output")
    t = g.call("ToggleCharacterLayoutOverride", CCC, pos=(pos[0] + 300, pos[1]))
    g.wire(gc, "ReturnValue", t, "self", exec=False)
    g.typed_input(t, "bInEnable", "true" if enable else "false", "bool")
    g.typed_input(t, "InDeferred", "true", "bool")
    g.typed_input(t, "InForce", "false", "bool")
    t.pin("InLayoutOverride").typed("struct", ir.struct_path(LAYOUT), direction="EGPD_Input", ref=True, const=True)
    g.wire(layout_src[0], layout_src[1], t, "InLayoutOverride", exec=False)
    g.wire(prev, prev_pin, t, "execute")
    return t


# Tick, a client: its own relay asks the server once for its look + outfits (OwlClientTm answers).
# Other players' relays have no owner here (their controllers don't exist on this client).
askCast = g.cast("/Script/Engine.PlayerController", pos=(600, Y - 1200))
askCast.pin("Object").typed("object", ir.obj_path(ACTOR), direction="EGPD_Input")
askOwner = g.call("GetOwner", ACTOR, pos=(400, Y - 1000))
askOwner.pin("ReturnValue").typed("object", ir.obj_path(ACTOR), direction="EGPD_Output")
g.wire(askOwner, "ReturnValue", askCast, "Object", exec=False)
g.wire(bAuth, "else", askCast, "execute")
isLocal = g.call("IsLocalPlayerController", CONTROLLER, pos=(900, Y - 1000))
g.wire(askCast, "AsPlayer Controller", isLocal, "self", exec=False)
notAsked = g.call("Not_PreBool", KML, pos=(900, Y - 850))
g.wire(g.var_get("TmAsked", "bool", pos=(700, Y - 850)), "TmAsked", notAsked, "A", exec=False)
mustAsk = g.call("BooleanAND", KML, pos=(1150, Y - 950))
g.wire(isLocal, "ReturnValue", mustAsk, "A", exec=False)
g.wire(notAsked, "ReturnValue", mustAsk, "B", exec=False)
bAsk = g.branch(pos=(900, Y - 1200))
g.wire(askCast, "then", bAsk, "execute")
g.wire(mustAsk, "ReturnValue", bAsk, "Condition", exec=False)
setAsked = g.var_set("TmAsked", "bool", pos=(1150, Y - 1200))
setAsked.pin("TmAsked").literal("true")
g.wire(bAsk, "then", setAsked, "execute")
ask = self_call("OwlServerTmRequest", (1400, Y - 1200))
g.wire(setAsked, "then", ask, "execute")

dds = g.call("IsDedicatedServer", KSL, pos=(1700, Y + 250))
bScreen = g.branch(pos=(1700, Y))
for e, ep in ((setPawn, "then"), (pcCast, "CastFailed"), (ask, "then"), (bAsk, "else"), (askCast, "CastFailed")):
    g.wire(e, ep, bScreen, "execute")
g.wire(dds, "ReturnValue", bScreen, "Condition", exec=False)
pawnCast = g.cast(CHAR_CLS, pos=(2000, Y))
g.wire(g.var_get("TmPawn", "object", ir.obj_path(PAWN), pos=(1800, Y + 250)), "TmPawn", pawnCast, "Object",
       exec=False)
g.wire(bScreen, "else", pawnCast, "execute")
real = g.var_get("CharacterLayout", "struct", ir.struct_path(LAYOUT), parent=CHAR_CLS, pos=(2000, Y + 400))
g.wire(pawnCast, "AsBase Player Char", real, "self", exec=False)
brk = struct_node("Break", LAYOUT, (2300, Y + 400))
g.wire(real, "CharacterLayout", brk, "CharacterLayout", exec=False)
for m, sp in LAYOUT_MEMBERS:
    brk.pin(m).typed("struct", ir.struct_path(sp), direction="EGPD_Output")
brkM = struct_node("Break", MESHL, (2600, Y + 400))
g.wire(brk, "MeshLayout", brkM, "CharacterMeshLayout", exec=False)
for m in MESH_MEMBERS:
    brkM.pin(m).typed("int", direction="EGPD_Output")
# the look must be N_SLOTS long; anything else counts as no look
look_ok = g.call("EqualEqual_IntInt", KML, pos=(2300, Y + 250))
g.wire(g.array_len(strings("TmLook", (2000, Y + 250)), "TmLook", (2150, Y + 250), elem_cat="string"), "ReturnValue",
       look_ok, "A", exec=False)
g.typed_input(look_ok, "B", str(N_SLOTS), "int")
bLen = g.branch(pos=(2300, Y))
g.wire(pawnCast, "then", bLen, "execute")
g.wire(look_ok, "ReturnValue", bLen, "Condition", exec=False)
# each mesh member: the picked item id where the look has one, else the real value
mkM = struct_node("Make", MESHL, (3800, Y + 400))
anyPick, key, has_of = None, None, {}
x = 2900
for m in MESH_MEMBERS:
    if m in picked_member:
        item = g.array_get(strings("TmLook", (x, Y + 900)), "TmLook", picked_member[m], (x + 150, Y + 900),
                           elem_cat="string")
        ln = g.call("Len", KSTR, pos=(x + 350, Y + 1050))
        g.wire(item, "Output", ln, "S", exec=False)
        has = g.call("Greater_IntInt", KML, pos=(x + 550, Y + 1050))
        g.wire(ln, "ReturnValue", has, "A", exec=False)
        g.typed_input(has, "B", "0", "int")
        asInt = g.call("Conv_StringToInt", KSTR, pos=(x + 350, Y + 900))
        g.wire(item, "Output", asInt, "InString", exec=False)
        sel = g.call("SelectInt", KML, pos=(x + 600, Y + 800))
        g.wire(asInt, "ReturnValue", sel, "A", exec=False)
        g.wire(brkM, m, sel, "B", exec=False)
        g.wire(has, "ReturnValue", sel, "bPickA", exec=False)
        src = (sel, "ReturnValue")
        has_of[m] = (has, "ReturnValue")
        if anyPick is None:
            anyPick = (has, "ReturnValue")
        else:
            orN = g.call("BooleanOR", KML, pos=(x + 750, Y + 1200))
            g.wire(anyPick[0], anyPick[1], orN, "A", exec=False)
            g.wire(has, "ReturnValue", orN, "B", exec=False)
            anyPick = (orN, "ReturnValue")
        x += 150
    else:
        src = (brkM, m)
    mkM.pin(m).typed("int", direction="EGPD_Input")
    g.wire(src[0], src[1], mkM, m, exec=False)
    # key: the pawn's name + the ten ids
    s = g.call("Conv_IntToString", KSTR, pos=(3600, Y + 1400 + 120 * MESH_MEMBERS.index(m)))
    g.wire(src[0], src[1], s, "InInt", exec=False)
    if key is None:
        nm = g.call("GetDisplayName", KSL, pos=(3600, Y + 1300))
        g.wire(pawnCast, "AsBase Player Char", nm, "Object", exec=False)
        key = (nm, "ReturnValue")
    cat = g.call("Concat_StrStr", KSTR, pos=(3850, Y + 1400 + 120 * MESH_MEMBERS.index(m)))
    g.wire(key[0], key[1], cat, "A", exec=False)
    g.wire(s, "ReturnValue", cat, "B", exec=False)
    sep = g.call("Concat_StrStr", KSTR, pos=(4100, Y + 1400 + 120 * MESH_MEMBERS.index(m)))
    g.wire(cat, "ReturnValue", sep, "A", exec=False)
    g.typed_input(sep, "B", "|", "string")
    key = (sep, "ReturnValue")
# dye: a picked slot shows its item undyed (all channels 0), the rest keep the real gear's dye
DYE, SLOT_DYE = CS + "CharacterArmourDyeParams", CS + "ArmourSlotDyeParams"
DYE_MEMBERS = ("Helmet", "Forearms", "Hands", "UpperBody", "LowerBody", "Legs", "Feet")
CHANNELS = ("Channel1", "Channel2", "Channel3", "Channel4")
brkD = struct_node("Break", DYE, (3000, Y + 3800))
g.wire(brk, "ArmourDyeParams", brkD, "CharacterArmourDyeParams", exec=False)
mkD = struct_node("Make", DYE, (4000, Y + 3800))
for i, m in enumerate(DYE_MEMBERS):
    brkD.pin(m).typed("struct", ir.struct_path(SLOT_DYE), direction="EGPD_Output")
    mkD.pin(m).typed("struct", ir.struct_path(SLOT_DYE), direction="EGPD_Input")
    if m not in has_of:
        g.wire(brkD, m, mkD, m, exec=False)
        continue
    y = Y + 3800 + 400 * i
    bs = struct_node("Break", SLOT_DYE, (3300, y))
    g.wire(brkD, m, bs, "ArmourSlotDyeParams", exec=False)
    ms = struct_node("Make", SLOT_DYE, (3750, y))
    for j, ch in enumerate(CHANNELS):
        bs.pin(ch).typed("int", direction="EGPD_Output")
        ms.pin(ch).typed("int", direction="EGPD_Input")
        sel = g.call("SelectInt", KML, pos=(3550, y + 90 * j))
        g.typed_input(sel, "A", "0", "int")
        g.wire(bs, ch, sel, "B", exec=False)
        g.wire(has_of[m][0], has_of[m][1], sel, "bPickA", exec=False)
        g.wire(sel, "ReturnValue", ms, ch, exec=False)
    g.wire(ms, "ArmourSlotDyeParams", mkD, m, exec=False)
mkL = struct_node("Make", LAYOUT, (4100, Y + 400))
for m, sp in LAYOUT_MEMBERS:
    mkL.pin(m).typed("struct", ir.struct_path(sp), direction="EGPD_Input")
    if m == "MeshLayout":
        g.wire(mkM, "CharacterMeshLayout", mkL, m, exec=False)
    elif m == "ArmourDyeParams":
        g.wire(mkD, "CharacterArmourDyeParams", mkL, m, exec=False)
    else:
        g.wire(brk, m, mkL, m, exec=False)
# a pick -> (re)apply when the result changed
bAny = g.branch(pos=(2600, Y))
g.wire(bLen, "then", bAny, "execute")
g.wire(anyPick[0], anyPick[1], bAny, "Condition", exec=False)
changed = g.call("NotEqual_StrStr", KSTR, pos=(4400, Y + 250))
g.wire(key[0], key[1], changed, "A", exec=False)
g.wire(g.var_get("TmApplied", "string", pos=(4200, Y + 300)), "TmApplied", changed, "B", exec=False)
bChanged = g.branch(pos=(4500, Y))
g.wire(bAny, "then", bChanged, "execute")
g.wire(changed, "ReturnValue", bChanged, "Condition", exec=False)
setKey = g.var_set("TmApplied", "string", pos=(4800, Y))
g.wire(key[0], key[1], setKey, "TmApplied", exec=False)
g.wire(bChanged, "then", setKey, "execute")
setOn = g.var_set("TmOn", "bool", pos=(5100, Y))
setOn.pin("TmOn").literal("true")
g.wire(setKey, "then", setOn, "execute")
toggle(setOn, "then", True, (mkL, "CharacterLayout"), (5400, Y))
# no pick (or no valid look) -> turn it off, once
bWasOn = g.branch(pos=(2900, Y + 2800))
for e, ep in ((bAny, "else"), (bLen, "else")):
    g.wire(e, ep, bWasOn, "execute")
g.wire(g.var_get("TmOn", "bool", pos=(2700, Y + 3000)), "TmOn", bWasOn, "Condition", exec=False)
setOff = g.var_set("TmOn", "bool", pos=(3200, Y + 2800))
setOff.pin("TmOn").literal("false")
g.wire(bWasOn, "then", setOff, "execute")
clearKey = g.var_set("TmApplied", "string", pos=(3500, Y + 2800))
clearKey.pin("TmApplied").literal("")
g.wire(setOff, "then", clearKey, "execute")
toggle(clearKey, "then", False, (real, "CharacterLayout"), (3800, Y + 2800))

# ---------------------------------------------------------------- character editor (admin menu, 03)
EVENTS.update(ce_server.build(types.SimpleNamespace(
    g=g, self_call=self_call, owner_pc=owner_pc, save_slot=save_slot, Auth=Auth, MOD=MOD, PKG=PKG,
    CTRL_CLS=CTRL_CLS, SG_CLS=SG_CLS, RUN_ON_SERVER=RUN_ON_SERVER, RUN_ON_OWNING_CLIENT=RUN_ON_OWNING_CLIENT),
    y0=24000))
# ---------------------------------------------------------------- bug reports (player menu 07, admin menu 03)
EVENTS.update(bug_server.build(types.SimpleNamespace(
    g=g, self_call=self_call, owner_pc=owner_pc, save_slot=save_slot, Auth=Auth, MOD=MOD, PKG=PKG,
    CTRL_CLS=CTRL_CLS, SG_CLS=SG_CLS, RUN_ON_SERVER=RUN_ON_SERVER, RUN_ON_OWNING_CLIENT=RUN_ON_OWNING_CLIENT),
    y0=48000))
# ---------------------------------------------------------------- the HUD tab (admin menu 03)
EVENTS.update(hud_server.build(types.SimpleNamespace(
    g=g, self_call=self_call, owner_pc=owner_pc, save_slot=save_slot, Auth=Auth, MOD=MOD, PKG=PKG,
    CTRL_CLS=CTRL_CLS, SG_CLS=SG_CLS, RUN_ON_SERVER=RUN_ON_SERVER, RUN_ON_OWNING_CLIENT=RUN_ON_OWNING_CLIENT),
    y0=60000))
# ---------------------------------------------------------------- the Server Restart tab (admin menu 03)
EVENTS.update(restart_server.build(types.SimpleNamespace(
    g=g, self_call=self_call, owner_pc=owner_pc, save_slot=save_slot, Auth=Auth, MOD=MOD, PKG=PKG,
    CTRL_CLS=CTRL_CLS, SG_CLS=SG_CLS, RUN_ON_SERVER=RUN_ON_SERVER, RUN_ON_OWNING_CLIENT=RUN_ON_OWNING_CLIENT),
    y0=66000))

# Clear + compile first, or a rebuild renames the pasted events (see 02)
bel.compile_blueprint(bp_obj)
_bp_ptr, _g_ptr = bp.find_graph(FULL, "EventGraph")
bp.clear_graph(_bp_ptr, _g_ptr)
bp.mark_structurally_modified(_bp_ptr)
bel.compile_blueprint(bp_obj)

rep = build.build_graph(FULL, g, verbose=False)
# the self-calls dropped (their events weren't functions yet); now they are: paste just those
# nodes and re-make their wires by name. (Pasting the whole graph again renames the events.)
assert rep["dropped_nodes"] == len(SELF_CALLS), "relay paste dropped %d nodes, expected the %d self-calls" % (
    rep["dropped_nodes"], len(SELF_CALLS))
pasted = bp.import_nodes(_g_ptr, "\n".join(c.render() for c in SELF_CALLS) + "\n")
_relinked, still = bp._relink_dropped(_g_ptr, g.render())
bp.mark_structurally_modified(_bp_ptr)
bel.compile_blueprint(bp_obj)
rep.update(build.scan(_g_ptr), dropped_nodes=len(SELF_CALLS) - pasted, dropped_links=still)
rep["ok"] = not (rep["dropped_nodes"] or rep["dropped_links"] or rep["orphans"] or rep["wildcards"] or rep["errors"])
print("relay: %d self-calls pasted again, %d wires re-made | errors %s" % (pasted, len(_relinked),
                                                                          rep["errors"] or "(clean)"))
assert rep["ok"], "relay graph not clean: %r" % {k: rep[k] for k in ("dropped_nodes", "dropped_links", "orphans",
                                                                     "wildcards", "errors")}
# the events must exist under their own names AND compile as RPCs of the right kind (INTERNALS §10:
# EFunctionFlags at 0xd0 of the UFunction in this build)
for fn, want in EVENTS.items():
    f = unreal.find_object(None, FULL + "_C:" + fn)
    assert f, "custom event %s missing after build (renamed on paste?)" % fn
    flags = ctypes.c_uint32.from_address(bp.obj_addr(f) + 0xd0).value
    assert flags & want == want and (want or not flags & 0x40), "%s has the wrong net flags: 0x%08x" % (fn, flags)
    print("%s: %s (flags 0x%08x)" % (fn, {RUN_ON_SERVER: "Run on Server, reliable",
                                          RUN_ON_OWNING_CLIENT: "Run on owning Client, reliable"}.get(want, "not replicated"),
                                     flags))
# TmVersion (the old replicated counter) is gone; drop it from the asset
bel.remove_unused_variables(bp_obj)
bel.compile_blueprint(bp_obj)

gen = unreal.load_object(None, FULL + "_C")
cdo = unreal.get_default_object(gen)
for var in ("TmLook", "TmPawn", "TmOutfitNames", "TmOutfitLooks", "TmClientVer", "TmApplied", "TmOn", "TmAsked") + \
        tuple(v for v, _t in CE_VARS):
    cdo.get_editor_property(var)                               # raises if remove_unused_variables took it
cdo.set_editor_property("replicates", True)
cdo.set_editor_property("only_relevant_to_owner", False)     # everyone sees everyone's look
cdo.set_editor_property("always_relevant", True)
tk = cdo.get_editor_property("primary_actor_tick")
tk.set_editor_property("tick_interval", 0.1)                 # a respawned character gets its look back fast
cdo.set_editor_property("primary_actor_tick", tk)
assert unreal.EditorAssetLibrary.save_asset(PATH), "save failed"
print("CDO: replicates=%s only_relevant_to_owner=%s always_relevant=%s" % (
    cdo.get_editor_property("replicates"), cdo.get_editor_property("only_relevant_to_owner"),
    cdo.get_editor_property("always_relevant")))
print("BUILD OK: owl-admin v%d -> %s%s" % (
    MOD.VERSION, FULL, "  [DRY RUN -- not shippable]" if PKG != MOD.OUTPUT_PKG else ""))
