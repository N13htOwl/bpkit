"""The admin menu's Players tab (03). Left: the players online (the Characters tab's list: the
relay's CeNames / CeStates, asked for every PL_ASK_SECONDS while the page is open). Right: the
picked player -- Teleport to, Bring here, Ban (with a confirm strip) and the status line; under
them Conan's banned list, Unban selected and Refresh.

    admin_layout(u, B, R) -> [(widget, slot props)]     admin_variables(unreal, bel, wbp)
    admin_tick(c, entries, unlocked, on_page, y) -> exits     admin_clicks(c, y)
    admin_events(c, y)             the banned-list event (OwlPlBanned) and its bind
    bind_live(bp, g_ptr)           after the paste: the bind's delegate wire (it doesn't paste)
    (c: ce_panel._Ctx on CeRelay)

Every action goes through the admin's relay (players_server); its answer (relay PlMsg, PlMsgVer)
shows in the status line. The banned list is the game's: the server's answer to
ServerGetBannedPlayerList arrives on the admin's own ConanPlayerController as
SignalBannedPlayerListReady(PlayerData), bound once (PlBound) to OwlPlBanned, which keeps it in
PlBans and raises PlBanVer. Unban sends the entry's own UniqueNetIdRepl back.
"""
from bpkit import ir
import menu_defs as D
from ce_panel import (_button, _text_button, _lab, CEP_ROWS, TEXT, BUTTON, SIZEBOX, PSTATE, KML, KSL, ROW_ON,
                      ROW_OFF)
from menu_shell import button_style, clicked

BAN_ROWS = 12
PL_ASK_SECONDS = 5.0
CPC = "/Script/ConanSandbox.ConanPlayerController"
BANNED = "/Script/ConanSandbox.BlacklistedUser"
DELEGATE = "SignalBannedPlayerListReady"
EVENT = "OwlPlBanned"
NOT_CONNECTED = "Still connecting to the server. Try again in a moment."
PICK = "Pick a player on the left first."
HINT = ("This is Conan's own ban list: banned players can't rejoin. "
        "If a ban doesn't show up here, the game wants you to be a Conan admin too.")


