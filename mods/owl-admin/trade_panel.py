"""Trading in the menus. Player menu (07), the Trade tab; admin menu (03), the trade log under the
Trading page's settings.

    player_layout(u, B, R) -> [(widget, slot props)]     player_variables(unreal, bel, wbp)
    player_tick(c, on_page, y)    player_clicks(c, y)
    admin_layout(u, B, R) -> [(widget, slot props)]      admin_variables(unreal, bel, wbp)
    admin_tick(c, entries, unlocked, on_page, y) -> exits     admin_clicks(c, y)
    (c: ce_panel._Ctx on the menu's relay variable)

The Trade tab shows one of four boxes by the relay's TrRoleC (trade_server): PTrIdle (players near
you, Ask to trade, Refresh), PTrWait (your request, Cancel), PTrInc (their request, Accept /
Decline) or PTrAct (both offers, coins, Confirm / Cancel, and your backpack with Offer per stack).
While the tab is up it asks for the state once, and for the players near you every NEAR_SECONDS
while not trading; it redraws when TrVer / TrNearVer change. Item names: the relay's class
defaults TrCatIds / TrCatNames. Every button is a server event; the server checks everything.
"""
from bpkit import ir
import menu_defs as D
from ce_panel import _text_button, _lab, _field, TEXT, KML, KSL, KSTR
from menu_shell import clicked

TMAX, BAG, NEAR, LOGN = D.TRADE_MAX, D.TRADE_BAG_ROWS, D.TRADE_NEAR_ROWS, D.TRADE_LOG_ROWS
NEAR_SECONDS = 5.0
HBOX, VBOX = "/Script/UMG.HorizontalBox", "/Script/UMG.VerticalBox"
PSTATE = "/Script/Engine.PlayerState"
NOT_CONNECTED = "Still connecting to the server. Try again in a moment."


def _i(c, fn, a, b, pos):
    lit = lambda v: v if isinstance(v, tuple) else (str(v), "int")
    return c.fn(fn, KML, {"A": lit(a), "B": lit(b)}, pos)


def _row(u, B, R, key, btn_label, px=17):
    """HorizontalBox key: key+"Txt" (fill) | button key+"Btn" (or none), collapsed."""
    u.text(key + "Txt", "", B if btn_label else R, px, "#f2e6e2", wrap=True)
    items = [(key + "Txt", ["Size=(SizeRule=Fill)", "VerticalAlignment=VAlign_Center"])]
    if btn_label:
        items.append((_text_button(u, B, key + "Btn", btn_label, h=36, px=14, pad=12), ["VerticalAlignment=VAlign_Center"]))
    u.box("HorizontalBox", key, items, props=["Visibility=Collapsed"], variable=True)
    return (key, ["Padding=%s" % u.margin(b=4)])


def _card(u, name, inner):
    u.border(name + "Fill", "#120909", 1.0, u.margin(16, 12, 16, 12), inner)
    return u.border(name, "#2a1012", 1.0, u.margin(1, 1, 1, 1), name + "Fill")


