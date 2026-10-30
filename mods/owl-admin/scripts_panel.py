"""Scripting in the admin menu (03): the Scripting page. N_SCRIPTS command scripts (a chip per
script, its name, SCRIPT_LINES one-line command boxes, Save script / Run script), then a console
line (Run) with the last HIST commands, and a status line.

    admin_layout(u, B, R) -> [(widget, slot props)]     admin_variables(unreal, bel, wbp)
    admin_tick(c, entries, unlocked, on_page, y) -> exits     admin_clicks(c, y)
    (c: ce_panel._Ctx on the menu's relay variable)

The scripts come from the server (scripts_server: OwlServerScGet when the page opens, OwlClientSc
answers into the relay's ScNamesC / ScLinesC / ScMsg / ScVer); Save script sends the boxes
(OwlServerScSave). Run script and the console line run on this client: each non-empty line goes
to ExecuteConsoleCommand as the owning player, exactly as if typed in the console, so the game
decides what is allowed. Each run is a line in the admin's own log (OwlServerScRan).
"""
import menu_defs as D
from ce_panel import _text_button, _lab, _field, ETB, KML, KSL, KSTR, CHIP_ON, CHIP_OFF
from kits_panel import _set_box_text
from menu_shell import clicked

N, L = D.N_SCRIPTS, D.SCRIPT_LINES
HIST = 5
LOADING = "Still loading the scripts. Try again in a moment."
NOTE = ("Commands run from your own console, as if you typed them, so the game decides what you may "
        "run: its admin commands also need you to be a Conan admin. One command per line; empty lines "
        "are skipped.")


def _i(c, fn, a, b, pos):
    lit = lambda v: v if isinstance(v, tuple) else (str(v), "int")
    return c.fn(fn, KML, {"A": lit(a), "B": lit(b)}, pos)


def admin_layout(u, B, R):
    u.box("WrapBox", "ScTabs", [
        (_text_button(u, B, "ScTab%d" % k, "Script %d" % (k + 1), h=40, px=15, pad=14, tinted=True, label_var=True),
         ["Padding=%s" % u.margin(r=8, b=8)]) for k in range(N)])
    items = [(_lab(u, B, "ScLab", "Scripts"), ["Padding=%s" % u.margin(b=8)]),
             ("ScTabs", ["Padding=%s" % u.margin(b=4)]),
             (_field(u, R, "ScName", "Script name"), ["Padding=%s" % u.margin(b=10)])]
    for j in range(L):
        items.append((_field(u, R, "ScLine%d" % j, "Command %d" % (j + 1)), ["Padding=%s" % u.margin(b=6)]))
    u.box("WrapBox", "ScBtns", [
        (_text_button(u, B, "ScSave", "Save script", h=44, px=15, pad=16), ["Padding=%s" % u.margin(l=10, b=8)]),
        (_text_button(u, B, "ScRun", "Run script", primary=True, h=44, px=15, pad=16), ["Padding=%s" % u.margin(l=10, b=8)])])
    u.text("ScStatus", "", R, 17, "#f2e6e2", wrap=True)
    items += [("ScBtns", ["HorizontalAlignment=HAlign_Right", "Padding=%s" % u.margin(t=4)]),
              ("ScStatus", ["Padding=%s" % u.margin(b=12)]),
              (_lab(u, B, "ScConLab", "Console"), ["Padding=%s" % u.margin(b=8)])]
    u.box("HorizontalBox", "ScConRow", [
        (_field(u, R, "ScCmd", "Type a console command"), ["Size=(SizeRule=Fill)", "VerticalAlignment=VAlign_Center"]),
        (_text_button(u, B, "ScCmdRun", "Run", primary=True, h=44, px=15, pad=18),
         ["Padding=%s" % u.margin(l=10), "VerticalAlignment=VAlign_Center"])])
    items.append(("ScConRow", ["Padding=%s" % u.margin(b=8)]))
    for k in range(HIST):
        u.text("ScH%d" % k, "", R, 16, "#b8a29c", wrap=True)
        items.append(("ScH%d" % k, ["Padding=%s" % u.margin(b=2)]))
    u.text("ScNote", NOTE, R, 15, "#a8908a", wrap=True, variable=False)
    return items + [("ScNote", ["Padding=%s" % u.margin(t=10)])]


def admin_variables(unreal, bel, wbp):
    i, s, b = (bel.get_basic_type_by_name(t) for t in ("int", "string", "bool"))
    for var, t in (("ScSel", i), ("ScShown", i), ("ScASeen", i), ("ScAsked", b), ("ScRunN", i),
                   ("ScTmp", bel.get_array_type(s)), ("ScHist", bel.get_array_type(s))):
        bel.add_member_variable(wbp, var, t)


