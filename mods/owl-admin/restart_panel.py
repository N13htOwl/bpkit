"""The admin menu's Server Restart tab (03): the design board's restart panel. A scheduled
restart card (Daily switch, the time with - / +, the server's clock), the player alert preview,
one row per menu_defs.RS_WARNS warning (Preview, on/off), the alert sound chips + Test sound,
then a status line, Reload, Save restart and Start / Cancel countdown.

    admin_layout(u, B, R) -> [(widget, slot props)]     admin_variables(unreal, bel, wbp)
    admin_tick(c, entries, on_page, ctrl, ctrl_cls, y) -> exits   (c: ce_panel._Ctx on CeRelay)
    admin_clicks(c, y)

The values live on the controller (02, restart_ctrl): RsVals, replicated. When its RsVer
differs from RsASeen, the controls (RsE<k>, menu_defs.RS_LIMITS order) load from it. Save sends
them through the admin's relay (OwlServerRsSet, restart_server); the countdown button sends
OwlServerRsCount. The server's answer (OwlClientRsSaved) shows in the status line.
Owl Admin only warns: the host's own schedule restarts the server.
"""
import menu_defs as D
import restart_ctrl
from ce_panel import _text_button, _step, _lab, CHIP_ON, CHIP_OFF, KML, KSL, KSTR
from menu_shell import clicked

N = len(D.RS_LIMITS)
I_DAILY, I_TIME, I_WARN, I_SOUND = restart_ctrl.I_DAILY, restart_ctrl.I_TIME, restart_ctrl.I_WARN, restart_ctrl.I_SOUND
NOT_CONNECTED = "Still connecting to the server. Try again in a moment."
HINT = "Owl Admin only warns players. Set your host's restart to the same time."
START, CANCEL = "Start restart countdown", "Cancel countdown"


def warn_msg(m):
    return "Server will restart in %d %s." % (m, "minute" if m == 1 else "minutes")


# ================================================================ layout
def _card(u, r, inner, accent="#4a1a1d"):
    u.border(r + "Fill", "#120909", 1.0, u.margin(20, 12, 20, 12), inner)
    u.strip(r + "Acc", accent, u.margin(l=3))
    u.box("HorizontalBox", r + "Row", [(r + "Acc", ["VerticalAlignment=VAlign_Fill"]),
                                       (r + "Fill", ["Size=(SizeRule=Fill)", "VerticalAlignment=VAlign_Fill"])])
    return u.border(r, "#2a1012", 1.0, u.margin(1, 1, 1, 1), r + "Row")


def _titled(u, B, R, r, title, desc):
    u.text(r + "Lbl", title, B, 19, "#ffffff", variable=False)
    u.text(r + "Desc", desc, R, 15, "#b8a29c", wrap=True, variable=False)
    return u.box("VerticalBox", r + "Txt", [(r + "Lbl", []), (r + "Desc", ["Padding=%s" % u.margin(t=2)])])