# ================================================================ player layout
def player_layout(u, B, R):
    u.text("PTrStatus", "", R, 17, "#f2e6e2", wrap=True)
    # idle: players near you
    rows = [(_lab(u, B, "PTrNearLab", "Players near you"), ["Padding=%s" % u.margin(b=8)])]
    rows += [_row(u, B, R, "PTrN%d" % k, "Ask to trade") for k in range(NEAR)]
    u.text("PTrNone", "Nobody is close enough to trade. Walk up to a player, then press Refresh.", R, 16, "#a8908a", wrap=True)
    rows += [("PTrNone", ["Padding=%s" % u.margin(b=8)]),
             (_text_button(u, B, "PTrRefresh", "Refresh", h=40, px=15, pad=16), ["HorizontalAlignment=HAlign_Left"])]
    u.box("VerticalBox", "PTrIdleIn", rows)
    u.box("VerticalBox", "PTrIdle", [(_card(u, "PTrIdleCard", "PTrIdleIn"), [])], variable=True)
    # waiting for an answer
    u.text("PTrWaitTxt", "", B, 18, "#ffffff", wrap=True)
    u.box("VerticalBox", "PTrWaitIn", [("PTrWaitTxt", ["Padding=%s" % u.margin(b=10)]),
                                       (_text_button(u, B, "PTrCancelW", "Cancel request", h=40, px=15, pad=16),
                                        ["HorizontalAlignment=HAlign_Left"])])
    u.box("VerticalBox", "PTrWait", [(_card(u, "PTrWaitCard", "PTrWaitIn"), [])], props=["Visibility=Collapsed"], variable=True)
    # asked by someone
    u.text("PTrIncTxt", "", B, 18, "#ffffff", wrap=True)
    u.box("HorizontalBox", "PTrIncBtns", [
        (_text_button(u, B, "PTrAccept", "Accept", primary=True, h=44, px=16, pad=20), ["Padding=%s" % u.margin(r=10)]),
        (_text_button(u, B, "PTrDecline", "Decline", h=44, px=16, pad=20), [])])
    u.box("VerticalBox", "PTrIncIn", [("PTrIncTxt", ["Padding=%s" % u.margin(b=10)]), ("PTrIncBtns", [])])
    u.box("VerticalBox", "PTrInc", [(_card(u, "PTrIncCard", "PTrIncIn"), [])], props=["Visibility=Collapsed"], variable=True)
    # trading
    mine = [(_lab(u, B, "PTrMyLab", "Your offer"), ["Padding=%s" % u.margin(b=6)])]
    mine += [_row(u, B, R, "PTrM%d" % r, "Take back", px=16) for r in range(TMAX)]
    u.text("PTrMyCoins", "", B, 16, "#ff5a5f")
    mine.append(("PTrMyCoins", ["Padding=%s" % u.margin(t=4)]))
    u.box("VerticalBox", "PTrMyCol", mine)
    u.text("PTrThLab", "THEIR OFFER", B, 15, "#f0343a", spacing_px=2)
    theirs = [("PTrThLab", ["Padding=%s" % u.margin(b=6)])]
    theirs += [_row(u, B, R, "PTrT%d" % r, None, px=16) for r in range(TMAX)]
    u.text("PTrThCoins", "", B, 16, "#ff5a5f")
    theirs.append(("PTrThCoins", ["Padding=%s" % u.margin(t=4)]))
    u.box("VerticalBox", "PTrThCol", theirs)
    u.box("HorizontalBox", "PTrCols", [
        (_card(u, "PTrMyCard", "PTrMyCol"), ["Size=(SizeRule=Fill)", "Padding=%s" % u.margin(r=10)]),
        (_card(u, "PTrThCard", "PTrThCol"), ["Size=(SizeRule=Fill)"])])
    u.text("PTrOkTxt", "", B, 16, "#f2e6e2", wrap=True)
    u.text("PTrWallet", "", R, 15, "#b8a29c")
    u.box("HorizontalBox", "PTrCoinRow", [
        (_field(u, R, "PTrCoinBox", "Owl coins to offer"), ["Size=(SizeRule=Fill)", "VerticalAlignment=VAlign_Center"]),
        (_text_button(u, B, "PTrCoinSet", "Offer coins", h=44, px=15, pad=14),
         ["Padding=%s" % u.margin(l=10), "VerticalAlignment=VAlign_Center"]),
        ("PTrWallet", ["Padding=%s" % u.margin(l=12), "VerticalAlignment=VAlign_Center"])], variable=True)
    u.box("HorizontalBox", "PTrActBtns", [
        (_text_button(u, B, "PTrConfirm", "Confirm", primary=True, h=46, px=16, pad=24), ["Padding=%s" % u.margin(r=10)]),
        (_text_button(u, B, "PTrCancelA", "Cancel trade", h=46, px=16, pad=20), [])])
    bag = [(_lab(u, B, "PTrBagLab", "Your backpack"), ["Padding=%s" % u.margin(b=6)])]
    bag += [_row(u, B, R, "PTrB%d" % k, "Offer", px=16) for k in range(BAG)]
    u.box("VerticalBox", "PTrBagCol", bag)
    u.box("VerticalBox", "PTrAct", [
        ("PTrCols", ["Padding=%s" % u.margin(b=10)]), ("PTrOkTxt", ["Padding=%s" % u.margin(b=8)]),
        ("PTrCoinRow", ["Padding=%s" % u.margin(b=10)]), ("PTrActBtns", ["Padding=%s" % u.margin(b=14)]),
        (_card(u, "PTrBagCard", "PTrBagCol"), [])], props=["Visibility=Collapsed"], variable=True)
    return [("PTrStatus", ["Padding=%s" % u.margin(b=10)]), ("PTrIdle", []), ("PTrWait", []), ("PTrInc", []),
            ("PTrAct", [])]


