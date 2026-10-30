"""Cheats, the server side: the relay's (10) cheat events and the tick that applies them. Each
admin's cheats are their own (on their relay, not the server-wide settings), work only on their own
character, and only while they are in admin mode.

    OwlServerChSet(Which, Value)  Which 0..N-1: menu_defs.CHEATS[Which] on (Value > 0) or off;
                                  Which = N: the move speed, x Value (1..CH_SPEED_MAX, 1 = off)
    OwlServerChGet()              just the current state
    each -> OwlClientCh(On, Speed, Msg)    the owner's copy: ChOnC, ChSpeedC, ChMsg, ChVer + 1

Every change is a line in the admin's own admin log (their OwlCe_<net id> save, made if missing;
Characters, Log shows it).

Server tick (tick(), after the relay's TmPawn update): while any cheat is on and the admin is no
longer in admin mode (logged out or locked), all of them turn off. Then, when the cheats or the
character changed (ChKey / ChPawn), the character gets them: bNoDamage (god mode; not saved, the
game's own temporary invulnerability flag), HungerEnabled / ThirstEnabled off (no hunger or thirst),
MovementSpeedOverride = RunSpeed x the speed (-1 = the game's own speed), and the game's ignore
building costs toggle (ShouldIgnoreBuildingCosts / ToggleIgnoreBuildingCosts: free building).
Nothing is written to a character that never had a cheat on (ChWasOn), so the game's own values
stay untouched. Infinite stamina tops stamina up to its maximum on every tick (there is no switch).
A new character (after dying) gets the cheats again; they stay until the admin turns them off,
logs out of admin mode, or leaves (the relay goes).
The owner's client also sets MovementSpeedOverride on its own character (client_tick), so moving
faster isn't corrected back by the client's own movement.
"""
from bpkit import ir
import menu_defs as D
from ce_server import helpers, T, KML, KSTR, GS, CHAR, CPC, PSTATE
from ce_panel import _Ctx

N = len(D.CHEATS)
SPEED = N                          # OwlServerChSet's Which for the move speed
GOD, NEEDS, STAM, FREE = (k for k, (key, _l, _d) in enumerate(D.CHEATS) if key in ("god", "needs", "stam", "free"))
PAWN = "/Script/Engine.Pawn"
CTRL = "/Script/Engine.Controller"
STATE_PINS = [("On", "int", True), ("Speed", "int", False), ("Msg", "string", False)]
SET_PINS = [("Which", "int", False), ("Value", "int", False)]
LOCKED = "Admin mode was locked, so your cheats were turned off."


def variables(unreal, bel, ce_save_cls):
    """(name, type) for the relay: Ch*C / ChMsg / ChVer = the owner's copy, ChSpd* = what the
    owner's client last set, the rest the server's."""
    i, s, b = (bel.get_basic_type_by_name(t) for t in ("int", "string", "bool"))
    ints, pawn = bel.get_array_type(i), bel.get_object_reference_type(unreal.Pawn.static_class())
    return [("ChOnC", ints), ("ChSpeedC", i), ("ChMsg", s), ("ChVer", i), ("ChSpdPawn", pawn), ("ChSpdKey", i),
            ("ChOn", ints), ("ChSpeed", i), ("ChNames", bel.get_array_type(s)), ("ChPawn", pawn), ("ChKey", s),
            ("ChWasOn", b), ("SvChSave", bel.get_object_reference_type(ce_save_cls)), ("SvChSlot", s)]


def defaults(cdo):
    cdo.set_editor_property("ChOn", [0] * N)
    cdo.set_editor_property("ChSpeed", 1)
    cdo.set_editor_property("ChSpdKey", 1)
    cdo.set_editor_property("ChNames", [label for _k, label, _d in D.CHEATS] + ["Move speed"])


def _ctx(R):
    c = _Ctx(R.g, None, None, None)
    lit = lambda v: v if isinstance(v, tuple) else (str(v), "int")
    imath = lambda fn, a, b, pos: c.fn(fn, KML, {"A": lit(a), "B": lit(b)}, pos)
    return c, imath


def _on(c, imath, k, pos):
    """ChOn[k] > 0 (pure)."""
    return imath("Greater_IntInt", c.at(c.arr("ChOn", "int", pos), k, "int", (pos[0] + 200, pos[1])), 0,
                 (pos[0] + 400, pos[1]))