def admin_tick(c, entries, unlocked, on_page, y):
    """While unlocked with the page up: ask for the scripts once per opening; on an answer, its
    message and a redraw; when the picked script changes, its name and lines into the boxes."""
    c.exits = list(entries)
    b = c.branch(c.fn("BooleanAND", KML, {"A": unlocked, "B": on_page}, (0, y + 300)), (200, y))
    c.exits = [(b, "else")]
    c.set_var("ScAsked", "bool", "false", (500, y + 700))
    out = c.exits
    c.exits = [(b, "then")]
    out += c.find_relay((500, y))
    ba = c.branch(c.fn("Not_PreBool", KML, {"A": c.var("ScAsked", "bool", (2400, y + 300))}, (2600, y + 300)), (2600, y))
    c.exits = [(ba, "then")]
    c.call_relay("OwlServerScGet", {}, (2900, y))
    c.set_var("ScAsked", "bool", "true", (3200, y))
    c.exits += [(ba, "else")]
    # an answer: its message, then redraw
    x = 3600
    bv = c.branch(_i(c, "NotEqual_IntInt", c.rvar("ScVer", "int", (x, y + 300)), c.var("ScASeen", "int", (x, y + 450)),
                     (x + 200, y + 300)), (x + 200, y))
    skip = [(bv, "else")]
    c.exits = [(bv, "then")]
    c.set_var("ScASeen", "int", c.rvar("ScVer", "int", (x + 300, y + 300)), (x + 500, y))
    c.set_var("ScShown", "int", "-1", (x + 800, y))
    bm = c.branch(_i(c, "Greater_IntInt", c.fn("Len", KSTR, {"S": c.rvar("ScMsg", "string", (x + 900, y + 450))},
                                                (x + 1100, y + 450)), 0, (x + 1300, y + 450)), (x + 1100, y))
    c.exits = [(bm, "then")]
    c.set_text("ScStatus", c.rvar("ScMsg", "string", (x + 1300, y + 600)), (x + 1400, y))
    c.exits += [(bm, "else")] + skip
    # the picked script changed (or must be redrawn)
    x = 5400
    sel = lambda pos: c.var("ScSel", "int", pos)
    bs = c.branch(_i(c, "NotEqual_IntInt", sel((x, y + 300)), c.var("ScShown", "int", (x, y + 450)), (x + 200, y + 300)),
                  (x + 200, y))
    skip = [(bs, "else")]
    c.exits = [(bs, "then")]
    c.set_var("ScShown", "int", sel((x + 300, y + 300)), (x + 500, y))
    names = lambda pos: c.rvar("ScNamesC", "string", pos, arr=True)
    _set_box_text(c, "ScName", c.at(names((x + 600, y + 600)), sel((x + 600, y + 750)), "string", (x + 800, y + 600)),
                  (x + 900, y))
    x += 1300
    for j in range(L):
        idx = _i(c, "Multiply_IntInt", sel((x, y + 900)), L, (x + 200, y + 900))
        if j:  # (a pasted B of 0 comes back as Add_IntInt's own default, 1)
            idx = _i(c, "Add_IntInt", idx, j, (x + 400, y + 900))
        _set_box_text(c, "ScLine%d" % j, c.at(c.rvar("ScLinesC", "string", (x, y + 600), arr=True), idx, "string",
                                              (x + 200, y + 600)), (x + 300, y))
        x += 700
    for k in range(N):
        on = _i(c, "EqualEqual_IntInt", sel((x, y + 600)), k, (x + 200, y + 600))
        c.color("ScTab%d" % k, on, CHIP_ON, CHIP_OFF, (x, y))
        nm = c.at(names((x + 300, y + 900)), k, "string", (x + 500, y + 900))
        named = _i(c, "Greater_IntInt", c.fn("Len", KSTR, {"S": nm}, (x + 700, y + 1050)), 0, (x + 900, y + 1050))
        c.set_text("ScTab%dText" % k, c.fn("SelectString", KML, {"A": nm, "B": ("Script %d" % (k + 1), "string"),
                                                                   "bPickA": named}, (x + 900, y + 900)), (x + 400, y))
        x += 1200
    c.exits += skip
    return out + c.exits


def _run(c, cmd, pos):
    """ExecuteConsoleCommand(cmd) as the owning player, in the exec chain."""
    g = c.g
    ex = g.call("ExecuteConsoleCommand", KSL, pos=pos)
    g.wire(cmd[0], cmd[1], ex, "Command", exec=False)
    g.wire(c.owning_player((pos[0] - 200, pos[1] + 300)), "ReturnValue", ex, "SpecificPlayer", exec=False)
    c.go(ex)


def _trimmed(c, box, pos):
    return c.fn("Trim", KSTR, {"SourceString": c.box_text(box, pos)}, (pos[0] + 400, pos[1]))