def player_variables(unreal, bel, wbp):
    i, b, r = (bel.get_basic_type_by_name(t) for t in ("int", "bool", "real"))
    for var, t in (("PTrSeen", i), ("PTrNearSeen", i), ("PTrAskAt", r), ("PTrOpen", b)):
        bel.add_member_variable(wbp, var, t)


# ================================================================ shared
def _name(c, tid, pos):
    """The item's name from the relay's TrCatIds / TrCatNames, else "Item <id>" (pure)."""
    x, y = pos
    k = c.find(c.rvar("TrCatIds", "int", (x, y), arr=True), tid, "int", (x + 200, y))
    got = c.at(c.rvar("TrCatNames", "string", (x, y + 150), arr=True), k, "string", (x + 400, y + 150))
    return c.fn("SelectString", KML, {"A": got, "B": c.concat(["Item ", c.int_text(tid, (x + 200, y + 300))], (x + 400, y + 300)),
                                      "bPickA": _i(c, "GreaterEqual_IntInt", k, 0, (x + 600, y + 450))}, (x + 800, y))


def _rows(c, prefix, ids, qty, n, pos):
    """Rows prefix0..n-1: "<name> x<qty>" for each entry of the relay arrays ids / qty, the rest collapsed."""
    x, y = pos
    ln = (c.g.array_len(*c.rvar(ids, "int", (x, y + 600), arr=True), (x + 200, y + 600), elem_cat="int"), "ReturnValue")
    for r in range(n):
        key = "%s%d" % (prefix, r)
        b = c.branch(_i(c, "Less_IntInt", r, ln, (x + 200, y + 450)), (x, y))
        c.exits = [(b, "then")]
        c.set_vis(key, HBOX, "Visible", (x + 300, y))
        tid = c.at(c.rvar(ids, "int", (x + 300, y + 750), arr=True), r, "int", (x + 500, y + 750))
        q = c.at(c.rvar(qty, "int", (x + 300, y + 900), arr=True), r, "int", (x + 500, y + 900))
        c.set_text(key + "Txt", c.concat([_name(c, tid, (x + 600, y + 1050)), " x", c.int_text(q, (x + 600, y + 1500))],
                                         (x + 1500, y + 1050)), (x + 600, y))
        ends = c.exits
        c.exits = [(b, "else")]
        c.set_vis(key, HBOX, "Collapsed", (x + 300, y + 350))
        c.exits += ends
        x += 1800


