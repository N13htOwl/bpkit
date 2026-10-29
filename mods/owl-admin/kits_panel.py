"""Kits in the menus. Admin menu (03), under the Kits tab's settings: per kit a name box with Save
name, and its items (KIT_MAX_ITEMS rows: name x quantity, Remove); items are added in Characters,
Item catalog (Add to Kit <n>, ce_panel). Player menu (07), the Kits tab: a card per kit with its
name, items and when it can be claimed, and Claim.

    admin_layout(u, B, R) -> [(widget, slot props)]     admin_variables(unreal, bel, wbp)
    admin_tick(c, entries, unlocked, ctrl, ctrl_cls, y) -> exits     admin_clicks(c, y)
    player_layout(u, B, R) -> [(widget, slot props)]    player_variables(unreal, bel, wbp)
    player_tick(c, ctrl, ctrl_cls, on_page, y)     player_clicks(c, y)     catalog_clicks(c, y)
    (c: ce_panel._Ctx on the menu's relay variable; ctrl: the controller (node, pin), valid)

The kits are the controller's replicated Kit* arrays (kits_ctrl); a menu redraws when KitVer
changes. Each kit's entries are first sorted into KitL0..KitL<n> (indexes into the Kit* arrays),
so row r of kit k is entry KitL<k>[r]. Every change goes through the admin's relay (kits_server);
its answer (relay KitAMsg) shows in the status line here and in the Characters tab's.
Players: the relay's KitLeft (minutes until each kit can be claimed, asked for every
ASK_SECONDS while the tab is open and after a claim) and KitMsg (the claim's answer).
"""
import menu_defs as D
from ce_panel import _text_button, _lab, _field, TEXT, ETB, KML, KSL, KSTR, KTXT
from menu_shell import clicked

N, ROWS = D.N_KITS, D.KIT_MAX_ITEMS
ASK_SECONDS = 30.0
NOT_CONNECTED = "Still connecting to the server. Try again in a moment."
EMPTY = "No items yet. Add them in Characters, Item catalog: Add to Kit %d."
HBOX = "/Script/UMG.HorizontalBox"


def _i(c, fn, a, b, pos):
    lit = lambda v: v if isinstance(v, tuple) else (str(v), "int")
    return c.fn(fn, KML, {"A": lit(a), "B": lit(b)}, pos)


# ================================================================ admin layout
def admin_layout(u, B, R):
    items = []
    for k in range(N):
        rows = []
        u.box("HorizontalBox", "KitNameRow%d" % k, [
            (_field(u, R, "KitName%d" % k, "Kit name"), ["Size=(SizeRule=Fill)", "VerticalAlignment=VAlign_Center"]),
            (_text_button(u, B, "KitNameSave%d" % k, "Save name", h=44, px=15, pad=14),
             ["Padding=%s" % u.margin(l=10), "VerticalAlignment=VAlign_Center"])])
        rows.append(("KitNameRow%d" % k, ["Padding=%s" % u.margin(b=10)]))
        for r in range(ROWS):
            key = "Kit%d_%d" % (k, r)
            u.text(key + "Txt", "", B, 17, "#f2e6e2", wrap=True)
            u.box("HorizontalBox", key, [
                (key + "Txt", ["Size=(SizeRule=Fill)", "VerticalAlignment=VAlign_Center"]),
                (_text_button(u, B, key + "Rm", "Remove", h=36, px=14, pad=12), ["VerticalAlignment=VAlign_Center"])],
                props=["Visibility=Collapsed"], variable=True)
            rows.append((key, ["Padding=%s" % u.margin(b=4)]))
        u.text("KitEmpty%d" % k, EMPTY % (k + 1), R, 16, "#a8908a", wrap=True)
        rows.append(("KitEmpty%d" % k, []))
        u.box("VerticalBox", "KitCardIn%d" % k, [(_lab(u, B, "KitLab%d" % k, "Kit %d" % (k + 1)), ["Padding=%s" % u.margin(b=8)])]
              + rows)
        u.border("KitCardFill%d" % k, "#120909", 1.0, u.margin(18, 14, 18, 14), "KitCardIn%d" % k)
        u.border("KitCard%d" % k, "#2a1012", 1.0, u.margin(1, 1, 1, 1), "KitCardFill%d" % k)
        items.append(("KitCard%d" % k, ["Padding=%s" % u.margin(b=10)]))
    u.text("KitStatus", "", R, 17, "#f2e6e2", wrap=True)
    return [("KitStatus", ["Padding=%s" % u.margin(t=4, b=10)])] + items


