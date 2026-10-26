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

Transmog (the player menu's tab, 07): TmLook / TmOutfitNames / TmOutfitLooks / TmVersion,
replicated to the owner. BeginPlay (server) loads them from the owner's OwlTransmog_<net id>
save; OwlServerTmApply(Look) and OwlServerTmSaveOutfit(Name, Look) (Run on Server) change and
save them.

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
for _m in ("oa_config", "oa_auth", "menu_defs"):
    sys.modules.pop(_m, None)
import oa_config as MOD
import menu_defs as D
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
EVENTS = ("OwlServerLogin", "OwlServerSetPassword", "OwlServerTmApply", "OwlServerTmSaveOutfit")

TM_SG_CLS = MOD.full(PKG, MOD.TM_SAVEGAME) + "_C"
assert unreal.load_object(None, TM_SG_CLS), "build 08 first: no " + TM_SG_CLS

bel = unreal.BlueprintEditorLibrary
bp_obj, _ = bp.scratch_blueprint(pkg=PKG, name=MOD.RELAY, parent=unreal.Actor)
# transmog state, replicated to the owner only (the relay is only relevant to its owner)
strings_t = bel.get_array_type(bel.get_basic_type_by_name("string"))
for var, vtype in (("TmLook", strings_t), ("TmOutfitNames", strings_t), ("TmOutfitLooks", strings_t),
                   ("TmVersion", bel.get_basic_type_by_name("int"))):
    bel.add_member_variable(bp_obj, var, vtype)
    bel.set_blueprint_variable_replication(bp_obj, var, unreal.BlueprintVariableReplication.REPLICATED)

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
# TmVersion goes up after every load/change so the open menu reloads.
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


def save_slot(cast, pos):
    """"OwlTransmog_" + the owner's net id, ':' and '/' made file-name safe (pure). In Play-in-
    Editor the id ends "-Context_<n>" and n goes up every session; that tail is dropped so a
    look survives a Play restart (real Steam ids have no such tail)."""
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
    g.typed_input(cat, "A", MOD.TM_SLOT_PREFIX, "string")
    g.wire(prev[0], prev[1], cat, "B", exec=False)
    return cat


def bump(entries, pos):
    """TmVersion += 1, entered from each (node, exec pin)."""
    add = g.call("Add_IntInt", KML, pos=(pos[0], pos[1] + 200))
    g.wire(g.var_get("TmVersion", "int", pos=(pos[0] - 250, pos[1] + 200)), "TmVersion", add, "A", exec=False)
    g.typed_input(add, "B", "1", "int")
    st = g.var_set("TmVersion", "int", pos=(pos[0] + 250, pos[1]))
    g.wire(add, "ReturnValue", st, "TmVersion", exec=False)
    for e, ep in entries:
        g.wire(e, ep, st, "execute")
    return st


def save_tm(entries, cast, pos):
    """Write TmLook / TmOutfitNames / TmOutfitLooks to the owner's save slot, then bump."""
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
    return bump([(sav, "then")], (x + 1600, y))


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
bump([(prev, "then"), (bEx, "else"), (sc, "CastFailed")], (3200, 6000))


def tm_event(name, pins, y):
    """A Run-on-Server transmog event with the given (name, category, is_array) params."""
    ce = g.custom_event(name, pos=(0, y))
    ce.set("FunctionFlags", str(RUN_ON_SERVER))
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