# ================================================================ player tick / clicks
def player_tick(c, on_page, y):
    """Entered from c.exits; leaves c.exits for whatever follows."""
    g = c.g
    b = c.branch(c.fn("BooleanAND", KML, {"A": on_page, "B": c.fn("IsValid", KSL, {"Object": c.relay((0, y + 450))},
                                                                   (200, y + 450))}, (400, y + 300)), (400, y))
    c.exits = [(b, "else")]
    c.set_var("PTrOpen", "bool", "false", (700, y + 900))
    out = c.exits
    c.exits = [(b, "then")]
    now = lambda pos: c.fn("GetGameTimeInSeconds", KSL, {}, pos)
    # just opened: the state and who is near
    bo = c.branch(c.fn("Not_PreBool", KML, {"A": c.var("PTrOpen", "bool", (600, y + 300))}, (800, y + 300)), (800, y))
    c.exits = [(bo, "then")]
    c.call_relay("OwlServerTrState", {}, (1100, y))
    c.call_relay("OwlServerTrNear", {}, (1400, y))
    c.set_var("PTrOpen", "bool", "true", (1700, y))
    c.set_var("PTrAskAt", "real", c.fn("Add_DoubleDouble", KML, {"A": now((1800, y + 300)), "B": (str(NEAR_SECONDS), "real")},
                                       (2000, y + 300)), (2000, y))
    c.exits += [(bo, "else")]
    # not trading: who is near, every NEAR_SECONDS
    x = 2400
    due = c.fn("BooleanAND", KML, {
        "A": _i(c, "EqualEqual_IntInt", c.rvar("TrRoleC", "int", (x, y + 300)), 0, (x + 200, y + 300)),
        "B": c.fn("Greater_DoubleDouble", KML, {"A": now((x, y + 450)), "B": c.var("PTrAskAt", "real", (x, y + 600))},
                  (x + 200, y + 450))}, (x + 400, y + 300))
    bd = c.branch(due, (x + 400, y))
    c.exits = [(bd, "then")]
    c.call_relay("OwlServerTrNear", {}, (x + 700, y))
    c.set_var("PTrAskAt", "real", c.fn("Add_DoubleDouble", KML, {"A": now((x + 800, y + 300)), "B": (str(NEAR_SECONDS), "real")},
                                       (x + 1000, y + 300)), (x + 1000, y))
    c.exits += [(bd, "else")]
    # the near list changed
    x = 3800
    bn = c.branch(_i(c, "NotEqual_IntInt", c.rvar("TrNearVer", "int", (x, y + 300)), c.var("PTrNearSeen", "int", (x, y + 450)),
                     (x + 200, y + 300)), (x + 200, y))
    skip = [(bn, "else")]
    c.exits = [(bn, "then")]
    c.set_var("PTrNearSeen", "int", c.rvar("TrNearVer", "int", (x + 300, y + 300)), (x + 500, y))
    names = lambda pos: c.rvar("TrNearNames", "string", pos, arr=True)
    ln = (g.array_len(*names((x + 600, y + 900)), (x + 800, y + 900), elem_cat="string"), "ReturnValue")
    x += 800
    for k in range(NEAR):
        key = "PTrN%d" % k
        b = c.branch(_i(c, "Less_IntInt", k, ln, (x + 200, y + 450)), (x, y))
        c.exits = [(b, "then")]
        c.set_vis(key, HBOX, "Visible", (x + 300, y))
        c.set_text(key + "Txt", c.at(names((x + 300, y + 750)), k, "string", (x + 500, y + 750)), (x + 600, y))
        ends = c.exits
        c.exits = [(b, "else")]
        c.set_vis(key, HBOX, "Collapsed", (x + 300, y + 350))
        c.exits += ends
        x += 1000
    c.vis_if(_i(c, "EqualEqual_IntInt", ln, 0, (x, y + 300)), [("PTrNone", TEXT)], (x + 200, y))
    c.exits += skip
    # the trade view changed
    y2 = y + 2500
    x = 0
    bv = c.branch(_i(c, "NotEqual_IntInt", c.rvar("TrVer", "int", (x, y2 + 300)), c.var("PTrSeen", "int", (x, y2 + 450)),
                     (x + 200, y2 + 300)), (x + 200, y2))
    skip = [(bv, "else")]
    c.exits = [(bv, "then")]
    c.set_var("PTrSeen", "int", c.rvar("TrVer", "int", (x + 300, y2 + 300)), (x + 500, y2))
    role = lambda pos: c.rvar("TrRoleC", "int", pos)
    x = 800
    for k, box in enumerate(("PTrIdle", "PTrWait", "PTrInc", "PTrAct")):
        c.vis_if(_i(c, "EqualEqual_IntInt", role((x, y2 + 450)), k, (x + 200, y2 + 450)), [(box, VBOX)], (x + 300, y2))
        x += 1000
    peer = lambda pos: c.rvar("TrPeerC", "string", pos)
    c.set_text("PTrWaitTxt", c.concat(["Waiting for ", peer((x, y2 + 450)), " to answer..."], (x + 200, y2 + 450)), (x, y2))
    c.set_text("PTrIncTxt", c.concat([peer((x + 300, y2 + 600)), " wants to trade with you."], (x + 500, y2 + 600)), (x + 300, y2))
    c.set_text("PTrThLab", c.fn("ToUpper", KSTR, {"SourceString": c.concat([peer((x + 600, y2 + 750)), "'s offer"],
                                                                            (x + 800, y2 + 750))}, (x + 1000, y2 + 750)), (x + 600, y2))
    x += 1300
    _rows(c, "PTrM", "TrMyIdsC", "TrMyQtyC", TMAX, (x, y2))
    x += 1800 * TMAX
    _rows(c, "PTrT", "TrThIdsC", "TrThQtyC", TMAX, (x, y2))
    x += 1800 * TMAX
    _rows(c, "PTrB", "TrBagIdsC", "TrBagQtyC", BAG, (x, y2))
    x += 1800 * BAG
    coins = lambda var, pos: c.concat(["Owl coins: ", c.int_text(c.rvar(var, "int", pos), (pos[0] + 200, pos[1]))],
                                      (pos[0] + 400, pos[1]))
    c.set_text("PTrMyCoins", coins("TrMyCoinsC", (x, y2 + 450)), (x, y2))
    c.set_text("PTrThCoins", coins("TrThCoinsC", (x + 300, y2 + 600)), (x + 300, y2))
    c.set_text("PTrWallet", c.concat(["Your wallet: ", c.int_text(c.rvar("TrWalletC", "int", (x + 600, y2 + 750)),
                                                                    (x + 800, y2 + 750))], (x + 1000, y2 + 750)), (x + 600, y2))
    yes_no = lambda var, pos: c.fn("SelectString", KML, {"A": ("confirmed", "string"), "B": ("not yet", "string"),
                                                          "bPickA": c.rvar(var, "bool", pos)}, (pos[0] + 200, pos[1]))
    c.set_text("PTrOkTxt", c.concat(["You: ", yes_no("TrMyOkC", (x + 900, y2 + 900)), ".  ", peer((x + 900, y2 + 1050)), ": ",
                                     yes_no("TrThOkC", (x + 900, y2 + 1200)), "."], (x + 1300, y2 + 900)), (x + 900, y2))
    x += 1400
    c.vis_if(c.rvar("TrCoinsOnC", "bool", (x, y2 + 300)), [("PTrCoinRow", HBOX)], (x + 200, y2))
    x += 900
    bm = c.branch(_i(c, "Greater_IntInt", c.fn("Len", KSTR, {"S": c.rvar("TrMsgC", "string", (x, y2 + 450))}, (x + 200, y2 + 450)),
                     0, (x + 400, y2 + 450)), (x + 300, y2))
    c.exits = [(bm, "then")]
    c.set_text("PTrStatus", c.rvar("TrMsgC", "string", (x + 500, y2 + 600)), (x + 600, y2))
    c.exits += [(bm, "else")] + skip + out