def _any(c, imath, pos):
    """Any cheat on (pure): the ChOn sum > 0, or ChSpeed > 1."""
    x, y = pos
    total = c.at(c.arr("ChOn", "int", (x, y)), 0, "int", (x + 200, y))
    for k in range(1, N):
        total = imath("Add_IntInt", total, c.at(c.arr("ChOn", "int", (x, y + 150 * k)), k, "int", (x + 200, y + 150 * k)),
                      (x + 400 + 150 * k, y))
    return c.fn("BooleanOR", KML, {"A": imath("Greater_IntInt", total, 0, (x + 1200, y)),
                                   "B": imath("Greater_IntInt", c.var("ChSpeed", "int", (x + 1000, y + 300)), 1,
                                              (x + 1200, y + 300))}, (x + 1400, y))


def admin_log(R, h, prev, oc, parts, pos):
    """SvLine = parts (time | admin | ...), added to the admin's own OwlCe save (made if missing,
    at most CE_LOG_MAX lines); oc: the admin's controller cast. Uses the relay's SvChSlot /
    SvChSave (cheats_server.variables), so any relay event can log with it. Returns the exec out."""
    g, MOD = R.g, R.MOD
    CE_SG = MOD.full(R.PKG, MOD.CE_SAVEGAME) + "_C"
    T.setdefault("cesave", ("object", ir.obj_path(CE_SG)))
    x, y = pos
    p = h.set_line(prev, oc, parts, (x, y))
    slot = R.save_slot(oc, (x + 1500, y + 900), prefix=MOD.CE_SLOT_PREFIX)
    p = h.setv(p, "SvChSlot", "string", (slot, "ReturnValue"), (x + 1700, y))
    sc, missing = h.load([p], h.get("SvChSlot", "string", (x + 1900, y + 900)), CE_SG, (x + 2000, y))
    have = h.setv((sc, "then"), "SvChSave", "cesave", (sc, h.save_as(CE_SG)), (x + 2900, y))
    crt = g.call("CreateSaveGameObject", GS, pos=(x + 2600, y + 600))
    cp = crt.pin("SaveGameClass").typed("class", ir.obj_path("/Script/Engine.SaveGame"), direction="EGPD_Input")
    cp.set("PinType.bIsUObjectWrapper", "True")
    cp.set("DefaultObject", '"%s"' % CE_SG)
    crt.pin("ReturnValue").typed("object", ir.obj_path(CE_SG), direction="EGPD_Output")
    for e, ep in missing:
        g.wire(e, ep, crt, "execute")
    made = h.setv((crt, "then"), "SvChSave", "cesave", (crt, "ReturnValue"), (x + 2900, y + 600))
    save = lambda pos: h.get("SvChSave", "cesave", pos)

    def log_arr(pos):
        lg = g.var_get("Log", "string", parent=CE_SG, pos=pos)
        lg.pin("Log").set("PinType.ContainerType", "Array")
        g.wire(*save((pos[0] - 200, pos[1])), lg, "self", exec=False)
        return lg

    add = g.array_fn("Array_Add", pos=(x + 3200, y), elem_cat="string")
    g.array_item_pin(add, "NewItem", "string")
    g.wire(log_arr((x + 3200, y + 300)), "Log", add, "TargetArray", exec=False)
    g.wire(*h.get("SvLine", "string", (x + 3200, y + 450)), add, "NewItem", exec=False)
    for e in (have, made):
        g.wire(e[0], e[1], add, "execute")
    over = h.op("Greater_IntInt", (g.array_len(log_arr((x + 3500, y + 600)), "Log", (x + 3700, y + 600),
                                               elem_cat="string"), "ReturnValue"), str(MOD.CE_LOG_MAX),
                (x + 3900, y + 600))
    bo = h.branch((add, "then"), over, (x + 3500, y))
    rm = g.array_fn("Array_Remove", pos=(x + 3800, y), elem_cat="string")
    rm.pin("IndexToRemove").typed("int", direction="EGPD_Input").literal("0")
    g.wire(log_arr((x + 3800, y + 300)), "Log", rm, "TargetArray", exec=False)
    g.wire(bo, "then", rm, "execute")
    sav = g.call("SaveGameToSlot", GS, pos=(x + 4100, y))
    g.wire(*save((x + 3900, y + 300)), sav, "SaveGameObject", exec=False)
    g.wire(*h.get("SvChSlot", "string", (x + 3900, y + 450)), sav, "SlotName", exec=False)
    g.typed_input(sav, "UserIndex", "0", "int")
    for e, ep in ((rm, "then"), (bo, "else")):
        g.wire(e, ep, sav, "execute")
    return (sav, "then")


