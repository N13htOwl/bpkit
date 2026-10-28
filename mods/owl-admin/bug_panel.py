"""Bug reports, the two menus' side (server side: bug_server.py).

Player menu (07), the Bug Report tab -- the Bug Report board:
    BugGate (WidgetSwitcher)
        0 form: kind chips (menu_defs.BUG_CATS), Short title, What happened? (multi-line), the
          error line | "Sent with your report": mod version, time, location (the server adds its
          name, the character and the account) | Clear, Send report
        1 sent: "Report sent. Thank you." | Report another
    player_layout(u, B, R) -> [(widget, slot props)]     player_variables(unreal, bel, wbp)
    player_tick(c, y)   (c: ce_panel._Ctx on MyRelay; enters/leaves through c.exits)
    player_clicks(c, y)
    bake_player(cdo)
Send report checks a kind and a title first (the server checks the title and the wait again),
then calls MyRelay.OwlServerBugReport; the answer (OwlClientBugSent) raises the relay's
BugSentVer: sent -> page 1 and a clean form; refused -> its message on the error line.

Admin menu (03), the Bug Reports tab:
    count line + Refresh | one row per report, newest first (BUG_ROWS): kind tag, title,
    Mark done / Reopen | character (account), time, location, server | the text
    admin_layout(u, B, R)    admin_variables(unreal, bel, wbp)
    admin_tick(c, entries, unlocked, on_page, y) -> exits    (c: ce_panel._Ctx on CeRelay)
    admin_clicks(c, y)
While unlocked and on the page: OwlServerBugList every ASK_SECONDS (Refresh asks at once);
the relay's BugVer changed -> redraw the rows.
"""
from bpkit import ir
import menu_defs as D
import oa_config as MOD
from ce_panel import (_text_button, _chips, _field, _lab, CHIP_ON, CHIP_OFF, KML, KSTR, KTXT, KSL, TEXT, WIDGET,
                      SWITCHER, ETB, SLATEVIS)
from menu_shell import framed, clicked

MLETB = "/Script/UMG.MultiLineEditableTextBox"
UW = "/Script/UMG.UserWidget"
BUG_ROWS = MOD.BUG_MAX
ASK_SECONDS = 5.0
NOT_CONNECTED = "Still connecting to the server. Try again in a moment."
# a report line's fields (bug_server)
F_TIME, F_CHAR, F_SERVER, F_KIND, F_TITLE, F_WHERE, F_ACCT, F_TEXT = range(8)


# ================================================================ player menu
def _multiline(u, R, name, hint, h):
    u.widget(MLETB, name, [
        'HintText=INVTEXT("%s")' % u.quote(hint),
        "WidgetStyle=(BackgroundImageNormal=%s,BackgroundImageHovered=%s,BackgroundImageFocused=%s,"
        "Padding=%s,ForegroundColor=(SpecifiedColor=%s),"
        "TextStyle=(Font=%s,ColorAndOpacity=(SpecifiedColor=%s)))" % (
            u.brush("#120909"), u.brush("#1a0c0c"), u.brush("#1a0c0c"), u.margin(14, 10, 14, 10), u.lin("#f2e6e2"),
            u.font(R, 18), u.lin("#f2e6e2")),
        "AutoWrapText=True"], variable=True)
    framed(u, name + "Frame", "#4a1a1d", "#120909", name, u.margin())
    return u.sized(name + "Size", name + "Frame", h=h)


def _fact(u, B, R, key, label, value):
    """A "label ... value" line of the side column (value: a TextBlock the graph may set)."""
    u.text(key + "Lbl", label, R, 16, "#b8a29c", variable=False)
    u.text(key + "Val", value, B, 16, "#f2e6e2", wrap=True)
    return u.box("HorizontalBox", key, [(key + "Lbl", ["VerticalAlignment=VAlign_Top"]),
                                        (key + "Val", ["Size=(SizeRule=Fill)", "Padding=%s" % u.margin(l=10),
                                                       "HorizontalAlignment=HAlign_Right"])])


