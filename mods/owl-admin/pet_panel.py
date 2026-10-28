"""The player menu's Pet Shop tab (07): the Pet Shop board. Left: the player's coins and a card per
menu_defs.PETS pet (game icon, name, price). Right: the picked pet -- big icon, name, what buying
does, the price, the status line and Buy.

    player_layout(u, B, R) -> [(widget, slot props)]     player_variables(unreal, bel, wbp)
    bake_player(cdo)       player_tick(c, y)     player_clicks(c, y)
    (c: ce_panel._Ctx on MyRelay)

The coins are the player's Owl wallet (admins set it on the Characters tab). The menu asks the
server for it once per open (OwlServerPetWallet); Buy sends OwlServerPetBuy(PetSel) and the
server's answer (OwlClientPet: new wallet + message) comes back through the relay's PetVer. The
pet item lands in the backpack; the player places it like any tamed pet. Prices and ids here are
for show only: the server uses its own (the relay's class defaults, pet_server).
"""
import menu_defs as D
from ce_panel import _button, _text_button, _lab, KML, KSL, KSTR
from menu_shell import button_style, clicked, SWITCHER

N = len(D.PETS)
IMAGE = "/Script/UMG.Image"
CARD_ON, CARD_OFF = "#2a0b0d", "#0f0707"
NOT_CONNECTED = "Still connecting to the server. Try again in a moment."


def _coins(n):
    return "{:,}".format(n)


def _icon(u, name, path, px):
    u.widget(IMAGE, name, ['Brush=(DrawAs=Image,ResourceObject="/Script/Engine.Texture2D\'%s\'",ImageSize=(X=%.6f,Y=%.6f))'
                           % (path, px * u.S, px * u.S)], variable=False)
    return u.sized(name + "Box", name, w=px, h=px)


# ================================================================ layout
def player_layout(u, B, R):
    mid = ["HorizontalAlignment=HAlign_Center"]
    cards = []
    for k, (name, _id, price, icon) in enumerate(D.PETS):
        c = "PetCard%d" % k
        u.text(c + "Name", name, B, 18, "#ffffff", variable=False)
        u.text(c + "Price", "%s coins" % _coins(price), B, 15, "#ff5a5f", variable=False)
        u.box("VerticalBox", c + "In", [(_icon(u, c + "Icon", icon, 56), mid),
                                        (c + "Name", mid + ["Padding=%s" % u.margin(t=4)]), (c + "Price", mid)])
        _button(u, c, c + "In", u.margin(6, 8, 6, 8), button_style(u, "#ffffff", "#ffffff", "#ffffff"))
        u.border(c + "Frame", "#3a1214", 1.0, u.margin(1, 1, 1, 1), c)
        u.sized(c + "Box", c + "Frame", w=124)
        cards.append((c + "Box", ["Padding=%s" % u.margin(r=6, b=6)]))
    u.box("WrapBox", "PetGrid", cards)
    # the coins under the heading, not beside it: the page is narrow in small windows (they overlapped
    # in a 1000 px Play window, 2026-10-28)
    u.text("PetCoins", "Your coins: ...", B, 20, "#ff5a5f")
    u.box("VerticalBox", "PetLeft", [(_lab(u, B, "PetForSale", "Pets for sale"), []),
                                     ("PetCoins", ["Padding=%s" % u.margin(t=4, b=10)]), ("PetGrid", [])])
    # the picked pet
    u.widget(SWITCHER, "PetBig", ["ActiveWidgetIndex=0"],
             [("/Script/UMG.WidgetSwitcherSlot", _icon(u, "PetBig%d" % k, icon, 120),
               ["HorizontalAlignment=HAlign_Center", "VerticalAlignment=VAlign_Center"])
              for k, (_n, _i, _p, icon) in enumerate(D.PETS)], variable=True)
    u.text("PetSelName", D.PETS[0][0].upper(), B, 26, "#ffffff", spacing_px=3)
    u.text("PetDesc", "", R, 17, "#d8c8c3", wrap=True)
    u.text("PetSelPrice", "", B, 20, "#ff5a5f")
    u.text("PetMsg", "", R, 17, "#f2e6e2", wrap=True)
    u.box("VerticalBox", "PetRightIn", [
        ("PetSelName", mid),
        ("PetBig", mid + ["Padding=%s" % u.margin(t=10, b=10)]),
        (_lab(u, B, "PetKind", "Companion pet"), ["Padding=%s" % u.margin(b=4)]),
        ("PetDesc", ["Padding=%s" % u.margin(b=10)]),
        ("PetSelPrice", ["Padding=%s" % u.margin(b=10)]),
        ("PetMsg", ["Padding=%s" % u.margin(b=12)]),
        (_text_button(u, B, "PetBuy", "Buy", primary=True, h=52, px=18, pad=24, label_var=True),
         ["HorizontalAlignment=HAlign_Fill"])])
    u.border("PetRight", "#0b0606", 1.0, u.margin(20, 16, 20, 16), "PetRightIn")
    u.border("PetRightFrame", "#3a1214", 1.0, u.margin(1, 1, 1, 1), "PetRight")
    u.sized("PetRightBox", "PetRightFrame", w=300)
    u.box("HorizontalBox", "PetBody", [("PetLeft", ["Size=(SizeRule=Fill)", "Padding=%s" % u.margin(r=12)]),
                                       ("PetRightBox", ["VerticalAlignment=VAlign_Top"])])
    return [("PetBody", [])]