# ================================================================ layout
def admin_layout(u, B, R):
    rows = []
    for i in range(CEP_ROWS):
        u.text("PlPName%d" % i, "", B, 19, "#ffffff")
        _button(u, "PlP%d" % i, "PlPName%d" % i, u.margin(18, 10, 18, 10), button_style(u, "#ffffff", "#ffffff", "#ffffff"),
                props=["Visibility=Collapsed"], halign="HAlign_Left")
        rows.append(("PlP%d" % i, ["Padding=%s" % u.margin(b=2), "HorizontalAlignment=HAlign_Fill"]))
    u.text("PlNoPlayers", "Asking the server for the players online...", R, 16, "#a8908a", wrap=True)
    rows.append(("PlNoPlayers", ["Padding=%s" % u.margin(18, 10, 18, 10)]))
    u.box("VerticalBox", "PlPList", rows)
    u.border("PlPCol", "#0b0606", 1.0, u.margin(t=12, b=12), "PlPList", valign="VAlign_Top")
    u.sized("PlPColBox", "PlPCol", w=170)

    u.text("PlSelName", "NO PLAYER SELECTED", B, 22, "#ffffff", spacing_px=3)
    u.text("PlSelHint", "Teleport to them, bring them to you, or ban them", R, 16, "#b8a29c", variable=False)
    acts = [(_text_button(u, B, b, label, h=44, px=16, pad=16), ["Padding=%s" % u.margin(r=8, b=8)])
            for b, label in (("PlGoto", "Teleport to"), ("PlBring", "Bring here"), ("PlBan", "Ban"))]
    u.box("WrapBox", "PlActs", acts)
    u.text("PlConfirmText", "", B, 17, "#ffffff", wrap=True)
    u.box("HorizontalBox", "PlConfirmBtns", [
        (_text_button(u, B, "PlBanYes", "Yes, ban", primary=True, h=44, px=16, pad=18), ["Padding=%s" % u.margin(r=8)]),
        (_text_button(u, B, "PlBanNo", "Cancel", h=44, px=16, pad=18), [])])
    u.box("VerticalBox", "PlConfirmIn", [("PlConfirmText", ["Padding=%s" % u.margin(b=10)]), ("PlConfirmBtns", [])])
    u.border("PlConfirm", "#2a0b0d", 1.0, u.margin(16, 12, 16, 12), "PlConfirmIn",
             props=["Visibility=Collapsed"], variable=True)
    u.text("PlStatus", "", R, 17, "#f2e6e2", wrap=True)

    bans = []
    for k in range(BAN_ROWS):
        u.text("PlBName%d" % k, "", B, 17, "#ffffff")
        _button(u, "PlB%d" % k, "PlBName%d" % k, u.margin(14, 8, 14, 8), button_style(u, "#ffffff", "#ffffff", "#ffffff"),
                props=["Visibility=Collapsed"], halign="HAlign_Left")
        bans.append(("PlB%d" % k, ["Padding=%s" % u.margin(b=2), "HorizontalAlignment=HAlign_Fill"]))
    u.text("PlNoBans", "Asking the server for the banned list...", R, 16, "#a8908a", wrap=True)
    bans.append(("PlNoBans", ["Padding=%s" % u.margin(t=4)]))
    u.box("VerticalBox", "PlBList", bans)
    u.text("PlBanHint", HINT, R, 15, "#b8a29c", wrap=True, variable=False)
    u.box("HorizontalBox", "PlBanBtns", [
        (_text_button(u, B, "PlUnban", "Unban selected", h=44, px=16, pad=16), ["Padding=%s" % u.margin(r=8)]),
        (_text_button(u, B, "PlRefresh", "Refresh", h=44, px=16, pad=16), [])])

    u.box("VerticalBox", "PlRight", [
        ("PlSelName", []), ("PlSelHint", ["Padding=%s" % u.margin(t=2, b=12)]),
        ("PlActs", []), ("PlConfirm", ["Padding=%s" % u.margin(t=4, b=8)]),
        ("PlStatus", ["Padding=%s" % u.margin(b=18)]),
        (_lab(u, B, "PlBannedLab", "Banned players"), ["Padding=%s" % u.margin(b=6)]),
        ("PlBanHint", ["Padding=%s" % u.margin(b=10)]),
        ("PlBList", ["Padding=%s" % u.margin(b=10)]),
        ("PlBanBtns", [])])
    u.strip("PlColLine", "#3a1214", u.margin(l=1))
    u.box("HorizontalBox", "PlBody", [("PlPColBox", ["VerticalAlignment=VAlign_Fill"]),
                                      ("PlColLine", ["VerticalAlignment=VAlign_Fill"]),
                                      ("PlRight", ["Size=(SizeRule=Fill)", "Padding=%s" % u.margin(l=20)])])
    return [("PlBody", ["Padding=%s" % u.margin(t=6)])]


def admin_variables(unreal, bel, wbp):
    i, b = bel.get_basic_type_by_name("int"), bel.get_basic_type_by_name("bool")
    for var, t in (("PlSel", i), ("PlBanSel", i), ("PlConfirmOn", b), ("PlBound", b), ("PlListSeen", i),
                   ("PlBanSeen", i), ("PlBanVer", i), ("PlMsgSeen", i), ("PlAskAt", bel.get_basic_type_by_name("real")),
                   ("PlBans", bel.get_array_type(bel.get_struct_type(unreal.BlacklistedUser.static_struct())))):
        bel.add_member_variable(wbp, var, t)


# ================================================================ helpers
def _i(c, fn, a, b, pos):
    lit = lambda v: v if isinstance(v, tuple) else (str(v), "int")
    return c.fn(fn, KML, {"A": lit(a), "B": lit(b)}, pos)


def _states(c, pos):
    return c.rvar("CeStates", "object", pos, arr=True, sub=ir.obj_path(PSTATE))


def _names(c, pos):
    return c.rvar("CeNames", "string", pos, arr=True)


