"""The admin menu's HUD tab (03): what every player sees on screen. One card per
menu_defs.HUD_ITEMS entry -- its name, what it is, an ON/OFF switch and, for the text items, a
text box -- then a status line, Reload and Save HUD.

    admin_layout(u, B, R) -> [(widget, slot props)]     admin_variables(unreal, bel, wbp)
    admin_tick(c, entries, on_page, ctrl, ctrl_cls, y) -> exits   (c: ce_panel._Ctx on CeRelay)
    admin_clicks(c, y)

The values live on the controller (02): HudOn / HudText, replicated. When its HudVer differs
from HudASeen, the switches (HudE<k>) and text boxes are loaded from it, so they show what the
server has: after this admin's Save, another admin's, or Reload (HudASeen = -1). Save HUD sends
everything through the admin's relay (OwlServerHudSet, hud_server); the server's answer
(OwlClientHudSaved) shows in the status line.
"""
import menu_defs as D
from ce_panel import _text_button, _field, CHIP_ON, CHIP_OFF, KML, KSL, ETB
from menu_shell import clicked

N = len(D.HUD_ITEMS)
NOT_CONNECTED = "Still connecting to the server. Try again in a moment."


# ================================================================ layout
def admin_layout(u, B, R):
    items = []
    for k, (key, label, desc, limit) in enumerate(D.HUD_ITEMS):
        r = "HudRow%d" % k
        u.text(r + "Lbl", label, B, 19, "#ffffff", variable=False)
        u.text(r + "Desc", desc, R, 15, "#b8a29c", wrap=True, variable=False)
        u.box("VerticalBox", r + "Txt", [(r + "Lbl", []), (r + "Desc", ["Padding=%s" % u.margin(t=2)])])
        u.box("HorizontalBox", r + "Top", [
            (r + "Txt", ["Size=(SizeRule=Fill)", "VerticalAlignment=VAlign_Center"]),
            (_text_button(u, B, "HudTg%d" % k, "OFF", h=40, px=15, pad=18, tinted=True, label_var=True),
             ["Padding=%s" % u.margin(l=24), "VerticalAlignment=VAlign_Center"])])
        inner = [(r + "Top", [])]
        if limit:
            inner.append((_field(u, R, "HudTx%d" % k, "Text, up to %d characters" % limit),
                          ["Padding=%s" % u.margin(t=10)]))
        u.box("VerticalBox", r + "In", inner)
        u.border(r + "Fill", "#120909", 1.0, u.margin(20, 14, 20, 14), r + "In")
        u.strip(r + "Acc", "#4a1a1d", u.margin(l=3))
        u.box("HorizontalBox", r + "Row", [(r + "Acc", ["VerticalAlignment=VAlign_Fill"]),
                                           (r + "Fill", ["Size=(SizeRule=Fill)", "VerticalAlignment=VAlign_Fill"])])
        u.border(r, "#2a1012", 1.0, u.margin(1, 1, 1, 1), r + "Row")
        items.append((r, ["Padding=%s" % u.margin(b=10)]))
    u.text("HudStatus", "A part with no text stays hidden even when it's on.", R, 16, "#b8a29c", wrap=True)
    u.box("HorizontalBox", "HudFoot", [
        ("HudStatus", ["Size=(SizeRule=Fill)", "VerticalAlignment=VAlign_Center"]),
        (_text_button(u, B, "HudReload", "Reload", h=44, px=16, pad=18),
         ["Padding=%s" % u.margin(l=16, r=12), "VerticalAlignment=VAlign_Center"]),
        (_text_button(u, B, "HudSave", "Save HUD", primary=True, h=44, px=16, pad=18), ["VerticalAlignment=VAlign_Center"])])
    items.append(("HudFoot", ["Padding=%s" % u.margin(t=6, b=10)]))
    return items


def admin_variables(unreal, bel, wbp):
    i = bel.get_basic_type_by_name("int")
    for var in ["HudE%d" % k for k in range(N)] + ["HudASeen", "HudMsgSeen"]:
        bel.add_member_variable(wbp, var, i)


