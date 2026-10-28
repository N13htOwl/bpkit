"""The player menu's Animal Masks tab (07): the Masks board. Left: a card per menu_defs.MASKS head
piece (game icon, name, WEARING on the one worn). Right: the picked one -- big icon, name, what
wearing does, the status line and Wear / Take off.

    player_layout(u, B, R) -> [(widget, slot props)]     player_variables(unreal, bel, wbp)
    bake_player(cdo)       player_tick(c, y)     player_clicks(c, y)
    (c: ce_panel._Ctx on MyRelay)

No server code of its own: a mask is a Transmog Head appearance. Wear sets the menu's TmPick[0]
(the look the Transmog tab edits) to the mask's row and sends the whole look with the relay's
OwlServerTmApply, so the other four slots stay as they are; Take off sets it to "" (worn gear).
What is worn is read back from the relay's replicated TmLook[0], so the cards show the server's
look. Looks only: the real helmet and its armor stay.
"""
import menu_defs as D
from ce_panel import _button, _text_button, _lab, KML, KSL, KSTR
from menu_shell import button_style, clicked, SWITCHER
from pet_panel import _icon, _i, CARD_ON, CARD_OFF, NOT_CONNECTED

N = len(D.MASKS)
DESC = "Changes how your head looks. Your real helmet, its armor and your stats stay the same."


# ================================================================ layout
def player_layout(u, B, R):
    mid = ["HorizontalAlignment=HAlign_Center"]
    cards = []
    for k, (name, _row, icon) in enumerate(D.MASKS):
        c = "MaskCard%d" % k
        u.text(c + "Name", name, B, 16, "#ffffff", wrap=True, variable=False,
               props=["Justification=Center"])
        u.text(c + "Worn", "", B, 13, "#ff5a5f", spacing_px=1)
        u.box("VerticalBox", c + "In", [(_icon(u, c + "Icon", icon, 56), mid),
                                        (c + "Name", mid + ["Padding=%s" % u.margin(t=4)]), (c + "Worn", mid)])
        _button(u, c, c + "In", u.margin(6, 8, 6, 8), button_style(u, "#ffffff", "#ffffff", "#ffffff"))
        u.border(c + "Frame", "#3a1214", 1.0, u.margin(1, 1, 1, 1), c)
        u.sized(c + "Box", c + "Frame", w=124, h=128)
        cards.append((c + "Box", ["Padding=%s" % u.margin(r=6, b=6)]))
    u.box("WrapBox", "MaskGrid", cards)
    u.box("VerticalBox", "MaskLeft", [(_lab(u, B, "MaskCollection", "Collection"), ["Padding=%s" % u.margin(b=10)]),
                                      ("MaskGrid", [])])
    u.widget(SWITCHER, "MaskBig", ["ActiveWidgetIndex=0"],
             [("/Script/UMG.WidgetSwitcherSlot", _icon(u, "MaskBig%d" % k, icon, 120),
               ["HorizontalAlignment=HAlign_Center", "VerticalAlignment=VAlign_Center"])
              for k, (_n, _r, icon) in enumerate(D.MASKS)], variable=True)
    u.text("MaskSelName", D.MASKS[0][0].upper(), B, 22, "#ffffff", spacing_px=2, wrap=True)
    u.text("MaskDesc", DESC, R, 17, "#d8c8c3", wrap=True, variable=False)
    u.text("MaskStatus", "No mask worn", B, 18, "#ff5a5f", wrap=True)
    u.text("MaskMsg", "", R, 16, "#f2e6e2", wrap=True)
    u.box("VerticalBox", "MaskRightIn", [
        ("MaskSelName", mid),
        ("MaskBig", mid + ["Padding=%s" % u.margin(t=10, b=10)]),
        ("MaskDesc", ["Padding=%s" % u.margin(b=10)]),
        ("MaskStatus", ["Padding=%s" % u.margin(b=6)]),
        ("MaskMsg", ["Padding=%s" % u.margin(b=12)]),
        (_text_button(u, B, "MaskWear", "Wear", primary=True, h=52, px=18, pad=24, label_var=True),
         ["HorizontalAlignment=HAlign_Fill"])])
    u.border("MaskRight", "#0b0606", 1.0, u.margin(20, 16, 20, 16), "MaskRightIn")
    u.border("MaskRightFrame", "#3a1214", 1.0, u.margin(1, 1, 1, 1), "MaskRight")
    u.sized("MaskRightBox", "MaskRightFrame", w=300)
    u.box("HorizontalBox", "MaskBody", [("MaskLeft", ["Size=(SizeRule=Fill)", "Padding=%s" % u.margin(r=12)]),
                                        ("MaskRightBox", ["VerticalAlignment=VAlign_Top"])])
    return [("MaskBody", [])]