def player_layout(u, B, R):
    gap = lambda px: ["Padding=%s" % u.margin(b=px)]
    _chips(u, B, "BugChips", "BugCat_", [("c%d" % k, label) for k, label in enumerate(D.BUG_CATS)])
    u.text("BugErr", "", B, 17, "#ff7a7e", wrap=True)
    form = u.box("VerticalBox", "BugForm", [
        (_lab(u, B, "BugKindLab", "What kind of bug?"), gap(8)), ("BugChips", gap(6)),
        (_lab(u, B, "BugTitleLab", "Short title"), gap(8)), (_field(u, R, "BugTitle", "One line about the problem"), gap(12)),
        (_lab(u, B, "BugDescLab", "What happened?"), gap(8)),
        (_multiline(u, R, "BugDesc", "What did you expect, and what happened instead? What were you doing just before?",
                    130), gap(10)),     # 170 pushed Clear/Send below the page at 1080p
        ("BugErr", [])])
    u.text("BugNote", "Reports go to the server admins only. The server adds its name, your character and "
                      "your account, so they can follow up.", R, 15, "#a8908a", wrap=True, variable=False)
    u.strip("BugSideLine", "#2a1012", u.margin(t=1))
    side = u.box("VerticalBox", "BugSideList", [
        (_lab(u, B, "BugSideLab", "Sent with your report"), gap(10)),
        (_fact(u, B, R, "BugVer", "Mod version", MOD.VERSION_NAME), gap(6)),
        (_fact(u, B, R, "BugTime", "Time", ""), gap(6)),
        (_fact(u, B, R, "BugWhere", "Location", ""), gap(12)),
        ("BugSideLine", gap(12)), ("BugNote", [])])
    u.border("BugSide", "#0a0505", 1.0, u.margin(16, 14, 16, 14), side)
    u.sized("BugSideBox", "BugSide", w=230)
    u.box("HorizontalBox", "BugBody", [
        (form, ["Size=(SizeRule=Fill)", "Padding=%s" % u.margin(r=16), "VerticalAlignment=VAlign_Top"]),
        ("BugSideBox", ["VerticalAlignment=VAlign_Top"])])
    u.box("HorizontalBox", "BugFoot", [
        (_text_button(u, B, "BugClear", "Clear", h=44, px=16, pad=18), ["Padding=%s" % u.margin(r=12)]),
        (_text_button(u, B, "BugSend", "Send report", primary=True, h=44, px=16, pad=18), [])])
    u.strip("BugFootLine", "#b3121a", u.margin(t=2))
    u.box("VerticalBox", "BugFormPage", [("BugBody", gap(14)), ("BugFootLine", gap(12)),
                                         ("BugFoot", ["HorizontalAlignment=HAlign_Right"])])
    # sent
    u.text("BugSentMsg", "Report sent. Thank you.", B, 22, "#ffffff", variable=False)
    u.border("BugSentFill", "#150909", 1.0, u.margin(28, 18, 28, 18), "BugSentMsg")
    u.strip("BugSentAcc", "#ffffff", u.margin(l=6))
    u.box("HorizontalBox", "BugSentIn", [("BugSentAcc", ["VerticalAlignment=VAlign_Fill"]), ("BugSentFill", [])])
    u.border("BugSentBox", "#8a2a2e", 1.0, u.margin(1, 1, 1, 1), "BugSentIn")
    u.text("BugSentNote", "Server admins can now see it.", R, 18, "#b8a29c", variable=False)
    u.box("VerticalBox", "BugDonePage", [
        ("BugSentBox", ["HorizontalAlignment=HAlign_Center", "Padding=%s" % u.margin(t=60, b=16)]),
        ("BugSentNote", ["HorizontalAlignment=HAlign_Center", "Padding=%s" % u.margin(b=16)]),
        (_text_button(u, B, "BugAgain", "Report another", h=44, px=16, pad=18), ["HorizontalAlignment=HAlign_Center"])])
    u.widget(SWITCHER, "BugGate", ["ActiveWidgetIndex=0"],
             [("/Script/UMG.WidgetSwitcherSlot", w, ["HorizontalAlignment=HAlign_Fill", "VerticalAlignment=VAlign_Top"])
              for w in ("BugFormPage", "BugDonePage")], variable=True)
    return [("BugGate", [])]


def player_variables(unreal, bel, wbp):
    i, s = bel.get_basic_type_by_name("int"), bel.get_basic_type_by_name("string")
    for var, t in (("BugCat", i), ("BugSeen", i), ("BugWhereStr", s), ("BugCatNames", bel.get_array_type(s))):
        bel.add_member_variable(wbp, var, t)


def bake_player(cdo):
    cdo.set_editor_property("BugCatNames", list(D.BUG_CATS))
    cdo.set_editor_property("BugCat", -1)


