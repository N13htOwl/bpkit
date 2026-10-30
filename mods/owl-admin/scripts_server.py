"""Scripting, the server side: the relay's (10) script events. The scripts are server-wide (every
unlocked admin sees and edits the same N_SCRIPTS), kept in the OwlScripts save, and only ever sent
to an unlocked admin (they aren't replicated).

    OwlServerScGet()                     -> OwlClientSc(Names, Lines, "")
    OwlServerScSave(Index, Name, Lines)  store script Index (Name, its SCRIPT_LINES lines) -> OwlClientSc
    OwlServerScRan(Text)                 a line in the admin's own admin log ("Ran script ...")
    OwlClientSc(Names, Lines, Msg)       the owner's copy: ScNamesC, ScLinesC, ScMsg, ScVer + 1

Names has one entry per script, Lines SCRIPT_LINES per script in order (script k's line j is
Lines[k * SCRIPT_LINES + j]); a save of another size is resized to fit. Running is the admin's own
client (scripts_panel): each line goes to the console as if typed, so the game's own admin checks
apply to every command; the server only keeps the scripts and the log.
"""
from bpkit import ir
import menu_defs as D
from ce_server import helpers, KSTR, GS
from cheats_server import admin_log

N, L = D.N_SCRIPTS, D.SCRIPT_LINES
SC_PINS = [("Names", "string", True), ("Lines", "string", True), ("Msg", "string", False)]


def variables(unreal, bel, sc_save_cls):
    """(name, type) for the relay: Sc*C / ScMsg / ScVer = the owner's copy, SvSc = the server's."""
    i, s = bel.get_basic_type_by_name("int"), bel.get_basic_type_by_name("string")
    strs = bel.get_array_type(s)
    return [("ScNamesC", strs), ("ScLinesC", strs), ("ScMsg", s), ("ScVer", i),
            ("SvSc", bel.get_object_reference_type(sc_save_cls))]


