"""NPCs in the admin menu (03): the NPC editor page (the Admin NPC Editor board). N_NPCS chips; the
picked NPC's name, role and what it says; whether it stands in the world; NPC_WARES ware rows (item
id + its name, price, currency, on/off); Place here, Save NPC, Delete NPC; a status line.

    admin_layout(u, B, R) -> [(widget, slot props)]     admin_variables(unreal, bel, wbp)
    admin_tick(c, entries, unlocked, on_page, y) -> exits     admin_clicks(c, y)
    (c: ce_panel._Ctx on the menu's relay variable)

The NPCs come from the server (npc_server: OwlServerNpcGet when the page opens, OwlClientNpc answers
into the relay's Npc*C / NpcMsgC / NpcVer). Save NPC sends the boxes (OwlServerNpcSave); Place here
stands the NPC in front of the admin wearing the admin's gear (OwlServerNpcPlace); Delete NPC
removes it (OwlServerNpcDelete). Item names: the menu's baked catalogue (CeCatIds / CeCatNames).
"""
import menu_defs as D
from ce_panel import _text_button, _lab, _field, ETB, KML, KSL, KSTR, CHIP_ON, CHIP_OFF
from kits_panel import _set_box_text
from menu_shell import clicked

N, W = D.N_NPCS, D.NPC_WARES
LOADING = "Still loading the NPCs. Try again in a moment."
NOTE = ("Place here stands the NPC in front of you, facing you, wearing what you have equipped (not your "
        "transmog look). Players press E on it to talk and buy. Prices are taken from their backpack; a ware "
        "needs an item id from the Item catalog (Characters tab) and Save NPC to go on sale.")
ON, OFF = "#b3121a", "#150909"


def _i(c, fn, a, b, pos):
    lit = lambda v: v if isinstance(v, tuple) else (str(v), "int")
    return c.fn(fn, KML, {"A": lit(a), "B": lit(b)}, pos)


def admin_layout(u, B, R):
    u.box("WrapBox", "NpTabs", [
        (_text_button(u, B, "NpTab%d" % k, "NPC %d" % (k + 1), h=40, px=15, pad=14, tinted=True, label_var=True),
         ["Padding=%s" % u.margin(r=8, b=8)]) for k in range(N)])
    items = [(_lab(u, B, "NpLab", "NPCs"), ["Padding=%s" % u.margin(b=8)]), ("NpTabs", ["Padding=%s" % u.margin(b=4)])]
    u.box("HorizontalBox", "NpNameRow", [
        (_field(u, R, "NpName", "NPC name"), ["Size=(SizeRule=Fill)", "Padding=%s" % u.margin(r=10)]),
        (_field(u, R, "NpRole", "Role (e.g. Smith of the Anvil)"), ["Size=(SizeRule=Fill)"])])
    u.text("NpWhere", "", R, 16, "#b8a29c", wrap=True)
    items += [("NpNameRow", ["Padding=%s" % u.margin(b=8)]),
              (_field(u, R, "NpLine", "What this NPC says when a player talks to them"), ["Padding=%s" % u.margin(b=6)]),
              ("NpWhere", ["Padding=%s" % u.margin(b=12)]),
              (_lab(u, B, "NpWLab", "Wares (item id, price, coins, on sale)"), ["Padding=%s" % u.margin(b=8)])]
    for w in range(W):
        u.sized("NpId%dBox" % w, _field(u, R, "NpId%d" % w, "Item id"), w=130)
        u.text("NpItem%d" % w, "", B, 16, "#f2e6e2", wrap=True)
        u.sized("NpPr%dBox" % w, _field(u, R, "NpPr%d" % w, "Price"), w=150)
        u.box("HorizontalBox", "NpW%d" % w, [
            ("NpId%dBox" % w, ["VerticalAlignment=VAlign_Center"]),
            ("NpItem%d" % w, ["Size=(SizeRule=Fill)", "Padding=%s" % u.margin(l=10, r=10), "VerticalAlignment=VAlign_Center"]),
            ("NpPr%dBox" % w, ["VerticalAlignment=VAlign_Center"]),
            (_text_button(u, B, "NpCur%d" % w, D.NPC_CURRENCIES[0][0], h=44, px=14, pad=12, label_var=True),
             ["Padding=%s" % u.margin(l=8), "VerticalAlignment=VAlign_Center"]),
            (_text_button(u, B, "NpOn%d" % w, "Off", h=44, px=14, pad=14, tinted=True, label_var=True),
             ["Padding=%s" % u.margin(l=8), "VerticalAlignment=VAlign_Center"])])
        items.append(("NpW%d" % w, ["Padding=%s" % u.margin(b=6)]))
    u.box("WrapBox", "NpBtns", [
        (_text_button(u, B, "NpDelete", "Delete NPC", h=44, px=15, pad=16), ["Padding=%s" % u.margin(l=10, b=8)]),
        (_text_button(u, B, "NpPlace", "Place here", h=44, px=15, pad=16), ["Padding=%s" % u.margin(l=10, b=8)]),
        (_text_button(u, B, "NpSave", "Save NPC", primary=True, h=44, px=15, pad=16), ["Padding=%s" % u.margin(l=10, b=8)])])
    u.text("NpStatus", "", R, 17, "#f2e6e2", wrap=True)
    u.text("NpNote", NOTE, R, 15, "#a8908a", wrap=True, variable=False)
    return items + [("NpBtns", ["HorizontalAlignment=HAlign_Right", "Padding=%s" % u.margin(t=4)]),
                    ("NpStatus", ["Padding=%s" % u.margin(b=10)]), ("NpNote", [])]