def admin_variables(unreal, bel, wbp):
    i = bel.get_basic_type_by_name("int")
    for var, t in [("KitASeen", i), ("KitAMsgSeen", i)] + [("KitL%d" % k, bel.get_array_type(i)) for k in range(N)]:
        bel.add_member_variable(wbp, var, t)


# ================================================================ shared graph
def _sort(c, ctrl, cvar, pos):
    """KitL0..: the entry indexes of each kit, in order."""
    g, (x, y) = c.g, pos
    for k in range(N):
        n = g.array_fn("Array_Clear", pos=(x + 300 * k, y), elem_cat="int")
        g.wire(*c.arr("KitL%d" % k, "int", (x + 300 * k, y + 300)), n, "TargetArray", exec=False)
        c.go(n)
    x += 300 * N
    each = c.foreach("int", cvar("KitEKit", "int", (x, y + 300), True), (x + 200, y))
    body = c.exits
    for k in range(N):
        c.exits = body
        b = c.branch(_i(c, "EqualEqual_IntInt", (each, "Array Element"), k, (x + 500 + 600 * k, y + 300)),
                     (x + 500 + 600 * k, y))
        c.exits = [(b, "then")]
        add = g.array_fn("Array_Add", pos=(x + 800 + 600 * k, y), elem_cat="int")
        g.wire(*c.arr("KitL%d" % k, "int", (x + 700 + 600 * k, y + 300)), add, "TargetArray", exec=False)
        g.array_item_pin(add, "NewItem", "int")
        g.wire(each, "Array Index", add, "NewItem", exec=False)
        c.go(add)
        body = [(b, "else"), (add, "then")]
    c.exits = [(each, "Completed")]


def _entry_text(c, cvar, entry, pos):
    """"<name> x<qty>" of the entry at index entry (node, pin)."""
    x, y = pos
    name = c.at(cvar("KitENames", "string", (x, y), True), entry, "string", (x + 200, y))
    qty = c.at(cvar("KitEQty", "int", (x, y + 150), True), entry, "int", (x + 200, y + 150))
    return c.concat([name, " x", c.int_text(qty, (x + 400, y + 150))], (x + 600, y))


def _ctrl_var(c, ctrl, ctrl_cls):
    def cvar(name, cat, pos, arr=False):
        n = c.g.var_get(name, cat, parent=ctrl_cls, pos=pos)
        if arr:
            n.pin(name).set("PinType.ContainerType", "Array")
        c.g.wire(ctrl[0], ctrl[1], n, "self", exec=False)
        return (n, name)
    return cvar


def _set_box_text(c, box, src, pos):
    t = c.fn("Conv_StringToText", KTXT, {"InString": src}, (pos[0], pos[1] + 200))
    st = c.g.call("SetText", ETB, pos=pos)
    w = c.widget(box, ETB, (pos[0] - 200, pos[1] + 350))
    c.g.wire(w[0], w[1], st, "self", exec=False)
    c.g.wire(t[0], t[1], st, "InText", exec=False)
    c.go(st)


