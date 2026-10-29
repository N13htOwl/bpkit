"""Cheats in the admin menu (03): the Cheats page. A row per cheat (menu_defs.CHEATS) with an
On / Off button, the move speed (x1..CH_SPEED_MAX, - and +), and a status line. Every click goes
to the admin's own relay (cheats_server, OwlServerChSet), which applies it to their own character
and logs it; the page shows the server's answer (relay ChOnC / ChSpeedC / ChMsg, on ChVer).

    admin_layout(u, B, R) -> [(widget, slot props)]     admin_variables(unreal, bel, wbp)
    admin_tick(c, entries, unlocked, on_page, y) -> exits     admin_clicks(c, y)
    (c: ce_panel._Ctx on the menu's relay variable)

The page asks for the current state (OwlServerChGet) each time it is opened while unlocked.
"""
import menu_defs as D
from ce_panel import _text_button, _step, _lab, KML, KSL, KSTR, CHIP_ON, CHIP_OFF
from menu_shell import clicked

N = len(D.CHEATS)
LOADING = "Still loading your cheats. Try again in a moment."
NOTE = ("Only your own character. Cheats stay on after you die, and turn off when you lock admin "
        "mode or leave the server. Fly, invisibility and instant crafting aren't offered: the game has "
        "no safe way to switch them.")


def _i(c, fn, a, b, pos):
    lit = lambda v: v if isinstance(v, tuple) else (str(v), "int")
    return c.fn(fn, KML, {"A": lit(a), "B": lit(b)}, pos)


def _row(u, B, R, key, label, desc, control):
    u.text(key + "Lbl", label, B, 19, "#ffffff", wrap=True, variable=False)
    u.text(key + "Desc", desc, R, 16, "#b8a29c", wrap=True, variable=False)
    u.box("VerticalBox", key + "Txt", [(key + "Lbl", []), (key + "Desc", ["Padding=%s" % u.margin(t=2)])])
    u.box("HorizontalBox", key + "Row", [
        (key + "Txt", ["Size=(SizeRule=Fill)", "VerticalAlignment=VAlign_Center"]),
        (control, ["Padding=%s" % u.margin(l=16), "VerticalAlignment=VAlign_Center"])])
    u.border(key + "Fill", "#120909", 1.0, u.margin(16, 10, 10, 10), key + "Row")
    u.strip(key + "Acc", "#4a1a1d", u.margin(l=3))
    u.box("HorizontalBox", key, [(key + "Acc", ["VerticalAlignment=VAlign_Fill"]),
                                 (key + "Fill", ["Size=(SizeRule=Fill)", "VerticalAlignment=VAlign_Fill"])])
    return (key, ["Padding=%s" % u.margin(b=8)])


def admin_layout(u, B, R):
    items = [(_lab(u, B, "ChLab", "Your cheats"), ["Padding=%s" % u.margin(b=8)])]
    for k, (_key, label, desc) in enumerate(D.CHEATS):
        btn = _text_button(u, B, "Ch%dBtn" % k, "Off", h=40, px=15, pad=14, tinted=True, label_var=True)
        items.append(_row(u, B, R, "Ch%d" % k, label, desc, btn))
    u.text("ChSpdVal", "x1", B, 22, "#ff5a5f")
    u.sized("ChSpdValBox", "ChSpdVal", w=56, halign="HAlign_Center", valign="VAlign_Center")
    u.box("HorizontalBox", "ChSpdCtl", [
        (_step(u, B, "ChSpdDec", "-"), ["VerticalAlignment=VAlign_Center"]),
        ("ChSpdValBox", ["Padding=%s" % u.margin(4, 0, 4, 0), "VerticalAlignment=VAlign_Center"]),
        (_step(u, B, "ChSpdInc", "+"), ["VerticalAlignment=VAlign_Center"])])
    items.append(_row(u, B, R, "ChSpd", "Move speed",
                      "Walk and run faster, up to x%d. x1 is the game's own speed." % D.CH_SPEED_MAX, "ChSpdCtl"))
    u.text("ChStatus", "", R, 17, "#f2e6e2", wrap=True)
    u.text("ChNote", NOTE, R, 15, "#a8908a", wrap=True, variable=False)
    return items + [("ChStatus", ["Padding=%s" % u.margin(t=4, b=8)]), ("ChNote", [])]


def admin_variables(unreal, bel, wbp):
    bel.add_member_variable(wbp, "ChASeen", bel.get_basic_type_by_name("int"))
    bel.add_member_variable(wbp, "ChAsked", bel.get_basic_type_by_name("bool"))