def build(R, y0):
    """Add the cheat events to R.g from y0 down (R as for ce_server.build). Returns {event: net flags}."""
    g, MOD = R.g, R.MOD
    CE_SG = MOD.full(R.PKG, MOD.CE_SAVEGAME) + "_C"
    T.setdefault("cesave", ("object", ir.obj_path(CE_SG)))
    flags = {}
    h = helpers(R, flags)
    c, imath = _ctx(R)

    def reply(prevs, msg, pos):
        """OwlClientCh(ChOn, ChSpeed, msg)."""
        x, y = pos
        call = h.call_self("OwlClientCh", STATE_PINS, pos)
        g.wire(*h.get("ChOn", "int", (x - 200, y + 300), arr=True), call, "On", exec=False)
        g.wire(*h.get("ChSpeed", "int", (x - 200, y + 450)), call, "Speed", exec=False)
        h.wire_in(msg, call, "Msg", "string")
        for e, ep in prevs:
            g.wire(e, ep, call, "execute")
        return call

    log = lambda prev, oc, parts, pos: admin_log(R, h, prev, oc, parts, pos)

    # ---- set one cheat
    y = y0
    ce = h.event("OwlServerChSet", SET_PINS, y, R.RUN_ON_SERVER)
    oc, _a, ok = h.unlocked(ce, y)
    which = (ce, "Which")
    is_speed = h.op("EqualEqual_IntInt", which, str(SPEED), (900, y + 300))
    bs = h.branch((ok, "then"), is_speed, (1000, y))
    sp = h.setv((bs, "then"), "ChSpeed", "int", h.clamp((ce, "Value"), (1, D.CH_SPEED_MAX), (1100, y + 600)), (1300, y))
    st = g.array_fn("Array_Set", pos=(1300, y + 900), elem_cat="int")
    g.wire(*h.get("ChOn", "int", (1100, y + 1200), arr=True), st, "TargetArray", exec=False)
    st.pin("Index").typed("int", direction="EGPD_Input")
    g.wire(*h.clamp(which, (0, N - 1), (1100, y + 1350)), st, "Index", exec=False)
    g.array_item_pin(st, "Item", "int")
    on = h.op("Greater_IntInt", (ce, "Value"), "0", (900, y + 1500))
    sel = g.call("SelectInt", KML, pos=(1100, y + 1500))
    g.typed_input(sel, "A", "1", "int")
    g.typed_input(sel, "B", "0", "int")
    g.wire(on[0], on[1], sel, "bPickA", exec=False)
    g.wire(sel, "ReturnValue", st, "Item", exec=False)
    g.wire(bs, "else", st, "execute")
    # the line and the answer: "<name> on/off" or "Move speed x<n>"
    name = c.at(c.arr("ChNames", "string", (1600, y + 600)), h.clamp(which, (0, SPEED), (1600, y + 750)), "string",
                (1800, y + 600))
    state = c.fn("SelectString", KML, {
        "A": h.text([" x", (h.get("ChSpeed", "int", (1700, y + 1050))[0], "ChSpeed", "int")], (1800, y + 1050)),
        "B": c.fn("SelectString", KML, {"A": (" on", "string"), "B": (" off", "string"), "bPickA": on}, (1800, y + 1200)),
        "bPickA": is_speed}, (2400, y + 1050))
    join = g.branch(pos=(1500, y))                      # both ways on: a branch that is always true
    g.typed_input(join, "Condition", "true", "bool")
    for e, ep in (sp, (st, "then")):
        g.wire(e, ep, join, "execute")
    p_line = log((join, "then"), oc, ["Cheat: ", name, state], (1700, y))
    reply([p_line], h.text([name, state, "."], (2600, y + 600)), (6200, y))

    # ---- the state, nothing changed
    y = y0 + 2500
    ce = h.event("OwlServerChGet", [], y, R.RUN_ON_SERVER)
    _oc, _a, ok = h.unlocked(ce, y)
    reply([(ok, "then")], "", (1000, y))

    h.client_event("OwlClientCh", STATE_PINS, ["ChOnC", "ChSpeedC", "ChMsg"], "ChVer", y0 + 3500)
    return flags