def _bans(c, pos):
    n = c.g.var_get("PlBans", "struct", ir.struct_path(BANNED), pos=pos)
    n.pin("PlBans").set("PinType.ContainerType", "Array")
    return (n, "PlBans")


def _len(c, arr, cat, pos, sub=None):
    return (c.g.array_len(arr[0], arr[1], pos, elem_cat=cat, elem_sub=sub), "ReturnValue")


def _ban_entry(c, index, pos):
    """Break PlBans[index]: (node) with m_PlayerName / m_UniqueNetId outputs."""
    g, (x, y) = c.g, pos
    it = g.array_get(*_bans(c, (x, y)), index, (x + 200, y), elem_cat="struct", elem_sub=ir.struct_path(BANNED))
    brk = g.node("K2Node_BreakStruct", ['StructType="%s"' % ir.struct_path(BANNED)], base="BreakStruct",
                 pos=(x + 450, y))
    brk.pin("BlacklistedUser").typed("struct", ir.struct_path(BANNED), direction="EGPD_Input")
    brk.pin("m_PlayerName").typed("string", direction="EGPD_Output")
    brk.pin("m_UniqueNetId").typed("struct", ir.struct_path("/Script/Engine.UniqueNetIdRepl"), direction="EGPD_Output")
    g.wire(it, "Output", brk, "BlacklistedUser", exec=False)
    return brk


def _sel_ok(c, pos):
    """PlSel indexes a player in the list (pure)."""
    x, y = pos
    n = _len(c, _states(c, (x, y + 150)), "object", (x + 200, y + 150), sub=ir.obj_path(PSTATE))
    return c.fn("BooleanAND", KML, {"A": _i(c, "GreaterEqual_IntInt", c.var("PlSel", "int", (x, y + 300)), 0,
                                            (x + 200, y + 300)),
                                    "B": _i(c, "Less_IntInt", c.var("PlSel", "int", (x, y + 450)), n, (x + 400, y + 150))},
                (x + 600, y))


# ================================================================ events
def admin_events(c, y):
    """OwlPlBanned(PlayerData): keep the list, raise PlBanVer. Bound in admin_tick (PlBound)."""
    g = c.g
    ev = g.custom_event(EVENT, pos=(0, y))
    ev.set('CustomProperties UserDefinedPin (PinName="PlayerData",PinType=(PinCategory="struct",'
           'PinSubCategoryObject="%s",ContainerType=Array,bIsReference=True,bIsConst=True),'
           'DesiredPinDirection=EGPD_Output)' % ir.struct_path(BANNED))
    ev.pin("PlayerData").typed("struct", ir.struct_path(BANNED), direction="EGPD_Output", container="Array")
    c.exits = [(ev, "then")]
    st = g.var_set("PlBans", "struct", ir.struct_path(BANNED), pos=(300, y))
    st.pin("PlBans").set("PinType.ContainerType", "Array")
    g.wire(ev, "PlayerData", st, "PlBans", exec=False)
    c.go(st)
    c.bump("PlBanVer", (600, y))


def bind_live(bp, g_ptr):
    """Wire OwlPlBanned's OutputDelegate into the AddDelegate node (delegate pins don't paste)."""
    bind = ev = None
    for p in bp.graph_nodes(g_ptr):
        t = bp.export_nodes([p])
        if "K2Node_AddDelegate" in t.splitlines()[0] and DELEGATE in t:
            bind = p
        elif 'CustomFunctionName="%s"' % EVENT in t:
            ev = p
    assert bind and ev, "the banned-list bind or its event is missing after the paste"
    a, b = bp.find_pin(ev, "OutputDelegate", 1), bp.find_pin(bind, "Delegate", 0)
    assert a and b, "delegate pins missing"
    assert bp.connect_pins(a, b), "the schema refused the banned-list delegate wire"