def admin_tick(c, entries, unlocked, on_page, y):
    """While unlocked with the page up: ask for the state once per opening, and redraw on an answer."""
    c.exits = list(entries)
    b = c.branch(c.fn("BooleanAND", KML, {"A": unlocked, "B": on_page}, (0, y + 300)), (200, y))
    c.exits = [(b, "else")]
    c.set_var("ChAsked", "bool", "false", (500, y + 700))
    out = c.exits
    c.exits = [(b, "then")]
    out += c.find_relay((500, y))
    ba = c.branch(c.fn("Not_PreBool", KML, {"A": c.var("ChAsked", "bool", (2400, y + 300))}, (2600, y + 300)), (2600, y))
    c.exits = [(ba, "then")]
    c.call_relay("OwlServerChGet", {}, (2900, y))
    c.set_var("ChAsked", "bool", "true", (3200, y))
    c.exits += [(ba, "else")]
    x = 3600
    bv = c.branch(_i(c, "NotEqual_IntInt", c.rvar("ChVer", "int", (x, y + 300)), c.var("ChASeen", "int", (x, y + 450)),
                     (x + 200, y + 300)), (x + 200, y))
    skip = [(bv, "else")]
    c.exits = [(bv, "then")]
    c.set_var("ChASeen", "int", c.rvar("ChVer", "int", (x + 300, y + 300)), (x + 500, y))
    x += 800
    for k in range(N):
        on = _i(c, "Greater_IntInt", c.at(c.rvar("ChOnC", "int", (x, y + 600), arr=True), k, "int", (x + 200, y + 600)), 0,
                (x + 400, y + 600))
        c.color("Ch%dBtn" % k, on, CHIP_ON, CHIP_OFF, (x, y))
        c.set_text("Ch%dBtnText" % k, c.fn("SelectString", KML, {"A": ("On", "string"), "B": ("Off", "string"),
                                                                   "bPickA": on}, (x + 400, y + 750)), (x + 300, y))
        x += 800
    c.set_text("ChSpdVal", c.int_text(c.rvar("ChSpeedC", "int", (x, y + 300)), (x + 200, y + 300), prefix="x"), (x + 300, y))
    x += 700
    bm = c.branch(_i(c, "Greater_IntInt", c.fn("Len", KSTR, {"S": c.rvar("ChMsg", "string", (x, y + 450))}, (x + 200, y + 450)),
                     0, (x + 400, y + 450)), (x + 300, y))
    c.exits = [(bm, "then")]
    c.set_text("ChStatus", c.rvar("ChMsg", "string", (x + 500, y + 600)), (x + 600, y))
    c.exits += [(bm, "else")] + skip
    return out + c.exits


def admin_clicks(c, y):
    g = c.g

    def ready(pos):
        """Go on only with the relay found and the state loaded."""
        b = c.branch(c.fn("BooleanAND", KML, {
            "A": c.fn("IsValid", KSL, {"Object": c.relay((pos[0], pos[1] + 300))}, (pos[0] + 200, pos[1] + 300)),
            "B": _i(c, "Greater_IntInt", c.var("ChASeen", "int", (pos[0], pos[1] + 450)), 0, (pos[0] + 200, pos[1] + 450))},
            (pos[0] + 400, pos[1] + 300)), pos)
        c.exits = [(b, "else")]
        c.set_text("ChStatus", LOADING, (pos[0] + 300, pos[1] + 600))
        c.exits = [(b, "then")]

    def send(which, value, pos):
        c.call_relay("OwlServerChSet", {"Which": c.fn("MakeLiteralInt", KSL, {"Value": (str(which), "int")},
                                                      (pos[0] - 300, pos[1] + 300)),
                                        "Value": value}, pos)
        c.set_text("ChStatus", "Sending...", (pos[0] + 300, pos[1]))

    for k in range(N):
        c.exits = [(clicked(g, "Ch%dBtn" % k, (0, y)), "then")]
        ready((300, y))
        on = _i(c, "Greater_IntInt", c.at(c.rvar("ChOnC", "int", (700, y + 600), arr=True), k, "int", (900, y + 600)), 0,
                (1100, y + 600))
        send(k, c.fn("SelectInt", KML, {"A": ("0", "int"), "B": ("1", "int"), "bPickA": on}, (1100, y + 450)), (1300, y))
        y += 1000
    speed = lambda pos: c.rvar("ChSpeedC", "int", pos)
    for btn, fn, delta, lim in (("ChSpdDec", "Max", -1, 1), ("ChSpdInc", "Min", 1, D.CH_SPEED_MAX)):
        c.exits = [(clicked(g, btn, (0, y)), "then")]
        ready((300, y))
        send(N, _i(c, fn, _i(c, "Add_IntInt", speed((700, y + 450)), delta, (900, y + 450)), lim, (1100, y + 450)), (1300, y))
        y += 1000