def _speed(c, imath, cast, speed, pos):
    """cast.MovementSpeedOverride = RunSpeed x speed, or -1 (the game's own) at x1; then
    UpdateMaxMovementSpeed. speed: (node, pin) int."""
    g, (x, y) = c.g, pos
    AS = "AsConan Character"
    run = g.var_get("RunSpeed", "int", parent=CHAR, pos=(x, y + 300))
    g.wire(cast, AS, run, "self", exec=False)
    fast = c.fn("Conv_IntToDouble", KML, {"InInt": imath("Multiply_IntInt", (run, "RunSpeed"), speed, (x + 200, y + 300))},
                (x + 400, y + 300))
    val = c.fn("SelectFloat", KML, {"A": fast, "B": ("-1.0", "real"),
                                    "bPickA": imath("Greater_IntInt", speed, 1, (x + 400, y + 450))}, (x + 600, y + 300))
    st = g.var_set("MovementSpeedOverride", "real", parent=CHAR, pos=(x + 800, y))
    st.pin("MovementSpeedOverride").set("PinType.PinSubCategory", '"float"')
    g.wire(cast, AS, st, "self", exec=False)
    g.wire(val[0], val[1], st, "MovementSpeedOverride", exec=False)
    c.go(st)
    up = g.call("UpdateMaxMovementSpeed", CHAR, pos=(x + 1100, y))
    g.wire(cast, AS, up, "self", exec=False)
    c.go(up)


def _set_char(c, cast, var, src, pos):
    n = c.g.var_set(var, "bool", parent=CHAR, pos=pos)
    c.g.wire(cast, "AsConan Character", n, "self", exec=False)
    c.g.wire(src[0], src[1], n, var, exec=False)
    c.go(n)