def player_variables(unreal, bel, wbp):
    i, s = bel.get_basic_type_by_name("int"), bel.get_basic_type_by_name("string")
    for var, t in (("MaskSel", i), ("MaskOff", bel.get_basic_type_by_name("bool")), ("MaskIds", bel.get_array_type(s)),
                   ("MaskNames", bel.get_array_type(s))):
        bel.add_member_variable(wbp, var, t)


def bake_player(cdo):
    cdo.set_editor_property("MaskIds", [row for _n, row, _i in D.MASKS])
    cdo.set_editor_property("MaskNames", [n for n, _r, _i in D.MASKS])


# ================================================================ tick
def _worn(c, pos):
    """The relay's TmLook[0] (the head appearance the server has), "" if TmLook is empty."""
    x, y = pos
    look = c.rvar("TmLook", "string", (x, y), arr=True)
    n = c.g.array_len(look[0], look[1], (x + 200, y + 150), elem_cat="string")
    first = c.at(c.rvar("TmLook", "string", (x, y + 300), arr=True), 0, "string", (x + 200, y + 300))
    return c.fn("SelectString", KML, {"A": first, "B": ("", "string"),
                                      "bPickA": _i(c, "Greater_IntInt", (n, "ReturnValue"), 0, (x + 400, y + 150))},
                (x + 600, y + 150))


def player_tick(c, y):
    """Entered from c.exits; leaves c.exits for whatever follows."""
    g, x = c.g, 0
    bv = c.branch(c.fn("IsValid", KSL, {"Object": c.relay((x, y + 300))}, (x + 200, y + 300)), (x + 200, y))
    out = [(bv, "else")]
    c.exits = [(bv, "then")]
    x = 500
    sel = lambda pos: c.var("MaskSel", "int", pos)
    ids = lambda pos: c.arr("MaskIds", "string", pos)
    for k in range(N):
        worn_k = c.fn("EqualEqual_StrStr", KSTR, {"A": _worn(c, (x, y + 700)),
                                                  "B": c.at(ids((x, y + 1100)), k, "string", (x + 200, y + 1100))},
                      (x + 800, y + 900))
        c.color("MaskCard%d" % k, _i(c, "EqualEqual_IntInt", sel((x, y + 650)), k, (x + 200, y + 650)),
                CARD_ON, CARD_OFF, (x, y))
        c.set_text("MaskCard%dWorn" % k, c.fn("SelectString", KML, {"A": ("WEARING", "string"), "B": ("", "string"),
                                                                    "bPickA": worn_k}, (x + 1000, y + 900)),
                   (x + 400, y))
        x += 1300
    sw = g.call("SetActiveWidgetIndex", SWITCHER, pos=(x, y))
    w = c.widget("MaskBig", SWITCHER, (x - 200, y + 250))
    g.wire(w[0], w[1], sw, "self", exec=False)
    s = sel((x - 200, y + 400))
    g.wire(s[0], s[1], sw, "Index", exec=False)
    c.go(sw)
    x += 400
    name = c.at(c.arr("MaskNames", "string", (x, y + 500)), sel((x, y + 650)), "string", (x + 200, y + 500))
    c.set_text("MaskSelName", c.fn("ToUpper", KSTR, {"SourceString": name}, (x + 400, y + 500)), (x + 500, y))
    # the worn one's name (or none), and Wear / Take off for the picked one
    worn = _worn(c, (x + 600, y + 700))
    found = c.find(ids((x + 1300, y + 900)), worn, "string", (x + 1500, y + 900))
    safe = c.fn("Max", KML, {"A": found, "B": ("0", "int")}, (x + 1600, y + 1250))   # -1 (none) would log a warning
    wname = c.at(c.arr("MaskNames", "string", (x + 1500, y + 1100)), safe, "string", (x + 1700, y + 1100))
    has = _i(c, "GreaterEqual_IntInt", found, 0, (x + 1700, y + 900))
    c.set_text("MaskStatus", c.fn("SelectString", KML, {"A": c.concat(["Wearing: ", wname], (x + 1900, y + 1100)),
                                                        "B": ("No mask worn", "string"), "bPickA": has},
                                  (x + 2100, y + 900)), (x + 1000, y))
    this = _i(c, "EqualEqual_IntInt", found, sel((x + 1900, y + 1300)), (x + 2100, y + 1300))
    c.set_text("MaskWearText", c.fn("SelectString", KML, {"A": ("TAKE OFF", "string"), "B": ("WEAR", "string"),
                                                          "bPickA": this}, (x + 2300, y + 1300)), (x + 1400, y))
    c.exits += out