def admin_layout(u, B, R):
    items = []
    mid = ["VerticalAlignment=VAlign_Center"]
    # scheduled restart
    u.text("RsTimeText", "4:00 AM", B, 22, "#ff5a5f")
    u.sized("RsTimeBox", "RsTimeText", w=120, halign="HAlign_Center", valign="VAlign_Center")
    u.box("HorizontalBox", "RsSchedTop", [
        (_titled(u, B, R, "RsSched", "Scheduled restart",
                 "Every day at this time, on the server's clock. The warnings below go out first."),
         ["Size=(SizeRule=Fill)"] + mid),
        (_text_button(u, B, "RsDaily", "OFF", h=40, px=15, pad=18, tinted=True, label_var=True),
         ["Padding=%s" % u.margin(l=24, r=16)] + mid),
        (_step(u, B, "RsTimeDec", "-"), mid),
        ("RsTimeBox", ["Padding=%s" % u.margin(4, 0, 4, 0)] + mid),
        (_step(u, B, "RsTimeInc", "+"), mid)])
    u.text("RsClockText", "Server clock: waiting for the server", R, 15, "#a8908a")
    u.box("VerticalBox", "RsSchedIn", [("RsSchedTop", []), ("RsClockText", ["Padding=%s" % u.margin(t=6)])])
    items.append((_card(u, "RsSchedCard", "RsSchedIn"), ["Padding=%s" % u.margin(b=10)]))
    # the player alert preview (the banner's look)
    u.text("RsPvLabel", "PLAYER ALERT", B, 15, "#f0343a", spacing_px=2, variable=False)
    u.text("RsPreview", "Press Preview on a warning to see it here.", B, 20, "#ffffff", wrap=True)
    u.box("HorizontalBox", "RsPvRow", [("RsPvLabel", ["Padding=%s" % u.margin(r=16)] + mid),
                                       ("RsPreview", ["Size=(SizeRule=Fill)"] + mid)])
    u.border("RsPvFill", "#1a0809", 1.0, u.margin(20, 12, 20, 12), "RsPvRow")
    u.strip("RsPvAcc", "#e5242b", u.margin(l=6))
    u.box("HorizontalBox", "RsPvIn", [("RsPvAcc", ["VerticalAlignment=VAlign_Fill"]),
                                      ("RsPvFill", ["Size=(SizeRule=Fill)", "VerticalAlignment=VAlign_Fill"])])
    u.border("RsPvCard", "#b3121a", 1.0, u.margin(1, 1, 1, 1), "RsPvIn")
    items.append(("RsPvCard", ["Padding=%s" % u.margin(b=10)]))
    # the warnings
    for k, m in enumerate(D.RS_WARNS):
        r = "RsWarn%d" % k
        u.box("HorizontalBox", r + "In", [
            (_titled(u, B, R, r, "%d %s before restart" % (m, "minute" if m == 1 else "minutes"), warn_msg(m)),
             ["Size=(SizeRule=Fill)"] + mid),
            (_text_button(u, B, "RsPv%d" % k, "Preview", h=40, px=15, pad=16), ["Padding=%s" % u.margin(l=16)] + mid),
            (_text_button(u, B, "RsW%d" % k, "OFF", h=40, px=15, pad=18, tinted=True, label_var=True),
             ["Padding=%s" % u.margin(l=10)] + mid)])
        items.append((_card(u, r + "Card", r + "In"), ["Padding=%s" % u.margin(b=8)]))
    # the sound
    row = [(_lab(u, B, "RsSndLbl", "Alert sound"), ["Padding=%s" % u.margin(r=12)] + mid)]
    for k, (label, _p) in enumerate(D.RS_SOUNDS):
        row.append((_text_button(u, B, "RsSnd%d" % k, label, h=38, px=15, pad=14, tinted=True),
                    ["Padding=%s" % u.margin(r=8)] + mid))
    row.append((_text_button(u, B, "RsTest", "Test sound", h=38, px=15, pad=14), ["Padding=%s" % u.margin(l=8)] + mid))
    u.box("HorizontalBox", "RsSndRow", row)
    items.append(("RsSndRow", ["Padding=%s" % u.margin(t=4, b=12)]))
    # status + buttons
    u.text("RsStatus", HINT, R, 16, "#b8a29c", wrap=True)
    u.box("HorizontalBox", "RsFoot", [
        ("RsStatus", ["Size=(SizeRule=Fill)"] + mid),
        (_text_button(u, B, "RsReload", "Reload", h=44, px=16, pad=18), ["Padding=%s" % u.margin(l=16, r=12)] + mid),
        (_text_button(u, B, "RsSave", "Save restart", primary=True, h=44, px=16, pad=18), ["Padding=%s" % u.margin(r=12)] + mid),
        (_text_button(u, B, "RsCount", START, h=44, px=16, pad=18, tinted=True, label_var=True), mid)])
    items.append(("RsFoot", ["Padding=%s" % u.margin(t=6, b=10)]))
    return items


def admin_variables(unreal, bel, wbp):
    i = bel.get_basic_type_by_name("int")
    for var in ["RsE%d" % k for k in range(N)] + ["RsASeen", "RsMsgSeen", "RsCounting"]:
        bel.add_member_variable(wbp, var, i)


# ================================================================ helpers
def _i(c, fn, a, b, pos):
    lit = lambda v: v if isinstance(v, tuple) else (str(v), "int")
    return c.fn(fn, KML, {"A": lit(a), "B": lit(b)}, pos)