def tick(R, prevs, ctl, y0):
    """Server, every tick, entered from prevs (see the docstring). ctl: the owner as a Controller
    (node, pin). Returns the exits."""
    g, MOD = R.g, R.MOD
    c, imath = _ctx(R)
    h = helpers(R, {})
    AS = "AsConan Character"
    c.exits = list(prevs)
    x, y = 0, y0
    # any on while the owner is no longer in admin mode: all off, and tell them
    b_any = c.branch(_any(c, imath, (x, y + 300)), (x + 1600, y))
    after = [(b_any, "else")]
    gac = R.Auth(g, R.CTRL_CLS, R.SG_CLS, MOD.SAVE_SLOT, None).controller(b_any, "then", (x + 1900, y))
    arr = g.array_var("UnlockedPlayers", pos=(x + 2100, y + 300), elem_cat="object", elem_sub=ir.obj_path(PSTATE),
                      parent=R.CTRL_CLS)
    g.wire(gac, "ReturnValue", arr, "self", exec=False)
    ps = g.var_get("PlayerState", "object", ir.obj_path(PSTATE), parent=CTRL, pos=(x + 2100, y + 450))
    g.wire(ctl[0], ctl[1], ps, "self", exec=False)
    has = g.array_fn("Array_Contains", pos=(x + 2300, y + 300), elem_cat="object", elem_sub=ir.obj_path(PSTATE))
    g.array_item_pin(has, "ItemToFind", "object", ir.obj_path(PSTATE))
    g.wire(arr, "UnlockedPlayers", has, "TargetArray", exec=False)
    g.wire(ps, "PlayerState", has, "ItemToFind", exec=False)
    c.exits = [(gac, "then")]
    b_in = c.branch((has, "ReturnValue"), (x + 2400, y))
    after.append((b_in, "then"))
    c.exits = [(b_in, "else")]
    for k in range(N):
        st = g.array_fn("Array_Set", pos=(x + 2700 + 300 * k, y + 600), elem_cat="int")
        g.wire(*c.arr("ChOn", "int", (x + 2600 + 300 * k, y + 900)), st, "TargetArray", exec=False)
        st.pin("Index").typed("int", direction="EGPD_Input").literal(str(k))
        g.array_item_pin(st, "Item", "int")
        st.pin("Item").literal("0")
        c.go(st)
    c.set_var("ChSpeed", "int", "1", (x + 2700 + 300 * N, y + 600))
    call = h.call_self("OwlClientCh", STATE_PINS, (x + 3300 + 300 * N, y + 600))
    g.wire(*h.get("ChOn", "int", (x + 3100 + 300 * N, y + 900), arr=True), call, "On", exec=False)
    g.wire(*h.get("ChSpeed", "int", (x + 3100 + 300 * N, y + 1050)), call, "Speed", exec=False)
    h.wire_in(LOCKED, call, "Msg", "string")
    c.go(call)
    cpc = g.cast(CPC, pos=(x + 3600 + 300 * N, y + 600))           # and a line in their admin log
    g.wire(ctl[0], ctl[1], cpc, "Object", exec=False)
    c.go(cpc)
    logged = admin_log(R, h, (cpc, "then"), cpc, ["Cheats turned off: admin mode locked"], (x + 3900 + 300 * N, y + 600))
    c.exits = after + [logged, (cpc, "CastFailed")]
    # the owner's character
    x = 4800 + 300 * N
    pawn = g.call("K2_GetPawn", CTRL, pos=(x, y + 300))
    g.wire(ctl[0], ctl[1], pawn, "self", exec=False)
    cast = g.cast(CHAR, pos=(x + 250, y))
    g.wire(pawn, "ReturnValue", cast, "Object", exec=False)
    c.go(cast)
    out = [(cast, "CastFailed")]
    c.exits = [(cast, "then")]
    x += 600
    key = c.concat([c.int_text(c.at(c.arr("ChOn", "int", (x, y + 600 + 150 * k)), k, "int", (x + 200, y + 600 + 150 * k)),
                               (x + 400, y + 600 + 150 * k)) for k in range(N)]
                   + [c.int_text(c.var("ChSpeed", "int", (x, y + 600 + 150 * N)), (x + 400, y + 600 + 150 * N))],
                   (x + 700, y + 600))
    me = lambda pos: c.var("ChPawn", "object", pos, sub=ir.obj_path(PAWN))
    changed = c.fn("BooleanOR", KML, {
        "A": c.fn("NotEqual_ObjectObject", KML, {"A": (cast, AS), "B": me((x + 1400, y + 300))}, (x + 1600, y + 300)),
        "B": c.fn("NotEqual_StrStr", KSTR, {"A": key, "B": c.var("ChKey", "string", (x + 1400, y + 450))},
                  (x + 1600, y + 450))}, (x + 1800, y + 300))
    bc = c.branch(changed, (x + 1900, y))
    skip = [(bc, "else")]
    c.exits = [(bc, "then")]
    same = c.fn("EqualEqual_ObjectObject", KML, {"A": (cast, AS), "B": me((x + 2000, y + 600))}, (x + 2200, y + 600))
    write = c.fn("BooleanOR", KML, {"A": _any(c, imath, (x + 2000, y + 900)),
                                    "B": c.fn("BooleanAND", KML, {"A": c.var("ChWasOn", "bool", (x + 2200, y + 450)),
                                                                  "B": same}, (x + 2400, y + 450))}, (x + 2600, y + 300))
    bw = c.branch(write, (x + 2700, y))
    nowrite = [(bw, "else")]
    c.exits = [(bw, "then")]
    x += 3000
    _set_char(c, cast, "bNoDamage", _on(c, imath, GOD, (x, y + 300)), (x + 400, y))
    for k, var in enumerate(("HungerEnabled", "ThirstEnabled")):
        _set_char(c, cast, var, c.fn("Not_PreBool", KML, {"A": _on(c, imath, NEEDS, (x + 400 + 300 * k, y + 600))},
                                     (x + 800 + 300 * k, y + 600)), (x + 700 + 300 * k, y))
    x += 1300
    _speed(c, imath, cast, c.var("ChSpeed", "int", (x, y + 600)), (x, y))
    x += 1500
    should = c.fn("ShouldIgnoreBuildingCosts", CHAR, {"self": (cast, AS)}, (x, y + 300))
    bf = c.branch(c.fn("NotEqual_BoolBool", KML, {"A": should, "B": _on(c, imath, FREE, (x, y + 450))}, (x + 300, y + 300)),
                  (x + 300, y))
    c.exits = [(bf, "then")]
    tg = g.call("ToggleIgnoreBuildingCosts", CHAR, pos=(x + 600, y))
    g.wire(cast, AS, tg, "self", exec=False)
    c.go(tg)
    c.exits += [(bf, "else")] + nowrite
    x += 1000
    c.set_var("ChPawn", "object", (cast, AS), (x, y), sub=ir.obj_path(PAWN))
    c.set_var("ChKey", "string", key, (x + 300, y))
    c.set_var("ChWasOn", "bool", _any(c, imath, (x + 300, y + 600)), (x + 600, y))
    c.exits += skip
    # infinite stamina: top it up
    x += 2200
    bs = c.branch(_on(c, imath, STAM, (x, y + 300)), (x + 300, y))
    out += [(bs, "else")]
    c.exits = [(bs, "then")]
    need = imath("Subtract_IntInt", c.fn("K2_GetStaminaMax", CHAR, {"self": (cast, AS)}, (x + 300, y + 600)),
                 c.fn("K2_GetStaminaCurrent", CHAR, {"self": (cast, AS)}, (x + 300, y + 750), out="StaminaCurrent"),
                 (x + 600, y + 600))
    bn = c.branch(imath("Greater_IntInt", need, 0, (x + 800, y + 450)), (x + 700, y))
    out += [(bn, "else")]
    c.exits = [(bn, "then")]
    adj = g.call("AdjustStaminaCurrent", CHAR, pos=(x + 1000, y))
    g.wire(cast, AS, adj, "self", exec=False)
    g.wire(need[0], need[1], adj, "StaminaChange", exec=False)
    c.go(adj)
    return c.exits + out