def _err(c, text, pos):
    c.set_text("BugErr", text, pos)


def _clear_form(c, pos):
    x, y = pos
    for k, (w, cls) in enumerate((("BugTitle", ETB), ("BugDesc", MLETB))):
        st = c.g.call("SetText", cls, pos=(x + 300 * k, y))
        r = c.widget(w, cls, (x + 300 * k - 200, y + 200))
        c.g.wire(r[0], r[1], st, "self", exec=False)
        c.go(st)
    c.set_var("BugCat", "int", "-1", (x + 600, y))
    _err(c, "", (x + 900, y))


def _gate(c, index, pos):
    sai = c.g.call("SetActiveWidgetIndex", SWITCHER, pos=pos)
    if index:
        c.g.typed_input(sai, "Index", str(index), "int")
    w = c.widget("BugGate", SWITCHER, (pos[0] - 200, pos[1] + 200))
    c.g.wire(w[0], w[1], sai, "self", exec=False)
    c.go(sai)


def player_tick(c, y):
    g = c.g
    # the time and where the player is, every frame
    dt = c.fn("AsDateTime_DateTime", KTXT, {"In": c.fn("Now", KML, {}, (0, y + 300))}, (200, y + 300))
    c.set_text("BugTimeVal", c.fn("Conv_TextToString", KTXT, {"InText": dt}, (400, y + 300)), (400, y))
    pawn = c.fn("GetOwningPlayerPawn", UW, {}, (600, y + 300))
    bp_ = c.branch(c.fn("IsValid", KSL, {"Object": pawn}, (800, y + 300)), (800, y))
    c.exits = [(bp_, "then")]
    loc = c.fn("K2_GetActorLocation", "/Script/Engine.Actor", {"self": pawn}, (900, y + 450))
    brk = g.call("BreakVector", KML, pos=(1100, y + 450))
    g.wire(loc[0], loc[1], brk, "InVec", exec=False)
    where = c.concat([c.int_text(c.fn("Round", KML, {"A": (brk, "X")}, (1300, y + 450)), (1500, y + 450)), ", ",
                      c.int_text(c.fn("Round", KML, {"A": (brk, "Y")}, (1300, y + 600)), (1500, y + 600))],
                     (1700, y + 450))
    c.set_var("BugWhereStr", "string", where, (1100, y))
    c.set_text("BugWhereVal", c.var("BugWhereStr", "string", (1300, y + 750)), (1400, y))
    ends = c.exits
    c.exits = [(bp_, "else")]
    c.set_var("BugWhereStr", "string", "", (1100, y + 300))
    c.set_text("BugWhereVal", "Unknown", (1400, y + 300))
    c.exits += ends
    # the kind chips
    x = 2000
    for k in range(len(D.BUG_CATS)):
        eq = c.fn("EqualEqual_IntInt", KML, {"A": c.var("BugCat", "int", (x + 300 * k, y + 900)), "B": (str(k), "int")},
                  (x + 300 * k, y + 800))
        c.color("BugCat_c%d" % k, eq, CHIP_ON, CHIP_OFF, (x + 300 * k, y))
    # the server answered a report
    x += 300 * len(D.BUG_CATS) + 200
    rv = c.branch(c.fn("IsValid", KSL, {"Object": c.relay((x - 200, y + 300))}, (x, y + 300)), (x, y))
    skip = [(rv, "else")]
    c.exits = [(rv, "then")]
    ver = lambda pos: c.rvar("BugSentVer", "int", pos)
    bv = c.branch(c.fn("NotEqual_IntInt", KML, {"A": ver((x + 200, y + 450)), "B": c.var("BugSeen", "int", (x + 200, y + 600))},
                       (x + 400, y + 450)), (x + 400, y))
    skip.append((bv, "else"))
    c.exits = [(bv, "then")]
    c.set_var("BugSeen", "int", ver((x + 600, y + 300)), (x + 700, y))
    bo = c.branch(c.rvar("BugOk", "bool", (x + 900, y + 300)), (x + 1000, y))
    c.exits = [(bo, "then")]
    _gate(c, 1, (x + 1300, y))
    _clear_form(c, (x + 1600, y))
    ends = c.exits
    c.exits = [(bo, "else")]
    _err(c, c.rvar("BugMsg", "string", (x + 1200, y + 700)), (x + 1300, y + 500))
    c.exits += ends + skip