def admin_variables(unreal, bel, wbp):
    i, b = bel.get_basic_type_by_name("int"), bel.get_basic_type_by_name("bool")
    ints = bel.get_array_type(i)
    for var, t in (("NpSel", i), ("NpShown", i), ("NpASeen", i), ("NpAsked", b), ("NpCur", ints), ("NpOn", ints),
                   ("NpTIds", ints), ("NpTPrice", ints)):
        bel.add_member_variable(wbp, var, t)


def _arr_set(c, name, index, item, pos):
    """One of the menu's int arrays: name[index] = item (exec)."""
    g = c.g
    n = g.array_fn("Array_Set", pos=pos, elem_cat="int")
    g.wire(*c.arr(name, "int", (pos[0] - 200, pos[1] + 300)), n, "TargetArray", exec=False)
    n.pin("Index").typed("int", direction="EGPD_Input")
    if isinstance(index, tuple):
        g.wire(index[0], index[1], n, "Index", exec=False)
    elif index:
        n.pin("Index").literal(str(index))
    g.array_item_pin(n, "Item", "int")
    g.wire(item[0], item[1], n, "Item", exec=False)
    c.go(n)


def _num(c, box, pos):
    """The box's text as a whole number (0 if it isn't one); commas are dropped, so 10,000 is 10000."""
    plain = c.fn("Replace", KSTR, {"SourceString": c.box_text(box, pos), "From": (",", "string"), "To": ("", "string")},
                 (pos[0] + 300, pos[1] + 150))
    t = c.fn("Trim", KSTR, {"SourceString": plain}, (pos[0] + 400, pos[1]))
    return c.fn("Conv_StringToInt", KSTR, {"InString": t}, (pos[0] + 600, pos[1]))