# ================================================================ tick
def admin_tick(c, entries, unlocked, on_page, y):
    """Entered from entries; returns the exits."""
    g = c.g
    c.exits = list(entries)
    b = c.branch(c.fn("BooleanAND", KML, {"A": unlocked, "B": on_page}, (0, y + 250)), (200, y))
    out = [(b, "else")]
    c.exits = [(b, "then")]
    out += c.find_relay((500, y))

    # once: the banned list's delegate on the admin's own controller
    x = 2600
    bb = c.branch(c.var("PlBound", "bool", (x, y + 300)), (x, y))
    later = [(bb, "then")]
    c.exits = [(bb, "else")]
    cast = g.cast(CPC, pos=(x + 300, y))
    # both ends typed (as 10 does), or the paste leaves the cast's Object a wildcard with no wire
    cast.pin("Object").typed("object", ir.obj_path("/Script/Engine.PlayerController"), direction="EGPD_Input")
    op = c.owning_player((x + 100, y + 250))
    op.pin("ReturnValue").typed("object", ir.obj_path("/Script/Engine.PlayerController"), direction="EGPD_Output")
    g.wire(op, "ReturnValue", cast, "Object", exec=False)
    c.go(cast)
    later.append((cast, "CastFailed"))
    bind = g.node("K2Node_AddDelegate", ['DelegateReference=(MemberParent="%s",MemberName="%s")'
                                         % (ir.obj_path(CPC), DELEGATE)], base="AddDelegate", pos=(x + 600, y))
    g.wire(cast, "AsConan Player Controller", bind, "self", exec=False)
    c.go(bind)
    c.set_var("PlBound", "bool", "true", (x + 900, y))
    c.exits += later

    # every PL_ASK_SECONDS: the players online and the banned list
    x = 3800
    now = c.fn("GetGameTimeInSeconds", KSL, {}, (x, y + 300))
    bd = c.branch(c.fn("Greater_DoubleDouble", KML, {"A": now, "B": c.var("PlAskAt", "real", (x, y + 450))},
                       (x + 250, y + 300)), (x + 250, y))
    skip = [(bd, "else")]
    c.exits = [(bd, "then")]
    c.set_var("PlAskAt", "real", c.fn("Add_DoubleDouble", KML, {"A": now, "B": (str(PL_ASK_SECONDS), "real")},
                                      (x + 500, y + 300)), (x + 550, y))
    c.call_relay("OwlServerCeList", {}, (x + 850, y))
    c.call_relay("OwlServerPlBanList", {}, (x + 1150, y))
    c.exits += skip

    # the player list changed: redraw the rows
    x = 5400
    bl = c.branch(_i(c, "NotEqual_IntInt", c.rvar("CeListVer", "int", (x, y + 300)), c.var("PlListSeen", "int", (x, y + 450)),
                     (x + 250, y + 300)), (x + 250, y))
    skip = [(bl, "else")]
    c.exits = [(bl, "then")]
    for i in range(CEP_ROWS):
        xi = x + 550 + 1000 * i
        bi = c.branch(_i(c, "Less_IntInt", i, _len(c, _names(c, (xi, y + 600)), "string", (xi + 200, y + 600)),
                         (xi + 200, y + 450)), (xi, y))
        c.exits = [(bi, "then")]
        c.set_vis("PlP%d" % i, BUTTON, "Visible", (xi + 250, y))
        c.set_text("PlPName%d" % i, c.at(_names(c, (xi + 400, y + 750)), i, "string", (xi + 550, y + 750)), (xi + 550, y))
        ends = c.exits
        c.exits = [(bi, "else")]
        c.set_vis("PlP%d" % i, BUTTON, "Collapsed", (xi + 250, y + 300))
        c.exits += ends
    x += 550 + 1000 * CEP_ROWS
    c.vis_if(_i(c, "EqualEqual_IntInt", _len(c, _names(c, (x, y + 1300)), "string", (x + 200, y + 1300)), 0,
                (x + 400, y + 1300)), [("PlNoPlayers", TEXT)], (x, y))
    c.set_var("PlListSeen", "int", c.rvar("CeListVer", "int", (x + 600, y + 300)), (x + 900, y))
    c.exits += skip

    # the banned list changed: redraw its rows
    y2 = y + 2500
    x = 0
    bv = c.branch(_i(c, "NotEqual_IntInt", c.var("PlBanVer", "int", (x, y2 + 300)), c.var("PlBanSeen", "int", (x, y2 + 450)),
                     (x + 250, y2 + 300)), (x + 250, y2))
    skip = [(bv, "else")]
    c.exits = [(bv, "then")]
    for k in range(BAN_ROWS):
        xk = x + 550 + 1200 * k
        bk = c.branch(_i(c, "Less_IntInt", k, _len(c, _bans(c, (xk, y2 + 600)), "struct", (xk + 200, y2 + 600),
                                                    sub=ir.struct_path(BANNED)), (xk + 200, y2 + 450)), (xk, y2))
        c.exits = [(bk, "then")]
        c.set_vis("PlB%d" % k, BUTTON, "Visible", (xk + 250, y2))
        c.set_text("PlBName%d" % k, (_ban_entry(c, k, (xk + 300, y2 + 800)), "m_PlayerName"), (xk + 550, y2))
        ends = c.exits
        c.exits = [(bk, "else")]
        c.set_vis("PlB%d" % k, BUTTON, "Collapsed", (xk + 250, y2 + 300))
        c.exits += ends
    x += 550 + 1200 * BAN_ROWS
    none = _i(c, "EqualEqual_IntInt", _len(c, _bans(c, (x, y2 + 1300)), "struct", (x + 200, y2 + 1300),
                                           sub=ir.struct_path(BANNED)), 0, (x + 400, y2 + 1300))
    c.set_text("PlNoBans", "No banned players.", (x, y2))
    c.vis_if(none, [("PlNoBans", TEXT)], (x + 300, y2))
    c.set_var("PlBanSeen", "int", c.var("PlBanVer", "int", (x + 900, y2 + 300)), (x + 1200, y2))
    c.exits += skip

    # the server's answer: the status line
    x += 1600
    bm = c.branch(_i(c, "NotEqual_IntInt", c.rvar("PlMsgVer", "int", (x, y2 + 300)), c.var("PlMsgSeen", "int", (x, y2 + 450)),
                     (x + 250, y2 + 300)), (x + 250, y2))
    skip = [(bm, "else")]
    c.exits = [(bm, "then")]
    c.set_var("PlMsgSeen", "int", c.rvar("PlMsgVer", "int", (x + 300, y2 + 300)), (x + 500, y2))
    c.set_text("PlStatus", c.rvar("PlMsg", "string", (x + 600, y2 + 450)), (x + 800, y2))
    c.exits += skip

    # every frame: the highlights, the picked player's name, the confirm strip
    y3 = y + 5000
    x = 0
    for i in range(CEP_ROWS):
        c.color("PlP%d" % i, _i(c, "EqualEqual_IntInt", c.var("PlSel", "int", (x, y3 + 600)), i, (x + 200, y3 + 600)),
                ROW_ON, ROW_OFF, (x, y3))
        x += 300
    for k in range(BAN_ROWS):
        c.color("PlB%d" % k, _i(c, "EqualEqual_IntInt", c.var("PlBanSel", "int", (x, y3 + 600)), k, (x + 200, y3 + 600)),
                ROW_ON, ROW_OFF, (x, y3))
        x += 300
    ok = _sel_ok(c, (x, y3 + 500))
    bs = c.branch(ok, (x, y3))
    c.exits = [(bs, "then")]
    c.set_text("PlSelName", c.at(_names(c, (x + 200, y3 + 900)), c.var("PlSel", "int", (x + 200, y3 + 1050)), "string",
                                 (x + 400, y3 + 900)), (x + 400, y3))
    ends = c.exits
    c.exits = [(bs, "else")]
    c.set_text("PlSelName", "NO PLAYER SELECTED", (x + 400, y3 + 300))
    c.exits += ends
    x += 800
    c.vis_if(c.var("PlConfirmOn", "bool", (x, y3 + 300)), [("PlConfirm", "/Script/UMG.Border")], (x + 200, y3))
    return out + c.exits