# ================================================================ clicks
def player_clicks(c, y):
    g = c.g
    for k in range(N):
        c.exits = [(clicked(g, "MaskCard%d" % k, (0, y)), "then")]
        c.set_var("MaskSel", "int", str(k), (300, y))
        c.set_text("MaskMsg", "", (600, y))
        y += 400
    # Wear / Take off: TmPick[0] = the picked mask, or "" when it's the one worn; then apply the look
    c.exits = [(clicked(g, "MaskWear", (0, y)), "then")]
    b = c.branch(c.fn("IsValid", KSL, {"Object": c.relay((100, y + 300))}, (300, y + 300)), (300, y))
    c.exits = [(b, "else")]
    c.set_text("MaskMsg", NOT_CONNECTED, (600, y + 400))
    c.exits = [(b, "then")]
    picked = c.at(c.arr("MaskIds", "string", (400, y + 600)), c.var("MaskSel", "int", (400, y + 750)), "string",
                  (600, y + 600))
    # kept in MaskOff: on a listen server the RPC below changes TmLook before the message is picked
    c.set_var("MaskOff", "bool", c.fn("EqualEqual_StrStr", KSTR, {"A": _worn(c, (400, y + 900)), "B": picked},
                                      (1000, y + 750)), (1100, y))
    off = c.var("MaskOff", "bool", (1100, y + 450))
    new = c.fn("SelectString", KML, {"A": ("", "string"), "B": picked, "bPickA": off}, (1200, y + 600))
    st = g.array_fn("Array_Set", pos=(1400, y), elem_cat="string")
    g.array_item_pin(st, "Item", "string")
    tp = c.arr("TmPick", "string", (1200, y + 300))
    g.wire(tp[0], tp[1], st, "TargetArray", exec=False)
    st.pin("Index").typed("int", direction="EGPD_Input").literal("0")
    g.wire(new[0], new[1], st, "Item", exec=False)
    c.go(st)
    c.set_var("TmDirty", "bool", "true", (1700, y))        # the Transmog tab shows it too
    c.call_relay("OwlServerTmApply", {"Look": c.arr("TmPick", "string", (1800, y + 300))}, (2000, y))
    c.set_text("MaskMsg", c.fn("SelectString", KML, {"A": ("Mask taken off.", "string"),
                                                     "B": ("Mask on. Only your look changed.", "string"),
                                                     "bPickA": c.var("MaskOff", "bool", (2000, y + 450))},
                                     (2200, y + 300)), (2400, y))
