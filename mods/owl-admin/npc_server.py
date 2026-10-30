"""NPCs, the server side: the relay's (10) NPC events, for the admin menu's NPC editor (03) and the
NPC window every player uses (15).

    OwlNpcSpawn(Index)       plain: NPC Index's BP_OwlNPC (14) removed and, if it is placed, spawned
                             again from the OwlNpcs save (name, role, line, its wares that are on,
                             its gear ids in NpcGear: the NPC puts them on itself)
    OwlNpcEnsure()           plain, once per relay (the server tick): leftovers (NpcIdx < 0) removed,
                             every placed NPC that has no BP_OwlNPC spawned
    OwlServerNpcGet()                    admins -> OwlClientNpc(...)
    OwlServerNpcSave(Index, Name, Role, Line, WIds, WPrice, WCur, WOn)   admins: text + wares, respawn
    OwlServerNpcPlace(Index)             admins: NPC Index stands in front of the admin, facing them,
                                         wearing the admin's equipped items; respawn
    OwlServerNpcDelete(Index)            admins: NPC Index unplaced and unnamed (its BP_OwlNPC removed)
    OwlClientNpc(Names, Roles, Lines, Placed, WIds, WPrice, WCur, WOn, Msg)   the admin's copy, NpcVer + 1
    OwlServerNpcBuy(Npc, Entry)          any player: buy ware Entry of that NPC -> OwlClientNpcBuy(Msg)

Buying: the player must be within NPC_TALK_DIST of the NPC and have a free backpack slot; the
price comes out of their backpack with the game's ValidatedDeleteItemsByTemplate (all or nothing:
fewer coins than the price takes none), then the item goes in. Currencies are menu_defs
NPC_CURRENCIES (item ids). The save keeps NPC_WARES wares and NPC_GEAR gear ids per NPC, flattened
(NPC k's ware w is at k * NPC_WARES + w). Offsets of 0 skip their Add node: a pasted B of 0 comes
back as Add_IntInt's own default, 1.
"""
from bpkit import ir
import menu_defs as D
from ce_server import helpers, T, KSTR, KSL, KML, GS, CS, CHAR, INV, ITEM
from ce_panel import _Ctx

N, W, G = D.N_NPCS, D.NPC_WARES, D.NPC_GEAR
ACTOR = "/Script/Engine.Actor"
CTRLR = "/Script/Engine.Controller"
KTXT = "/Script/Engine.KismetTextLibrary"
CLIENT_PINS = [("Names", "string", True), ("Roles", "string", True), ("Lines", "string", True), ("Placed", "int", True),
               ("WIds", "int", True), ("WPrice", "int", True), ("WCur", "int", True), ("WOn", "int", True),
               ("Msg", "string", False)]
CLIENT_MINE = ["NpcNamesC", "NpcRolesC", "NpcLinesC", "NpcPlacedC", "NpcWIdsC", "NpcWPriceC", "NpcWCurC", "NpcWOnC",
               "NpcMsgC"]
SAVE_STRS = ("Names", "Roles", "Lines", "Locs")
SAVE_WARES = ("WIds", "WPrice", "WCur", "WOn")
T.setdefault("actor", ("object", ir.obj_path(ACTOR)))
T.setdefault("real", ("real", None))


def variables(unreal, bel, npc_save_cls, npc_cls):
    """(name, type) for the relay. Npc*C / NpcVer / NpcBuy* = the owner's copy; Sv* the server's."""
    i, s, b = (bel.get_basic_type_by_name(t) for t in ("int", "string", "bool"))
    ints, strs = bel.get_array_type(i), bel.get_array_type(s)
    client = [("NpcNamesC", strs), ("NpcRolesC", strs), ("NpcLinesC", strs), ("NpcPlacedC", ints), ("NpcWIdsC", ints),
              ("NpcWPriceC", ints), ("NpcWCurC", ints), ("NpcWOnC", ints), ("NpcMsgC", s), ("NpcVer", i),
              ("NpcBuyMsgC", s), ("NpcBuyVer", i)]
    server = [("SvNpc", bel.get_object_reference_type(npc_save_cls)), ("SvNpcSeen", ints), ("SvNpcPlaced", ints),
              ("SvNpcActor", bel.get_object_reference_type(npc_cls)), ("SvNpcDone", b)]
    return client + server