def admin_tick(c, entries, unlocked, on_page, y):
    """While unlocked with the page up: ask for the NPCs once per opening; on an answer, its message
    and a redraw; when the picked NPC changes, its boxes; every tick, each row's item name, currency
    and on/off labels, and the chip labels."""
    g = c.g
    c.exits = list(entries)
    b = c.branch(c.fn("BooleanAND", KML, {"A": unlocked, "B": on_page}, (0, y + 300)), (200, y))
    c.exits = [(b, "else")]
    c.set_var("NpAsked", "bool", "false", (500, y + 700))
    out = c.exits
    c.exits = [(b, "then")]
    out += c.find_relay((500, y))
    ba = c.branch(c.fn("Not_PreBool", KML, {"A": c.var("NpAsked", "bool", (2400, y + 300))}, (2600, y + 300)), (2600, y))
    c.exits = [(ba, "then")]
    c.call_relay("OwlServerNpcGet", {}, (2900, y))
    c.set_var("NpAsked", "bool", "true", (3200, y))
    c.exits += [(ba, "else")]
    # an answer: its message, then redraw
    x = 3600
    bv = c.branch(_i(c, "NotEqual_IntInt", c.rvar("NpcVer", "int", (x, y + 300)), c.var("NpASeen", "int", (x, y + 450)),
                     (x + 200, y + 300)), (x + 200, y))
    skip = [(bv, "else")]
    c.exits = [(bv, "then")]
    c.set_var("NpASeen", "int", c.rvar("NpcVer", "int", (x + 300, y + 300)), (x + 500, y))
    c.set_var("NpShown", "int", "-1", (x + 800, y))
    bm = c.branch(_i(c, "Greater_IntInt", c.fn("Len", KSTR, {"S": c.rvar("NpcMsgC", "string", (x + 900, y + 450))},
                                                (x + 1100, y + 450)), 0, (x + 1300, y + 450)), (x + 1100, y))
    c.exits = [(bm, "then")]
    c.set_text("NpStatus", c.rvar("NpcMsgC", "string", (x + 1300, y + 600)), (x + 1400, y))
    c.exits += [(bm, "else")] + skip
    # the picked NPC changed (or must be redrawn), once loaded
    x = 5400
    sel = lambda pos: c.var("NpSel", "int", pos)
    loaded = _i(c, "Greater_IntInt", c.var("NpASeen", "int", (x, y + 600)), 0, (x + 200, y + 600))
    bs = c.branch(c.fn("BooleanAND", KML, {"A": _i(c, "NotEqual_IntInt", sel((x, y + 300)), c.var("NpShown", "int", (x, y + 450)),
                                                   (x + 200, y + 300)), "B": loaded}, (x + 400, y + 300)), (x + 400, y))
    skip = [(bs, "else")]
    c.exits = [(bs, "then")]
    c.set_var("NpShown", "int", sel((x + 300, y + 300)), (x + 700, y))
    for k, name in enumerate(("NpcNamesC", "NpcRolesC", "NpcLinesC")):
        box = ("NpName", "NpRole", "NpLine")[k]
        _set_box_text(c, box, c.at(c.rvar(name, "string", (x + 900 + 400 * k, y + 600), arr=True), sel((x + 900 + 400 * k, y + 750)),
                                   "string", (x + 1100 + 400 * k, y + 600)), (x + 1000 + 400 * k, y))
    x += 2300
    placed = _i(c, "EqualEqual_IntInt", c.at(c.rvar("NpcPlacedC", "int", (x, y + 600), arr=True), sel((x, y + 750)), "int",
                                             (x + 200, y + 600)), 1, (x + 400, y + 600))
    c.set_text("NpWhere", c.fn("SelectString", KML, {
        "A": ("Stands in the world. Place here moves it to you.", "string"),
        "B": ("Not placed yet: stand where it should be and press Place here.", "string"), "bPickA": placed},
        (x + 600, y + 600)), (x + 400, y))
    x += 900
    for name in ("NpCur", "NpOn"):
        rs = g.array_fn("Array_Resize", pos=(x, y), elem_cat="int")
        g.wire(*c.arr(name, "int", (x - 200, y + 300)), rs, "TargetArray", exec=False)
        rs.pin("Size").typed("int", direction="EGPD_Input").literal(str(W))
        c.go(rs)
        x += 300
    base = _i(c, "Multiply_IntInt", sel((x, y + 1200)), W, (x + 200, y + 1200))
    for w in range(W):
        idx = _i(c, "Add_IntInt", base, w, (x + 400, y + 1200)) if w else base
        wa = lambda nm, p: c.at(c.rvar(nm, "int", p, arr=True), idx, "int", (p[0] + 200, p[1]))
        wid = wa("NpcWIdsC", (x, y + 600))
        _set_box_text(c, "NpId%d" % w, c.fn("SelectString", KML, {
            "A": c.int_text(wid, (x + 400, y + 600)), "B": ("", "string"),
            "bPickA": _i(c, "Greater_IntInt", wid, 0, (x + 400, y + 750))}, (x + 600, y + 600)), (x + 300, y))
        wp = wa("NpcWPriceC", (x + 800, y + 600))
        _set_box_text(c, "NpPr%d" % w, c.fn("SelectString", KML, {
            "A": c.int_text(wp, (x + 1200, y + 600)), "B": ("", "string"),
            "bPickA": _i(c, "Greater_IntInt", wp, 0, (x + 1200, y + 750))}, (x + 1400, y + 600)), (x + 1100, y))
        _arr_set(c, "NpCur", w, wa("NpcWCurC", (x + 1500, y + 600)), (x + 1600, y))
        _arr_set(c, "NpOn", w, wa("NpcWOnC", (x + 1800, y + 600)), (x + 1900, y))
        x += 2200
    c.exits += skip
    # every tick: row labels, chips
    x += 300
    for w in range(W):
        cur0 = _i(c, "EqualEqual_IntInt", c.at(c.arr("NpCur", "int", (x, y + 600)), w, "int", (x + 200, y + 600)), 0,
                  (x + 400, y + 600))
        c.set_text("NpCur%dText" % w, c.fn("SelectString", KML, {"A": (D.NPC_CURRENCIES[0][0], "string"),
                                                                  "B": (D.NPC_CURRENCIES[1][0], "string"), "bPickA": cur0},
                                            (x + 600, y + 600)), (x + 300, y))
        on = _i(c, "EqualEqual_IntInt", c.at(c.arr("NpOn", "int", (x, y + 900)), w, "int", (x + 200, y + 900)), 1,
                (x + 400, y + 900))
        c.set_text("NpOn%dText" % w, c.fn("SelectString", KML, {"A": ("On sale", "string"), "B": ("Off", "string"),
                                                                 "bPickA": on}, (x + 600, y + 900)), (x + 600, y))
        c.color("NpOn%d" % w, on, ON, OFF, (x + 900, y))
        tid = _num(c, "NpId%d" % w, (x, y + 1200))
        at = c.find(c.arr("CeCatIds", "int", (x + 600, y + 1350)), tid, "int", (x + 800, y + 1350))
        c.set_text("NpItem%d" % w, c.fn("SelectString", KML, {
            "A": c.at(c.arr("CeCatNames", "string", (x + 800, y + 1500)), at, "string", (x + 1000, y + 1500)),
            "B": c.fn("SelectString", KML, {"A": ("No such item", "string"), "B": ("", "string"),
                                            "bPickA": _i(c, "Greater_IntInt", tid, 0, (x + 1000, y + 1800))}, (x + 1200, y + 1800)),
            "bPickA": _i(c, "GreaterEqual_IntInt", at, 0, (x + 1000, y + 1650))}, (x + 1300, y + 1500)), (x + 1200, y))
        x += 1700
    for k in range(N):
        on = _i(c, "EqualEqual_IntInt", sel((x, y + 600)), k, (x + 200, y + 600))
        c.color("NpTab%d" % k, on, CHIP_ON, CHIP_OFF, (x, y))
        nm = c.at(c.rvar("NpcNamesC", "string", (x + 300, y + 900), arr=True), k, "string", (x + 500, y + 900))
        named = _i(c, "Greater_IntInt", c.fn("Len", KSTR, {"S": nm}, (x + 700, y + 1050)), 0, (x + 900, y + 1050))
        c.set_text("NpTab%dText" % k, c.fn("SelectString", KML, {"A": nm, "B": ("NPC %d" % (k + 1), "string"),
                                                                   "bPickA": named}, (x + 900, y + 900)), (x + 400, y))
        x += 1200
    return out + c.exits