def admin_clicks(c, y):
    g = c.g

    def ready(pos, loaded=True):
        """Go on only with the relay found (and, for Save, the scripts loaded)."""
        cond = c.fn("IsValid", KSL, {"Object": c.relay((pos[0], pos[1] + 300))}, (pos[0] + 200, pos[1] + 300))
        if loaded:
            cond = c.fn("BooleanAND", KML, {"A": cond, "B": _i(c, "Greater_IntInt", c.var("ScASeen", "int", (pos[0], pos[1] + 450)),
                                                                0, (pos[0] + 200, pos[1] + 450))}, (pos[0] + 400, pos[1] + 300))
        b = c.branch(cond, pos)
        c.exits = [(b, "else")]
        c.set_text("ScStatus", LOADING, (pos[0] + 300, pos[1] + 600))
        c.exits = [(b, "then")]

    for k in range(N):
        c.exits = [(clicked(g, "ScTab%d" % k, (0, y)), "then")]
        c.set_var("ScSel", "int", str(k), (300, y))
        y += 400
    # save: the boxes -> OwlServerScSave
    c.exits = [(clicked(g, "ScSave", (0, y)), "then")]
    ready((300, y))
    clr = g.array_fn("Array_Clear", pos=(800, y), elem_cat="string")
    g.wire(*c.arr("ScTmp", "string", (700, y + 300)), clr, "TargetArray", exec=False)
    c.go(clr)
    x = 1100
    for j in range(L):
        add = g.array_fn("Array_Add", pos=(x, y), elem_cat="string")
        g.wire(*c.arr("ScTmp", "string", (x, y + 300)), add, "TargetArray", exec=False)
        g.array_item_pin(add, "NewItem", "string")
        t = _trimmed(c, "ScLine%d" % j, (x - 400, y + 450))
        g.wire(t[0], t[1], add, "NewItem", exec=False)
        c.go(add)
        x += 300
    c.call_relay("OwlServerScSave", {"Index": c.var("ScSel", "int", (x, y + 300)), "Name": c.box_text("ScName", (x, y + 450)),
                                     "Lines": c.arr("ScTmp", "string", (x, y + 600))}, (x + 300, y))
    c.set_text("ScStatus", "Saving...", (x + 600, y))
    y += 1200
    # run the script: each non-empty line, as the owning player
    c.exits = [(clicked(g, "ScRun", (0, y)), "then")]
    ready((300, y), loaded=False)
    c.set_var("ScRunN", "int", "0", (700, y))
    x = 1000
    for j in range(L):
        t = _trimmed(c, "ScLine%d" % j, (x, y + 450))
        b = c.branch(_i(c, "Greater_IntInt", c.fn("Len", KSTR, {"S": t}, (x + 200, y + 600)), 0, (x + 400, y + 600)),
                     (x + 300, y))
        c.exits = [(b, "then")]
        _run(c, _trimmed(c, "ScLine%d" % j, (x + 300, y + 750)), (x + 600, y))
        c.bump("ScRunN", (x + 900, y))
        c.exits += [(b, "else")]
        x += 1300
    n = c.int_text(c.var("ScRunN", "int", (x, y + 600)), (x + 200, y + 600))
    c.call_relay("OwlServerScRan", {"Text": c.concat(["Ran script ", c.box_text("ScName", (x, y + 450)), " (", n,
                                                      " commands)"], (x + 400, y + 450))}, (x + 300, y))
    c.set_text("ScStatus", c.concat(["Ran ", c.int_text(c.var("ScRunN", "int", (x + 600, y + 750)), (x + 800, y + 750)),
                                     " commands."], (x + 1000, y + 750)), (x + 900, y))
    y += 1500
    # the console line
    c.exits = [(clicked(g, "ScCmdRun", (0, y)), "then")]
    ready((300, y), loaded=False)
    cmd = lambda pos: _trimmed(c, "ScCmd", pos)
    b = c.branch(_i(c, "Greater_IntInt", c.fn("Len", KSTR, {"S": cmd((600, y + 450))}, (1000, y + 600)), 0, (1200, y + 600)),
                 (900, y))
    c.exits = [(b, "then")]
    _run(c, cmd((1000, y + 900)), (1300, y))
    ins = g.array_fn("Array_Insert", pos=(1600, y), elem_cat="string")
    g.wire(*c.arr("ScHist", "string", (1500, y + 300)), ins, "TargetArray", exec=False)
    g.array_item_pin(ins, "NewItem", "string")
    t = cmd((1300, y + 1050))
    g.wire(t[0], t[1], ins, "NewItem", exec=False)
    ins.pin("Index").typed("int", direction="EGPD_Input").literal("0")
    c.go(ins)
    rs = g.array_fn("Array_Resize", pos=(1900, y), elem_cat="string")
    g.wire(*c.arr("ScHist", "string", (1800, y + 300)), rs, "TargetArray", exec=False)
    rs.pin("Size").typed("int", direction="EGPD_Input").literal(str(HIST))
    c.go(rs)
    x = 2200
    for k in range(HIST):
        c.set_text("ScH%d" % k, c.at(c.arr("ScHist", "string", (x, y + 300)), k, "string", (x + 200, y + 300)), (x + 300, y))
        x += 500
    c.call_relay("OwlServerScRan", {"Text": c.concat(["Console: ", cmd((x, y + 450))], (x + 400, y + 450))}, (x + 300, y))
    c.set_text("ScStatus", c.concat(["Ran: ", c.at(c.arr("ScHist", "string", (x + 500, y + 750)), 0, "string",
                                                     (x + 700, y + 750))], (x + 900, y + 750)), (x + 600, y))
    _set_box_text(c, "ScCmd", ("", "string"), (x + 900, y))
    c.exits += [(b, "else")]