def player_clicks(c, y):
    g = c.g

    def ready(pos):
        b = c.branch(c.fn("IsValid", KSL, {"Object": c.relay((pos[0], pos[1] + 300))}, (pos[0] + 200, pos[1] + 300)), pos)
        c.exits = [(b, "else")]
        c.set_text("PTrStatus", NOT_CONNECTED, (pos[0] + 300, pos[1] + 600))
        c.exits = [(b, "then")]

    lit_int = lambda v, pos: c.fn("MakeLiteralInt", KSL, {"Value": (str(v), "int")}, pos)
    lit_bool = lambda v, pos: c.fn("MakeLiteralBool", KSL, {"Value": ("true" if v else "false", "bool")}, pos)

    def button(btn, event, ins, pos):
        x, yy = pos
        c.exits = [(clicked(g, btn, (x, yy)), "then")]
        ready((x + 300, yy))
        c.call_relay(event, ins(x + 700, yy) if callable(ins) else ins, (x + 1000, yy))

    for k in range(NEAR):
        def ins(x, yy, k=k):
            st = g.array_get(*c.rvar("TrNearStates", "object", (x, yy + 600), arr=True, sub=ir.obj_path(PSTATE)), k,
                             (x + 200, yy + 600), elem_cat="object", elem_sub=ir.obj_path(PSTATE))
            return {"State": (st, "Output")}
        button("PTrN%dBtn" % k, "OwlServerTrAsk", ins, (0, y))
        y += 800
    for btn, event in (("PTrRefresh", "OwlServerTrNear"), ("PTrCancelW", "OwlServerTrCancel"),
                       ("PTrCancelA", "OwlServerTrCancel"), ("PTrConfirm", "OwlServerTrConfirm")):
        button(btn, event, {}, (0, y))
        y += 600
    for btn, yes in (("PTrAccept", True), ("PTrDecline", False)):
        button(btn, "OwlServerTrAnswer", lambda x, yy, yes=yes: {"Yes": lit_bool(yes, (x, yy + 600))}, (0, y))
        y += 700
    for r in range(TMAX):
        button("PTrM%dBtn" % r, "OwlServerTrTake", lambda x, yy, r=r: {"Entry": lit_int(r, (x, yy + 600))}, (0, y))
        y += 700
    for k in range(BAG):
        button("PTrB%dBtn" % k, "OwlServerTrOffer",
               lambda x, yy, k=k: {"Slot": c.at(c.rvar("TrBagSlotsC", "int", (x, yy + 600), arr=True), k, "int",
                                                (x + 200, yy + 600))}, (0, y))
        y += 700
    button("PTrCoinSet", "OwlServerTrCoins",
           lambda x, yy: {"Amount": c.fn("Conv_StringToInt", KSTR, {"InString": c.box_text("PTrCoinBox", (x, yy + 600))},
                                         (x + 400, yy + 600))}, (0, y))