def admin_clicks(c, y):
    g = c.g

    def ready(pos):
        """Go on only with the relay found and the NPCs loaded."""
        cond = c.fn("BooleanAND", KML, {
            "A": c.fn("IsValid", KSL, {"Object": c.relay((pos[0], pos[1] + 300))}, (pos[0] + 200, pos[1] + 300)),
            "B": _i(c, "Greater_IntInt", c.var("NpASeen", "int", (pos[0], pos[1] + 450)), 0, (pos[0] + 200, pos[1] + 450))},
            (pos[0] + 400, pos[1] + 300))
        b = c.branch(cond, pos)
        c.exits = [(b, "else")]
        c.set_text("NpStatus", LOADING, (pos[0] + 300, pos[1] + 600))
        c.exits = [(b, "then")]

    for k in range(N):
        c.exits = [(clicked(g, "NpTab%d" % k, (0, y)), "then")]
        c.set_var("NpSel", "int", str(k), (300, y))
        y += 400
    # a row's currency / on-sale button flips it
    for w in range(W):
        for name in ("NpCur", "NpOn"):
            c.exits = [(clicked(g, "%s%d" % (name, w), (0, y)), "then")]
            flip = _i(c, "Subtract_IntInt", 1, c.at(c.arr(name, "int", (200, y + 300)), w, "int", (400, y + 300)), (600, y + 300))
            _arr_set(c, name, w, flip, (700, y))
            y += 400
    # save: the boxes -> OwlServerNpcSave
    c.exits = [(clicked(g, "NpSave", (0, y)), "then")]
    ready((300, y))
    x = 800
    for name in ("NpTIds", "NpTPrice"):
        clr = g.array_fn("Array_Clear", pos=(x, y), elem_cat="int")
        g.wire(*c.arr(name, "int", (x - 100, y + 300)), clr, "TargetArray", exec=False)
        c.go(clr)
        x += 300
    for w in range(W):
        for name, box in (("NpTIds", "NpId%d" % w), ("NpTPrice", "NpPr%d" % w)):
            add = g.array_fn("Array_Add", pos=(x, y), elem_cat="int")
            g.wire(*c.arr(name, "int", (x, y + 300)), add, "TargetArray", exec=False)
            g.array_item_pin(add, "NewItem", "int")
            v = _num(c, box, (x - 600, y + 450))
            g.wire(v[0], v[1], add, "NewItem", exec=False)
            c.go(add)
            x += 300
    c.call_relay("OwlServerNpcSave", {
        "Index": c.var("NpSel", "int", (x, y + 300)), "Name": c.box_text("NpName", (x, y + 450)),
        "Role": c.box_text("NpRole", (x, y + 600)), "Line": c.box_text("NpLine", (x, y + 750)),
        "WIds": c.arr("NpTIds", "int", (x, y + 900)), "WPrice": c.arr("NpTPrice", "int", (x, y + 1050)),
        "WCur": c.arr("NpCur", "int", (x, y + 1200)), "WOn": c.arr("NpOn", "int", (x, y + 1350))}, (x + 300, y))
    c.set_text("NpStatus", "Saving...", (x + 600, y))
    y += 1600
    for btn, event, msg in (("NpPlace", "OwlServerNpcPlace", "Placing..."), ("NpDelete", "OwlServerNpcDelete", "Deleting...")):
        c.exits = [(clicked(g, btn, (0, y)), "then")]
        ready((300, y))
        c.call_relay(event, {"Index": c.var("NpSel", "int", (800, y + 300))}, (1000, y))
        c.set_text("NpStatus", msg, (1300, y))
        y += 1000