def build(R, y0):
    """Add the NPC events to R.g from y0 down (R as for trade_server.build). Returns {event: net flags}."""
    g, MOD = R.g, R.MOD
    SG = MOD.full(R.PKG, MOD.NPC_SAVEGAME) + "_C"
    NPC = MOD.full(R.PKG, MOD.NPC_BP) + "_C"
    AS_N = "AsBP Owl NPC"
    T.setdefault("npcsave", ("object", ir.obj_path(SG)))
    T.setdefault("npc", ("object", ir.obj_path(NPC)))
    flags = {}
    h = helpers(R, flags)
    c = _Ctx(g, None, None, None)
    lit = lambda v: v if isinstance(v, tuple) else (str(v), "int")
    imath = lambda fn, a, b, pos: c.fn(fn, KML, {"A": lit(a), "B": lit(b)}, pos)
    sv = lambda pos: h.get("SvNpc", "npcsave", pos)

    # ------------------------------------------------------------ small pieces
    def event(name, pins, y, fl):
        ce = h.event(name, pins, y, fl)
        c.exits = [(ce, "then")]
        return ce

    def field(name, cat, pos):
        n = g.var_get(name, cat, parent=SG, pos=pos)
        n.pin(name).set("PinType.ContainerType", "Array")
        g.wire(*sv((pos[0] - 200, pos[1])), n, "self", exec=False)
        return (n, name)

    def npc_field(npc, name, cat, pos, arr=False):
        n = g.var_get(name, cat, parent=NPC, pos=pos)
        if arr:
            n.pin(name).set("PinType.ContainerType", "Array")
        g.wire(npc[0], npc[1], n, "self", exec=False)
        return (n, name)

    def npc_set(npc, name, cat, src, pos):
        n = g.var_set(name, cat, parent=NPC, pos=pos)
        g.wire(npc[0], npc[1], n, "self", exec=False)
        h.wire_in(src, n, name, cat)
        return c.go(n)

    def arr_set(array, index, item, cat, pos):
        n = g.array_fn("Array_Set", pos=pos, elem_cat=cat)
        g.wire(array[0], array[1], n, "TargetArray", exec=False)
        n.pin("Index").typed("int", direction="EGPD_Input")
        h.wire_in(index, n, "Index")
        g.array_item_pin(n, "Item", cat)
        h.wire_in(item, n, "Item", cat)
        return c.go(n)

    def arr_add(array, item, cat, pos):
        n = g.array_fn("Array_Add", pos=pos, elem_cat=cat)
        g.wire(array[0], array[1], n, "TargetArray", exec=False)
        g.array_item_pin(n, "NewItem", cat)
        h.wire_in(item, n, "NewItem", cat)
        return c.go(n)

    def offset(base, k, pos):
        """base + k, with no node for k == 0."""
        return imath("Add_IntInt", base, k, pos) if k else base

    def save_now(pos):
        sav = g.call("SaveGameToSlot", GS, pos=pos)
        g.wire(*sv((pos[0] - 200, pos[1] + 300)), sav, "SaveGameObject", exec=False)
        g.typed_input(sav, "SlotName", MOD.NPC_SLOT, "string")
        g.typed_input(sav, "UserIndex", "0", "int")
        return c.go(sav)

    def open_save(pos):
        """SvNpc = the OwlNpcs save, loaded or new, its arrays sized to N NPCs."""
        x, y = pos
        sc, missing = h.load(c.exits, _slot((x - 200, y + 300)), SG, (x, y))
        have = h.setv((sc, "then"), "SvNpc", "npcsave", (sc, h.save_as(SG)), (x + 1100, y))
        crt = g.call("CreateSaveGameObject", GS, pos=(x + 800, y + 600))
        cp = crt.pin("SaveGameClass").typed("class", ir.obj_path("/Script/Engine.SaveGame"), direction="EGPD_Input")
        cp.set("PinType.bIsUObjectWrapper", "True")
        cp.set("DefaultObject", '"%s"' % SG)
        crt.pin("ReturnValue").typed("object", ir.obj_path(SG), direction="EGPD_Output")
        for e, ep in missing:
            g.wire(e, ep, crt, "execute")
        made = h.setv((crt, "then"), "SvNpc", "npcsave", (crt, "ReturnValue"), (x + 1100, y + 600))
        c.exits = [have, made]
        xx = x + 1400
        for name, cat, size in ([(s, "string", N) for s in SAVE_STRS] + [("Gear", "int", N * G)]
                                + [(wv, "int", N * W) for wv in SAVE_WARES]):
            rs = g.array_fn("Array_Resize", pos=(xx, y), elem_cat=cat)
            g.wire(*field(name, cat, (xx, y + 300)), rs, "TargetArray", exec=False)
            rs.pin("Size").typed("int", direction="EGPD_Input").literal(str(size))
            c.go(rs)
            xx += 300

    def _slot(pos):
        """MOD.NPC_SLOT as a (node, pin) string (h.load wires its slot name)."""
        return c.fn("Concat_StrStr", KSTR, {"A": (MOD.NPC_SLOT, "string"), "B": ("", "string")}, pos)

    def reply(msg, pos):
        """SvNpcPlaced (1 per placed NPC), then OwlClientNpc to the owner."""
        x, y = pos
        cl = g.array_fn("Array_Clear", pos=(x, y), elem_cat="int")
        g.wire(*h.get("SvNpcPlaced", "int", (x, y + 300), arr=True), cl, "TargetArray", exec=False)
        c.go(cl)
        for k in range(N):
            xx = x + 300 + 400 * k
            placed = c.fn("SelectInt", KML, {"A": ("1", "int"), "B": ("0", "int"), "bPickA": imath(
                "Greater_IntInt", c.fn("Len", KSTR, {"S": c.at(field("Locs", "string", (xx, y + 450)), k, "string",
                                                               (xx + 150, y + 450))}, (xx + 300, y + 600)), 0,
                (xx + 300, y + 750))}, (xx + 200, y + 300))
            arr_add(h.get("SvNpcPlaced", "int", (xx, y + 150), arr=True), placed, "int", (xx + 200, y))
        x += 300 + 400 * N
        call = h.call_self("OwlClientNpc", CLIENT_PINS, (x, y))
        for k, name in enumerate(SAVE_STRS[:3]):
            g.wire(*field(name, "string", (x - 200, y + 300 + 150 * k)), call, name, exec=False)
        g.wire(*h.get("SvNpcPlaced", "int", (x - 200, y + 750), arr=True), call, "Placed", exec=False)
        for k, name in enumerate(SAVE_WARES):
            g.wire(*field(name, "int", (x - 200, y + 900 + 150 * k)), call, name, exec=False)
        h.wire_in(msg, call, "Msg", "string")
        c.go(call)

    def spawn_call(index, pos):
        n = h.call_self("OwlNpcSpawn", [("Index", "int", False)], pos)
        h.wire_in(index, n, "Index")
        return c.go(n)

    def name_or(k, pos):
        """Names[k], or "Merchant" (pure)."""
        nm = c.at(field("Names", "string", pos), k, "string", (pos[0] + 200, pos[1]))
        return c.fn("SelectString", KML, {"A": nm, "B": ("Merchant", "string"),
                                          "bPickA": imath("Greater_IntInt", c.fn("Len", KSTR, {"S": nm}, (pos[0] + 400, pos[1] + 150)),
                                                          0, (pos[0] + 600, pos[1] + 150))}, (pos[0] + 800, pos[1]))

    def all_npcs(pos):
        """GetAllActorsOfClass(BP_OwlNPC) -> ForEach (exits on the body, cast to the NPC); returns
        (each, cast). each's Completed is the caller's."""
        x, y = pos
        found = g.get_all_actors(NPC, pos=(x, y))
        c.go(found)
        each = g.foreach(ACTOR, pos=(x + 300, y))
        g.wire(found, "then", each, "Exec")
        g.wire(found, "OutActors", each, "Array", exec=False)
        cast = g.cast(NPC, pos=(x + 600, y))
        cast.pin("Object").typed("object", ir.obj_path(ACTOR), direction="EGPD_Input")
        g.wire(each, "Array Element", cast, "Object", exec=False)
        g.wire(each, "LoopBody", cast, "execute")
        c.exits = [(cast, "then")]
        return each, cast

    def destroy(cast, pos):
        d = g.call("K2_DestroyActor", ACTOR, pos=pos)
        g.wire(cast, AS_N, d, "self", exec=False)
        return c.go(d)

    def admin_event(name, pins, y):
        ce = event(name, pins, y, R.RUN_ON_SERVER)
        oc, _a, ok = h.unlocked(ce, y)
        c.exits = [(ok, "then")]
        open_save((1000, y))
        return ce, oc

    # ================================================================ OwlNpcSpawn(Index) (plain)
    y = y0
    ce = event("OwlNpcSpawn", [("Index", "int", False)], y, 0)
    idx = (ce, "Index")
    # remove the one there is
    each, cast = all_npcs((300, y))
    bm = c.branch(imath("EqualEqual_IntInt", npc_field((cast, AS_N), "NpcIdx", "int", (800, y + 300)), idx,
                        (1000, y + 300)), (1000, y))
    c.exits = [(bm, "then")]
    destroy(cast, (1300, y))
    c.exits = [(each, "Completed")]
    # placed?  Locs[Index] = "x|y|z|yaw"
    x = 1700
    loc = c.at(field("Locs", "string", (x, y + 300)), idx, "string", (x + 200, y + 300))
    bp_ = c.branch(imath("Greater_IntInt", c.fn("Len", KSTR, {"S": loc}, (x + 400, y + 450)), 0, (x + 600, y + 450)), (x + 600, y))
    c.exits = [(bp_, "then")]
    parts = c.split(loc, (x + 800, y + 600))
    num = lambda k, p: c.fn("Conv_StringToDouble", KSTR, {"InString": c.at((parts, "ReturnValue"), k, "string", p)},
                            (p[0] + 200, p[1]))
    vec = c.fn("MakeVector", KML, {"X": num(0, (x + 1000, y + 600)), "Y": num(1, (x + 1000, y + 750)),
                                   "Z": num(2, (x + 1000, y + 900))}, (x + 1400, y + 600))
    rot = c.fn("MakeRotator", KML, {"Yaw": num(3, (x + 1000, y + 1050))}, (x + 1400, y + 1050))
    xf = c.fn("MakeTransform", KML, {"Location": vec, "Rotation": rot}, (x + 1600, y + 750))
    spawn = g.node("K2Node_SpawnActorFromClass", [], base="SpawnActor", pos=(x + 1900, y))
    sc = spawn.pin("Class").typed("class", ir.obj_path(ACTOR), direction="EGPD_Input")
    sc.set("DefaultObject", '"%s"' % NPC)
    spawn.pin("ReturnValue").typed("object", ir.obj_path(NPC), direction="EGPD_Output")
    g.typed_input(spawn, "CollisionHandlingOverride", "AdjustIfPossibleButAlwaysSpawn", "byte",
                  ir.enum_path("/Script/Engine.ESpawnActorCollisionHandlingMethod"))
    g.wire(xf[0], xf[1], spawn, "SpawnTransform", exec=False)
    c.go(spawn)
    h_npc = lambda pos: h.get("SvNpcActor", "npc", pos)
    def _setv(name, t, src, pos):
        n = g.var_set(name, *T[t], pos=pos)
        h.wire_in(src, n, name, t)
        return c.go(n)

    _setv("SvNpcActor", "npc", (spawn, "ReturnValue"), (x + 2200, y))
    x += 2500
    npc_set(h_npc((x, y + 300)), "NpcIdx", "int", idx, (x, y))
    for k, (name, src) in enumerate((("NpcName", "Names"), ("NpcRole", "Roles"), ("NpcLine", "Lines"))):
        npc_set(h_npc((x + 300 + 300 * k, y + 300)), name, "string",
                c.at(field(src, "string", (x + 300 + 300 * k, y + 450)), idx, "string", (x + 400 + 300 * k, y + 600)),
                (x + 300 + 300 * k, y))
    x += 1300
    # the wares that are on, in order
    wbase = imath("Multiply_IntInt", idx, W, (x, y + 1200))
    for w in range(W):
        xx = x + 700 * w
        at = offset(wbase, w, (xx, y + 1050))
        on = c.fn("BooleanAND", KML, {
            "A": imath("EqualEqual_IntInt", c.at(field("WOn", "int", (xx, y + 300)), at, "int", (xx + 150, y + 300)), 1,
                       (xx + 300, y + 300)),
            "B": imath("Greater_IntInt", c.at(field("WIds", "int", (xx, y + 450)), at, "int", (xx + 150, y + 450)), 0,
                       (xx + 300, y + 450))}, (xx + 450, y + 350))
        bw = c.branch(on, (xx, y))
        c.exits = [(bw, "then")]
        for j, (src, dst) in enumerate((("WIds", "NpcWIds"), ("WPrice", "NpcWPrice"), ("WCur", "NpcWCur"))):
            arr_add(npc_field(h_npc((xx + 100, y + 600 + 150 * j)), dst, "int", (xx + 200, y + 600 + 150 * j), arr=True),
                    c.at(field(src, "int", (xx + 200, y + 750 + 150 * j)), at, "int", (xx + 400, y + 750 + 150 * j)),
                    "int", (xx + 200 + 150 * j, y))
        c.exits += [(bw, "else")]
    x += 700 * W
    # its gear ids, slot by slot (0 = empty): the NPC puts them on itself once its body shows (14), since
    # items added in the spawning frame are kept but never drawn
    gbase = imath("Multiply_IntInt", idx, G, (x, y + 1350))
    for k in range(G):
        xx = x + 400 * k
        gid = c.at(field("Gear", "int", (xx, y + 300)), offset(gbase, k, (xx, y + 1200)), "int", (xx + 150, y + 300))
        arr_add(npc_field(h_npc((xx, y + 600)), "NpcGear", "int", (xx + 100, y + 600), arr=True), gid, "int", (xx, y))

    # ================================================================ OwlNpcEnsure() (plain)
    y = y0 + 3000
    ce = event("OwlNpcEnsure", [], y, 0)
    open_save((300, y))
    x = 4500
    cl = g.array_fn("Array_Clear", pos=(x, y), elem_cat="int")
    g.wire(*h.get("SvNpcSeen", "int", (x, y + 300), arr=True), cl, "TargetArray", exec=False)
    c.go(cl)
    each, cast = all_npcs((x + 300, y))
    nidx = npc_field((cast, AS_N), "NpcIdx", "int", (x + 900, y + 300))
    bl = c.branch(imath("Less_IntInt", nidx, 0, (x + 1100, y + 300)), (x + 1100, y))
    c.exits = [(bl, "then")]
    destroy(cast, (x + 1400, y))
    c.exits = [(bl, "else")]
    arr_add(h.get("SvNpcSeen", "int", (x + 1400, y + 450), arr=True), nidx, "int", (x + 1400, y + 300))
    c.exits = [(each, "Completed")]
    x += 1900
    for k in range(N):
        xx = x + 600 * k
        cont = g.array_fn("Array_Contains", pos=(xx + 150, y + 300), elem_cat="int")
        g.wire(*h.get("SvNpcSeen", "int", (xx, y + 300), arr=True), cont, "TargetArray", exec=False)
        g.array_item_pin(cont, "ItemToFind", "int")
        if k:
            cont.pin("ItemToFind").literal(str(k))
        cont.pin("ReturnValue").typed("bool", direction="EGPD_Output")
        placed = imath("Greater_IntInt", c.fn("Len", KSTR, {"S": c.at(field("Locs", "string", (xx, y + 450)), k, "string",
                                                                            (xx + 150, y + 450))}, (xx + 300, y + 450)),
                       0, (xx + 450, y + 450))
        need = c.fn("BooleanAND", KML, {"A": c.fn("Not_PreBool", KML, {"A": (cont, "ReturnValue")}, (xx + 300, y + 300)),
                                        "B": placed}, (xx + 450, y + 300))
        bn = c.branch(need, (xx, y))
        c.exits = [(bn, "then")]
        spawn_call(str(k), (xx + 300, y))
        c.exits += [(bn, "else")]

    # ================================================================ admins: get
    y = y0 + 4500
    admin_event("OwlServerNpcGet", [], y)
    reply("", (3000, y))

    # ================================================================ admins: save the text + wares
    y = y0 + 6000
    ce, oc = admin_event("OwlServerNpcSave", [("Index", "int", False), ("Name", "string", False), ("Role", "string", False),
                                              ("Line", "string", False), ("WIds", "int", True), ("WPrice", "int", True),
                                              ("WCur", "int", True), ("WOn", "int", True)], y)
    k = h.clamp((ce, "Index"), (0, N - 1), (3000, y + 900))
    x = 3200
    for j, (pin, name, mx) in enumerate((("Name", "Names", D.NPC_NAME_MAX), ("Role", "Roles", D.NPC_NAME_MAX),
                                         ("Line", "Lines", D.NPC_LINE_MAX))):
        trimmed = c.fn("Left", KSTR, {"SourceString": c.fn("Trim", KSTR, {"SourceString": (ce, pin)}, (x + 300 * j, y + 750)),
                                      "Count": (str(mx), "int")}, (x + 150 + 300 * j, y + 600))
        arr_set(field(name, "string", (x + 300 * j, y + 300)), k, trimmed, "string", (x + 300 * j, y))
    x += 1000
    wbase = imath("Multiply_IntInt", k, W, (x, y + 1200))
    for w in range(W):
        xx = x + 1300 * w
        at = offset(wbase, w, (xx, y + 1050))
        for j, (pin, lim) in enumerate((("WIds", None), ("WPrice", (0, D.NPC_PRICE_MAX)),
                                        ("WCur", (0, len(D.NPC_CURRENCIES) - 1)), ("WOn", (0, 1)))):
            v = c.at((ce, pin), w, "int", (xx + 300 * j, y + 600))
            if lim:
                v = h.clamp(v, lim, (xx + 150 + 300 * j, y + 750))
            arr_set(field(pin, "int", (xx + 300 * j, y + 300)), at, v, "int", (xx + 300 * j, y))
    x += 1300 * W
    save_now((x, y))
    spawn_call(k, (x + 300, y))
    reply(h.text(["Saved ", name_or(k, (x + 600, y + 1200)), "."], (x + 1400, y + 1200)), (x + 600, y))

    # ================================================================ admins: place in front of me, my gear
    y = y0 + 8000
    ce, oc = admin_event("OwlServerNpcPlace", [("Index", "int", False)], y)
    k = h.clamp((ce, "Index"), (0, N - 1), (3000, y + 900))
    x = 3200
    pawn = c.fn("K2_GetPawn", CTRLR, {"self": (oc, "AsConan Player Controller")}, (x, y + 1200))
    pc_ = g.cast(CHAR, pos=(x, y))
    g.wire(pawn[0], pawn[1], pc_, "Object", exec=False)
    c.go(pc_)
    nochar = [(pc_, "CastFailed")]
    c.exits = [(pc_, "then")]
    me = (pc_, "AsConan Character")
    here = c.fn("K2_GetActorLocation", ACTOR, {"self": me}, (x + 300, y + 600))
    fwd = c.fn("GetActorForwardVector", ACTOR, {"self": me}, (x + 300, y + 750))
    spot = c.fn("Add_VectorVector", KML, {"A": here, "B": c.fn("Multiply_VectorFloat", KML, {
        "A": fwd, "B": ("150.0", "real")}, (x + 500, y + 750))}, (x + 700, y + 600))
    bv = g.call("BreakVector", KML, pos=(x + 900, y + 600))
    g.wire(spot[0], spot[1], bv, "InVec", exec=False)
    br = g.call("BreakRotator", KML, pos=(x + 900, y + 900))
    g.wire(*c.fn("K2_GetActorRotation", ACTOR, {"self": me}, (x + 700, y + 900)), br, "InRot", exec=False)
    yaw = c.fn("Add_DoubleDouble", KML, {"A": (br, "Yaw"), "B": ("180.0", "real")}, (x + 1100, y + 900))
    s = lambda src, p: c.fn("Conv_DoubleToString", KSTR, {"InDouble": src}, p)
    loc = c.concat([s((bv, "X"), (x + 1300, y + 600)), "|", s((bv, "Y"), (x + 1300, y + 750)), "|",
                    s((bv, "Z"), (x + 1300, y + 900)), "|", s(yaw, (x + 1300, y + 1050))], (x + 1500, y + 600))
    arr_set(field("Locs", "string", (x + 1200, y + 300)), k, loc, "string", (x + 1500, y))
    arr_set(field("Names", "string", (x + 1800, y + 300)), k, name_or(k, (x + 1800, y + 1200)), "string", (x + 1800, y))
    x += 2200
    inv = g.call("GetInventoryByType", INV, pos=(x, y + 1500))
    g.wire(me[0], me[1], inv, "owner", exec=False)
    g.typed_input(inv, "inventoryType", "Equipment", "byte", ir.enum_path(CS + "EInventoryType"))
    gbase = imath("Multiply_IntInt", k, G, (x, y + 1350))
    for j in range(G):
        xx = x + 600 * j
        it = c.fn("GetItem", INV, {"self": (inv, "ReturnValue")}, (xx, y + 600))
        if j:
            g.typed_input(it[0], "index", str(j), "int")
        bi = c.branch(c.fn("IsValid", KSL, {"Object": it}, (xx + 200, y + 450)), (xx, y))
        at = offset(gbase, j, (xx, y + 1200))
        tid = g.var_get("TemplateID", "int", parent=ITEM, pos=(xx + 200, y + 750))
        g.wire(it[0], it[1], tid, "self", exec=False)
        c.exits = [(bi, "then")]
        arr_set(field("Gear", "int", (xx + 200, y + 900)), at, (tid, "TemplateID"), "int", (xx + 300, y))
        worn = c.exits
        c.exits = [(bi, "else")]
        arr_set(field("Gear", "int", (xx + 200, y + 1050)), at, "0", "int", (xx + 300, y + 300))
        c.exits += worn
    x += 600 * G
    save_now((x, y))
    spawn_call(k, (x + 300, y))
    reply(h.text(["Placed ", name_or(k, (x + 600, y + 1200)), " in front of you."], (x + 1400, y + 1200)), (x + 600, y))
    c.exits = nochar
    reply("You have no character right now.", (x + 600, y + 1800))

    # ================================================================ admins: delete
    y = y0 + 10000
    ce, oc = admin_event("OwlServerNpcDelete", [("Index", "int", False)], y)
    k = h.clamp((ce, "Index"), (0, N - 1), (3000, y + 900))
    x = 3200
    for j, name in enumerate(SAVE_STRS):
        arr_set(field(name, "string", (x + 300 * j, y + 300)), k, "", "string", (x + 300 * j, y))
    x += 1300
    save_now((x, y))
    spawn_call(k, (x + 300, y))
    reply("Deleted.", (x + 600, y))

    # ================================================================ any player: buy
    y = y0 + 12000
    ce = event("OwlServerNpcBuy", [("Npc", "actor", False), ("Entry", "int", False)], y, R.RUN_ON_SERVER)

    def answer(msg, pos):
        n = h.call_self("OwlClientNpcBuy", [("Msg", "string", False)], pos)
        h.wire_in(msg, n, "Msg", "string")
        c.go(n)

    def refuse(cond, msg, pos):
        b = c.branch(cond, pos)
        c.exits = [(b, "else")]
        answer(msg, (pos[0] + 300, pos[1] + 900))
        c.exits = [(b, "then")]
        return b

    oc = R.owner_pc(ce, "then", (300, y))
    c.exits = [(oc, "then")]
    x = 600
    pawn = c.fn("K2_GetPawn", CTRLR, {"self": (oc, "AsConan Player Controller")}, (x, y + 300))
    pc_ = g.cast(CHAR, pos=(x, y))
    g.wire(pawn[0], pawn[1], pc_, "Object", exec=False)
    c.go(pc_)
    me = (pc_, "AsConan Character")
    nc = g.cast(NPC, pos=(x + 300, y))
    nc.pin("Object").typed("object", ir.obj_path(ACTOR), direction="EGPD_Input")
    g.wire(ce, "Npc", nc, "Object", exec=False)
    c.go(nc)
    npc = (nc, AS_N)
    c.exits = [(nc, "CastFailed")]
    answer("That merchant is gone.", (x + 600, y + 900))
    c.exits = [(nc, "then")]
    x += 700
    nname = npc_field(npc, "NpcName", "string", (x, y + 600))
    refuse(c.fn("LessEqual_DoubleDouble", KML, {"A": c.fn("GetDistanceTo", ACTOR, {"self": me, "OtherActor": npc}, (x, y + 300)),
                                                "B": ("%d.0" % D.NPC_TALK_DIST, "real")}, (x + 200, y + 300)),
           h.text(["Walk closer to ", nname, " to trade."], (x + 300, y + 1200)), (x + 300, y))
    x += 700
    wids = npc_field(npc, "NpcWIds", "int", (x, y + 600), arr=True)
    valid = c.fn("BooleanAND", KML, {"A": imath("GreaterEqual_IntInt", (ce, "Entry"), 0, (x + 200, y + 300)),
                                     "B": imath("Less_IntInt", (ce, "Entry"), (g.array_len(wids[0], wids[1], (x, y + 450),
                                                                                           elem_cat="int"), "ReturnValue"),
                                                (x + 200, y + 450))}, (x + 400, y + 350))
    refuse(valid, "That ware isn't for sale any more.", (x + 500, y))
    x += 800
    item = c.at(wids, (ce, "Entry"), "int", (x, y + 600))
    price = c.at(npc_field(npc, "NpcWPrice", "int", (x, y + 750), arr=True), (ce, "Entry"), "int", (x + 200, y + 750))
    cur = c.at(npc_field(npc, "NpcWCur", "int", (x, y + 900), arr=True), (ce, "Entry"), "int", (x + 200, y + 900))
    gold = imath("EqualEqual_IntInt", cur, 0, (x + 400, y + 900))
    cur_id = c.fn("SelectInt", KML, {"A": (str(D.NPC_CURRENCIES[0][1]), "int"), "B": (str(D.NPC_CURRENCIES[1][1]), "int"),
                                     "bPickA": gold}, (x + 600, y + 900))
    cur_name = c.fn("SelectString", KML, {"A": (D.NPC_CURRENCIES[0][0] + "s", "string"),
                                          "B": (D.NPC_CURRENCIES[1][0] + "s", "string"), "bPickA": gold}, (x + 600, y + 1050))
    bag = g.call("GetInventoryByType", INV, pos=(x, y + 1200))
    g.wire(me[0], me[1], bag, "owner", exec=False)
    g.typed_input(bag, "inventoryType", "Backpack", "byte", ir.enum_path(CS + "EInventoryType"))
    bagv = (bag, "ReturnValue")
    refuse(imath("Greater_IntInt", c.fn("GetFreeSpaceCount", INV, {"self": bagv}, (x + 200, y + 300)), 0, (x + 400, y + 300)),
           "Your backpack is full.", (x + 500, y))
    x += 800
    have = c.fn("GetNumberOfItemsByTemplate", INV, {"self": bagv, "templateID": cur_id}, (x, y + 300))
    short = h.text(["You need ", price + ("int",), " ", cur_name, ". You have ", have + ("int",), "."], (x + 200, y + 1200))
    refuse(imath("GreaterEqual_IntInt", have, price, (x + 200, y + 300)), short, (x + 300, y))
    x += 700
    pay = g.call("ValidatedDeleteItemsByTemplate", INV, pos=(x, y))
    g.wire(bagv[0], bagv[1], pay, "self", exec=False)
    g.wire(cur_id[0], cur_id[1], pay, "templateID", exec=False)
    g.typed_input(pay, "context", MOD.CE_CONTEXT, "name")
    g.wire(price[0], price[1], pay, "quantity", exec=False)
    c.go(pay)
    refuse((pay, "ReturnValue"), short, (x + 300, y))
    x += 700
    ad = g.call("AddItemTemplate", INV, pos=(x, y))
    g.wire(bagv[0], bagv[1], ad, "self", exec=False)
    g.wire(item[0], item[1], ad, "templateID", exec=False)
    g.typed_input(ad, "index", "-1", "int")
    g.typed_input(ad, "context", MOD.CE_CONTEXT, "name")
    g.typed_input(ad, "quantity", "1", "int")
    c.go(ad)
    answer(h.text(["Bought for ", price + ("int",), " ", cur_name, "."], (x + 300, y + 600)), (x + 300, y))
    c.exits = [(pc_, "CastFailed")]
    answer("You have no character right now.", (x + 300, y + 1500))

    # ================================================================ the owner's copies
    h.client_event("OwlClientNpc", CLIENT_PINS, CLIENT_MINE, "NpcVer", y0 + 15000)
    h.client_event("OwlClientNpcBuy", [("Msg", "string", False)], ["NpcBuyMsgC"], "NpcBuyVer", y0 + 15500)
    return flags


def tick(R, prevs, y0):
    """Server, entered from prevs: the first time, OwlNpcEnsure. Returns the exits."""
    g = R.g
    h = helpers(R, {})
    c = _Ctx(g, None, None, None)
    c.exits = list(prevs)
    b = c.branch(h.get("SvNpcDone", "bool", (0, y0 + 300)), (200, y0))
    done = [(b, "then")]
    c.exits = [(b, "else")]
    n = g.var_set("SvNpcDone", "bool", pos=(500, y0))
    n.pin("SvNpcDone").literal("true")
    c.go(n)
    c.go(h.call_self("OwlNpcEnsure", [], (800, y0)))
    return done + c.exits