def build(R, y0):
    """Add the script events to R.g from y0 down (R as for ce_server.build). Returns {event: net flags}."""
    g, MOD = R.g, R.MOD
    SG = MOD.full(R.PKG, MOD.SCRIPTS_SAVEGAME) + "_C"
    flags = {}
    h = helpers(R, flags)
    from ce_server import T
    T.setdefault("scsave", ("object", ir.obj_path(SG)))
    sv = lambda pos: h.get("SvSc", "scsave", pos)

    def field(name, pos):
        n = g.var_get(name, "string", parent=SG, pos=pos)
        n.pin(name).set("PinType.ContainerType", "Array")
        g.wire(*sv((pos[0] - 200, pos[1])), n, "self", exec=False)
        return (n, name)

    def open_save(prev, pos):
        """SvSc = the OwlScripts save, loaded or new, its arrays resized to N names / N*L lines."""
        x, y = pos
        slot = ("", "string")
        dse = g.call("DoesSaveGameExist", GS, pos=(x, y))
        g.typed_input(dse, "SlotName", MOD.SCRIPTS_SLOT, "string")
        g.typed_input(dse, "UserIndex", "0", "int")
        g.wire(prev[0], prev[1], dse, "execute")
        b = h.branch((dse, "then"), (dse, "ReturnValue"), (x + 250, y))
        ld = g.call("LoadGameFromSlot", GS, pos=(x + 500, y))
        g.typed_input(ld, "SlotName", MOD.SCRIPTS_SLOT, "string")
        g.typed_input(ld, "UserIndex", "0", "int")
        g.wire(b, "then", ld, "execute")
        sc = g.cast(SG, pos=(x + 800, y))
        g.wire(ld, "ReturnValue", sc, "Object", exec=False)
        g.wire(ld, "then", sc, "execute")
        have = h.setv((sc, "then"), "SvSc", "scsave", (sc, h.save_as(SG)), (x + 1100, y))
        crt = g.call("CreateSaveGameObject", GS, pos=(x + 800, y + 600))
        cp = crt.pin("SaveGameClass").typed("class", ir.obj_path("/Script/Engine.SaveGame"), direction="EGPD_Input")
        cp.set("PinType.bIsUObjectWrapper", "True")
        cp.set("DefaultObject", '"%s"' % SG)
        crt.pin("ReturnValue").typed("object", ir.obj_path(SG), direction="EGPD_Output")
        for e, ep in ((b, "else"), (sc, "CastFailed")):
            g.wire(e, ep, crt, "execute")
        made = h.setv((crt, "then"), "SvSc", "scsave", (crt, "ReturnValue"), (x + 1100, y + 600))
        prevs = [have, made]
        for k, (name, size) in enumerate((("Names", N), ("Lines", N * L))):
            rs = g.array_fn("Array_Resize", pos=(x + 1400 + 300 * k, y), elem_cat="string")
            g.wire(*field(name, (x + 1400 + 300 * k, y + 300)), rs, "TargetArray", exec=False)
            rs.pin("Size").typed("int", direction="EGPD_Input").literal(str(size))
            for e, ep in prevs:
                g.wire(e, ep, rs, "execute")
            prevs = [(rs, "then")]
        return prevs[0]

    def reply(prev, msg, pos):
        x, y = pos
        call = h.call_self("OwlClientSc", SC_PINS, pos)
        g.wire(*field("Names", (x - 200, y + 300)), call, "Names", exec=False)
        g.wire(*field("Lines", (x - 200, y + 450)), call, "Lines", exec=False)
        h.wire_in(msg, call, "Msg", "string")
        g.wire(prev[0], prev[1], call, "execute")
        return (call, "then")

    # ---- get
    y = y0
    ce = h.event("OwlServerScGet", [], y, R.RUN_ON_SERVER)
    _oc, _a, ok = h.unlocked(ce, y)
    p = open_save((ok, "then"), (1000, y))
    reply(p, "", (3000, y))

    # ---- save one script
    y = y0 + 1500
    ce = h.event("OwlServerScSave", [("Index", "int", False), ("Name", "string", False), ("Lines", "string", True)],
                 y, R.RUN_ON_SERVER)
    oc, _a, ok = h.unlocked(ce, y)
    p = open_save((ok, "then"), (1000, y))
    k = h.clamp((ce, "Index"), (0, N - 1), (2800, y + 600))
    name = g.call("Left", KSTR, pos=(2800, y + 750))
    trim = g.call("Trim", KSTR, pos=(2600, y + 750))
    g.wire(ce, "Name", trim, "SourceString", exec=False)
    g.wire(trim, "ReturnValue", name, "SourceString", exec=False)
    g.typed_input(name, "Count", str(D.SCRIPT_NAME_MAX), "int")
    st = g.array_fn("Array_Set", pos=(3000, y), elem_cat="string")
    g.wire(*field("Names", (2800, y + 300)), st, "TargetArray", exec=False)
    st.pin("Index").typed("int", direction="EGPD_Input")
    g.wire(k[0], k[1], st, "Index", exec=False)
    g.array_item_pin(st, "Item", "string")
    g.wire(name, "ReturnValue", st, "Item", exec=False)
    g.wire(p[0], p[1], st, "execute")
    p = (st, "then")
    for j in range(L):
        x = 3300 + 300 * j
        ls = g.array_fn("Array_Set", pos=(x, y), elem_cat="string")
        g.wire(*field("Lines", (x, y + 300)), ls, "TargetArray", exec=False)
        ls.pin("Index").typed("int", direction="EGPD_Input")
        at = h.op("Multiply_IntInt", k, str(L), (x, y + 600))
        if j:  # (a pasted B of 0 comes back as Add_IntInt's own default, 1)
            at = h.op("Add_IntInt", at, str(j), (x + 150, y + 600))
        g.wire(*at, ls, "Index", exec=False)
        g.array_item_pin(ls, "Item", "string")
        g.wire(g.array_get(ce, "Lines", j, (x, y + 750), elem_cat="string"), "Output", ls, "Item", exec=False)
        g.wire(p[0], p[1], ls, "execute")
        p = (ls, "then")
    x = 3300 + 300 * L
    sav = g.call("SaveGameToSlot", GS, pos=(x, y))
    g.wire(*sv((x - 200, y + 300)), sav, "SaveGameObject", exec=False)
    g.typed_input(sav, "SlotName", MOD.SCRIPTS_SLOT, "string")
    g.typed_input(sav, "UserIndex", "0", "int")
    g.wire(p[0], p[1], sav, "execute")
    p = admin_log(R, h, (sav, "then"), oc, ["Saved script ", (name, "ReturnValue")], (x + 300, y))
    reply(p, h.text(["Saved ", (name, "ReturnValue"), "."], (x + 4600, y + 600)), (x + 4800, y))

    # ---- ran: just the log line
    y = y0 + 3000
    ce = h.event("OwlServerScRan", [("Text", "string", False)], y, R.RUN_ON_SERVER)
    oc, _a, ok = h.unlocked(ce, y)
    admin_log(R, h, (ok, "then"), oc, [(ce, "Text")], (1000, y))

    h.client_event("OwlClientSc", SC_PINS, ["ScNamesC", "ScLinesC", "ScMsg"], "ScVer", y0 + 4500)
    return flags
