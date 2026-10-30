"""Trading, the server side: the relay's (10) trade events, for every player (no admin login), and
the trade log for the admin menu's Trading page.

    OwlServerTrNear()            -> OwlClientTrNear(Names, States): other players within the distance
    OwlServerTrState()           -> this player's trade view again (OwlTrSync)
    OwlServerTrAsk(State)        ask that player to trade
    OwlServerTrAnswer(Yes)       answer a request
    OwlServerTrOffer(Slot)       put a backpack slot's whole stack on the table
    OwlServerTrTake(Entry)       take an offered entry back
    OwlServerTrCoins(Amount)     offer Owl coins (the Character Editor's wallet), with "tradecur"
    OwlServerTrConfirm()         confirm; when both have, the trade happens (OwlTrExecute)
    OwlServerTrCancel()          leave the request or the trade (both sides reset)
    OwlServerTrLog()             admins: -> OwlClientTrLog(Lines), the OwlTrades save's log
    each change -> OwlTrSync(Msg) on both relays -> OwlClientTr(...) to each owner

A trade lives on the two relays (server side, nothing replicated): TrRole (0 none, 1 asked and
waiting, 2 asked by the other, 3 trading), TrPeer (the other relay), TrAt (when asked), and each
side's offer: TrSlots (backpack slots), TrIds / TrQty (the item and stack size when offered),
TrCoins, TrOk (confirmed). Any change to an offer clears both confirmations. Items stay in their
owner's backpack until the trade happens: then every offered slot must still hold the same item
and stack size, each backpack needs a free slot per item coming in, and each wallet the coins it
offered; only then are the items moved (ItemInventory.MoveItem: the real items, durability, dye
and all) and the coins changed. TrLast (when a player last traded) is the cooldown ("tradecd").
The relay tick (tick()) ends a request that went unanswered ("tradetimeout") and a trade whose
other side left. Settings: menu_defs "tradeon", "tradedist" (m), "tradeslots" (at most
TRADE_MAX), "tradecd", "tradetimeout", "tradecur", "tradelog" (a line per trade in OwlTrades).
Item names come from TrCatIds / TrCatNames on the relay's class defaults (the item table, set by
10), so the log and both menus can name them.
"""
from bpkit import ir
import menu_defs as D
from ce_server import helpers, T, KSTR, KSL, KML, GS, CS, CHAR, INV, ITEM
from ce_panel import _Ctx

TMAX = D.TRADE_MAX
ACTOR = "/Script/Engine.Actor"
CTRL = "/Script/Engine.Controller"
PAWN = "/Script/Engine.Pawn"
PSTATE = "/Script/Engine.PlayerState"
SET = {k: D.index(k) for k in ("tradeon", "tradedist", "tradeslots", "tradecd", "tradetimeout", "tradecur", "tradelog")}
DEF = {st["id"]: st["default"] for st in D.SETTINGS}
SYNC_PINS = [("Role", "int", False), ("Peer", "string", False), ("MyIds", "int", True), ("MyQty", "int", True),
             ("ThIds", "int", True), ("ThQty", "int", True), ("MyCoins", "int", False), ("ThCoins", "int", False),
             ("MyOk", "bool", False), ("ThOk", "bool", False), ("BagSlots", "int", True), ("BagIds", "int", True),
             ("BagQty", "int", True), ("Wallet", "int", False), ("Coins", "bool", False), ("Msg", "string", False)]
SYNC_MINE = ["TrRoleC", "TrPeerC", "TrMyIdsC", "TrMyQtyC", "TrThIdsC", "TrThQtyC", "TrMyCoinsC", "TrThCoinsC",
             "TrMyOkC", "TrThOkC", "TrBagSlotsC", "TrBagIdsC", "TrBagQtyC", "TrWalletC", "TrCoinsOnC", "TrMsgC"]
NEAR_PINS = [("Names", "string", True), ("States", "state", True)]
MSG_PIN = [("Msg", "string", False)]
SV_INTS = ("SvTrOn", "SvTrDist", "SvTrMax", "SvTrCd", "SvTrTo", "SvTrCur", "SvTrLog")
T.setdefault("actor", ("object", ir.obj_path(ACTOR)))
T.setdefault("real", ("real", None))


def variables(unreal, bel, ce_save_cls, tr_save_cls):
    """(name, type) for the relay. Tr*C / TrNear* / TrLog* = the owner's copy; the rest the server's."""
    i, s, b, r = (bel.get_basic_type_by_name(t) for t in ("int", "string", "bool", "real"))
    ints, strs = bel.get_array_type(i), bel.get_array_type(s)
    actor = bel.get_object_reference_type(unreal.Actor.static_class())
    states = bel.get_array_type(bel.get_object_reference_type(unreal.PlayerState.static_class()))
    client = [("TrRoleC", i), ("TrPeerC", s), ("TrMyIdsC", ints), ("TrMyQtyC", ints), ("TrThIdsC", ints),
              ("TrThQtyC", ints), ("TrMyCoinsC", i), ("TrThCoinsC", i), ("TrMyOkC", b), ("TrThOkC", b),
              ("TrBagSlotsC", ints), ("TrBagIdsC", ints), ("TrBagQtyC", ints), ("TrWalletC", i), ("TrCoinsOnC", b),
              ("TrMsgC", s), ("TrVer", i), ("TrNearNames", strs), ("TrNearStates", states), ("TrNearVer", i),
              ("TrLogC", strs), ("TrLogVer", i)]
    server = ([("TrPeer", actor), ("TrRole", i), ("TrAt", r), ("TrSlots", ints), ("TrIds", ints), ("TrQty", ints),
               ("TrCoins", i), ("TrOk", b), ("TrLast", r), ("SvTrFound", actor), ("SvTrNames", strs),
               ("SvTrStates", states), ("SvTrBagS", ints), ("SvTrBagI", ints), ("SvTrBagQ", ints), ("SvTrThIds", ints),
               ("SvTrThQty", ints), ("SvTrThCoins", i), ("SvTrThOk", b), ("SvTrPeerName", s), ("SvTrBal", i),
               ("SvTrPBal", i), ("SvTrBad", b), ("SvTrLine", s), ("SvTrSave", bel.get_object_reference_type(ce_save_cls)),
               ("SvTrPSave", bel.get_object_reference_type(ce_save_cls)), ("SvTrPSlot", s), ("SvTrSlot", s),
               ("SvTrLogSave", bel.get_object_reference_type(tr_save_cls)), ("TrCatIds", ints), ("TrCatNames", strs)]
              + [(v, i) for v in SV_INTS])
    return client + server


def defaults(cdo, catalog):
    cdo.set_editor_property("TrCatIds", [e["id"] for e in catalog])
    cdo.set_editor_property("TrCatNames", [e["name"] for e in catalog])


def _pawn(g, cast, as_r, rc, pos):
    """cast (a relay)'s TmPawn (pure)."""
    n = g.var_get("TmPawn", "object", ir.obj_path(PAWN), parent=rc, pos=pos)
    g.wire(cast, as_r, n, "self", exec=False)
    return (n, "TmPawn")


def _self(g, pos):
    n = g.node("K2Node_Self", [], base="Self", pos=pos)
    n.pin("self").typed("object", direction="EGPD_Output")
    return (n, "self")


def _ctx(R):
    c = _Ctx(R.g, None, None, None)
    lit = lambda v: v if isinstance(v, tuple) else (str(v), "int")
    imath = lambda fn, a, b, pos: c.fn(fn, KML, {"A": lit(a), "B": lit(b)}, pos)
    return c, imath