def clock_text(c, minutes, pos):
    """"4:05 AM" from minutes after midnight."""
    x, y = pos
    hh = _i(c, "Divide_IntInt", minutes, 60, (x, y))
    mi = _i(c, "Percent_IntInt", minutes, 60, (x, y + 150))
    h12 = _i(c, "Add_IntInt", _i(c, "Percent_IntInt", _i(c, "Add_IntInt", hh, 11, (x + 200, y)), 12, (x + 400, y)), 1,
             (x + 600, y))
    pad = c.fn("SelectString", KML, {"A": ("0", "string"), "B": ("", "string"),
                                     "bPickA": _i(c, "Less_IntInt", mi, 10, (x + 200, y + 150))}, (x + 400, y + 150))
    ampm = c.fn("SelectString", KML, {"A": (" AM", "string"), "B": (" PM", "string"),
                                      "bPickA": _i(c, "Less_IntInt", hh, 12, (x + 200, y + 300))}, (x + 400, y + 300))
    return c.concat([c.fn("Conv_IntToString", KSTR, {"InInt": h12}, (x + 800, y)), ":", pad,
                     c.fn("Conv_IntToString", KSTR, {"InInt": mi}, (x + 800, y + 150)), ampm], (x + 1000, y))


# ================================================================ tick
def admin_tick(c, entries, on_page, ctrl, ctrl_cls, y):
    """Entered from entries (the controller found). ctrl: (node, pin) of the controller."""
    g = c.g
    c.exits = list(entries)

    def cvar(name, pos, arr=False):
        n = g.var_get(name, "int", parent=ctrl_cls, pos=pos)
        if arr:
            n.pin(name).set("PinType.ContainerType", "Array")
        g.wire(ctrl[0], ctrl[1], n, "self", exec=False)
        return (n, name)

    # the server's values changed (or Reload): load the controls
    bv = c.branch(_i(c, "NotEqual_IntInt", cvar("RsVer", (0, y + 300)), c.var("RsASeen", "int", (0, y + 450)),
                     (250, y + 300)), (250, y))
    skip = [(bv, "else")]
    c.exits = [(bv, "then")]
    c.set_var("RsASeen", "int", cvar("RsVer", (400, y + 300)), (500, y))
    x = 800
    for k in range(N):
        c.set_var("RsE%d" % k, "int", c.at(cvar("RsVals", (x, y + 450), arr=True), k, "int", (x + 200, y + 450)),
                  (x + 200, y))
        x += 400
    c.exits += skip
    # on the page: the controls show their values
    bp_ = c.branch(on_page, (x, y))
    out = [(bp_, "else")]
    c.exits = [(bp_, "then")]
    x += 300
    e = lambda k, pos: c.var("RsE%d" % k, "int", pos)

    def switch(btn, k, on_label, pos):
        on = _i(c, "EqualEqual_IntInt", e(k, (pos[0], pos[1] + 650)), 1, (pos[0] + 200, pos[1] + 650))
        c.color(btn, on, CHIP_ON, CHIP_OFF, pos)
        c.set_text(btn + "Text", c.fn("SelectString", KML, {"A": (on_label, "string"), "B": ("OFF", "string"),
                                                            "bPickA": on}, (pos[0] + 400, pos[1] + 650)),
                   (pos[0] + 300, pos[1]))

    switch("RsDaily", I_DAILY, "DAILY", (x, y))
    x += 700
    c.set_text("RsTimeText", clock_text(c, e(I_TIME, (x, y + 500)), (x + 200, y + 500)), (x + 1300, y))
    x += 1700
    clock = cvar("RsClock", (x, y + 500))
    known = c.concat(["Server clock now: ", clock_text(c, clock, (x + 200, y + 700))], (x + 1300, y + 700))
    c.set_text("RsClockText", c.fn("SelectString", KML, {
        "A": known, "B": ("Server clock: waiting for the server", "string"),
        "bPickA": _i(c, "GreaterEqual_IntInt", cvar("RsClock", (x + 1300, y + 900)), 0, (x + 1500, y + 900))},
        (x + 1700, y + 700)), (x + 1800, y))
    x += 2200
    for k in range(len(D.RS_WARNS)):
        switch("RsW%d" % k, I_WARN + k, "SENDING", (x, y))
        x += 700
    for k in range(len(D.RS_SOUNDS)):
        c.color("RsSnd%d" % k, _i(c, "EqualEqual_IntInt", e(I_SOUND, (x, y + 650)), k, (x + 200, y + 650)),
                CHIP_ON, CHIP_OFF, (x, y))
        x += 400
    # the countdown button: Cancel while a countdown is on screen
    counting = _i(c, "GreaterEqual_IntInt", cvar("RsLeft", (x, y + 650)), 0, (x + 200, y + 650))
    c.set_var("RsCounting", "int", c.fn("SelectInt", KML, {"A": ("1", "int"), "B": ("0", "int"), "bPickA": counting},
                                        (x + 400, y + 650)), (x, y))
    c.color("RsCount", counting, CHIP_ON, CHIP_OFF, (x + 300, y))
    c.set_text("RsCountText", c.fn("SelectString", KML, {"A": (CANCEL, "string"), "B": (START, "string"),
                                                         "bPickA": counting}, (x + 700, y + 650)), (x + 700, y))
    x += 1100
    out += c.find_relay((x, y))
    x += 2000
    sv = lambda pos: c.rvar("RsSavedVer", "int", pos)
    bs = c.branch(_i(c, "NotEqual_IntInt", sv((x + 200, y + 450)), c.var("RsMsgSeen", "int", (x + 200, y + 600)),
                     (x + 400, y + 450)), (x + 400, y))
    out.append((bs, "else"))
    c.exits = [(bs, "then")]
    c.set_var("RsMsgSeen", "int", sv((x + 600, y + 300)), (x + 700, y))
    c.set_text("RsStatus", c.rvar("RsMsg", "string", (x + 900, y + 500)), (x + 1000, y))
    return out + c.exits