def player_clicks(c, y):
    g = c.g
    for k in range(len(D.BUG_CATS)):
        c.exits = [(clicked(g, "BugCat_c%d" % k, (0, y)), "then")]
        c.set_var("BugCat", "int", str(k), (300, y))
        _err(c, "", (600, y))
        y += 300
    c.exits = [(clicked(g, "BugClear", (0, y)), "then")]
    _clear_form(c, (300, y))
    y += 500
    c.exits = [(clicked(g, "BugAgain", (0, y)), "then")]
    _gate(c, 0, (300, y))
    _err(c, "", (600, y))
    y += 500
    # Send report: a kind, a title, a relay -> OwlServerBugReport
    c.exits = [(clicked(g, "BugSend", (0, y)), "then")]
    b1 = c.branch(c.fn("Less_IntInt", KML, {"A": c.var("BugCat", "int", (200, y + 300)), "B": ("0", "int")},
                       (300, y + 300)), (300, y))
    c.exits = [(b1, "then")]
    _err(c, "Pick what kind of bug it is.", (600, y - 300))
    c.exits = [(b1, "else")]
    title = c.fn("Trim", KSTR, {"SourceString": c.box_text("BugTitle", (400, y + 500))}, (800, y + 500))
    b2 = c.branch(c.fn("EqualEqual_IntInt", KML, {"A": c.fn("Len", KSTR, {"S": title}, (1000, y + 500)), "B": ("0", "int")},
                       (1200, y + 500)), (1200, y))
    c.exits = [(b2, "then")]
    _err(c, "Add a short title.", (1500, y - 300))
    c.exits = [(b2, "else")]
    b3 = c.branch(c.fn("IsValid", KSL, {"Object": c.relay((1300, y + 300))}, (1500, y + 300)), (1600, y))
    c.exits = [(b3, "else")]
    _err(c, NOT_CONNECTED, (1900, y - 300))
    c.exits = [(b3, "then")]
    desc = c.fn("Conv_TextToString", KTXT, {"InText": c.fn("GetText", MLETB, {"self": c.widget("BugDesc", MLETB, (1700, y + 900))},
                                                         (1900, y + 900))}, (2100, y + 900))
    kind = c.at(c.arr("BugCatNames", "string", (1700, y + 600)), c.var("BugCat", "int", (1700, y + 750)), "string",
                (1900, y + 600))
    c.call_relay("OwlServerBugReport", {"Kind": kind, "Title": c.box_text("BugTitle", (1900, y + 1050)), "Text": desc,
                                        "Where": c.var("BugWhereStr", "string", (2100, y + 1200))}, (2300, y))
    _err(c, "Sending your report...", (2600, y))


# ================================================================ admin menu
def admin_layout(u, B, R):
    u.text("BugACount", "Asking the server for the reports...", B, 18, "#f2e6e2", wrap=True)
    u.box("HorizontalBox", "BugAHead", [
        ("BugACount", ["Size=(SizeRule=Fill)", "VerticalAlignment=VAlign_Center"]),
        (_text_button(u, B, "BugARefresh", "Refresh", h=40, px=15, pad=14), ["VerticalAlignment=VAlign_Center"])])
    items = [("BugAHead", ["Padding=%s" % u.margin(b=12)])]
    u.text("BugAEmpty", "No reports yet.", R, 17, "#a8908a", variable=True)
    items.append(("BugAEmpty", ["Padding=%s" % u.margin(b=8)]))
    for k in range(BUG_ROWS):
        u.text("BugAK%d" % k, "", B, 14, "#ffffff", spacing_px=1)
        u.border("BugAKBg%d" % k, "#3a0b0e", 1.0, u.margin(8, 2, 8, 2), "BugAK%d" % k)
        u.text("BugAT%d" % k, "", B, 19, "#ffffff", wrap=True)
        u.box("HorizontalBox", "BugATop%d" % k, [
            ("BugAKBg%d" % k, ["VerticalAlignment=VAlign_Center"]),
            ("BugAT%d" % k, ["Size=(SizeRule=Fill)", "Padding=%s" % u.margin(l=10, r=10), "VerticalAlignment=VAlign_Center"]),
            (_text_button(u, B, "BugAB%d" % k, "Mark done", h=36, px=14, pad=12, tinted=True, label_var=True),
             ["VerticalAlignment=VAlign_Center"])])
        u.text("BugAM%d" % k, "", R, 15, "#b8a29c", wrap=True)
        u.text("BugAX%d" % k, "", R, 17, "#f2e6e2", wrap=True)
        u.box("VerticalBox", "BugAIn%d" % k, [("BugATop%d" % k, []), ("BugAM%d" % k, ["Padding=%s" % u.margin(t=4)]),
                                              ("BugAX%d" % k, ["Padding=%s" % u.margin(t=6)])])
        u.border("BugAFill%d" % k, "#120909", 1.0, u.margin(14, 10, 14, 10), "BugAIn%d" % k)
        u.strip("BugAAcc%d" % k, "#4a1a1d", u.margin(l=3))
        u.box("HorizontalBox", "BugARow%d" % k, [("BugAAcc%d" % k, ["VerticalAlignment=VAlign_Fill"]),
                                                 ("BugAFill%d" % k, ["Size=(SizeRule=Fill)", "VerticalAlignment=VAlign_Fill"])],
              props=["Visibility=Collapsed"], variable=True)
        items.append(("BugARow%d" % k, ["Padding=%s" % u.margin(b=8)]))
    return items


