"""Character editor, the server side: the relay's (10) CE events, for the admin menu's Characters
tab. The admin's own relay carries them (a client can only call Run-on-Server events on an actor
its connection owns). Every server event first checks that the admin is unlocked
(oa_auth.require_unlocked) and names the target by their PlayerState (replicated, so it can be an
RPC parameter). Online players only: the target must have a character right now.

    OwlServerCeList()                      -> OwlClientCeList(Names, Levels, States): every player
                                              in the game state (level 0 = no character now)
    OwlServerCeGet(State)                  -> OwlClientCe(State, Level, Points, A0..A6, Ids, Counts,
                                              Slots, Wallet, Log): one player's editor data
    OwlServerCeApply(State, Level, Points, A0..A6)
    OwlServerCeRefund(State)               every attribute point back (the game's own reset)
    OwlServerCeReset(State)                level 1, no points
    OwlServerCeRemove(State, Slot, Qty)    Slot = kind * 1000 + slot, kind = menu_defs.CE_INVS index
    OwlServerCeGrant(State, TemplateId, Qty)   into the backpack
    OwlServerCeWallet(State, Balance)
    OwlServerCeEconomy(Store, CurOn, SellQ, BuyQ) -> OwlClientCeEconomy(CurOn, SellQ, BuyQ)
                                              Store = false only reads them

A change sets SvLine ("time|admin|text") and calls OwlCeCommit (a plain event): it adds the line
to the target's OwlCe_<net id> save (and sets the wallet there, if SvSetWallet), then
OwlServerCeGet sends the target's real data back, so the panel shows what the game did. The
client events store what arrives in the Ce* variables and raise CeListVer / CeClientVer /
CeEconVer, so the open panel reloads (the transmog tab's TmClientVer pattern).

Level, points and attributes follow docs/CONAN-NOTES.md "Editing a character": the native
ProgressionSystem calls do nothing; the values live on the BP_ProgressionSystem component.
"""
from bpkit import ir
import menu_defs as D

KML = "/Script/Engine.KismetMathLibrary"
KSTR = "/Script/Engine.KismetStringLibrary"
KTXT = "/Script/Engine.KismetTextLibrary"
KSL = "/Script/Engine.KismetSystemLibrary"
GS = "/Script/Engine.GameplayStatics"
ACTOR = "/Script/Engine.Actor"
CS = "/Script/ConanSandbox."
CHAR = CS + "ConanCharacter"
INV = CS + "ItemInventory"
ITEM = CS + "GameItem"
CPC = CS + "ConanPlayerController"
PSTATE = "/Script/Engine.PlayerState"
PROG = "/Game/Systems/Progression/BP_ProgressionSystem.BP_ProgressionSystem_C"
STAT_E = ir.enum_path(CS + "ECharIntStatID")
ATTR_PINS = ["A%d" % i for i in range(len(D.CE_ATTRS))]
SHORT = [label[:3] for label, _e in D.CE_ATTRS]
T = {"int": ("int", None), "string": ("string", None), "bool": ("bool", None),
     "state": ("object", ir.obj_path(PSTATE))}
CE_PINS = ([("State", "state", False), ("Level", "int", False), ("Points", "int", False)]
           + [(p, "int", False) for p in ATTR_PINS]
           + [("Ids", "int", True), ("Counts", "int", True), ("Slots", "int", True), ("Wallet", "int", False),
              ("Log", "string", True)])
LIST_PINS = [("Names", "string", True), ("Levels", "int", True), ("States", "state", True)]
ECON_PINS = [("CurOn", "int", True), ("SellQ", "int", False), ("BuyQ", "int", False)]
NO_CHAR = "That player has no character right now."


def variables(unreal, bel, ce_save_cls):
    """(name, type) for the relay: Ce* = the owner's copy the panel reads, Sv* = the server's
    scratch values. None replicate: the RPCs carry them."""
    i, s, b = (bel.get_basic_type_by_name(t) for t in ("int", "string", "bool"))
    ps = bel.get_object_reference_type(unreal.PlayerState.static_class())
    arr = bel.get_array_type
    client = ([("CeNames", arr(s)), ("CeLevels", arr(i)), ("CeStates", arr(ps)), ("CeListVer", i),
               ("CeTarget", ps), ("CeLevel", i), ("CePoints", i)] + [("Ce" + p, i) for p in ATTR_PINS]
              + [("CeInvIds", arr(i)), ("CeInvCounts", arr(i)), ("CeInvSlots", arr(i)), ("CeWallet", i),
                 ("CeLog", arr(s)), ("CeClientVer", i), ("CeCurOn", arr(i)), ("CeSellQ", i), ("CeBuyQ", i),
                 ("CeEconVer", i)])
    server = [("SvNames", arr(s)), ("SvLevels", arr(i)), ("SvStates", arr(ps)), ("SvIds", arr(i)),
              ("SvCounts", arr(i)), ("SvSlots", arr(i)), ("SvState", ps), ("SvLine", s), ("SvAdmin", s),
              ("SvSetWallet", b),
              ("SvWallet", i), ("SvLog", arr(s)), ("SvCurOn", arr(i)), ("SvSellQ", i), ("SvBuyQ", i),
              ("SvSave", bel.get_object_reference_type(ce_save_cls))]
    return client + server


EVENT_NAMES = ["OwlServerCeList", "OwlClientCeList", "OwlServerCeGet", "OwlClientCe", "OwlCeCommit",
               "OwlServerCeApply", "OwlServerCeRefund", "OwlServerCeReset", "OwlServerCeRemove",
               "OwlServerCeGrant", "OwlServerCeWallet", "OwlServerCeEconomy", "OwlClientCeEconomy"]