# ================================================================ admin tick / clicks
def admin_tick(c, entries, unlocked, ctrl, ctrl_cls, y):
    """While unlocked: the server's answer into the status lines; on a KitVer change, redraw."""
    g = c.g
    c.exits = list(entries)
    cvar = _ctrl_var(c, ctrl, ctrl_cls)
    b = c.branch(unlocked, (0, y))
    out = [(b, "else")]
    c.exits = [(b, "then")]
    out += c.find_relay((300, y))
    x = 2400
    bm = c.branch(_i(c, "NotEqual_IntInt", c.rvar("KitAMsgVer", "int", (x, y + 300)), c.var("KitAMsgSeen", "int", (x, y + 450)),
                     (x + 200, y + 300)), (x + 200, y))
    skip = [(bm, "else")]
    c.exits = [(bm, "then")]
    c.set_var("KitAMsgSeen", "int", c.rvar("KitAMsgVer", "int", (x + 300, y + 300)), (x + 500, y))
    c.set_text("KitStatus", c.rvar("KitAMsg", "string", (x + 600, y + 450)), (x + 800, y))
    c.set_var("CeMsg", "string", c.rvar("KitAMsg", "string", (x + 900, y + 450)), (x + 1100, y))
    c.exits += skip
    # redraw on a change
    x = 4000
    bv = c.branch(_i(c, "NotEqual_IntInt", cvar("KitVer", "int", (x, y + 300)), c.var("KitASeen", "int", (x, y + 450)),
                     (x + 200, y + 300)), (x + 200, y))
    skip = [(bv, "else")]
    c.exits = [(bv, "then")]
    c.set_var("KitASeen", "int", cvar("KitVer", "int", (x + 300, y + 300)), (x + 500, y))
    for k in range(N):
        _set_box_text(c, "KitName%d" % k, c.at(cvar("KitNames", "string", (x + 600 + 300 * k, y + 600), True), k, "string",
                                               (x + 800 + 300 * k, y + 600)), (x + 800 + 300 * k, y))
    x += 800 + 300 * N
    _sort(c, ctrl, cvar, (x, y))
    x += 300 * N + 2200
    for k in range(N):
        ln = (g.array_len(*c.arr("KitL%d" % k, "int", (x, y + 1300)), (x + 200, y + 1300), elem_cat="int"), "ReturnValue")
        for r in range(ROWS):
            key = "Kit%d_%d" % (k, r)
            br = c.branch(_i(c, "Less_IntInt", r, ln, (x + 200, y + 450)), (x, y))
            c.exits = [(br, "then")]
            c.set_vis(key, HBOX, "Visible", (x + 300, y))
            entry = c.at(c.arr("KitL%d" % k, "int", (x + 300, y + 750)), r, "int", (x + 500, y + 750))
            c.set_text(key + "Txt", _entry_text(c, cvar, entry, (x + 600, y + 900)), (x + 600, y))
            ends = c.exits
            c.exits = [(br, "else")]
            c.set_vis(key, HBOX, "Collapsed", (x + 300, y + 350))
            c.exits += ends
            x += 1400
        c.vis_if(_i(c, "EqualEqual_IntInt", ln, 0, (x, y + 300)), [("KitEmpty%d" % k, TEXT)], (x + 200, y))
        x += 700
    c.exits += skip
    return out + c.exits


def admin_clicks(c, y):
    g = c.g

    def ready(pos):
        b = c.branch(c.fn("IsValid", KSL, {"Object": c.relay((pos[0], pos[1] + 300))}, (pos[0] + 200, pos[1] + 300)), pos)
        c.exits = [(b, "else")]
        c.set_text("KitStatus", NOT_CONNECTED, (pos[0] + 300, pos[1] + 400))
        c.exits = [(b, "then")]

    for k in range(N):
        c.exits = [(clicked(g, "KitNameSave%d" % k, (0, y)), "then")]
        ready((300, y))
        c.call_relay("OwlServerKitName", {"Kit": c.fn("MakeLiteralInt", KSL, {"Value": (str(k), "int")}, (700, y + 300)),
                                          "Name": c.box_text("KitName%d" % k, (700, y + 450))}, (1000, y))
        c.set_text("KitStatus", "Saving the name...", (1300, y))
        y += 800
        for r in range(ROWS):
            c.exits = [(clicked(g, "Kit%d_%dRm" % (k, r), (0, y)), "then")]
            ready((300, y))
            ln = (g.array_len(*c.arr("KitL%d" % k, "int", (600, y + 600)), (800, y + 600), elem_cat="int"), "ReturnValue")
            bh = c.branch(_i(c, "Less_IntInt", r, ln, (900, y + 600)), (800, y))
            c.exits = [(bh, "then")]
            c.call_relay("OwlServerKitRemove", {"Entry": c.at(c.arr("KitL%d" % k, "int", (900, y + 750)), r, "int",
                                                              (1100, y + 750))}, (1200, y))
            c.set_text("KitStatus", "Removing...", (1500, y))
            y += 1000