# ================================================================ tick
def admin_tick(c, entries, on_page, ctrl, ctrl_cls, y):
    """Entered from entries (the controller found). ctrl: (node, pin) of the controller."""
    g = c.g
    c.exits = list(entries)

    def cvar(name, cat, pos, arr=False):
        n = g.var_get(name, cat, parent=ctrl_cls, pos=pos)
        if arr:
            n.pin(name).set("PinType.ContainerType", "Array")
        g.wire(ctrl[0], ctrl[1], n, "self", exec=False)
        return (n, name)

    # the server's values changed (or Reload): load the controls
    bv = c.branch(c.fn("NotEqual_IntInt", KML, {"A": cvar("HudVer", "int", (0, y + 300)),
                                                "B": c.var("HudASeen", "int", (0, y + 450))}, (250, y + 300)), (250, y))
    skip = [(bv, "else")]
    c.exits = [(bv, "then")]
    c.set_var("HudASeen", "int", cvar("HudVer", "int", (400, y + 300)), (500, y))
    x = 800
    for k in range(N):
        c.set_var("HudE%d" % k, "int", c.at(cvar("HudOn", "int", (x, y + 450), arr=True), k, "int",
                                            (x + 200, y + 450)), (x + 200, y))
        x += 400
    for j in range(len(D.HUD_TEXTS)):
        tt = c.fn("Conv_StringToText", "/Script/Engine.KismetTextLibrary",
                  {"InString": c.at(cvar("HudText", "string", (x, y + 600), arr=True), j, "string",
                                    (x + 200, y + 600))}, (x + 400, y + 600))
        st = g.call("SetText", ETB, pos=(x + 400, y))
        w = c.widget("HudTx%d" % j, ETB, (x + 200, y + 300))
        g.wire(w[0], w[1], st, "self", exec=False)
        g.wire(tt[0], tt[1], st, "InText", exec=False)
        c.go(st)
        x += 600
    c.exits += skip
    # on the page: the switches show their state; the server's answer to Save shows in the status
    bp_ = c.branch(on_page, (x, y))
    out = [(bp_, "else")]
    c.exits = [(bp_, "then")]
    x += 300
    for k in range(N):
        on = c.fn("EqualEqual_IntInt", KML, {"A": c.var("HudE%d" % k, "int", (x, y + 650)), "B": ("1", "int")},
                  (x + 200, y + 650))
        c.color("HudTg%d" % k, on, CHIP_ON, CHIP_OFF, (x, y))
        c.set_text("HudTg%dText" % k, c.fn("SelectString", KML, {"A": ("ON", "string"), "B": ("OFF", "string"),
                                                                 "bPickA": on}, (x + 400, y + 650)), (x + 300, y))
        x += 700
    # look the relay up here too: Characters / Bug Reports only do it while they're open, and
    # Save HUD needs it (opening HUD first left it unset: "Still connecting", 2026-10-27)
    out += c.find_relay((x, y))
    x += 2000
    sv = lambda pos: c.rvar("HudSavedVer", "int", pos)
    bs = c.branch(c.fn("NotEqual_IntInt", KML, {"A": sv((x + 200, y + 450)), "B": c.var("HudMsgSeen", "int", (x + 200, y + 600))},
                       (x + 400, y + 450)), (x + 400, y))
    out.append((bs, "else"))
    c.exits = [(bs, "then")]
    c.set_var("HudMsgSeen", "int", sv((x + 600, y + 300)), (x + 700, y))
    c.set_text("HudStatus", c.rvar("HudMsg", "string", (x + 900, y + 500)), (x + 1000, y))
    return out + c.exits


# ================================================================ clicks
def admin_clicks(c, y):
    g = c.g
    for k in range(N):                                # a switch: on <-> off (sent on Save HUD)
        c.exits = [(clicked(g, "HudTg%d" % k, (0, y)), "then")]
        c.set_var("HudE%d" % k, "int", c.fn("Subtract_IntInt", KML, {"A": ("1", "int"),
                                                                     "B": c.var("HudE%d" % k, "int", (100, y + 250))},
                                            (300, y + 250)), (400, y))
        y += 400
    c.exits = [(clicked(g, "HudReload", (0, y)), "then")]
    c.set_var("HudASeen", "int", "-1", (300, y))
    c.set_text("HudStatus", "Showing what the server has.", (600, y))
    y += 500
    c.exits = [(clicked(g, "HudSave", (0, y)), "then")]
    b = c.branch(c.fn("IsValid", KSL, {"Object": c.relay((100, y + 300))}, (300, y + 300)), (300, y))
    c.exits = [(b, "else")]
    c.set_text("HudStatus", NOT_CONNECTED, (600, y + 400))
    c.exits = [(b, "then")]
    ins = {"On%d" % k: c.var("HudE%d" % k, "int", (500, y + 300 + 150 * k)) for k in range(N)}
    ins.update({"T%d" % j: c.box_text("HudTx%d" % j, (800, y + 300 + 150 * j)) for j in range(len(D.HUD_TEXTS))})
    c.call_relay("OwlServerHudSet", ins, (1200, y))
    c.set_text("HudStatus", "Saving...", (1500, y))