# ================================================================ clicks
def admin_clicks(c, y):
    g = c.g
    e = lambda k, pos: c.var("RsE%d" % k, "int", pos)

    def on_click(btn):
        c.exits = [(clicked(g, btn, (0, y)), "then")]

    def flip(btn, k):
        on_click(btn)
        c.set_var("RsE%d" % k, "int", _i(c, "Subtract_IntInt", 1, e(k, (100, y + 250)), (300, y + 250)), (400, y))

    flip("RsDaily", I_DAILY)
    y += 400
    for btn, step in (("RsTimeDec", -D.RS_STEP), ("RsTimeInc", D.RS_STEP)):
        on_click(btn)
        c.set_var("RsE%d" % I_TIME, "int", _i(c, "Percent_IntInt", _i(c, "Add_IntInt", e(I_TIME, (100, y + 250)),
                                                                      1440 + step, (300, y + 250)), 1440, (500, y + 250)),
                  (600, y))
        y += 400
    for k, m in enumerate(D.RS_WARNS):
        flip("RsW%d" % k, I_WARN + k)
        y += 400
        on_click("RsPv%d" % k)                       # the message in the preview strip, with the sound
        c.set_text("RsPreview", warn_msg(m), (300, y))
        restart_ctrl.play_chosen(c, e(I_SOUND, (500, y + 300)), (700, y))
        y += 500
    for k in range(len(D.RS_SOUNDS)):
        on_click("RsSnd%d" % k)
        c.set_var("RsE%d" % I_SOUND, "int", str(k), (300, y))
        y += 400
    on_click("RsTest")
    restart_ctrl.play_chosen(c, e(I_SOUND, (100, y + 300)), (300, y))
    y += 500
    on_click("RsReload")
    c.set_var("RsASeen", "int", "-1", (300, y))
    c.set_text("RsStatus", "Showing what the server has.", (600, y))
    y += 500

    def send(btn, event, ins, msg):
        nonlocal y
        on_click(btn)
        b = c.branch(c.fn("IsValid", KSL, {"Object": c.relay((100, y + 300))}, (300, y + 300)), (300, y))
        c.exits = [(b, "else")]
        c.set_text("RsStatus", NOT_CONNECTED, (600, y + 400))
        c.exits = [(b, "then")]
        c.call_relay(event, ins, (1200, y))
        c.set_text("RsStatus", msg, (1500, y))
        y += 600

    send("RsSave", "OwlServerRsSet", {"V%d" % k: e(k, (500, y + 300 + 150 * k)) for k in range(N)}, "Saving...")
    send("RsCount", "OwlServerRsCount",
         {"Start": _i(c, "Subtract_IntInt", 1, c.var("RsCounting", "int", (500, y + 300)), (700, y + 300))},
         "Sending...")