def catalog_clicks(c, y):
    """Characters, Item catalog: Add to Kit <n> -> OwlServerKitAdd(n, the picked item, CeEdQty)."""
    g = c.g
    sel = lambda pos: c.var("CeCatSel", "int", pos)
    for k in range(N):
        c.exits = [(clicked(g, "CeCatKit%d" % k, (0, y)), "then")]
        b = c.branch(c.fn("BooleanAND", KML, {"A": c.fn("IsValid", KSL, {"Object": c.relay((100, y + 300))}, (300, y + 300)),
                                              "B": _i(c, "GreaterEqual_IntInt", sel((300, y + 600)), 0, (500, y + 600))},
                          (600, y + 300)), (600, y))
        c.exits = [(b, "else")]
        c.set_var("CeMsg", "string", "Pick an item first.", (900, y + 400))
        c.exits = [(b, "then")]
        c.call_relay("OwlServerKitAdd", {
            "Kit": c.fn("MakeLiteralInt", KSL, {"Value": (str(k), "int")}, (700, y + 300)),
            "Id": c.at(c.arr("CeCatIds", "int", (700, y + 450)), sel((700, y + 600)), "int", (900, y + 450)),
            "Qty": c.var("CeEdQty", "int", (700, y + 750)),
            "Name": c.at(c.arr("CeCatNames", "string", (700, y + 900)), sel((700, y + 1050)), "string", (900, y + 900))},
            (1000, y))
        c.set_var("CeMsg", "string", "Adding to Kit %d..." % (k + 1), (1300, y))
        y += 1200


# ================================================================ player layout
def player_layout(u, B, R):
    cards = []
    for k in range(N):
        p = "PKit%d" % k
        u.text(p + "Name", D.KIT_NAMES[k].upper(), B, 20, "#ffffff", spacing_px=2, wrap=True)
        u.text(p + "Items", "", R, 16, "#d8c8c3", wrap=True)
        u.text(p + "State", "", B, 16, "#ff5a5f", wrap=True)
        u.box("VerticalBox", p + "In", [
            (p + "Name", ["Padding=%s" % u.margin(b=6)]), (p + "Items", ["Padding=%s" % u.margin(b=10)]),
            (p + "State", ["Padding=%s" % u.margin(b=10)]),
            (_text_button(u, B, p + "Claim", "Claim", primary=True, h=46, px=17, pad=20), ["HorizontalAlignment=HAlign_Fill"])])
        u.border(p + "Fill", "#0f0707", 1.0, u.margin(18, 14, 18, 14), p + "In")
        u.border(p + "Frame", "#3a1214", 1.0, u.margin(1, 1, 1, 1), p + "Fill")
        u.sized(p + "Box", p + "Frame", w=210)
        cards.append((p + "Box", ["Padding=%s" % u.margin(r=10, b=10)]))
    u.box("WrapBox", "PKitCards", cards)
    u.text("PKitMsg", "", R, 17, "#f2e6e2", wrap=True)
    return [(_lab(u, B, "PKitLab", "Kits you can claim"), ["Padding=%s" % u.margin(b=10)]),
            ("PKitMsg", ["Padding=%s" % u.margin(b=10)]), ("PKitCards", [])]