def helpers(R, flags):
    """The small graph builders the CE events use (and bug_server's): R as for build();
    event() records each event's net flags in flags. Returns them as attributes."""
    import types
    g, MOD = R.g, R.MOD

    def event(name, pins, y, fl):
        ce = g.custom_event(name, pos=(0, y))
        if fl:
            ce.set("FunctionFlags", str(fl))
        flags[name] = fl
        for pn, t, arr in pins:
            cat, sub = T[t]
            ce.set('CustomProperties UserDefinedPin (PinName="%s",PinType=(PinCategory="%s"%s%s),'
                   'DesiredPinDirection=EGPD_Output)' % (
                       pn, cat, ',PinSubCategoryObject="%s"' % sub if sub else "",
                       # arrays: const ref, or the compiler says "No value will be returned by reference"
                       ",ContainerType=Array,bIsReference=True,bIsConst=True" if arr else ""))
        return ce

    def call_self(name, pins, pos):
        c = R.self_call(name, pos)
        for pn, t, arr in pins:
            cat, sub = T[t]
            c.pin(pn).typed(cat, sub, direction="EGPD_Input", container="Array" if arr else None, ref=arr, const=arr)
        return c

    def get(name, t, pos, arr=False, parent=None):
        cat, sub = T[t]
        n = g.var_get(name, cat, sub, parent=parent, pos=pos)
        if arr:
            n.pin(name).set("PinType.ContainerType", "Array")
        return (n, name)

    def wire_in(src, node, pin, t="int"):
        """src: (node, pin) to wire, or a literal."""
        if isinstance(src, tuple):
            g.wire(src[0], src[1], node, pin, exec=False)
        else:
            cat, sub = T[t]
            node.pin(pin).typed(cat, sub, direction="EGPD_Input").literal(src)

    def setv(prev, name, t, src, pos, arr=False):
        cat, sub = T[t]
        n = g.var_set(name, cat, sub, pos=pos)
        if arr:
            n.pin(name).set("PinType.ContainerType", "Array")
        wire_in(src, n, name, t)
        g.wire(prev[0], prev[1], n, "execute")
        return (n, "then")

    def arr_fn(prev, fn, name, t, pos, item=None, item_pin="NewItem"):
        """Array_Clear / Array_Add / Array_Remove on a self array variable."""
        cat, sub = T[t]
        n = g.array_fn(fn, pos=pos, elem_cat=cat, elem_sub=sub)
        src = get(name, t, (pos[0], pos[1] + 200), arr=True)
        g.wire(src[0], src[1], n, "TargetArray", exec=False)
        if item is not None:
            if item_pin == "NewItem":
                g.array_item_pin(n, item_pin, cat, sub)
            else:
                n.pin(item_pin).typed("int", direction="EGPD_Input")
            wire_in(item, n, item_pin, t if item_pin == "NewItem" else "int")
        g.wire(prev[0], prev[1], n, "execute")
        return (n, "then")

    def op(fn, a, b, pos):
        n = g.call(fn, KML, pos=pos)
        wire_in(a, n, "A")
        wire_in(b, n, "B")
        return (n, "ReturnValue")

    def clamp(v, lim, pos):
        n = g.call("Clamp", KML, pos=pos)
        wire_in(v, n, "Value")
        wire_in(str(lim[0]), n, "Min")
        wire_in(str(lim[1]), n, "Max")
        return (n, "ReturnValue")

    def branch(prev, cond, pos):
        b = g.branch(pos=pos)
        g.wire(prev[0], prev[1], b, "execute")
        g.wire(cond[0], cond[1], b, "Condition", exec=False)
        return b

    def text(parts, pos):
        """Concatenate parts: literal strings, (node, pin) strings or (node, pin, "int")."""
        acc = None
        for k, p in enumerate(parts):
            n = g.call("Concat_StrStr", KSTR, pos=(pos[0] + 250 * k, pos[1]))
            wire_in(acc if acc else "", n, "A", "string")
            if isinstance(p, tuple) and len(p) == 3:
                cv = g.call("Conv_IntToString", KSTR, pos=(pos[0] + 250 * k, pos[1] + 150))
                g.wire(p[0], p[1], cv, "InInt", exec=False)
                p = (cv, "ReturnValue")
            wire_in(p, n, "B", "string")
            acc = (n, "ReturnValue")
        return acc

    def stat(chc, entry, pos):
        n = g.call("GetIntStat", CHAR, pos=pos)
        g.wire(chc, "AsConan Character", n, "self", exec=False)
        g.typed_input(n, "statID", entry, "byte", STAT_E)
        g.typed_input(n, "mode", "Base", "byte", ir.enum_path(CS + "EStatModifierMode"))
        return (n, "ReturnValue")

    def set_stat(prev, chc, entry, val, pos):
        n = g.call("SetIntStat", CHAR, pos=pos)
        g.wire(chc, "AsConan Character", n, "self", exec=False)
        g.typed_input(n, "statID", entry, "byte", STAT_E)
        wire_in(val, n, "value")
        g.wire(prev[0], prev[1], n, "execute")
        return (n, "then")

    def prog_call(prev, prog, fn, pos, points=None):
        n = g.call(fn, PROG, pos=pos)
        g.wire(prog[0], prog[1], n, "self", exec=False)
        if points is not None:
            wire_in(points, n, "Points")
        g.wire(prev[0], prev[1], n, "execute")
        return (n, "then")

    def set_level(prev, chc, prog, level, pos):
        """LEVEL stat, the level's XP range, XP = the range's start (SetLevelRange only clamps
        it, and going down that leaves XP at the range's end: the next gain levels back up)."""
        x, y = pos
        p = set_stat(prev, chc, "Level", level, (x, y))
        p = prog_call(p, prog, "SetLevelRange", (x + 300, y))
        start = g.var_get("LevelStart", "int", parent=PROG, pos=(x + 300, y + 250))
        g.wire(prog[0], prog[1], start, "self", exec=False)
        conv = g.call("Conv_IntToDouble", KML, pos=(x + 550, y + 250))
        g.wire(start, "LevelStart", conv, "InInt", exec=False)
        xp = g.var_set("ExperiencePoints", "real", parent=PROG, pos=(x + 600, y))
        xp.pin("ExperiencePoints").set("PinType.PinSubCategory", '"double"')
        g.wire(prog[0], prog[1], xp, "self", exec=False)
        g.wire(conv, "ReturnValue", xp, "ExperiencePoints", exec=False)
        g.wire(p[0], p[1], xp, "execute")
        return (xp, "then")

    def unlocked(ce, y):
        """The relay's owner (the admin) as a ConanPlayerController, their Auth, and the
        admin-mode branch (carry on from "then")."""
        oc = R.owner_pc(ce, "then", (300, y))
        a = R.Auth(g, R.CTRL_CLS, R.SG_CLS, MOD.SAVE_SLOT, (oc, "AsConan Player Controller"))
        ok, _ = a.require_unlocked(oc, "then", (600, y))
        return oc, a, ok

    def target(ce, ok, a, y):
        """The target's character (cast, exec) and its BP_ProgressionSystem component."""
        pawn = g.call("GetPawn", PSTATE, pos=(1400, y + 250))
        g.wire(ce, "State", pawn, "self", exec=False)
        chc = g.cast(CHAR, pos=(1700, y))
        g.wire(pawn, "ReturnValue", chc, "Object", exec=False)
        g.wire(ok, "then", chc, "execute")
        a.message(chc, "CastFailed", NO_CHAR, (2000, y + 900))
        gc = g.call("GetComponentByClass", ACTOR, pos=(1700, y + 400))
        g.wire(chc, "AsConan Character", gc, "self", exec=False)
        cp = gc.pin("ComponentClass").typed("class", ir.obj_path("/Script/Engine.ActorComponent"), direction="EGPD_Input")
        cp.set("DefaultObject", '"%s"' % PROG)
        gc.pin("ReturnValue").typed("object", ir.obj_path(PROG), direction="EGPD_Output")
        return chc, (gc, "ReturnValue")

    def action(name, pins, y):
        ce = event(name, [("State", "state", False)] + pins, y, R.RUN_ON_SERVER)
        oc, a, ok = unlocked(ce, y)
        chc, prog = target(ce, ok, a, y)
        return ce, oc, a, chc, prog

    def set_line(prev, oc, parts, pos):
        """SvLine = "<date time>|<admin>|<parts>". The admin is their character's name, like the
        player list (else their player name, which in Play-in-Editor is only the net id)."""
        x, y = pos
        pawn = g.call("K2_GetPawn", "/Script/Engine.Controller", pos=(x, y + 300))
        g.wire(oc, "AsConan Player Controller", pawn, "self", exec=False)
        ac = g.cast(CHAR, pos=(x, y))
        g.wire(pawn, "ReturnValue", ac, "Object", exec=False)
        g.wire(prev[0], prev[1], ac, "execute")
        cn = g.call("GetCharacterName", CHAR, pos=(x + 300, y + 300))
        g.wire(ac, "AsConan Character", cn, "self", exec=False)
        named = setv((ac, "then"), "SvAdmin", "string", (cn, "ReturnValue"), (x + 300, y))
        ps = g.var_get("PlayerState", "object", ir.obj_path(PSTATE), parent="/Script/Engine.Controller",
                       pos=(x + 300, y + 750))
        g.wire(oc, "AsConan Player Controller", ps, "self", exec=False)
        pn = g.call("GetPlayerName", PSTATE, pos=(x + 550, y + 750))
        g.wire(ps, "PlayerState", pn, "self", exec=False)
        unnamed = setv((ac, "CastFailed"), "SvAdmin", "string", (pn, "ReturnValue"), (x + 300, y + 600))
        now = g.call("Now", KML, pos=(x + 600, y + 300))
        dt = g.call("AsDateTime_DateTime", KTXT, pos=(x + 800, y + 300))
        g.wire(now, "ReturnValue", dt, "In", exec=False)
        ts = g.call("Conv_TextToString", KTXT, pos=(x + 1050, y + 300))
        g.wire(dt, "ReturnValue", ts, "InText", exec=False)
        line = text([(ts, "ReturnValue"), "|", get("SvAdmin", "string", (x + 1050, y + 450)), "|"] + parts,
                    (x + 1300, y + 300))
        n = g.var_set("SvLine", "string", pos=(x + 900, y))
        g.wire(line[0], line[1], n, "SvLine", exec=False)
        for e in (named, unnamed):
            g.wire(e[0], e[1], n, "execute")
        return (n, "then")

    def commit(prev, ce, pos):
        p = setv(prev, "SvState", "state", (ce, "State"), pos)
        c = call_self("OwlCeCommit", [], (pos[0] + 300, pos[1]))
        g.wire(p[0], p[1], c, "execute")
        return c

    def ce_slot(prev, state_src, pos):
        """The target's controller (cast, exec) and OwlCe_<their net id>."""
        x, y = pos
        pawn = g.call("GetPawn", PSTATE, pos=(x, y + 250))
        g.wire(state_src[0], state_src[1], pawn, "self", exec=False)
        ctl = g.call("GetController", "/Script/Engine.Pawn", pos=(x + 250, y + 250))
        g.wire(pawn, "ReturnValue", ctl, "self", exec=False)
        cc = g.cast(CPC, pos=(x + 300, y))
        g.wire(ctl, "ReturnValue", cc, "Object", exec=False)
        g.wire(prev[0], prev[1], cc, "execute")
        return cc, (R.save_slot(cc, (x + 300, y + 450), prefix=MOD.CE_SLOT_PREFIX), "ReturnValue")

    def load(prevs, slot_src, sg_cls, pos):
        """Exists? -> load -> cast, entered from each (node, exec pin) in prevs. Returns (cast
        node, [exec outs where there is no save])."""
        x, y = pos
        dse = g.call("DoesSaveGameExist", GS, pos=(x, y))
        g.wire(slot_src[0], slot_src[1], dse, "SlotName", exec=False)
        g.typed_input(dse, "UserIndex", "0", "int")
        for prev in prevs:
            g.wire(prev[0], prev[1], dse, "execute")
        bEx = branch((dse, "then"), (dse, "ReturnValue"), (x + 250, y))
        ld = g.call("LoadGameFromSlot", GS, pos=(x + 500, y))
        g.wire(slot_src[0], slot_src[1], ld, "SlotName", exec=False)
        g.typed_input(ld, "UserIndex", "0", "int")
        g.wire(bEx, "then", ld, "execute")
        sc = g.cast(sg_cls, pos=(x + 800, y))
        g.wire(ld, "ReturnValue", sc, "Object", exec=False)
        g.wire(ld, "then", sc, "execute")
        return sc, [(bEx, "else"), (sc, "CastFailed")]

    def save_as(sg_cls):
        return "As" + " ".join(_words(sg_cls.split(".")[-1][:-2]))

    def bump(prev, name, pos):
        inc = g.call("Add_IntInt", KML, pos=(pos[0], pos[1] + 200))
        v = get(name, "int", (pos[0] - 200, pos[1] + 200))
        g.wire(v[0], v[1], inc, "A", exec=False)
        g.typed_input(inc, "B", "1", "int")
        return setv(prev, name, "int", (inc, "ReturnValue"), pos)

    def client_event(name, pins, mine, ver, y):
        """Run on owning Client: store each param in its Ce variable, then raise ver."""
        ce = event(name, pins, y, R.RUN_ON_OWNING_CLIENT)
        p = (ce, "then")
        for k, ((pn, t, arr), var) in enumerate(zip(pins, mine)):
            p = setv(p, var, t, (ce, pn), (300 + 300 * k, y), arr=arr)
        bump(p, ver, (300 + 300 * len(pins), y))

    return types.SimpleNamespace(event=event, call_self=call_self, get=get, wire_in=wire_in, setv=setv, arr_fn=arr_fn, op=op, clamp=clamp, branch=branch, text=text, stat=stat, set_stat=set_stat, prog_call=prog_call, set_level=set_level, unlocked=unlocked, target=target, action=action, set_line=set_line, commit=commit, ce_slot=ce_slot, load=load, save_as=save_as, bump=bump, client_event=client_event)