def build(R, y0):
    """Add the trade events to R.g from y0 down (R as for ce_server.build, plus RELAY_C).
    Returns {event: net flags}."""
    g, MOD = R.g, R.MOD
    RC = R.RELAY_C
    AS_R = "AsBP Owl Relay"
    AS_C = "AsConan Character"
    CE_SG = MOD.full(R.PKG, MOD.CE_SAVEGAME) + "_C"
    TR_SG = MOD.full(R.PKG, MOD.TRADES_SAVEGAME) + "_C"
    T.setdefault("cesave", ("object", ir.obj_path(CE_SG)))
    T.setdefault("trsave", ("object", ir.obj_path(TR_SG)))
    T.setdefault("actor", ("object", ir.obj_path(ACTOR)))
    T.setdefault("real", ("real", None))
    flags = {}
    h = helpers(R, flags)
    c, imath = _ctx(R)
    var = lambda name, cat, pos, arr=False: h.get(name, cat, pos, arr=arr)

    # ------------------------------------------------------------ small pieces
    def event(name, pins, y, fl):
        ce = h.event(name, pins, y, fl)
        c.exits = [(ce, "then")]
        return ce

    def call(name, pins, vals, pos, target=None):
        n = h.call_self(name, pins, pos)
        if target is not None:
            n.pin("self").typed("object", ir.obj_path(RC), direction="EGPD_Input")
            g.wire(target[0], target[1], n, "self", exec=False)
        for pn, t, _arr in pins:
            h.wire_in(vals[pn], n, pn, t)
        return c.go(n)

    def sync(msg, pos, target=None):
        call("OwlTrSync", MSG_PIN, {"Msg": msg}, pos, target)

    def reset(msg, pos, target=None):
        call("OwlTrReset", MSG_PIN, {"Msg": msg}, pos, target)

    def setv(name, t, src, pos, arr=False):
        n = g.var_set(name, *T[t], pos=pos)
        if arr:
            n.pin(name).set("PinType.ContainerType", "Array")
        h.wire_in(src, n, name, t)
        return c.go(n)

    def pget(cast, name, t, pos, arr=False):
        n = g.var_get(name, *T[t], parent=RC, pos=pos)
        if arr:
            n.pin(name).set("PinType.ContainerType", "Array")
        g.wire(cast, AS_R, n, "self", exec=False)
        return (n, name)

    def pset(cast, name, t, src, pos):
        n = g.var_set(name, *T[t], parent=RC, pos=pos)
        g.wire(cast, AS_R, n, "self", exec=False)
        h.wire_in(src, n, name, t)
        return c.go(n)

    def cast_relay(src, pos):
        """src cast to the relay class (exec): returns the cast; its CastFailed is the caller's."""
        n = g.cast(RC, pos=pos)
        n.pin("Object").typed("object", ir.obj_path(ACTOR), direction="EGPD_Input")
        g.wire(src[0], src[1], n, "Object", exec=False)
        c.go(n)
        return n

    def cast_char(src, pos):
        n = g.cast(CHAR, pos=pos)
        g.wire(src[0], src[1], n, "Object", exec=False)
        c.go(n)
        return n

    def branch(cond, pos, fail=None, msg_pos=None):
        """Carry on from "then"; on "else" sync msg fail (if given) to self."""
        b = c.branch(cond, pos)
        if fail is not None:
            c.exits = [(b, "else")]
            sync(fail, msg_pos or (pos[0] + 300, pos[1] + 600))
            ends = c.exits
        else:
            ends = [(b, "else")]
        c.exits = [(b, "then")]
        return ends

    def now(pos):
        return c.fn("GetGameTimeInSeconds", KSL, {}, pos)

    def bag(char, pos):
        inv = g.call("GetInventoryByType", INV, pos=pos)
        g.wire(char, AS_C, inv, "owner", exec=False)
        g.typed_input(inv, "inventoryType", "Backpack", "byte", ir.enum_path(CS + "EInventoryType"))
        return (inv, "ReturnValue")

    def item_at(inv, slot, pos):
        lst = c.fn("GetItemList", INV, {"self": inv}, pos)
        return (g.array_get(lst[0], lst[1], slot, (pos[0] + 200, pos[1]), elem_cat="object", elem_sub=ir.obj_path(ITEM)),
                "Output")

    def item_id(item, pos):
        n = g.var_get("TemplateID", "int", parent=ITEM, pos=pos)
        g.wire(item[0], item[1], n, "self", exec=False)
        return (n, "TemplateID")

    def item_qty(item, pos):
        n = g.call("GetIntStat", ITEM, pos=pos)
        g.wire(item[0], item[1], n, "self", exec=False)
        g.typed_input(n, "statID", "StackSize", "byte", ir.enum_path(CS + "EItemIntStatID"))
        return (n, "ReturnValue")

    def name_of(char, pos):
        return c.fn("GetCharacterName", CHAR, {"self": (char, AS_C)}, pos)

    def item_name(tid, pos):
        """TrCatNames[Find(TrCatIds, tid)], or "Item <id>" (pure)."""
        x, y = pos
        k = c.find(var("TrCatIds", "int", (x, y), arr=True), tid, "int", (x + 200, y))
        got = c.at(var("TrCatNames", "string", (x, y + 150), arr=True), k, "string", (x + 400, y + 150))
        return c.fn("SelectString", KML, {"A": got, "B": c.concat(["Item ", c.int_text(tid, (x + 200, y + 300))], (x + 400, y + 300)),
                                          "bPickA": imath("GreaterEqual_IntInt", k, 0, (x + 600, y + 450))}, (x + 800, y))

    def settings(pos):
        """SvTr*: the trade settings from the controller's AppliedSettings (all of them saved), else the
        defaults. SvTrDist in cm; SvTrMax at most TRADE_MAX."""
        x, y = pos
        gac = R.Auth(g, R.CTRL_CLS, R.SG_CLS, MOD.SAVE_SLOT, None).controller(c.exits[0][0], c.exits[0][1], (x, y))
        for e, ep in c.exits[1:]:
            g.wire(e, ep, gac, "execute")
        c.exits = [(gac, "then")]

        def applied(p):
            n = g.var_get("AppliedSettings", "string", parent=R.CTRL_CLS, pos=p)
            n.pin("AppliedSettings").set("PinType.ContainerType", "Array")
            g.wire(gac, "ReturnValue", n, "self", exec=False)
            return (n, "AppliedSettings")

        full = imath("GreaterEqual_IntInt", (g.array_len(*applied((x + 200, y + 300)), (x + 400, y + 300), elem_cat="string"),
                                             "ReturnValue"), len(D.SETTINGS), (x + 600, y + 300))
        b = c.branch(full, (x + 600, y))
        ends = []
        for side, live in (("then", True), ("else", False)):
            c.exits = [(b, side)]
            xx, yy = x + 900, y + (0 if live else 1200)
            for k, sv in enumerate(SV_INTS):
                key = ("tradeon", "tradedist", "tradeslots", "tradecd", "tradetimeout", "tradecur", "tradelog")[k]
                scale = 100 if key == "tradedist" else 1
                if live:
                    s = c.at(applied((xx, yy + 600)), SET[key], "string", (xx + 200, yy + 600))
                    v = c.fn("Round", KML, {"A": c.fn("Multiply_DoubleDouble", KML, {
                        "A": c.fn("Conv_StringToDouble", KSTR, {"InString": s}, (xx + 400, yy + 600)),
                        "B": (str(float(scale)), "real")}, (xx + 600, yy + 600))}, (xx + 800, yy + 600))
                    if key == "tradeslots":
                        v = c.fn("Min", KML, {"A": v, "B": (str(TMAX), "int")}, (xx + 900, yy + 750))
                else:
                    d = DEF[key]
                    v = str(int(round(float(d) * scale)) if not isinstance(d, bool) else int(d))
                    if key == "tradeslots":
                        v = str(min(int(v), TMAX))
                setv(sv, "int", v, (xx + 300, yy))
                xx += 1100
            ends += c.exits
        c.exits = ends

    def wallet(slot_var, save_var, bal_var, cast_pc, pos):
        """bal_var = Balance from OwlCe_<id of cast_pc> (save_var = it, or a new one), slot_var = its slot."""
        x, y = pos
        slot = R.save_slot(cast_pc, (x, y + 600), prefix=MOD.CE_SLOT_PREFIX)
        setv(slot_var, "string", (slot, "ReturnValue"), (x, y))
        sc, missing = h.load(c.exits, var(slot_var, "string", (x + 200, y + 600)), CE_SG, (x + 300, y))
        c.exits = [(sc, "then")]
        setv(save_var, "cesave", (sc, h.save_as(CE_SG)), (x + 1200, y))
        bg = g.var_get("Balance", "int", parent=CE_SG, pos=(x + 1200, y + 300))
        g.wire(sc, h.save_as(CE_SG), bg, "self", exec=False)
        setv(bal_var, "int", (bg, "Balance"), (x + 1500, y))
        have = c.exits
        crt = g.call("CreateSaveGameObject", GS, pos=(x + 1100, y + 900))
        cp = crt.pin("SaveGameClass").typed("class", ir.obj_path("/Script/Engine.SaveGame"), direction="EGPD_Input")
        cp.set("PinType.bIsUObjectWrapper", "True")
        cp.set("DefaultObject", '"%s"' % CE_SG)
        crt.pin("ReturnValue").typed("object", ir.obj_path(CE_SG), direction="EGPD_Output")
        c.exits = missing
        c.go(crt)
        setv(save_var, "cesave", (crt, "ReturnValue"), (x + 1400, y + 900))
        setv(bal_var, "int", "0", (x + 1700, y + 900))
        c.exits = have + c.exits

    def owner_cast(target_relay_cast, pos):
        """target relay's owner as a ConanPlayerController (exec). target_relay_cast None = self."""
        x, y = pos
        own = g.call("GetOwner", ACTOR, pos=(x, y + 250))
        if target_relay_cast is not None:
            g.wire(target_relay_cast, AS_R, own, "self", exec=False)
        oc = g.cast(CS + "ConanPlayerController", pos=(x + 250, y))
        g.wire(own, "ReturnValue", oc, "Object", exec=False)
        c.go(oc)
        return oc

    # ================================================================ plain events (server)
    # ---- OwlTrReset(Msg): this side back to no trade, then its view
    y = y0
    ce = event("OwlTrReset", MSG_PIN, y, 0)
    setv("TrRole", "int", "0", (300, y))
    nul = g.var_set("TrPeer", *T["actor"], pos=(600, y))
    c.go(nul)
    for k, arr in enumerate(("TrSlots", "TrIds", "TrQty")):
        cl = g.array_fn("Array_Clear", pos=(900 + 300 * k, y), elem_cat="int")
        g.wire(*var(arr, "int", (900 + 300 * k, y + 300), arr=True), cl, "TargetArray", exec=False)
        c.go(cl)
    setv("TrCoins", "int", "0", (1900, y))
    setv("TrOk", "bool", "false", (2200, y))
    sync((ce, "Msg"), (2500, y))

    # ---- OwlTrSync(Msg): this side's view -> OwlClientTr to its owner
    y = y0 + 1500
    ce = event("OwlTrSync", MSG_PIN, y, 0)
    settings((300, y))
    for k, arr in enumerate(("SvTrBagS", "SvTrBagI", "SvTrBagQ", "SvTrThIds", "SvTrThQty")):
        cl = g.array_fn("Array_Clear", pos=(9000 + 300 * k, y), elem_cat="int")
        g.wire(*var(arr, "int", (9000 + 300 * k, y + 300), arr=True), cl, "TargetArray", exec=False)
        c.go(cl)
    setv("SvTrThCoins", "int", "0", (10600, y))
    setv("SvTrThOk", "bool", "false", (10900, y))
    setv("SvTrPeerName", "string", "", (11200, y))
    # my backpack
    x = 11600
    ch = cast_char((g.var_get("TmPawn", "object", ir.obj_path(PAWN), pos=(x, y + 300)), "TmPawn"), (x + 200, y))
    nochar = [(ch, "CastFailed")]
    c.exits = [(ch, "then")]
    lst = c.fn("GetItemList", INV, {"self": bag(ch, (x + 300, y + 600))}, (x + 600, y + 600))
    loop = g.foreach(ITEM, pos=(x + 700, y))
    g.wire(lst[0], lst[1], loop, "Array", exec=False)
    c.go(loop, "Exec")
    c.exits = [(loop, "LoopBody")]
    el = (loop, "Array Element")
    bv = c.branch(c.fn("IsValid", KSL, {"Object": el}, (x + 900, y + 300)), (x + 1000, y))
    c.exits = [(bv, "then")]
    for k, (arr, src) in enumerate((("SvTrBagS", (loop, "Array Index")), ("SvTrBagI", item_id(el, (x + 1300, y + 450))),
                                    ("SvTrBagQ", item_qty(el, (x + 1600, y + 450))))):
        ad = g.array_fn("Array_Add", pos=(x + 1300 + 300 * k, y), elem_cat="int")
        g.wire(*var(arr, "int", (x + 1300 + 300 * k, y + 300), arr=True), ad, "TargetArray", exec=False)
        g.array_item_pin(ad, "NewItem", "int")
        g.wire(src[0], src[1], ad, "NewItem", exec=False)
        c.go(ad)
    c.exits = [(loop, "Completed")] + nochar
    # my wallet
    x += 2400
    oc = owner_cast(None, (x, y))
    no_owner = [(oc, "CastFailed")]
    c.exits = [(oc, "then")]
    wallet("SvTrSlot", "SvTrSave", "SvTrBal", oc, (x + 600, y))
    c.exits += no_owner
    # the other side, if any
    x += 2600
    pc = cast_relay(var("TrPeer", "actor", (x, y + 300)), (x + 200, y))
    nopeer = [(pc, "CastFailed")]
    c.exits = [(pc, "then")]
    for k, (mine, theirs, t, arr) in enumerate((("SvTrThIds", "TrIds", "int", True), ("SvTrThQty", "TrQty", "int", True),
                                               ("SvTrThCoins", "TrCoins", "int", False), ("SvTrThOk", "TrOk", "bool", False))):
        setv(mine, t, pget(pc, theirs, t, (x + 400 + 300 * k, y + 300), arr=arr), (x + 500 + 300 * k, y), arr=arr)
    x += 1800
    pch = cast_char(_pawn(g, pc, AS_R, RC, (x, y + 300)), (x + 200, y))
    c.exits = [(pch, "then")]
    setv("SvTrPeerName", "string", name_of(pch, (x + 400, y + 300)), (x + 500, y))
    c.exits += [(pch, "CastFailed")] + nopeer
    # -> the owner
    x += 1000
    vals = {"Role": var("TrRole", "int", (x, y + 300)), "Peer": var("SvTrPeerName", "string", (x, y + 450)),
            "MyIds": var("TrIds", "int", (x, y + 600), arr=True), "MyQty": var("TrQty", "int", (x, y + 750), arr=True),
            "ThIds": var("SvTrThIds", "int", (x, y + 900), arr=True), "ThQty": var("SvTrThQty", "int", (x, y + 1050), arr=True),
            "MyCoins": var("TrCoins", "int", (x, y + 1200)), "ThCoins": var("SvTrThCoins", "int", (x, y + 1350)),
            "MyOk": var("TrOk", "bool", (x, y + 1500)), "ThOk": var("SvTrThOk", "bool", (x, y + 1650)),
            "BagSlots": var("SvTrBagS", "int", (x, y + 1800), arr=True), "BagIds": var("SvTrBagI", "int", (x, y + 1950), arr=True),
            "BagQty": var("SvTrBagQ", "int", (x, y + 2100), arr=True), "Wallet": var("SvTrBal", "int", (x, y + 2250)),
            "Coins": imath("Greater_IntInt", var("SvTrCur", "int", (x, y + 2400)), 0, (x + 200, y + 2400)),
            "Msg": (ce, "Msg")}
    call("OwlClientTr", SYNC_PINS, vals, (x + 400, y))

    # ================================================================ player RPCs
    def me_pawn(pos):
        return (g.var_get("TmPawn", "object", ir.obj_path(PAWN), pos=pos), "TmPawn")

    def dist_ok(a, b, pos):
        """GetDistanceTo(a, b) <= SvTrDist (pure)."""
        d = c.fn("GetDistanceTo", ACTOR, {"self": a, "OtherActor": b}, pos)
        return c.fn("LessEqual_DoubleDouble", KML, {"A": d, "B": c.fn("Conv_IntToDouble", KML, {
            "InInt": var("SvTrDist", "int", (pos[0], pos[1] + 150))}, (pos[0] + 200, pos[1] + 150))}, (pos[0] + 400, pos[1]))

    def each_relay(pos):
        """ForEach over every relay but this one, entered from c.exits: leaves c.exits on the
        body with (cast) the other relay; returns (loop, cast)."""
        x, y = pos
        all_ = g.get_all_actors(RC, pos=(x, y))
        c.go(all_)
        loop = g.foreach(ACTOR, pos=(x + 300, y))
        g.wire(all_, "OutActors", loop, "Array", exec=False)
        g.wire(all_, "then", loop, "Exec")
        c.exits = [(loop, "LoopBody")]
        other = c.fn("NotEqual_ObjectObject", KML, {"A": (loop, "Array Element"), "B": _self(g, (x + 300, y + 450))},
                     (x + 500, y + 300))
        b = c.branch(other, (x + 600, y))
        c.exits = [(b, "then")]
        rc = cast_relay((loop, "Array Element"), (x + 900, y))
        c.exits = [(rc, "then")]
        return loop, rc

    def peer_name(pos):
        return var("SvTrPeerName", "string", pos)

    # ---- the players near me
    y = y0 + 5000
    event("OwlServerTrNear", [], y, R.RUN_ON_SERVER)
    settings((300, y))
    for k, (arr, t) in enumerate((("SvTrNames", "string"), ("SvTrStates", "state"))):
        h_clear = g.array_fn("Array_Clear", pos=(9000 + 300 * k, y), elem_cat=T[t][0], elem_sub=T[t][1])
        g.wire(*var(arr, t, (9000 + 300 * k, y + 300), arr=True), h_clear, "TargetArray", exec=False)
        c.go(h_clear)
    loop, rc = each_relay((9700, y))
    other_pawn = _pawn(g, rc, AS_R, RC, (10600, y + 450))
    och = cast_char(other_pawn, (10900, y))
    c.exits = [(och, "then")]
    branch(dist_ok(me_pawn((11000, y + 600)), (och, AS_C), (11200, y + 600)), (11300, y))
    own = g.call("GetOwner", ACTOR, pos=(11500, y + 450))
    g.wire(rc, AS_R, own, "self", exec=False)
    occ = g.cast(CTRL, pos=(11600, y))
    occ.pin("Object").typed("object", ir.obj_path(ACTOR), direction="EGPD_Input")
    g.wire(own, "ReturnValue", occ, "Object", exec=False)
    c.go(occ)
    c.exits = [(occ, "then")]
    st = g.var_get("PlayerState", "object", ir.obj_path(PSTATE), parent=CTRL, pos=(11800, y + 450))
    g.wire(occ, "AsController", st, "self", exec=False)
    for k, (arr, t, src) in enumerate((("SvTrNames", "string", name_of(och, (11900, y + 600))),
                                       ("SvTrStates", "state", (st, "PlayerState")))):
        ad = g.array_fn("Array_Add", pos=(12100 + 300 * k, y), elem_cat=T[t][0], elem_sub=T[t][1])
        g.wire(*var(arr, t, (12100 + 300 * k, y + 300), arr=True), ad, "TargetArray", exec=False)
        g.array_item_pin(ad, "NewItem", T[t][0], T[t][1])
        g.wire(src[0], src[1], ad, "NewItem", exec=False)
        c.go(ad)
    c.exits = [(loop, "Completed")]
    call("OwlClientTrNear", NEAR_PINS, {"Names": var("SvTrNames", "string", (12700, y + 300), arr=True),
                                        "States": var("SvTrStates", "state", (12700, y + 450), arr=True)}, (12900, y))

    # ---- my view again
    y = y0 + 6500
    event("OwlServerTrState", [], y, R.RUN_ON_SERVER)
    sync("", (300, y))

    # ---- ask a player
    y = y0 + 8000
    ce = event("OwlServerTrAsk", [("State", "state", False)], y, R.RUN_ON_SERVER)
    settings((300, y))
    x = 9000
    branch(imath("Greater_IntInt", var("SvTrOn", "int", (x, y + 300)), 0, (x + 200, y + 300)), (x + 300, y),
           "Trading is turned off on this server.")
    x += 900
    branch(imath("EqualEqual_IntInt", var("TrRole", "int", (x, y + 300)), 0, (x + 200, y + 300)), (x + 300, y),
           "Finish or cancel the trade you're in first.")
    x += 900
    since = c.fn("Subtract_DoubleDouble", KML, {"A": now((x, y + 300)), "B": var("TrLast", "real", (x, y + 450))}, (x + 200, y + 300))
    waited = c.fn("BooleanOR", KML, {
        "A": c.fn("LessEqual_DoubleDouble", KML, {"A": var("TrLast", "real", (x, y + 600)), "B": ("0.0", "real")}, (x + 200, y + 600)),
        "B": c.fn("GreaterEqual_DoubleDouble", KML, {"A": since, "B": c.fn("Conv_IntToDouble", KML, {
            "InInt": var("SvTrCd", "int", (x, y + 750))}, (x + 200, y + 750))}, (x + 400, y + 450))}, (x + 600, y + 450))
    branch(waited, (x + 700, y), "You traded a moment ago. Wait a little before the next trade.")
    # find the relay of that player
    x += 1500
    c.go(g.var_set("SvTrFound", *T["actor"], pos=(x, y)))          # none found yet
    loop, rc = each_relay((x + 300, y))
    own = g.call("GetOwner", ACTOR, pos=(x + 1300, y + 450))
    g.wire(rc, AS_R, own, "self", exec=False)
    occ = g.cast(CTRL, pos=(x + 1400, y))
    occ.pin("Object").typed("object", ir.obj_path(ACTOR), direction="EGPD_Input")
    g.wire(own, "ReturnValue", occ, "Object", exec=False)
    c.go(occ)
    c.exits = [(occ, "then")]
    st = g.var_get("PlayerState", "object", ir.obj_path(PSTATE), parent=CTRL, pos=(x + 1600, y + 450))
    g.wire(occ, "AsController", st, "self", exec=False)
    branch(c.fn("EqualEqual_ObjectObject", KML, {"A": (st, "PlayerState"), "B": (ce, "State")}, (x + 1800, y + 450)), (x + 1900, y))
    setv("SvTrFound", "actor", (rc, AS_R), (x + 2200, y))
    c.exits = [(loop, "Completed")]
    x += 2700
    fc = cast_relay(var("SvTrFound", "actor", (x, y + 300)), (x + 200, y))
    c.exits = [(fc, "CastFailed")]
    sync("That player isn't available to trade.", (x + 500, y + 900))
    c.exits = [(fc, "then")]
    x += 600
    branch(c.fn("NotEqual_ObjectObject", KML, {"A": (fc, AS_R), "B": _self(g, (x, y + 450))}, (x + 200, y + 300)),
           (x + 300, y), "You can't trade with yourself.")
    x += 700
    branch(imath("EqualEqual_IntInt", pget(fc, "TrRole", "int", (x, y + 300)), 0, (x + 200, y + 300)), (x + 300, y),
           "That player is busy with another trade.")
    x += 700
    fch = cast_char(_pawn(g, fc, AS_R, RC, (x, y + 300)), (x + 200, y))
    c.exits = [(fch, "CastFailed")]
    sync("That player has no character right now.", (x + 500, y + 900))
    c.exits = [(fch, "then")]
    x += 600
    branch(dist_ok(me_pawn((x, y + 600)), (fch, AS_C), (x + 200, y + 600)), (x + 300, y),
           h.text(["Get closer: you must be within ", (var("SvTrDist", "int", (x, y + 1200))[0], "SvTrDist", "int"),
                   " cm of them."], (x + 300, y + 1200)))
    x += 700
    t_now = lambda pos: now(pos)
    setv("TrRole", "int", "1", (x, y))
    setv("TrPeer", "actor", (fc, AS_R), (x + 300, y))
    setv("TrAt", "real", t_now((x + 400, y + 300)), (x + 600, y))
    pset(fc, "TrRole", "int", "2", (x + 900, y))
    pset(fc, "TrPeer", "actor", _self(g, (x + 1000, y + 300)), (x + 1200, y))
    pset(fc, "TrAt", "real", t_now((x + 1300, y + 450)), (x + 1500, y))
    sync(h.text(["Asked ", name_of(fch, (x + 1600, y + 600)), " to trade. Waiting for an answer..."], (x + 1800, y + 600)),
         (x + 1800, y))
    me_ch = cast_char(me_pawn((x + 2100, y + 300)), (x + 2200, y))
    c.exits = [(me_ch, "then")]
    sync(h.text([name_of(me_ch, (x + 2400, y + 600)), " wants to trade with you."], (x + 2600, y + 600)), (x + 2600, y),
         target=(fc, AS_R))

    # ---- answer a request
    y = y0 + 11000
    ce = event("OwlServerTrAnswer", [("Yes", "bool", False)], y, R.RUN_ON_SERVER)
    pc = cast_relay(var("TrPeer", "actor", (300, y + 300)), (500, y))
    c.exits = [(pc, "CastFailed")]
    reset("That trade request is gone.", (800, y + 900))
    c.exits = [(pc, "then")]
    ok = c.fn("BooleanAND", KML, {
        "A": imath("EqualEqual_IntInt", var("TrRole", "int", (700, y + 300)), 2, (900, y + 300)),
        "B": imath("EqualEqual_IntInt", pget(pc, "TrRole", "int", (700, y + 450)), 1, (900, y + 450))}, (1100, y + 300))
    b = c.branch(ok, (1200, y))
    c.exits = [(b, "else")]
    reset("That trade request is gone.", (1500, y + 900))
    c.exits = [(b, "then")]
    by = c.branch((ce, "Yes"), (1500, y))
    c.exits = [(by, "then")]
    setv("TrRole", "int", "3", (1800, y))
    pset(pc, "TrRole", "int", "3", (2100, y))
    sync("Trade started. Offer items from your backpack, then Confirm.", (2400, y))
    sync("Trade started. Offer items from your backpack, then Confirm.", (2700, y), target=(pc, AS_R))
    c.exits = [(by, "else")]
    reset("The other player declined your trade.", (1800, y + 600), target=(pc, AS_R))
    reset("You declined the trade.", (2100, y + 600))

    # ---- cancel
    y = y0 + 12500
    event("OwlServerTrCancel", [], y, R.RUN_ON_SERVER)
    pc = cast_relay(var("TrPeer", "actor", (300, y + 300)), (500, y))
    c.exits = [(pc, "then")]
    reset("The other player cancelled the trade.", (800, y), target=(pc, AS_R))
    c.exits += [(pc, "CastFailed")]
    reset("Trade cancelled.", (1100, y))

    # ---- offer / take back / coins: each clears both confirmations and syncs both
    def changed(pos):
        """Both TrOk off and both views again (from c.exits; needs the peer cast)."""
        x, y = pos
        pc = cast_relay(var("TrPeer", "actor", (x, y + 300)), (x + 200, y))
        gone = [(pc, "CastFailed")]
        c.exits = [(pc, "then")]
        setv("TrOk", "bool", "false", (x + 500, y))
        pset(pc, "TrOk", "bool", "false", (x + 800, y))
        sync("", (x + 1100, y))
        sync("", (x + 1400, y), target=(pc, AS_R))
        c.exits += gone

    def in_trade(pos):
        branch(imath("EqualEqual_IntInt", var("TrRole", "int", (pos[0], pos[1] + 300)), 3, (pos[0] + 200, pos[1] + 300)), pos,
               "You aren't in a trade.")

    y = y0 + 14000
    ce = event("OwlServerTrOffer", [("Slot", "int", False)], y, R.RUN_ON_SERVER)
    settings((300, y))
    x = 9000
    in_trade((x, y))
    x += 600
    branch(imath("Less_IntInt", (g.array_len(*var("TrSlots", "int", (x, y + 300), arr=True), (x + 200, y + 300), elem_cat="int"),
                                 "ReturnValue"), var("SvTrMax", "int", (x, y + 450)), (x + 400, y + 300)), (x + 500, y),
           "Your side of the trade is full.")
    x += 800
    branch(imath("EqualEqual_IntInt", c.find(var("TrSlots", "int", (x, y + 300), arr=True), (ce, "Slot"), "int", (x + 200, y + 300)),
                 -1, (x + 400, y + 300)), (x + 500, y), "That item is already on the table.")
    x += 800
    mch = cast_char(me_pawn((x, y + 300)), (x + 200, y))
    c.exits = [(mch, "then")]
    item = item_at(bag(mch, (x + 300, y + 600)), (ce, "Slot"), (x + 500, y + 600))
    branch(c.fn("IsValid", KSL, {"Object": item}, (x + 800, y + 450)), (x + 800, y), "That backpack slot is empty.")
    x += 1100
    for k, (arr, src) in enumerate((("TrSlots", (ce, "Slot")), ("TrIds", item_id(item, (x + 300 * k, y + 450))),
                                    ("TrQty", item_qty(item, (x + 300 * k, y + 600))))):
        ad = g.array_fn("Array_Add", pos=(x + 300 * k, y), elem_cat="int")
        g.wire(*var(arr, "int", (x + 300 * k, y + 300), arr=True), ad, "TargetArray", exec=False)
        g.array_item_pin(ad, "NewItem", "int")
        g.wire(src[0], src[1], ad, "NewItem", exec=False)
        c.go(ad)
    changed((x + 1000, y))
    c.exits += [(mch, "CastFailed")]

    y = y0 + 15500
    ce = event("OwlServerTrTake", [("Entry", "int", False)], y, R.RUN_ON_SERVER)
    in_trade((300, y))
    branch(c.fn("BooleanAND", KML, {
        "A": imath("GreaterEqual_IntInt", (ce, "Entry"), 0, (600, y + 300)),
        "B": imath("Less_IntInt", (ce, "Entry"), (g.array_len(*var("TrSlots", "int", (600, y + 450), arr=True), (800, y + 450),
                                                              elem_cat="int"), "ReturnValue"), (1000, y + 450))}, (1100, y + 300)),
           (1100, y))
    for k, arr in enumerate(("TrSlots", "TrIds", "TrQty")):
        rm = g.array_fn("Array_Remove", pos=(1400 + 300 * k, y), elem_cat="int")
        g.wire(*var(arr, "int", (1400 + 300 * k, y + 300), arr=True), rm, "TargetArray", exec=False)
        rm.pin("IndexToRemove").typed("int", direction="EGPD_Input")
        g.wire(ce, "Entry", rm, "IndexToRemove", exec=False)
        c.go(rm)
    changed((2400, y))

    y = y0 + 17000
    ce = event("OwlServerTrCoins", [("Amount", "int", False)], y, R.RUN_ON_SERVER)
    settings((300, y))
    in_trade((9000, y))
    branch(imath("Greater_IntInt", var("SvTrCur", "int", (9600, y + 300)), 0, (9800, y + 300)), (9900, y),
           "Coins can't be traded on this server.")
    setv("TrCoins", "int", h.clamp((ce, "Amount"), (0, 100000000), (10100, y + 300)), (10300, y))
    changed((10600, y))

    # ---- confirm
    y = y0 + 18500
    event("OwlServerTrConfirm", [], y, R.RUN_ON_SERVER)
    in_trade((300, y))
    pc = cast_relay(var("TrPeer", "actor", (900, y + 300)), (1000, y))
    c.exits = [(pc, "CastFailed")]
    reset("The other player is gone.", (1300, y + 900))
    c.exits = [(pc, "then")]
    setv("TrOk", "bool", "true", (1300, y))
    both = c.branch(pget(pc, "TrOk", "bool", (1400, y + 300)), (1600, y))
    c.exits = [(both, "then")]
    call("OwlTrExecute", [], {}, (1900, y))
    c.exits = [(both, "else")]
    sync("Confirmed. Waiting for the other player to confirm.", (1900, y + 600))
    sync("The other player confirmed. Check the offer, then Confirm.", (2200, y + 600), target=(pc, AS_R))

    # ================================================================ the trade itself
    y = y0 + 20000
    event("OwlTrExecute", [], y, 0)
    settings((300, y))
    x = 9000
    pc = cast_relay(var("TrPeer", "actor", (x, y + 300)), (x + 200, y))
    c.exits = [(pc, "CastFailed")]
    reset("The other player is gone.", (x + 500, y + 900))
    c.exits = [(pc, "then")]
    x += 600
    mch = cast_char(me_pawn((x, y + 300)), (x + 200, y))
    c.exits = [(mch, "CastFailed")]
    reset("You need a character to trade.", (x + 500, y + 900))
    reset("The other player has no character right now.", (x + 800, y + 900), target=(pc, AS_R))
    c.exits = [(mch, "then")]
    x += 600
    pch = cast_char(_pawn(g, pc, AS_R, RC, (x, y + 300)), (x + 200, y))
    c.exits = [(pch, "CastFailed")]
    reset("The other player has no character right now.", (x + 500, y + 900))
    reset("You need a character to trade.", (x + 800, y + 900), target=(pc, AS_R))
    c.exits = [(pch, "then")]
    x += 600
    my_bag = lambda pos: bag(mch, pos)
    th_bag = lambda pos: bag(pch, pos)

    def fail(msg, pos):
        """Both confirmations off, both views with msg."""
        setv("TrOk", "bool", "false", pos)
        pset(pc, "TrOk", "bool", "false", (pos[0] + 300, pos[1]))
        sync(msg, (pos[0] + 600, pos[1]))
        sync(msg, (pos[0] + 900, pos[1]), target=(pc, AS_R))

    b = c.branch(dist_ok((mch, AS_C), (pch, AS_C), (x, y + 300)), (x + 300, y))
    c.exits = [(b, "else")]
    fail("You're too far apart to trade. Get closer and confirm again.", (x + 500, y + 900))
    c.exits = [(b, "then")]
    x += 1700
    # every offered slot still holds what was offered (both sides)
    setv("SvTrBad", "bool", "false", (x, y))
    x += 300
    for side in range(2):
        get = (lambda n, p, arr=True: var(n, "int", p, arr=arr)) if side == 0 else \
            (lambda n, p, arr=True: pget(pc, n, "int", p, arr=arr))
        inv = my_bag if side == 0 else th_bag
        each = c.foreach("int", get("TrSlots", (x, y + 300)), (x + 200, y))
        item = item_at(inv((x + 300, y + 600)), (each, "Array Element"), (x + 500, y + 600))
        okv = c.fn("BooleanAND", KML, {
            "A": c.fn("IsValid", KSL, {"Object": item}, (x + 700, y + 450)),
            "B": c.fn("BooleanAND", KML, {
                "A": imath("EqualEqual_IntInt", item_id(item, (x + 700, y + 750)),
                           c.at(get("TrIds", (x + 700, y + 900)), (each, "Array Index"), "int", (x + 900, y + 900)), (x + 1100, y + 750)),
                "B": imath("EqualEqual_IntInt", item_qty(item, (x + 700, y + 1050)),
                           c.at(get("TrQty", (x + 700, y + 1200)), (each, "Array Index"), "int", (x + 900, y + 1200)), (x + 1100, y + 1050))},
                (x + 1300, y + 900))}, (x + 1500, y + 450))
        bo = c.branch(okv, (x + 500, y))
        c.exits = [(bo, "else")]
        setv("SvTrBad", "bool", "true", (x + 800, y + 300))
        c.exits = [(each, "Completed")]
        x += 1800
    b = c.branch(c.fn("Not_PreBool", KML, {"A": var("SvTrBad", "bool", (x, y + 300))}, (x + 200, y + 300)), (x + 300, y))
    c.exits = [(b, "else")]
    fail("An offered item moved or changed. Check both offers and confirm again.", (x + 500, y + 900))
    c.exits = [(b, "then")]
    x += 1700
    # room for what comes in
    n_mine = (g.array_len(*var("TrSlots", "int", (x, y + 300), arr=True), (x + 200, y + 300), elem_cat="int"), "ReturnValue")
    n_th = (g.array_len(*pget(pc, "TrSlots", "int", (x, y + 450), arr=True), (x + 200, y + 450), elem_cat="int"), "ReturnValue")
    room = c.fn("BooleanAND", KML, {
        "A": imath("LessEqual_IntInt", n_th, c.fn("GetFreeSpaceCount", INV, {"self": my_bag((x, y + 600))}, (x + 200, y + 600)),
                   (x + 400, y + 450)),
        "B": imath("LessEqual_IntInt", n_mine, c.fn("GetFreeSpaceCount", INV, {"self": th_bag((x, y + 750))}, (x + 200, y + 750)),
                   (x + 400, y + 600))}, (x + 600, y + 450))
    b = c.branch(room, (x + 700, y))
    c.exits = [(b, "else")]
    fail("Not enough free backpack slots for the trade: make room and confirm again.", (x + 900, y + 900))
    c.exits = [(b, "then")]
    x += 2000
    # coins: each wallet must cover its own offer
    moc = owner_cast(None, (x, y))
    no1 = [(moc, "CastFailed")]
    c.exits = [(moc, "then")]
    wallet("SvTrSlot", "SvTrSave", "SvTrBal", moc, (x + 500, y))
    x += 2500
    poc = owner_cast(pc, (x, y))
    no2 = [(poc, "CastFailed")]
    c.exits = [(poc, "then")]
    wallet("SvTrPSlot", "SvTrPSave", "SvTrPBal", poc, (x + 500, y))
    x += 2500
    coins_ok = c.fn("BooleanAND", KML, {
        "A": imath("GreaterEqual_IntInt", var("SvTrBal", "int", (x, y + 300)), var("TrCoins", "int", (x, y + 450)), (x + 200, y + 300)),
        "B": imath("GreaterEqual_IntInt", var("SvTrPBal", "int", (x, y + 600)), pget(pc, "TrCoins", "int", (x, y + 750)),
                   (x + 200, y + 600))}, (x + 400, y + 450))
    b = c.branch(coins_ok, (x + 500, y))
    c.exits = [(b, "else")] + no1 + no2
    fail("Not enough Owl coins in a wallet for the offer.", (x + 800, y + 900))
    c.exits = [(b, "then")]
    x += 2000
    # the move: my offer to them, theirs to me
    for side in range(2):
        get = (lambda n, p: var(n, "int", p, arr=True)) if side == 0 else (lambda n, p: pget(pc, n, "int", p, arr=True))
        src, dst = (my_bag, th_bag) if side == 0 else (th_bag, my_bag)
        each = c.foreach("int", get("TrSlots", (x, y + 300)), (x + 200, y))
        mv = g.call("MoveItem", INV, pos=(x + 500, y))
        s_ = src((x + 300, y + 600))
        g.wire(s_[0], s_[1], mv, "self", exec=False)
        g.wire(each, "Array Element", mv, "srcIndex", exec=False)
        d_ = dst((x + 300, y + 750))
        g.wire(d_[0], d_[1], mv, "targetInventory", exec=False)
        g.typed_input(mv, "targetIndex", "-1", "int")
        g.wire(*c.at(get("TrQty", (x + 300, y + 900)), (each, "Array Index"), "int", (x + 500, y + 900)), mv, "quantity", exec=False)
        c.go(mv)
        c.exits = [(each, "Completed")]
        x += 1200
    # coins: Balance += what comes in - what goes out, on both saves
    for side, (save_v, slot_v, bal_v) in enumerate((("SvTrSave", "SvTrSlot", "SvTrBal"), ("SvTrPSave", "SvTrPSlot", "SvTrPBal"))):
        give = var("TrCoins", "int", (x, y + 600)) if side == 0 else pget(pc, "TrCoins", "int", (x, y + 600))
        get_ = pget(pc, "TrCoins", "int", (x, y + 750)) if side == 0 else var("TrCoins", "int", (x, y + 750))
        nb = imath("Add_IntInt", imath("Subtract_IntInt", var(bal_v, "int", (x, y + 450)), give, (x + 200, y + 450)), get_,
                   (x + 400, y + 450))
        sb = g.var_set("Balance", "int", parent=CE_SG, pos=(x + 500, y))
        g.wire(*var(save_v, "cesave", (x + 300, y + 300)), sb, "self", exec=False)
        g.wire(nb[0], nb[1], sb, "Balance", exec=False)
        c.go(sb)
        sv = g.call("SaveGameToSlot", GS, pos=(x + 800, y))
        g.wire(*var(save_v, "cesave", (x + 600, y + 300)), sv, "SaveGameObject", exec=False)
        g.wire(*var(slot_v, "string", (x + 600, y + 450)), sv, "SlotName", exec=False)
        g.typed_input(sv, "UserIndex", "0", "int")
        c.go(sv)
        x += 1200
    # the log line: "<A> gave <B>: x, y | <B> gave <A>: z"
    with_log = c.branch(imath("Greater_IntInt", var("SvTrLog", "int", (x, y + 300)), 0, (x + 200, y + 300)), (x + 300, y))
    nolog = [(with_log, "else")]
    c.exits = [(with_log, "then")]
    x += 600
    me_name = lambda pos: name_of(mch, pos)
    th_name = lambda pos: name_of(pch, pos)
    setv("SvTrLine", "string", c.concat([me_name((x, y + 300)), " gave ", th_name((x, y + 450)), ":"], (x + 200, y + 300)), (x + 600, y))
    x += 900
    for side in range(2):
        if side:
            setv("SvTrLine", "string", c.concat([var("SvTrLine", "string", (x, y + 300)), " | ", th_name((x, y + 450)), " gave ",
                                                 me_name((x, y + 600)), ":"], (x + 200, y + 300)), (x + 700, y))
            x += 900
        get = (lambda n, p: var(n, "int", p, arr=True)) if side == 0 else (lambda n, p: pget(pc, n, "int", p, arr=True))
        each = c.foreach("int", get("TrIds", (x, y + 300)), (x + 200, y))
        nm = item_name((each, "Array Element"), (x + 300, y + 600))
        setv("SvTrLine", "string", c.concat([var("SvTrLine", "string", (x + 400, y + 300)), " ", nm, " x",
                                             c.int_text(c.at(get("TrQty", (x + 300, y + 1100)), (each, "Array Index"), "int",
                                                             (x + 500, y + 1100)), (x + 700, y + 1100)), ","], (x + 900, y + 300)),
             (x + 500, y))
        c.exits = [(each, "Completed")]
        coins = var("TrCoins", "int", (x, y + 1300)) if side == 0 else pget(pc, "TrCoins", "int", (x, y + 1300))
        bc = c.branch(imath("Greater_IntInt", coins, 0, (x + 1300, y + 1300)), (x + 1300, y))
        c.exits = [(bc, "then")]
        setv("SvTrLine", "string", c.concat([var("SvTrLine", "string", (x + 1400, y + 300)), " ",
                                             c.int_text(coins, (x + 1400, y + 1450)), " coins"], (x + 1600, y + 300)), (x + 1600, y))
        c.exits += [(bc, "else")]
        x += 2000
    # into OwlTrades (made if missing), at most TRADE_LOG_MAX lines
    sc, missing = h.load(c.exits, c.fn("MakeLiteralString", KSL, {"Value": (MOD.TRADES_SLOT, "string")}, (x, y + 600)), TR_SG,
                         (x, y))
    c.exits = [(sc, "then")]
    setv("SvTrLogSave", "trsave", (sc, h.save_as(TR_SG)), (x + 900, y))
    have = c.exits
    crt = g.call("CreateSaveGameObject", GS, pos=(x + 700, y + 900))
    cp = crt.pin("SaveGameClass").typed("class", ir.obj_path("/Script/Engine.SaveGame"), direction="EGPD_Input")
    cp.set("PinType.bIsUObjectWrapper", "True")
    cp.set("DefaultObject", '"%s"' % TR_SG)
    crt.pin("ReturnValue").typed("object", ir.obj_path(TR_SG), direction="EGPD_Output")
    c.exits = missing
    c.go(crt)
    setv("SvTrLogSave", "trsave", (crt, "ReturnValue"), (x + 900, y + 900))
    c.exits = have + c.exits
    x += 1300

    def log_arr(pos):
        lg = g.var_get("Log", "string", parent=TR_SG, pos=pos)
        lg.pin("Log").set("PinType.ContainerType", "Array")
        g.wire(*var("SvTrLogSave", "trsave", (pos[0] - 200, pos[1])), lg, "self", exec=False)
        return (lg, "Log")

    stamp = c.fn("Conv_TextToString", "/Script/Engine.KismetTextLibrary", {"InText": c.fn(
        "AsDateTime_DateTime", "/Script/Engine.KismetTextLibrary", {"In": c.fn("Now", KML, {}, (x, y + 750))}, (x + 200, y + 750))},
        (x + 400, y + 750))
    ad = g.array_fn("Array_Add", pos=(x, y), elem_cat="string")
    g.wire(*log_arr((x, y + 300)), ad, "TargetArray", exec=False)
    g.array_item_pin(ad, "NewItem", "string")
    line = c.concat([stamp, "|", var("SvTrLine", "string", (x + 400, y + 600))], (x + 600, y + 600))
    g.wire(line[0], line[1], ad, "NewItem", exec=False)
    c.go(ad)
    over = imath("Greater_IntInt", (g.array_len(*log_arr((x + 300, y + 900)), (x + 500, y + 900), elem_cat="string"), "ReturnValue"),
                 D.TRADE_LOG_MAX, (x + 700, y + 900))
    bo = c.branch(over, (x + 300, y))
    c.exits = [(bo, "then")]
    rm = g.array_fn("Array_Remove", pos=(x + 600, y), elem_cat="string")
    g.wire(*log_arr((x + 600, y + 300)), rm, "TargetArray", exec=False)
    rm.pin("IndexToRemove").typed("int", direction="EGPD_Input").literal("0")
    c.go(rm)
    c.exits += [(bo, "else")]
    sv = g.call("SaveGameToSlot", GS, pos=(x + 900, y))
    g.wire(*var("SvTrLogSave", "trsave", (x + 700, y + 300)), sv, "SaveGameObject", exec=False)
    g.typed_input(sv, "SlotName", MOD.TRADES_SLOT, "string")
    g.typed_input(sv, "UserIndex", "0", "int")
    c.go(sv)
    c.exits += nolog
    x += 1400
    # done: both cooldowns start, both sides reset
    setv("TrLast", "real", now((x, y + 300)), (x + 200, y))
    pset(pc, "TrLast", "real", now((x + 300, y + 300)), (x + 500, y))
    reset("Trade done. Check your backpack.", (x + 800, y), target=(pc, AS_R))
    reset("Trade done. Check your backpack.", (x + 1100, y))

    # ================================================================ admins: the log
    y = y0 + 23000
    ce = event("OwlServerTrLog", [], y, R.RUN_ON_SERVER)
    _oc, _a, ok = h.unlocked(ce, y)
    sc, missing = h.load([(ok, "then")], c.fn("MakeLiteralString", KSL, {"Value": (MOD.TRADES_SLOT, "string")}, (900, y + 600)),
                         TR_SG, (1000, y))
    lg = g.var_get("Log", "string", parent=TR_SG, pos=(2000, y + 300))
    lg.pin("Log").set("PinType.ContainerType", "Array")
    g.wire(sc, h.save_as(TR_SG), lg, "self", exec=False)
    c.exits = [(sc, "then")]
    call("OwlClientTrLog", [("Lines", "string", True)], {"Lines": (lg, "Log")}, (2300, y))
    c.exits = missing
    clr = g.array_fn("Array_Clear", pos=(2000, y + 900), elem_cat="string")
    g.wire(*var("SvTrNames", "string", (1900, y + 1200), arr=True), clr, "TargetArray", exec=False)
    c.go(clr)
    call("OwlClientTrLog", [("Lines", "string", True)], {"Lines": var("SvTrNames", "string", (2100, y + 1200), arr=True)},
         (2300, y + 900))

    h.client_event("OwlClientTr", SYNC_PINS, SYNC_MINE, "TrVer", y0 + 25000)
    h.client_event("OwlClientTrNear", NEAR_PINS, ["TrNearNames", "TrNearStates"], "TrNearVer", y0 + 26000)
    h.client_event("OwlClientTrLog", [("Lines", "string", True)], ["TrLogC"], "TrLogVer", y0 + 26500)
    return flags