def player_variables(unreal, bel, wbp):
    i, s = bel.get_basic_type_by_name("int"), bel.get_basic_type_by_name("string")
    for var, t in ([("PKitSeen", i), ("PKitLeftSeen", i), ("PKitMsgSeen", i), ("PKitAskAt", bel.get_basic_type_by_name("real"))]
                   + [("KitL%d" % k, bel.get_array_type(i)) for k in range(N)] + [("PKitTxt", s)]):
        bel.add_member_variable(wbp, var, t)


# ================================================================ player tick / clicks
def _left_text(c, left, pos):
    """KitLeft code -> what the card says."""
    x, y = pos
    hours = c.int_text(_i(c, "Divide_IntInt", left, 60, (x, y + 150)), (x + 200, y + 150))
    mins = c.int_text(_i(c, "Percent_IntInt", left, 60, (x, y + 300)), (x + 200, y + 300))
    txt = c.fn("SelectString", KML, {"A": c.concat(["Ready again in ", hours, "h ", mins, "m"], (x + 400, y + 150)),
                                     "B": ("Ready to claim", "string"),
                                     "bPickA": _i(c, "Greater_IntInt", left, 0, (x + 400, y + 450))}, (x + 1000, y))
    for code, msg in ((-1, "Turned off by the admins"), (-2, "Kits are turned off on this server"), (-3, "Nothing in it yet")):
        x += 250
        txt = c.fn("SelectString", KML, {"A": (msg, "string"), "B": txt,
                                         "bPickA": _i(c, "EqualEqual_IntInt", left, code, (x + 1000, y + 600))}, (x + 1100, y))
    return txt