# ================================================================ clicks
def admin_clicks(c, y):
    g = c.g

    def on_click(btn):
        c.exits = [(clicked(g, btn, (0, y)), "then")]

    def ready(pos, need_player=True):
        """Relay valid (and, if need_player, a player picked); the status says why not. Leaves the
        exits where it's fine."""
        x, yy = pos
        b = c.branch(c.fn("IsValid", KSL, {"Object": c.relay((x, yy + 300))}, (x + 200, yy + 300)), (x + 200, yy))
        c.exits = [(b, "else")]
        c.set_text("PlStatus", NOT_CONNECTED, (x + 500, yy + 400))
        c.exits = [(b, "then")]
        if need_player:
            bp_ = c.branch(_sel_ok(c, (x + 300, yy + 600)), (x + 500, yy))
            c.exits = [(bp_, "else")]
            c.set_text("PlStatus", PICK, (x + 800, yy + 400))
            c.exits = [(bp_, "then")]

    def state(pos):
        return c.at(_states(c, pos), c.var("PlSel", "int", (pos[0], pos[1] + 150)), "object", (pos[0] + 200, pos[1]))

    for i in range(CEP_ROWS):
        on_click("PlP%d" % i)
        c.set_var("PlSel", "int", str(i), (300, y))
        c.set_var("PlConfirmOn", "bool", "false", (600, y))
        c.set_text("PlStatus", "", (900, y))
        y += 400
    for k in range(BAN_ROWS):
        on_click("PlB%d" % k)
        c.set_var("PlBanSel", "int", str(k), (300, y))
        y += 400

    for btn, event, msg in (("PlGoto", "OwlServerPlGoto", "Teleporting..."),
                            ("PlBring", "OwlServerPlBring", "Bringing them to you...")):
        on_click(btn)
        ready((100, y))
        c.set_var("PlConfirmOn", "bool", "false", (1200, y))
        c.call_relay(event, {"State": state((1300, y + 300))}, (1500, y))
        c.set_text("PlStatus", msg, (1800, y))
        y += 1000

    on_click("PlBan")
    ready((100, y))
    name = c.at(_names(c, (1200, y + 300)), c.var("PlSel", "int", (1200, y + 450)), "string", (1400, y + 300))
    c.set_text("PlConfirmText", c.concat(["Ban ", name, "? They're removed from the server and can't rejoin until you "
                                                         "unban them."], (1600, y + 300)), (1300, y))
    c.set_var("PlConfirmOn", "bool", "true", (1700, y))
    y += 1000
    on_click("PlBanNo")
    c.set_var("PlConfirmOn", "bool", "false", (300, y))
    y += 400
    on_click("PlBanYes")
    ready((100, y))
    c.set_var("PlConfirmOn", "bool", "false", (1200, y))
    c.call_relay("OwlServerPlBan", {"State": state((1300, y + 300))}, (1500, y))
    c.set_text("PlStatus", "Banning...", (1800, y))
    y += 1000

    on_click("PlUnban")
    ready((100, y), need_player=False)
    n = _len(c, _bans(c, (1100, y + 600)), "struct", (1300, y + 600), sub=ir.struct_path(BANNED))
    have = c.fn("BooleanAND", KML, {"A": _i(c, "GreaterEqual_IntInt", c.var("PlBanSel", "int", (1300, y + 750)), 0,
                                            (1500, y + 750)),
                                    "B": _i(c, "Less_IntInt", c.var("PlBanSel", "int", (1300, y + 900)), n,
                                            (1500, y + 600))}, (1700, y + 600))
    bh = c.branch(have, (1200, y))
    c.exits = [(bh, "else")]
    c.set_text("PlStatus", "Pick a banned player first.", (1500, y + 400))
    c.exits = [(bh, "then")]
    e = _ban_entry(c, c.var("PlBanSel", "int", (1300, y + 1100)), (1500, y + 1100))
    c.call_relay("OwlServerPlUnban", {"Id": (e, "m_UniqueNetId"), "Name": (e, "m_PlayerName")}, (2100, y))
    c.set_text("PlStatus", "Unbanning...", (2400, y))
    y += 1500

    on_click("PlRefresh")
    ready((100, y), need_player=False)
    c.call_relay("OwlServerCeList", {}, (1200, y))
    c.call_relay("OwlServerPlBanList", {}, (1500, y))
    c.set_text("PlStatus", "Asking the server again...", (1800, y))