def tick(R, prevs, y0):
    """Server, every tick, entered from prevs; returns the exits. In a request or trade: the other
    relay gone (they left) -> reset; asked and unanswered past "tradetimeout" -> both reset."""
    g = R.g
    RC, AS_R = R.RELAY_C, "AsBP Owl Relay"
    c, imath = _ctx(R)
    h = helpers(R, {})
    c.exits = list(prevs)
    x, y = 0, y0

    def reset(msg, pos, target=None):
        n = h.call_self("OwlTrReset", MSG_PIN, pos)
        if target is not None:
            n.pin("self").typed("object", ir.obj_path(RC), direction="EGPD_Input")
            g.wire(target[0], target[1], n, "self", exec=False)
        h.wire_in(msg, n, "Msg", "string")
        c.go(n)

    role = lambda pos: h.get("TrRole", "int", pos)
    b = c.branch(imath("NotEqual_IntInt", role((x, y + 300)), 0, (x + 200, y + 300)), (x + 300, y))
    out = [(b, "else")]
    c.exits = [(b, "then")]
    pc = g.cast(RC, pos=(x + 600, y))
    pc.pin("Object").typed("object", ir.obj_path(ACTOR), direction="EGPD_Input")
    g.wire(*h.get("TrPeer", "actor", (x + 400, y + 300)), pc, "Object", exec=False)
    c.go(pc)
    c.exits = [(pc, "CastFailed")]
    reset("The other player left.", (x + 900, y + 600))
    out += c.exits
    c.exits = [(pc, "then")]
    waited = c.fn("Subtract_DoubleDouble", KML, {"A": c.fn("GetGameTimeInSeconds", KSL, {}, (x + 900, y + 300)),
                                                 "B": h.get("TrAt", "real", (x + 900, y + 450))}, (x + 1100, y + 300))
    late = c.fn("BooleanAND", KML, {
        "A": imath("EqualEqual_IntInt", role((x + 1100, y + 600)), 1, (x + 1300, y + 600)),
        "B": c.fn("Greater_DoubleDouble", KML, {"A": waited, "B": c.fn("Conv_IntToDouble", KML, {
            "InInt": h.get("SvTrTo", "int", (x + 1100, y + 750))}, (x + 1300, y + 750))}, (x + 1500, y + 450))},
        (x + 1700, y + 450))
    bl = c.branch(late, (x + 1200, y))
    out += [(bl, "else")]
    c.exits = [(bl, "then")]
    reset("Nobody answered the trade request.", (x + 1500, y), target=(pc, AS_R))
    reset("Your trade request ran out: they didn't answer.", (x + 1800, y))
    return out + c.exits