def build(R, y0):
    """Add the CE events to R.g (10's graph) from y0 down. R carries 10's helpers: g, self_call,
    owner_pc, save_slot, Auth, MOD, PKG, CTRL_CLS, SG_CLS, RUN_ON_SERVER, RUN_ON_OWNING_CLIENT.
    Returns {event name: net flags} (0 = a plain event)."""
    g, MOD = R.g, R.MOD
    CE_SG = MOD.full(R.PKG, MOD.CE_SAVEGAME) + "_C"
    ECON_SG = MOD.full(R.PKG, MOD.ECON_SAVEGAME) + "_C"
    flags = {}
    h = helpers(R, flags)
    (event, call_self, get, wire_in, setv, arr_fn, op, clamp, branch, text, stat, set_stat, prog_call, set_level, unlocked, target, action, set_line, commit, ce_slot, load, save_as, bump, client_event) = (h.event, h.call_self, h.get, h.wire_in, h.setv, h.arr_fn, h.op, h.clamp, h.branch, h.text, h.stat, h.set_stat, h.prog_call, h.set_level, h.unlocked, h.target, h.action, h.set_line, h.commit, h.ce_slot, h.load, h.save_as, h.bump, h.client_event)

    # ------------------------------------------------------------ OwlServerCeList
    y = y0
    ce = event("OwlServerCeList", [], y, R.RUN_ON_SERVER)
    oc, a, ok = unlocked(ce, y)
    p = (ok, "then")
    for k, (name, t, _arr) in enumerate((("SvNames", "string", 1), ("SvLevels", "int", 1), ("SvStates", "state", 1))):
        p = arr_fn(p, "Array_Clear", name, t, (1400 + 300 * k, y))
    gst = g.call("GetGameState", GS, pos=(2300, y + 300))
    pa = g.var_get("PlayerArray", "object", ir.obj_path(PSTATE), parent="/Script/Engine.GameStateBase",
                   pos=(2300, y + 450))
    pa.pin("PlayerArray").set("PinType.ContainerType", "Array")
    g.wire(gst, "ReturnValue", pa, "self", exec=False)
    loop = g.foreach(PSTATE, pos=(2600, y))
    g.wire(pa, "PlayerArray", loop, "Array", exec=False)
    g.wire(p[0], p[1], loop, "Exec")
    el = (loop, "Array Element")
    q = arr_fn((loop, "LoopBody"), "Array_Add", "SvStates", "state", (2900, y), item=el)
    pawn = g.call("GetPawn", PSTATE, pos=(3200, y + 400))
    g.wire(el[0], el[1], pawn, "self", exec=False)
    lc = g.cast(CHAR, pos=(3200, y))
    g.wire(pawn, "ReturnValue", lc, "Object", exec=False)
    g.wire(q[0], q[1], lc, "execute")
    # a character: its name + level; none (dead, creating one): the player's name + level 0
    cn = g.call("GetCharacterName", CHAR, pos=(3500, y + 400))
    g.wire(lc, "AsConan Character", cn, "self", exec=False)
    q = arr_fn((lc, "then"), "Array_Add", "SvNames", "string", (3500, y), item=(cn, "ReturnValue"))
    arr_fn(q, "Array_Add", "SvLevels", "int", (3800, y), item=stat(lc, "Level", (3800, y + 400)))
    pn = g.call("GetPlayerName", PSTATE, pos=(3500, y + 1100))
    g.wire(el[0], el[1], pn, "self", exec=False)
    q = arr_fn((lc, "CastFailed"), "Array_Add", "SvNames", "string", (3500, y + 700), item=(pn, "ReturnValue"))
    arr_fn(q, "Array_Add", "SvLevels", "int", (3800, y + 700), item="0")
    send = call_self("OwlClientCeList", LIST_PINS, (2900, y + 1100))
    g.wire(loop, "Completed", send, "execute")
    for k, (pn, t, arr) in enumerate(LIST_PINS):
        src = get(("SvNames", "SvLevels", "SvStates")[k], t, (2600, y + 1300 + 150 * k), arr=True)
        g.wire(src[0], src[1], send, pn, exec=False)
    client_event("OwlClientCeList", LIST_PINS, ["CeNames", "CeLevels", "CeStates"], "CeListVer", y + 2000)

    # ------------------------------------------------------------ OwlServerCeGet
    y = y0 + 3000
    ce, oc, a, chc, prog = action("OwlServerCeGet", [], y)
    p = (chc, "then")
    for k, name in enumerate(("SvIds", "SvCounts", "SvSlots")):
        p = arr_fn(p, "Array_Clear", name, "int", (2000 + 300 * k, y))
    x = 3000
    for kind, (entry, _label) in enumerate(D.CE_INVS):
        inv = g.call("GetInventoryByType", INV, pos=(x, y + 400))
        g.wire(chc, "AsConan Character", inv, "owner", exec=False)
        g.typed_input(inv, "inventoryType", entry, "byte", ir.enum_path(CS + "EInventoryType"))
        lst = g.call("GetItemList", INV, pos=(x + 250, y + 400))
        g.wire(inv, "ReturnValue", lst, "self", exec=False)
        loop = g.foreach(ITEM, pos=(x + 300, y))
        g.wire(lst, "ReturnValue", loop, "Array", exec=False)
        g.wire(p[0], p[1], loop, "Exec")
        el = (loop, "Array Element")
        iv = g.call("IsValid", KSL, pos=(x + 600, y + 250))
        g.wire(el[0], el[1], iv, "Object", exec=False)
        bv = branch((loop, "LoopBody"), (iv, "ReturnValue"), (x + 600, y))
        tid = g.var_get("TemplateID", "int", parent=ITEM, pos=(x + 900, y + 250))
        g.wire(el[0], el[1], tid, "self", exec=False)
        q = arr_fn((bv, "then"), "Array_Add", "SvIds", "int", (x + 900, y), item=(tid, "TemplateID"))
        cnt = g.call("GetIntStat", ITEM, pos=(x + 1200, y + 250))
        g.wire(el[0], el[1], cnt, "self", exec=False)
        g.typed_input(cnt, "statID", "StackSize", "byte", ir.enum_path(CS + "EItemIntStatID"))
        q = arr_fn(q, "Array_Add", "SvCounts", "int", (x + 1200, y), item=(cnt, "ReturnValue"))
        # kind 0: the index as it is (a pasted "0" on Add_IntInt's B doesn't stick: B stays 1)
        at = op("Add_IntInt", (loop, "Array Index"), str(1000 * kind), (x + 1500, y + 250)) if kind else \
            (loop, "Array Index")
        arr_fn(q, "Array_Add", "SvSlots", "int", (x + 1500, y), item=at)
        p = (loop, "Completed")
        x += 2000
    # wallet + log from the target's save
    cc, slot = ce_slot(p, (ce, "State"), (x, y))
    sc, missing = load([(cc, "then")], slot, CE_SG, (x + 600, y))
    bal = get("Balance", "int", (x + 1500, y + 250), parent=CE_SG)
    g.wire(sc, save_as(CE_SG), bal[0], "self", exec=False)
    w = setv((sc, "then"), "SvWallet", "int", bal, (x + 1500, y))
    lg = get("Log", "string", (x + 1800, y + 250), arr=True, parent=CE_SG)
    g.wire(sc, save_as(CE_SG), lg[0], "self", exec=False)
    have = setv(w, "SvLog", "string", lg, (x + 1800, y), arr=True)
    w0 = g.var_set("SvWallet", "int", pos=(x + 1500, y + 700))
    w0.pin("SvWallet").typed("int", direction="EGPD_Input").literal("0")
    for e, ep in missing + [(cc, "CastFailed")]:
        g.wire(e, ep, w0, "execute")
    none = arr_fn((w0, "then"), "Array_Clear", "SvLog", "string", (x + 1800, y + 700))
    send = call_self("OwlClientCe", CE_PINS, (x + 2300, y))
    for e in (have, none):
        g.wire(e[0], e[1], send, "execute")
    srcs = {"State": (ce, "State"), "Level": stat(chc, "Level", (x + 2000, y + 1200))}
    pts = g.var_get("AttributePointsUndistributed", "int", parent=PROG, pos=(x + 2000, y + 1350))
    g.wire(prog[0], prog[1], pts, "self", exec=False)
    srcs["Points"] = (pts, "AttributePointsUndistributed")
    for k, (_label, entry) in enumerate(D.CE_ATTRS):
        srcs[ATTR_PINS[k]] = stat(chc, entry, (x + 2000, y + 1500 + 150 * k))
    for pn, var in (("Ids", "SvIds"), ("Counts", "SvCounts"), ("Slots", "SvSlots"), ("Log", "SvLog")):
        srcs[pn] = get(var, "string" if pn == "Log" else "int", (x + 2000, y + 2700 + 150 * len(srcs)), arr=True)
    srcs["Wallet"] = get("SvWallet", "int", (x + 2000, y + 2600))
    for pn, _t, _arr in CE_PINS:
        g.wire(srcs[pn][0], srcs[pn][1], send, pn, exec=False)
    client_event("OwlClientCe", CE_PINS,
                 ["CeTarget", "CeLevel", "CePoints"] + ["Ce" + p for p in ATTR_PINS]
                 + ["CeInvIds", "CeInvCounts", "CeInvSlots", "CeWallet", "CeLog"], "CeClientVer", y + 4000)

    # ------------------------------------------------------------ OwlCeCommit (plain event, server)
    y = y0 + 9000
    ce = event("OwlCeCommit", [], y, 0)
    st = get("SvState", "state", (0, y + 300))
    cc, slot = ce_slot((ce, "then"), st, (300, y))
    sc, missing = load([(cc, "then")], slot, CE_SG, (900, y))
    sv = g.var_set("SvSave", "object", ir.obj_path(CE_SG), pos=(1800, y))
    g.wire(sc, save_as(CE_SG), sv, "SvSave", exec=False)
    g.wire(sc, "then", sv, "execute")
    crt = g.call("CreateSaveGameObject", GS, pos=(1500, y + 600))
    cp = crt.pin("SaveGameClass").typed("class", ir.obj_path("/Script/Engine.SaveGame"), direction="EGPD_Input")
    cp.set("PinType.bIsUObjectWrapper", "True")
    cp.set("DefaultObject", '"%s"' % CE_SG)
    crt.pin("ReturnValue").typed("object", ir.obj_path(CE_SG), direction="EGPD_Output")
    for e, ep in missing:
        g.wire(e, ep, crt, "execute")
    sv2 = g.var_set("SvSave", "object", ir.obj_path(CE_SG), pos=(1800, y + 600))
    g.wire(crt, "ReturnValue", sv2, "SvSave", exec=False)
    g.wire(crt, "then", sv2, "execute")
    save = lambda pos: g.var_get("SvSave", "object", ir.obj_path(CE_SG), pos=pos)
    bW = g.branch(pos=(2100, y))
    for e in (sv, sv2):
        g.wire(e, "then", bW, "execute")
    g.wire(*get("SvSetWallet", "bool", (2100, y + 250)), bW, "Condition", exec=False)
    sb = g.var_set("Balance", "int", parent=CE_SG, pos=(2400, y))
    s0 = save((2400, y + 250))
    g.wire(s0, "SvSave", sb, "self", exec=False)
    g.wire(*get("SvWallet", "int", (2400, y + 400)), sb, "Balance", exec=False)
    g.wire(bW, "then", sb, "execute")
    off = setv((sb, "then"), "SvSetWallet", "bool", "false", (2700, y))
    ln = g.call("Len", KSTR, pos=(3000, y + 250))
    g.wire(*get("SvLine", "string", (2800, y + 250)), ln, "S", exec=False)
    bL = g.branch(pos=(3000, y))
    for e in (off, (bW, "else")):
        g.wire(e[0], e[1], bL, "execute")
    g.wire(*op("Greater_IntInt", (ln, "ReturnValue"), "0", (3200, y + 250)), bL, "Condition", exec=False)
    add = g.array_fn("Array_Add", pos=(3300, y), elem_cat="string")
    g.array_item_pin(add, "NewItem", "string")
    lg = g.var_get("Log", "string", parent=CE_SG, pos=(3300, y + 250))
    lg.pin("Log").set("PinType.ContainerType", "Array")
    g.wire(save((3100, y + 400)), "SvSave", lg, "self", exec=False)
    g.wire(lg, "Log", add, "TargetArray", exec=False)
    g.wire(*get("SvLine", "string", (3300, y + 400)), add, "NewItem", exec=False)
    g.wire(bL, "then", add, "execute")
    lg2 = g.var_get("Log", "string", parent=CE_SG, pos=(3600, y + 250))
    lg2.pin("Log").set("PinType.ContainerType", "Array")
    g.wire(save((3400, y + 450)), "SvSave", lg2, "self", exec=False)
    over = op("Greater_IntInt", (g.array_len(lg2, "Log", (3800, y + 250), elem_cat="string"), "ReturnValue"),
              str(MOD.CE_LOG_MAX), (4000, y + 250))
    bO = branch((add, "then"), over, (3700, y))
    rm = g.array_fn("Array_Remove", pos=(4000, y), elem_cat="string")
    rm.pin("IndexToRemove").typed("int", direction="EGPD_Input").literal("0")
    lg3 = g.var_get("Log", "string", parent=CE_SG, pos=(4000, y + 400))
    lg3.pin("Log").set("PinType.ContainerType", "Array")
    g.wire(save((3800, y + 550)), "SvSave", lg3, "self", exec=False)
    g.wire(lg3, "Log", rm, "TargetArray", exec=False)
    g.wire(bO, "then", rm, "execute")
    sav = g.call("SaveGameToSlot", GS, pos=(4300, y))
    g.wire(save((4100, y + 300)), "SvSave", sav, "SaveGameObject", exec=False)
    g.wire(slot[0], slot[1], sav, "SlotName", exec=False)
    g.typed_input(sav, "UserIndex", "0", "int")
    for e, ep in ((rm, "then"), (bO, "else"), (bL, "else")):
        g.wire(e, ep, sav, "execute")
    clr = setv((sav, "then"), "SvLine", "string", "", (4600, y))
    for k, e in enumerate((clr, (cc, "CastFailed"))):
        again = call_self("OwlServerCeGet", [("State", "state", False)], (4900, y + 400 * k))
        g.wire(e[0], e[1], again, "execute")
        g.wire(*get("SvState", "state", (4700, y + 250 + 400 * k)), again, "State", exec=False)

    # ------------------------------------------------------------ OwlServerCeApply
    y = y0 + 11000
    pins = [("Level", "int", False), ("Points", "int", False)] + [(p, "int", False) for p in ATTR_PINS]
    ce, oc, a, chc, prog = action("OwlServerCeApply", pins, y)
    lv = clamp((ce, "Level"), D.CE_LEVEL, (1700, y + 700))
    pt = clamp((ce, "Points"), D.CE_POINTS, (1700, y + 850))
    av = [clamp((ce, pn), D.CE_ATTR, (1700, y + 1000 + 150 * k)) for k, pn in enumerate(ATTR_PINS)]
    bLv = branch((chc, "then"), op("NotEqual_IntInt", stat(chc, "Level", (2000, y + 300)), lv, (2200, y + 300)),
                 (2000, y))
    lvDone = set_level((bLv, "then"), chc, prog, lv, (2300, y))
    first = None
    p = None
    for k, (_label, entry) in enumerate(D.CE_ATTRS):
        n = g.call("SetIntStat", CHAR, pos=(3300 + 300 * k, y))
        g.wire(chc, "AsConan Character", n, "self", exec=False)
        g.typed_input(n, "statID", entry, "byte", STAT_E)
        wire_in(av[k], n, "value")
        if p is None:
            for e in (lvDone, (bLv, "else")):
                g.wire(e[0], e[1], n, "execute")
        else:
            g.wire(p[0], p[1], n, "execute")
        p = (n, "then")
    total = av[0]
    for k in range(1, len(av)):
        total = op("Add_IntInt", total, av[k], (3300 + 200 * k, y + 600))
    p = prog_call(p, prog, "SetDistributedAttributePoints", (5500, y), points=total)
    p = prog_call(p, prog, "SetUndistributedAttributePoints", (5800, y), points=pt)
    p = prog_call(p, prog, "SetTotalAttributePoints", (6100, y), points=op("Add_IntInt", total, pt, (6000, y + 300)))
    parts = ["Stats set: level ", lv + ("int",), ", points ", pt + ("int",)]
    for k, s in enumerate(SHORT):
        parts += [", %s " % s, av[k] + ("int",)]
    p = set_line(p, oc, parts, (6400, y))
    commit(p, ce, (6800, y))

    # ------------------------------------------------------------ OwlServerCeRefund / OwlServerCeReset
    y = y0 + 13000
    ce, oc, a, chc, prog = action("OwlServerCeRefund", [], y)
    p = prog_call((chc, "then"), prog, "ServerResetAttributeAll", (2000, y))
    p = set_line(p, oc, ["Attributes refunded"], (2300, y))
    commit(p, ce, (2700, y))

    y = y0 + 14500
    ce, oc, a, chc, prog = action("OwlServerCeReset", [], y)
    p = set_level((chc, "then"), chc, prog, "1", (2000, y))
    p = prog_call(p, prog, "ServerResetAttributeAll", (2700, y))
    for k, fn in enumerate(("SetTotalAttributePoints", "SetUndistributedAttributePoints",
                            "SetDistributedAttributePoints")):
        p = prog_call(p, prog, fn, (3000 + 300 * k, y), points="0")
    p = set_line(p, oc, ["Reset to level 1"], (4000, y))
    commit(p, ce, (4400, y))

    # ------------------------------------------------------------ OwlServerCeRemove(State, Slot, Qty)
    y = y0 + 16000
    ce, oc, a, chc, prog = action("OwlServerCeRemove", [("Slot", "int", False), ("Qty", "int", False)], y)
    kind = op("Divide_IntInt", (ce, "Slot"), "1000", (2000, y + 900))
    idx = op("Percent_IntInt", (ce, "Slot"), "1000", (2000, y + 1050))
    invs = []
    for k, (entry, _label) in enumerate(D.CE_INVS):
        inv = g.call("GetInventoryByType", INV, pos=(2300, y + 600 + 150 * k))
        g.wire(chc, "AsConan Character", inv, "owner", exec=False)
        g.typed_input(inv, "inventoryType", entry, "byte", ir.enum_path(CS + "EInventoryType"))
        invs.append((inv, "ReturnValue"))
    pick = invs[0]
    for k in range(1, len(invs)):
        sel = g.call("SelectObject", KML, pos=(2600 + 250 * k, y + 600))
        g.wire(invs[k][0], invs[k][1], sel, "A", exec=False)
        g.wire(pick[0], pick[1], sel, "B", exec=False)
        g.wire(*op("EqualEqual_IntInt", kind, str(k), (2600 + 250 * k, y + 800)), sel, "bSelectA", exec=False)
        pick = (sel, "ReturnValue")
    ic = g.cast(INV, pos=(2000, y))
    g.wire(pick[0], pick[1], ic, "Object", exec=False)
    g.wire(chc, "then", ic, "execute")
    lst = g.call("GetItemList", INV, pos=(2300, y + 300))
    g.wire(ic, "AsItem Inventory", lst, "self", exec=False)
    item = g.array_get(lst, "ReturnValue", idx, (2550, y + 300), elem_cat="object", elem_sub=ir.obj_path(ITEM))
    iv = g.call("IsValid", KSL, pos=(2800, y + 300))
    g.wire(item, "Output", iv, "Object", exec=False)
    bIt = branch((ic, "then"), (iv, "ReturnValue"), (2800, y))
    a.message(bIt, "else", "That slot is empty now.", (3100, y + 900))
    a.message(ic, "CastFailed", NO_CHAR, (2300, y + 1300))
    tid = g.var_get("TemplateID", "int", parent=ITEM, pos=(3100, y + 300))
    g.wire(item, "Output", tid, "self", exec=False)
    qty = clamp((ce, "Qty"), D.CE_QTY, (3100, y + 450))
    p = set_line((bIt, "then"), oc, ["Removed ", qty + ("int",), " of item ", (tid, "TemplateID", "int")],
                 (3100, y))       # before the delete: the item is gone after it
    dl = g.call("DeleteItems", INV, pos=(3500, y))
    g.wire(ic, "AsItem Inventory", dl, "self", exec=False)
    g.wire(idx[0], idx[1], dl, "index", exec=False)
    g.typed_input(dl, "context", MOD.CE_CONTEXT, "name")
    g.wire(qty[0], qty[1], dl, "quantity", exec=False)
    g.wire(p[0], p[1], dl, "execute")
    commit((dl, "then"), ce, (3800, y))

    # ------------------------------------------------------------ OwlServerCeGrant(State, TemplateId, Qty)
    y = y0 + 18000
    ce, oc, a, chc, prog = action("OwlServerCeGrant", [("TemplateId", "int", False), ("Qty", "int", False)], y)
    inv = g.call("GetInventoryByType", INV, pos=(2000, y + 300))
    g.wire(chc, "AsConan Character", inv, "owner", exec=False)
    g.typed_input(inv, "inventoryType", "Backpack", "byte", ir.enum_path(CS + "EInventoryType"))
    qty = clamp((ce, "Qty"), D.CE_QTY, (2000, y + 450))
    ad = g.call("AddItemTemplate", INV, pos=(2300, y))
    g.wire(inv, "ReturnValue", ad, "self", exec=False)
    g.wire(ce, "TemplateId", ad, "templateID", exec=False)
    g.typed_input(ad, "index", "-1", "int")         # -1: onto a matching stack, else the first free slot
    g.typed_input(ad, "context", MOD.CE_CONTEXT, "name")
    g.wire(qty[0], qty[1], ad, "quantity", exec=False)
    g.wire(chc, "then", ad, "execute")
    p = set_line((ad, "then"), oc, ["Granted ", qty + ("int",), " of item ", (ce, "TemplateId", "int")], (2600, y))
    commit(p, ce, (3000, y))

    # ------------------------------------------------------------ OwlServerCeWallet(State, Balance)
    y = y0 + 19500
    ce, oc, a, chc, prog = action("OwlServerCeWallet", [("Balance", "int", False)], y)
    p = setv((chc, "then"), "SvSetWallet", "bool", "true", (2000, y))
    bal = clamp((ce, "Balance"), (0, D.CE_WALLET_MAX), (2300, y + 250))
    p = setv(p, "SvWallet", "int", bal, (2300, y))
    p = set_line(p, oc, ["Wallet set to ", bal + ("int",)], (2600, y))
    commit(p, ce, (3000, y))

    # ------------------------------------------------------------ OwlServerCeEconomy(Store, CurOn, SellQ, BuyQ)
    y = y0 + 21000
    ce = event("OwlServerCeEconomy", [("Store", "bool", False)] + ECON_PINS, y, R.RUN_ON_SERVER)
    oc, a, ok = unlocked(ce, y)
    bSt = branch((ok, "then"), (ce, "Store"), (1400, y))
    crt = g.call("CreateSaveGameObject", GS, pos=(1700, y))
    cp = crt.pin("SaveGameClass").typed("class", ir.obj_path("/Script/Engine.SaveGame"), direction="EGPD_Input")
    cp.set("PinType.bIsUObjectWrapper", "True")
    cp.set("DefaultObject", '"%s"' % ECON_SG)
    crt.pin("ReturnValue").typed("object", ir.obj_path(ECON_SG), direction="EGPD_Output")
    g.wire(bSt, "then", crt, "execute")
    p = (crt, "then")
    for k, (field, src) in enumerate((("CurOn", (ce, "CurOn")), ("SellQ", clamp((ce, "SellQ"), D.CE_SELL_Q, (2000, y + 700))),
                                      ("BuyQ", clamp((ce, "BuyQ"), D.CE_BUY_Q, (2000, y + 850))))):
        n = g.var_set(field, "int", parent=ECON_SG, pos=(2000 + 300 * k, y))
        if field == "CurOn":
            n.pin(field).set("PinType.ContainerType", "Array")
        g.wire(crt, "ReturnValue", n, "self", exec=False)
        g.wire(src[0], src[1], n, field, exec=False)
        g.wire(p[0], p[1], n, "execute")
        p = (n, "then")
    sav = g.call("SaveGameToSlot", GS, pos=(3000, y))
    g.typed_input(sav, "SlotName", MOD.ECON_SLOT, "string")
    g.typed_input(sav, "UserIndex", "0", "int")
    g.wire(crt, "ReturnValue", sav, "SaveGameObject", exec=False)
    g.wire(p[0], p[1], sav, "execute")
    slotLit = g.call("Concat_StrStr", KSTR, pos=(3300, y + 300))         # the slot name as a pin
    wire_in(MOD.ECON_SLOT, slotLit, "A", "string")
    wire_in("", slotLit, "B", "string")
    # Store = false: straight to the load
    sc, missing = load([(sav, "then"), (bSt, "else")], (slotLit, "ReturnValue"), ECON_SG, (3300, y))
    p = (sc, "then")
    for k, (field, var) in enumerate((("CurOn", "SvCurOn"), ("SellQ", "SvSellQ"), ("BuyQ", "SvBuyQ"))):
        src = get(field, "int", (4300 + 300 * k, y + 250), arr=field == "CurOn", parent=ECON_SG)
        g.wire(sc, save_as(ECON_SG), src[0], "self", exec=False)
        p = setv(p, var, "int", src, (4300 + 300 * k, y), arr=field == "CurOn")
    d = arr_fn(missing[0], "Array_Clear", "SvCurOn", "int", (4300, y + 700))
    g.wire(missing[1][0], missing[1][1], d[0], "execute")
    d = setv(d, "SvSellQ", "int", "4", (4600, y + 700))
    d = setv(d, "SvBuyQ", "int", "4", (4900, y + 700))
    send = call_self("OwlClientCeEconomy", ECON_PINS, (5300, y))
    for e in (p, d):
        g.wire(e[0], e[1], send, "execute")
    for pn, var in (("CurOn", "SvCurOn"), ("SellQ", "SvSellQ"), ("BuyQ", "SvBuyQ")):
        src = get(var, "int", (5100, y + 300 + 150 * ECON_PINS.index((pn, "int", pn == "CurOn"))), arr=pn == "CurOn")
        g.wire(src[0], src[1], send, pn, exec=False)
    client_event("OwlClientCeEconomy", ECON_PINS, ["CeCurOn", "CeSellQ", "CeBuyQ"], "CeEconVer", y + 1200)
    return flags


def _words(name):
    """'BP_OwlCeSave' -> ['BP', 'Owl', 'Ce', 'Save'] (the cast pin's 'As<display name>')."""
    import re
    out = []
    for part in name.split("_"):
        out += re.findall(r"[A-Z]+(?![a-z])|[A-Z][a-z0-9]*|[a-z0-9]+", part)
    return out