def admin_variables(unreal, bel, wbp):
    for var, t in (("BugAskAt", "real"), ("BugASeen", "int"), ("BugAOpen", "int")):
        bel.add_member_variable(wbp, var, bel.get_basic_type_by_name(t))


def admin_tick(c, entries, unlocked, on_page, y):
    g = c.g
    c.exits = list(entries)
    b = c.branch(c.fn("BooleanAND", KML, {"A": unlocked, "B": on_page}, (0, y + 250)), (200, y))
    out = [(b, "else")]
    c.exits = [(b, "then")]
    out += c.find_relay((400, y))
    # every ASK_SECONDS: the list
    x = 2600
    now = c.fn("GetGameTimeInSeconds", KSL, {}, (x, y + 300))
    bd = c.branch(c.fn("Greater_DoubleDouble", KML, {"A": now, "B": c.var("BugAskAt", "real", (x, y + 450))},
                       (x + 250, y + 300)), (x + 250, y))
    c.exits = [(bd, "then")]
    c.set_var("BugAskAt", "real", c.fn("Add_DoubleDouble", KML, {"A": now, "B": (str(ASK_SECONDS), "real")},
                                       (x + 500, y + 300)), (x + 550, y))
    c.call_relay("OwlServerBugList", {}, (x + 850, y))
    c.exits += [(bd, "else")]
    # the list changed: redraw the rows, newest first
    x = 4000
    bv = c.branch(c.fn("NotEqual_IntInt", KML, {"A": c.rvar("BugVer", "int", (x, y + 300)),
                                                "B": c.var("BugASeen", "int", (x, y + 450))}, (x + 250, y + 300)),
                  (x + 250, y))
    out.append((bv, "else"))
    c.exits = [(bv, "then")]
    c.set_var("BugASeen", "int", c.rvar("BugVer", "int", (x + 400, y + 300)), (x + 500, y))
    c.set_var("BugAOpen", "int", "0", (x + 800, y))
    lines = lambda pos: c.rvar("BugLines", "string", pos, arr=True)
    for k in range(BUG_ROWS):
        xk = x + 1100 + 2400 * k
        ln = g.array_len(lines((xk, y + 600))[0], "BugLines", (xk + 200, y + 600), elem_cat="string")
        bk = c.branch(c.fn("Less_IntInt", KML, {"A": (str(k), "int"), "B": (ln, "ReturnValue")}, (xk + 200, y + 450)),
                      (xk, y))
        c.exits = [(bk, "then")]
        c.set_vis("BugARow%d" % k, "/Script/UMG.HorizontalBox", "Visible", (xk + 250, y))
        at = c.fn("Subtract_IntInt", KML, {"A": (ln, "ReturnValue"), "B": (str(k + 1), "int")}, (xk + 400, y + 750))
        line = g.array_get(lines((xk + 400, y + 900))[0], "BugLines", at, (xk + 600, y + 900), elem_cat="string")
        parts = c.split((line, "Output"), (xk + 800, y + 900))
        f = lambda n, dy: (g.array_get(parts, "ReturnValue", n, (xk + 1000, y + 1000 + dy), elem_cat="string"), "Output")
        # no server name (Play in the editor has none): show "-" rather than a trailing dot
        srv = f(F_SERVER, 900)
        srv = c.fn("SelectString", KML, {
            "A": ("-", "string"), "B": srv,
            "bPickA": c.fn("EqualEqual_IntInt", KML, {"A": c.fn("Len", KSTR, {"S": srv}, (xk + 1200, y + 1350)),
                                                       "B": ("0", "int")}, (xk + 1350, y + 1350))},
            (xk + 1500, y + 1350))
        c.set_text("BugAK%d" % k, c.fn("ToUpper", KSTR, {"SourceString": f(F_KIND, 0)}, (xk + 1200, y + 1000)), (xk + 500, y))
        c.set_text("BugAT%d" % k, f(F_TITLE, 150), (xk + 800, y))
        c.set_text("BugAM%d" % k, c.concat([f(F_CHAR, 300), " (", f(F_ACCT, 450), ")  ·  ", f(F_TIME, 600), "  ·  at ",
                                           f(F_WHERE, 750), "  ·  ", srv], (xk + 1200, y + 1200)), (xk + 1100, y))
        c.set_text("BugAX%d" % k, f(F_TEXT, 1050), (xk + 1400, y))
        done = c.fn("EqualEqual_IntInt", KML, {
            "A": c.at(c.rvar("BugDone", "int", (xk + 1400, y + 1500), arr=True), at, "int", (xk + 1600, y + 1500)),
            "B": ("1", "int")}, (xk + 1800, y + 1500))
        c.set_text("BugAB%dText" % k, c.fn("SelectString", KML, {"A": ("Reopen", "string"), "B": ("Mark done", "string"),
                                                                 "bPickA": done}, (xk + 1800, y + 1650)), (xk + 1700, y))
        c.color("BugAB%d" % k, done, CHIP_OFF, CHIP_ON, (xk + 2000, y))
        bo = c.branch(done, (xk + 2200, y))
        c.exits = [(bo, "else")]                    # an open report: count it
        c.bump("BugAOpen", (xk + 2300, y + 300))
        ends = c.exits + [(bo, "then")]
        c.exits = [(bk, "else")]
        c.set_vis("BugARow%d" % k, "/Script/UMG.HorizontalBox", "Collapsed", (xk + 250, y + 300))
        c.exits += ends
    x += 1100 + 2400 * BUG_ROWS
    total = g.array_len(lines((x, y + 600))[0], "BugLines", (x + 200, y + 600), elem_cat="string")
    c.set_text("BugACount", c.concat([c.int_text(c.var("BugAOpen", "int", (x, y + 300)), (x + 200, y + 300)), " open  ·  ",
                                      c.items_text((total, "ReturnValue"), (x + 200, y + 450))], (x + 400, y + 300)),
               (x + 400, y))
    c.vis_if(c.fn("EqualEqual_IntInt", KML, {"A": (total, "ReturnValue"), "B": ("0", "int")}, (x + 600, y + 600)),
             [("BugAEmpty", TEXT)], (x + 800, y))
    return out + c.exits


