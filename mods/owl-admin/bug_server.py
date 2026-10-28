"""Bug reports, the server side: the relay's (10) bug events. A player's report goes up through
their own relay; the admin menu's Bug Reports tab reads and marks them through the admin's.

    OwlServerBugReport(Kind, Title, Text, Where)  -> OwlClientBugSent(Ok, Msg)   any player
    OwlServerBugList()                            -> OwlClientBugList(Lines, Done)  admins (unlocked)
    OwlServerBugDone(Line, Done)                  mark one report done (1) or open (0), then list

A report is one line in BP_OwlBugSave.Reports (slot OwlBugReports, oldest first, the newest
BUG_MAX kept), Done holding 1/0 for each:
    "<date time>|<character>|<server>|<kind>|<title>|<where>|<account>|<text>"
The server stamps the time, the character's name (else the player's), the account (the
player's name: in Play-in-Editor, the net id) and the server's name (GetServerName), so a client
can't fake who sent it. Kind / title / where / text come from the client: "|" in them becomes
"/", and title and text are cut to menu_defs.BUG_TITLE_MAX / BUG_TEXT_MAX. A player can send
one report every BUG_WAIT seconds (SvBugAt, on their relay). A report is marked by its whole
line, not its position, so one arriving meanwhile can't shift the mark onto another.
"""
from bpkit import ir
import menu_defs as D
from ce_server import helpers, KML, KSTR, KSL, GS, PSTATE

DW = "/Script/UE4Dreamworld.DreamworldBlueprints"
SENT_PINS = [("Ok", "bool", False), ("Msg", "string", False)]
LIST_PINS = [("Lines", "string", True), ("Done", "int", True)]
FIELDS = ["Kind", "Title", "Where", "Text"]


def variables(unreal, bel, bug_save_cls):
    """(name, type) for the relay: Bug* = the owner's copy the menus read, SvBug* = the server's."""
    i, s, b = (bel.get_basic_type_by_name(t) for t in ("int", "string", "bool"))
    arr = bel.get_array_type
    return [("BugOk", b), ("BugMsg", s), ("BugSentVer", i), ("BugLines", arr(s)), ("BugDone", arr(i)),
            ("BugVer", i), ("SvBugAt", bel.get_basic_type_by_name("real")),
            ("SvBugSave", bel.get_object_reference_type(bug_save_cls)), ("SvBugR", arr(s)), ("SvBugD", arr(i))]