def player_variables(unreal, bel, wbp):
    i, s = bel.get_basic_type_by_name("int"), bel.get_basic_type_by_name("string")
    for var, t in (("PetSel", i), ("PetSeen", i), ("PetAsked", i), ("PetNames", bel.get_array_type(s)),
                   ("PetPrices", bel.get_array_type(i))):
        bel.add_member_variable(wbp, var, t)


def bake_player(cdo):
    cdo.set_editor_property("PetNames", [n for n, _i, _p, _c in D.PETS])
    cdo.set_editor_property("PetPrices", [p for _n, _i, p, _c in D.PETS])


# ================================================================ tick
def _i(c, fn, a, b, pos):
    lit = lambda v: v if isinstance(v, tuple) else (str(v), "int")
    return c.fn(fn, KML, {"A": lit(a), "B": lit(b)}, pos)


def player_tick(c, y):
    """Entered from c.exits; leaves c.exits for whatever follows."""
    g, x = c.g, 0
    bv = c.branch(c.fn("IsValid", KSL, {"Object": c.relay((x, y + 300))}, (x + 200, y + 300)), (x + 200, y))
    out = [(bv, "else")]
    c.exits = [(bv, "then")]
    # once per open: ask for the wallet
    ba = c.branch(_i(c, "EqualEqual_IntInt", c.var("PetAsked", "int", (x + 300, y + 450)), 0, (x + 500, y + 450)),
                  (x + 500, y))
    c.exits = [(ba, "then")]
    c.call_relay("OwlServerPetWallet", {}, (x + 800, y))
    c.set_var("PetAsked", "int", "1", (x + 1100, y))
    c.exits += [(ba, "else")]
    x = 1500
    wallet = lambda pos: c.rvar("PetWallet", "int", pos)
    c.set_text("PetCoins", c.int_text(wallet((x, y + 500)), (x + 200, y + 500), prefix="Your coins: "), (x + 300, y))
    x += 600
    sel = lambda pos: c.var("PetSel", "int", pos)
    for k in range(N):
        c.color("PetCard%d" % k, _i(c, "EqualEqual_IntInt", sel((x, y + 650)), k, (x + 200, y + 650)),
                CARD_ON, CARD_OFF, (x, y))
        x += 400
    sw = g.call("SetActiveWidgetIndex", SWITCHER, pos=(x, y))
    w = c.widget("PetBig", SWITCHER, (x - 200, y + 250))
    g.wire(w[0], w[1], sw, "self", exec=False)
    s = sel((x - 200, y + 400))
    g.wire(s[0], s[1], sw, "Index", exec=False)
    c.go(sw)
    x += 400
    name = c.at(c.arr("PetNames", "string", (x, y + 500)), sel((x, y + 650)), "string", (x + 200, y + 500))
    price = c.at(c.arr("PetPrices", "int", (x, y + 800)), sel((x, y + 950)), "int", (x + 200, y + 800))
    c.set_text("PetSelName", c.fn("ToUpper", KSTR, {"SourceString": name}, (x + 400, y + 500)), (x + 500, y))
    c.set_text("PetDesc", c.concat(["A grown, tamed ", name, ". It arrives in your inventory: place it to call it "
                                    "to your side."], (x + 700, y + 500)), (x + 900, y))
    ptxt = c.int_text(price, (x + 400, y + 800))
    c.set_text("PetSelPrice", c.concat(["Price: ", ptxt, " coins"], (x + 700, y + 800)), (x + 1300, y))
    afford = _i(c, "GreaterEqual_IntInt", wallet((x + 1300, y + 1000)), price, (x + 1500, y + 1000))
    c.set_text("PetBuyText", c.fn("SelectString", KML, {"A": c.concat(["BUY FOR ", ptxt], (x + 1500, y + 1150)),
                                                        "B": ("NOT ENOUGH COINS", "string"), "bPickA": afford},
                                  (x + 1700, y + 1000)), (x + 1700, y))
    x += 2100
    # the server's answer: its message
    ver = lambda pos: c.rvar("PetVer", "int", pos)
    bm = c.branch(_i(c, "NotEqual_IntInt", ver((x, y + 300)), c.var("PetSeen", "int", (x, y + 450)), (x + 200, y + 300)),
                  (x + 200, y))
    skip = [(bm, "else")]
    c.exits = [(bm, "then")]
    c.set_var("PetSeen", "int", ver((x + 300, y + 300)), (x + 400, y))
    c.set_text("PetMsg", c.rvar("PetMsg", "string", (x + 600, y + 500)), (x + 700, y))
    c.exits += skip + out


# ================================================================ clicks
def player_clicks(c, y):
    g = c.g
    for k in range(N):
        c.exits = [(clicked(g, "PetCard%d" % k, (0, y)), "then")]
        c.set_var("PetSel", "int", str(k), (300, y))
        c.set_text("PetMsg", "", (600, y))
        y += 400
    c.exits = [(clicked(g, "PetBuy", (0, y)), "then")]
    b = c.branch(c.fn("IsValid", KSL, {"Object": c.relay((100, y + 300))}, (300, y + 300)), (300, y))
    c.exits = [(b, "else")]
    c.set_text("PetMsg", NOT_CONNECTED, (600, y + 400))
    c.exits = [(b, "then")]
    c.call_relay("OwlServerPetBuy", {"Index": c.var("PetSel", "int", (900, y + 300))}, (1200, y))
    c.set_text("PetMsg", "Buying...", (1500, y))