def admin_clicks(c, y):
    g = c.g
    c.exits = [(clicked(g, "BugARefresh", (0, y)), "then")]
    c.set_var("BugAskAt", "real", "0.0", (300, y))
    y += 400
    lines = lambda pos: c.rvar("BugLines", "string", pos, arr=True)
    for k in range(BUG_ROWS):
        c.exits = [(clicked(g, "BugAB%d" % k, (0, y)), "then")]
        ok = c.fn("IsValid", KSL, {"Object": c.relay((100, y + 300))}, (300, y + 300))
        b = c.branch(ok, (300, y))
        c.exits = [(b, "then")]
        ln = g.array_len(lines((400, y + 450))[0], "BugLines", (600, y + 450), elem_cat="string")
        b2 = c.branch(c.fn("Less_IntInt", KML, {"A": (str(k), "int"), "B": (ln, "ReturnValue")}, (700, y + 450)), (700, y))
        c.exits = [(b2, "then")]
        at = c.fn("Subtract_IntInt", KML, {"A": (ln, "ReturnValue"), "B": (str(k + 1), "int")}, (800, y + 600))
        line = c.at(lines((900, y + 750)), at, "string", (1100, y + 750))
        flip = c.fn("Subtract_IntInt", KML, {"A": ("1", "int"),
                                             "B": c.at(c.rvar("BugDone", "int", (900, y + 900), arr=True), at, "int",
                                                       (1100, y + 900))}, (1300, y + 900))
        c.call_relay("OwlServerBugDone", {"Line": line, "Done": flip}, (1500, y))
        y += 1200