# ================================================================ admin: the trade log
def admin_layout(u, B, R):
    items = [(_lab(u, B, "TrLogLab", "Trade log (newest first)"), ["Padding=%s" % u.margin(t=10, b=8)])]
    for k in range(LOGN):
        u.text("TrL%d" % k, "", R, 15, "#f2e6e2", wrap=True, props=["Visibility=Collapsed"])
        items.append(("TrL%d" % k, ["Padding=%s" % u.margin(b=4)]))
    u.text("TrLogNone", "No trades yet.", R, 16, "#a8908a", wrap=True)
    items += [("TrLogNone", ["Padding=%s" % u.margin(b=8)]),
              (_text_button(u, B, "TrLogRefresh", "Refresh log", h=40, px=15, pad=16), ["HorizontalAlignment=HAlign_Left"])]
    return items


def admin_variables(unreal, bel, wbp):
    bel.add_member_variable(wbp, "TrLogSeen", bel.get_basic_type_by_name("int"))
    bel.add_member_variable(wbp, "TrLogAsked", bel.get_basic_type_by_name("bool"))


def admin_tick(c, entries, unlocked, on_page, y):
    g = c.g
    c.exits = list(entries)
    b = c.branch(c.fn("BooleanAND", KML, {"A": unlocked, "B": on_page}, (0, y + 300)), (200, y))
    c.exits = [(b, "else")]
    c.set_var("TrLogAsked", "bool", "false", (500, y + 700))
    out = c.exits
    c.exits = [(b, "then")]
    out += c.find_relay((500, y))
    ba = c.branch(c.fn("Not_PreBool", KML, {"A": c.var("TrLogAsked", "bool", (2400, y + 300))}, (2600, y + 300)), (2600, y))
    c.exits = [(ba, "then")]
    c.call_relay("OwlServerTrLog", {}, (2900, y))
    c.set_var("TrLogAsked", "bool", "true", (3200, y))
    c.exits += [(ba, "else")]
    x = 3600
    bv = c.branch(_i(c, "NotEqual_IntInt", c.rvar("TrLogVer", "int", (x, y + 300)), c.var("TrLogSeen", "int", (x, y + 450)),
                     (x + 200, y + 300)), (x + 200, y))
    skip = [(bv, "else")]
    c.exits = [(bv, "then")]
    c.set_var("TrLogSeen", "int", c.rvar("TrLogVer", "int", (x + 300, y + 300)), (x + 500, y))
    lines = lambda pos: c.rvar("TrLogC", "string", pos, arr=True)
    ln = (g.array_len(*lines((x + 600, y + 900)), (x + 800, y + 900), elem_cat="string"), "ReturnValue")
    x += 800
    for k in range(LOGN):
        key = "TrL%d" % k
        bk = c.branch(_i(c, "Less_IntInt", k, ln, (x + 200, y + 450)), (x, y))
        c.exits = [(bk, "then")]
        c.set_vis(key, TEXT, "Visible", (x + 300, y))
        # (one Subtract of k + 1: a pasted B of 0 comes back as Subtract_IntInt's own default, 1)
        idx = _i(c, "Subtract_IntInt", ln, k + 1, (x + 500, y + 900))
        line = c.at(lines((x + 300, y + 750)), idx, "string", (x + 700, y + 750))
        nice = c.fn("Replace", KSTR, {"SourceString": line, "From": ("|", "string"), "To": ("  ", "string")}, (x + 900, y + 750))
        c.set_text(key, nice, (x + 600, y))
        ends = c.exits
        c.exits = [(bk, "else")]
        c.set_vis(key, TEXT, "Collapsed", (x + 300, y + 350))
        c.exits += ends
        x += 1300
    c.vis_if(_i(c, "EqualEqual_IntInt", ln, 0, (x, y + 300)), [("TrLogNone", TEXT)], (x + 200, y))
    c.exits += skip
    return out + c.exits


def admin_clicks(c, y):
    c.exits = [(clicked(c.g, "TrLogRefresh", (0, y)), "then")]
    b = c.branch(c.fn("IsValid", KSL, {"Object": c.relay((300, y + 300))}, (500, y + 300)), (500, y))
    c.exits = [(b, "then")]
    c.call_relay("OwlServerTrLog", {}, (800, y))