def client_tick(R, prevs, y0):
    """The owner's client, every tick, entered from prevs: MovementSpeedOverride on its own
    character (TmPawn) from ChSpeedC, when it or the character changed. Returns the exits."""
    g = R.g
    c, imath = _ctx(R)
    AS = "AsConan Character"
    c.exits = list(prevs)
    x, y = 0, y0
    cast = g.cast(CHAR, pos=(x + 300, y))
    g.wire(*c.var("TmPawn", "object", (x, y + 300), sub=ir.obj_path(PAWN)), cast, "Object", exec=False)
    c.go(cast)
    out = [(cast, "CastFailed")]
    c.exits = [(cast, "then")]
    spd = lambda pos: c.var("ChSpeedC", "int", pos)
    was = lambda pos: c.var("ChSpdKey", "int", pos)
    mine = lambda pos: c.var("ChSpdPawn", "object", pos, sub=ir.obj_path(PAWN))
    changed = c.fn("BooleanOR", KML, {
        "A": c.fn("NotEqual_ObjectObject", KML, {"A": (cast, AS), "B": mine((x + 500, y + 300))}, (x + 700, y + 300)),
        "B": imath("NotEqual_IntInt", spd((x + 500, y + 450)), was((x + 500, y + 600)), (x + 700, y + 450))},
        (x + 900, y + 300))
    bc = c.branch(changed, (x + 900, y))
    out += [(bc, "else")]
    c.exits = [(bc, "then")]
    write = c.fn("BooleanOR", KML, {
        "A": imath("Greater_IntInt", spd((x + 1000, y + 600)), 1, (x + 1200, y + 600)),
        "B": c.fn("BooleanAND", KML, {
            "A": imath("Greater_IntInt", was((x + 1000, y + 750)), 1, (x + 1200, y + 750)),
            "B": c.fn("EqualEqual_ObjectObject", KML, {"A": (cast, AS), "B": mine((x + 1000, y + 900))}, (x + 1200, y + 900))},
            (x + 1400, y + 750))}, (x + 1600, y + 600))
    bw = c.branch(write, (x + 1300, y))
    c.exits = [(bw, "then")]
    _speed(c, imath, cast, spd((x + 1500, y + 600)), (x + 1500, y))
    c.exits += [(bw, "else")]
    c.set_var("ChSpdPawn", "object", (cast, AS), (x + 2900, y), sub=ir.obj_path(PAWN))
    c.set_var("ChSpdKey", "int", spd((x + 3000, y + 300)), (x + 3200, y))
    return c.exits + out