def player_tick(c, ctrl_src, ctrl_cls, on_page, y):
    """Entered from c.exits (the controller valid: ctrl_src); leaves c.exits for whatever follows."""
    g = c.g
    cvar = _ctrl_var(c, ctrl_src, ctrl_cls)
    # the kits changed: names and item lists
    x = 0
    bv = c.branch(_i(c, "NotEqual_IntInt", cvar("KitVer", "int", (x, y + 300)), c.var("PKitSeen", "int", (x, y + 450)),
                     (x + 200, y + 300)), (x + 200, y))
    skip = [(bv, "else")]
    c.exits = [(bv, "then")]
    c.set_var("PKitSeen", "int", cvar("KitVer", "int", (x + 300, y + 300)), (x + 500, y))
    _sort(c, ctrl_src, cvar, (x + 800, y))
    x += 800 + 300 * N + 2200
    for k in range(N):
        p = "PKit%d" % k
        c.set_text(p + "Name", c.fn("ToUpper", KSTR, {"SourceString": c.at(cvar("KitNames", "string", (x, y + 450), True), k,
                                                                           "string", (x + 200, y + 450))}, (x + 400, y + 450)),
                   (x + 300, y))
        c.set_var("PKitTxt", "string", "", (x + 600, y))
        each = c.foreach("int", c.arr("KitL%d" % k, "int", (x + 700, y + 300)), (x + 900, y))
        line = _entry_text(c, cvar, (each, "Array Element"), (x + 1000, y + 600))
        # "a x1, b x2": a typed-in "\n" is lost in the paste, so items are joined with ", "
        sep = c.fn("SelectString", KML, {"A": ("", "string"), "B": (", ", "string"),
                                         "bPickA": _i(c, "EqualEqual_IntInt", c.fn("Len", KSTR, {"S": c.var("PKitTxt", "string",
                                                                                                         (x + 1400, y + 900))},
                                                                                   (x + 1500, y + 900)), 0, (x + 1600, y + 900))},
                     (x + 1700, y + 750))
        c.set_var("PKitTxt", "string", c.concat([c.var("PKitTxt", "string", (x + 1600, y + 450)), sep, line],
                                                (x + 1800, y + 450)), (x + 1300, y))
        c.exits = [(each, "Completed")]
        none = _i(c, "EqualEqual_IntInt", (g.array_len(*c.arr("KitL%d" % k, "int", (x + 2000, y + 600)), (x + 2200, y + 600),
                                                        elem_cat="int"), "ReturnValue"), 0, (x + 2400, y + 600))
        c.set_text(p + "Items", c.fn("SelectString", KML, {"A": ("No items yet.", "string"),
                                                          "B": c.var("PKitTxt", "string", (x + 2400, y + 750)),
                                                          "bPickA": none}, (x + 2600, y + 600)), (x + 2600, y))
        x += 3000
    c.exits += skip
    # the relay: while the tab is open, ask for the cooldowns every ASK_SECONDS
    y2 = y + 2500
    bp_ = c.branch(c.fn("BooleanAND", KML, {"A": on_page, "B": c.fn("IsValid", KSL, {"Object": c.relay((0, y2 + 450))},
                                                                     (200, y2 + 450))}, (400, y2 + 300)), (400, y2))
    c.exits = [(bp_, "else")]
    c.set_var("PKitAskAt", "real", "0.0", (700, y2 + 1200))     # ask as soon as the tab opens again
    out = c.exits
    c.exits = [(bp_, "then")]
    now = c.fn("GetGameTimeInSeconds", KSL, {}, (600, y2 + 300))
    ba = c.branch(c.fn("Greater_DoubleDouble", KML, {"A": now, "B": c.var("PKitAskAt", "real", (600, y2 + 450))},
                       (800, y2 + 300)), (800, y2))
    later = [(ba, "else")]
    c.exits = [(ba, "then")]
    c.set_var("PKitAskAt", "real", c.fn("Add_DoubleDouble", KML, {"A": now, "B": (str(ASK_SECONDS), "real")}, (1000, y2 + 300)),
              (1100, y2))
    c.call_relay("OwlServerKitStatus", {}, (1400, y2))
    c.exits += later
    # an answer: the cards' states
    x = 1800
    bl = c.branch(_i(c, "NotEqual_IntInt", c.rvar("KitLeftVer", "int", (x, y2 + 300)), c.var("PKitLeftSeen", "int", (x, y2 + 450)),
                     (x + 200, y2 + 300)), (x + 200, y2))
    skip = [(bl, "else")]
    c.exits = [(bl, "then")]
    c.set_var("PKitLeftSeen", "int", c.rvar("KitLeftVer", "int", (x + 300, y2 + 300)), (x + 500, y2))
    x += 800
    for k in range(N):
        left = c.at(c.rvar("KitLeft", "int", (x, y2 + 600), arr=True), k, "int", (x + 200, y2 + 600))
        c.set_text("PKit%dState" % k, _left_text(c, left, (x + 300, y2 + 800)), (x + 300, y2))
        x += 2200
    c.exits += skip
    bm = c.branch(_i(c, "NotEqual_IntInt", c.rvar("KitMsgVer", "int", (x, y2 + 300)), c.var("PKitMsgSeen", "int", (x, y2 + 450)),
                     (x + 200, y2 + 300)), (x + 200, y2))
    skip = [(bm, "else")]
    c.exits = [(bm, "then")]
    c.set_var("PKitMsgSeen", "int", c.rvar("KitMsgVer", "int", (x + 300, y2 + 300)), (x + 500, y2))
    c.set_text("PKitMsg", c.rvar("KitMsg", "string", (x + 600, y2 + 450)), (x + 800, y2))
    c.exits += skip + out


def player_clicks(c, y):
    g = c.g
    for k in range(N):
        c.exits = [(clicked(g, "PKit%dClaim" % k, (0, y)), "then")]
        b = c.branch(c.fn("IsValid", KSL, {"Object": c.relay((100, y + 300))}, (300, y + 300)), (300, y))
        c.exits = [(b, "else")]
        c.set_text("PKitMsg", NOT_CONNECTED, (600, y + 400))
        c.exits = [(b, "then")]
        c.call_relay("OwlServerKitClaim", {"Kit": c.fn("MakeLiteralInt", KSL, {"Value": (str(k), "int")}, (600, y + 300))},
                     (900, y))
        c.set_text("PKitMsg", "Claiming...", (1200, y))
        y += 700