def build(R, y0):
    """Add the bug events to R.g from y0 down (R as for ce_server.build). Returns {event: net flags}."""
    g, MOD = R.g, R.MOD
    SG = MOD.full(R.PKG, MOD.BUG_SAVEGAME) + "_C"
    flags = {}
    h = helpers(R, flags)
    as_sg = h.save_as(SG)

    def save_ref(pos):
        return g.var_get("SvBugSave", "object", ir.obj_path(SG), pos=pos)

    def save_arr(name, t, pos):
        """SvBugSave.<name> (an array)."""
        n = h.get(name, t, pos, arr=True, parent=SG)
        g.wire(save_ref((pos[0] - 200, pos[1])), "SvBugSave", n[0], "self", exec=False)
        return n

    def arr_add(prev, name, t, item, pos):
        n = g.array_fn("Array_Add", pos=pos, elem_cat=t)
        g.array_item_pin(n, "NewItem", t)
        n.pin("ReturnValue").typed("int", direction="EGPD_Output")
        a = save_arr(name, t, (pos[0], pos[1] + 250))
        g.wire(a[0], a[1], n, "TargetArray", exec=False)
        h.wire_in(item, n, "NewItem", t)
        g.wire(prev[0], prev[1], n, "execute")
        return (n, "then")

    def slot_pin(pos):
        n = g.call("Concat_StrStr", KSTR, pos=pos)              # the slot name as a pin
        h.wire_in(MOD.BUG_SLOT, n, "A", "string")
        h.wire_in("", n, "B", "string")
        return (n, "ReturnValue")

    def open_save(prevs, pos, create):
        """SvBugSave = the saved reports; none saved: a new save object (create) or the missing
        exits. Returns (exits with SvBugSave set, missing exits)."""
        x, y = pos
        sc, missing = h.load(prevs, slot_pin((x - 300, y + 300)), SG, (x, y))
        st = g.var_set("SvBugSave", "object", ir.obj_path(SG), pos=(x + 1100, y))
        g.wire(sc, as_sg, st, "SvBugSave", exec=False)
        g.wire(sc, "then", st, "execute")
        if not create:
            return [(st, "then")], missing
        crt = g.call("CreateSaveGameObject", GS, pos=(x + 1100, y + 500))
        cp = crt.pin("SaveGameClass").typed("class", ir.obj_path("/Script/Engine.SaveGame"), direction="EGPD_Input")
        cp.set("PinType.bIsUObjectWrapper", "True")
        cp.set("DefaultObject", '"%s"' % SG)
        crt.pin("ReturnValue").typed("object", ir.obj_path(SG), direction="EGPD_Output")
        for m in missing:
            g.wire(m[0], m[1], crt, "execute")
        st2 = g.var_set("SvBugSave", "object", ir.obj_path(SG), pos=(x + 1400, y + 500))
        g.wire(crt, "ReturnValue", st2, "SvBugSave", exec=False)
        g.wire(crt, "then", st2, "execute")
        return [(st, "then"), (st2, "then")], []

    def write(prevs, pos):
        sav = g.call("SaveGameToSlot", GS, pos=pos)
        g.wire(save_ref((pos[0] - 200, pos[1] + 250)), "SvBugSave", sav, "SaveGameObject", exec=False)
        sl = slot_pin((pos[0] - 200, pos[1] + 400))
        g.wire(sl[0], sl[1], sav, "SlotName", exec=False)
        g.typed_input(sav, "UserIndex", "0", "int")
        for p in prevs:
            g.wire(p[0], p[1], sav, "execute")
        return (sav, "then")

    def reply(prev, ok, msg, pos):
        c = h.call_self("OwlClientBugSent", SENT_PINS, pos)
        c.pin("Ok").literal("true" if ok else "false")
        c.pin("Msg").literal(msg)
        g.wire(prev[0], prev[1], c, "execute")
        return c

    def clean(src, limit, pos):
        """src with "|" -> "/", trimmed, cut to limit characters (limit None: no cut)."""
        rep = g.call("Replace", KSTR, pos=pos)
        g.wire(src[0], src[1], rep, "SourceString", exec=False)
        g.typed_input(rep, "From", "|", "string")
        g.typed_input(rep, "To", "/", "string")
        tr = g.call("Trim", KSTR, pos=(pos[0] + 250, pos[1]))
        g.wire(rep, "ReturnValue", tr, "SourceString", exec=False)
        if limit is None:
            return (tr, "ReturnValue")
        lf = g.call("Left", KSTR, pos=(pos[0] + 500, pos[1]))
        g.wire(tr, "ReturnValue", lf, "SourceString", exec=False)
        g.typed_input(lf, "Count", str(limit), "int")
        return (lf, "ReturnValue")

    # ------------------------------------------------------------ OwlServerBugReport(Kind, Title, Text, Where)
    y = y0
    ce = h.event("OwlServerBugReport", [(f, "string", False) for f in FIELDS], y, R.RUN_ON_SERVER)
    now = g.call("GetGameTimeInSeconds", KSL, pos=(300, y + 300))
    at = g.var_get("SvBugAt", "real", pos=(300, y + 450))
    at.pin("SvBugAt").set("PinType.PinSubCategory", '"double"')
    sent_before = g.call("Greater_DoubleDouble", KML, pos=(550, y + 450))
    g.wire(at, "SvBugAt", sent_before, "A", exec=False)
    g.typed_input(sent_before, "B", "0.0", "real")
    until = g.call("Add_DoubleDouble", KML, pos=(550, y + 600))
    g.wire(at, "SvBugAt", until, "A", exec=False)
    g.typed_input(until, "B", str(MOD.BUG_WAIT), "real")
    early = g.call("Less_DoubleDouble", KML, pos=(800, y + 450))
    g.wire(now, "ReturnValue", early, "A", exec=False)
    g.wire(until, "ReturnValue", early, "B", exec=False)
    wait = h.op("BooleanAND", (sent_before, "ReturnValue"), (early, "ReturnValue"), (1000, y + 400))
    bw = h.branch((ce, "then"), wait, (1000, y))
    reply((bw, "then"), False, "Please wait a minute before sending another report.", (1300, y - 300))
    title = clean((ce, "Title"), D.BUG_TITLE_MAX, (1000, y + 900))
    tl = g.call("Len", KSTR, pos=(1700, y + 900))
    g.wire(title[0], title[1], tl, "S", exec=False)
    empty = h.op("EqualEqual_IntInt", (tl, "ReturnValue"), "0", (1800, y + 700))
    bt = h.branch((bw, "else"), empty, (1700, y))
    reply((bt, "then"), False, "Add a short title.", (2000, y - 300))
    # the line: set_line stamps "<time>|<character>|", the rest is the report
    oc = R.owner_pc(bt, "else", (2000, y))
    ps = g.var_get("PlayerState", "object", ir.obj_path(PSTATE), parent="/Script/Engine.Controller", pos=(2000, y + 1300))
    g.wire(oc, "AsConan Player Controller", ps, "self", exec=False)
    acct = g.call("GetPlayerName", PSTATE, pos=(2250, y + 1300))
    g.wire(ps, "PlayerState", acct, "self", exec=False)
    server = g.call("GetServerName", DW, pos=(2250, y + 1450))
    parts = [(server, "ReturnValue"), "|", clean((ce, "Kind"), None, (1000, y + 1100)), "|", title, "|",
             clean((ce, "Where"), None, (1000, y + 1300)), "|", (acct, "ReturnValue"), "|",
             clean((ce, "Text"), D.BUG_TEXT_MAX, (1000, y + 1500))]
    p = h.set_line((oc, "then"), oc, parts, (2300, y))
    # into the save: add, drop the oldest past BUG_MAX, write
    done, _ = open_save([p], (3500, y), create=True)
    p = arr_add(done[0], "Reports", "string", h.get("SvLine", "string", (4700, y + 450)), (4900, y))
    for d in done[1:]:
        g.wire(d[0], d[1], p[0], "execute")
    p = arr_add(p, "Done", "int", "0", (5200, y))
    ln = g.array_len(save_arr("Reports", "string", (5300, y + 600))[0], "Reports", (5500, y + 600), elem_cat="string")
    over = h.op("Greater_IntInt", (ln, "ReturnValue"), str(MOD.BUG_MAX), (5700, y + 600))
    bo = h.branch(p, over, (5500, y))
    q = (bo, "then")
    for k, (name, t) in enumerate((("Reports", "string"), ("Done", "int"))):
        rm = g.array_fn("Array_Remove", pos=(5800 + 300 * k, y + 900), elem_cat=t)
        rm.pin("IndexToRemove").typed("int", direction="EGPD_Input")
        a = save_arr(name, t, (5800 + 300 * k, y + 1150))
        g.wire(a[0], a[1], rm, "TargetArray", exec=False)
        g.wire(q[0], q[1], rm, "execute")
        q = (rm, "then")
    w = write([q, (bo, "else")], (6500, y))
    now2 = g.call("GetGameTimeInSeconds", KSL, pos=(6800, y + 300))
    sa = g.var_set("SvBugAt", "real", pos=(6800, y))
    sa.pin("SvBugAt").set("PinType.PinSubCategory", '"double"')
    g.wire(now2, "ReturnValue", sa, "SvBugAt", exec=False)
    g.wire(w[0], w[1], sa, "execute")
    reply((sa, "then"), True, "", (7100, y))
    h.client_event("OwlClientBugSent", SENT_PINS, ["BugOk", "BugMsg"], "BugSentVer", y + 2000)

    # ------------------------------------------------------------ OwlServerBugList()
    y = y0 + 3500
    ce = h.event("OwlServerBugList", [], y, R.RUN_ON_SERVER)
    _oc, _a, ok = h.unlocked(ce, y)
    found, missing = open_save([(ok, "then")], (1400, y), create=False)
    p = h.setv(found[0], "SvBugR", "string", save_arr("Reports", "string", (2700, y + 300)), (2700, y), arr=True)
    p = h.setv(p, "SvBugD", "int", save_arr("Done", "int", (3000, y + 300)), (3000, y), arr=True)
    e0 = h.arr_fn(missing[0], "Array_Clear", "SvBugR", "string", (2700, y + 600))
    for m in missing[1:]:
        g.wire(m[0], m[1], e0[0], "execute")
    e0 = h.arr_fn(e0, "Array_Clear", "SvBugD", "int", (3000, y + 600))
    send = h.call_self("OwlClientBugList", LIST_PINS, (3400, y))
    for e in (p, e0):
        g.wire(e[0], e[1], send, "execute")
    for k, (pn, var, t) in enumerate((("Lines", "SvBugR", "string"), ("Done", "SvBugD", "int"))):
        src = h.get(var, t, (3200, y + 300 + 150 * k), arr=True)
        g.wire(src[0], src[1], send, pn, exec=False)
    h.client_event("OwlClientBugList", LIST_PINS, ["BugLines", "BugDone"], "BugVer", y + 1200)

    # ------------------------------------------------------------ OwlServerBugDone(Line, Done)
    y = y0 + 6000
    ce = h.event("OwlServerBugDone", [("Line", "string", False), ("Done", "int", False)], y, R.RUN_ON_SERVER)
    _oc, _a, ok = h.unlocked(ce, y)
    found, missing = open_save([(ok, "then")], (1400, y), create=False)
    f = g.array_fn("Array_Find", pos=(2700, y + 300), elem_cat="string")
    g.array_item_pin(f, "ItemToFind", "string")
    f.pin("ReturnValue").typed("int", direction="EGPD_Output")
    a = save_arr("Reports", "string", (2500, y + 300))
    g.wire(a[0], a[1], f, "TargetArray", exec=False)
    g.wire(ce, "Line", f, "ItemToFind", exec=False)
    dl = g.array_len(save_arr("Done", "int", (2500, y + 600))[0], "Done", (2700, y + 600), elem_cat="int")
    inside = h.op("BooleanAND", h.op("GreaterEqual_IntInt", (f, "ReturnValue"), "0", (2950, y + 300)),
                  h.op("Less_IntInt", (f, "ReturnValue"), (dl, "ReturnValue"), (2950, y + 600)), (3200, y + 400))
    bi = h.branch(found[0], inside, (2700, y))
    st = g.array_fn("Array_Set", pos=(3200, y), elem_cat="int")
    g.array_item_pin(st, "Item", "int")
    a = save_arr("Done", "int", (3000, y + 800))
    g.wire(a[0], a[1], st, "TargetArray", exec=False)
    g.wire(f, "ReturnValue", st, "Index", exec=False)
    clamp01 = h.clamp((ce, "Done"), (0, 1), (3000, y + 1000))
    g.wire(clamp01[0], clamp01[1], st, "Item", exec=False)
    g.wire(bi, "then", st, "execute")
    w = write([(st, "then")], (3500, y))
    again = h.call_self("OwlServerBugList", [], (3900, y))
    for e in [w, (bi, "else")] + missing:
        g.wire(e[0], e[1], again, "execute")
    return flags
