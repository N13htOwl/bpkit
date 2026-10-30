"""owl-admin step 15: WBP_OwlNpcWindow -- the window a player gets by pressing E on an Owl NPC (14).

The Custom NPC Dialogue and Trade board, in the menus' frame (menu_shell), as a UI module (06's
OwlNpcWindow row, no key: BP_OwlNPC toggles it by name):
    Conversation  -- the NPC's name and role, what it says; Browse wares, Farewell
    Wares         -- one row per ware ("<item> - <price> <coins>", Buy), the server's answer, Back
    footer        -- the player's Gold and Silver Coins (their own backpack, read on their client)

Tick: the NPC is the Owl NPC nearest the player (Npc); its replicated NpcName / NpcRole / NpcLine /
NpcWIds / NpcWPrice / NpcWCur fill the pages. Buy -> MyRelay.OwlServerNpcBuy(Npc, row) (npc_server
checks distance, room and coins, then swaps); the answer (NpcBuyMsgC) shows under the wares.
Item names: NwCatIds / NwCatNames on the class defaults (ce_catalog).

Run with Play STOPPED, after 10 and 14:  python ue_run.py mods/owl-admin/15_npc_window.py
"""
import sys
for _m in list(sys.modules):
    if _m == "bpkit" or _m.startswith("bpkit."):
        sys.modules.pop(_m, None)
import unreal
import os
from bpkit import bridge as bp, ir, build, config as _cfg
sys.path.insert(0, os.path.join(_cfg.REPO_ROOT, "mods", "owl-admin"))
for _m in ("oa_config", "umg_text", "menu_defs", "menu_shell", "ce_panel", "ce_catalog", "tm_catalog"):
    sys.modules.pop(_m, None)
import oa_config as MOD
import menu_defs as D
import ce_catalog
from ce_panel import _Ctx, _text_button, TEXT, KML, KSL, KSTR, KTXT, UW, SWITCHER
from umg_text import Umg
from menu_shell import Shell, clicked

eal = unreal.EditorAssetLibrary
assert not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor(), \
    "Play-in-Editor is running -- stop Play first"

PKG = MOD.resolve_pkg()
PATH = "%s/%s" % (PKG, MOD.NPC_WINDOW_WBP)
FULL = MOD.full(PKG, MOD.NPC_WINDOW_WBP)
RELAY_CLS = MOD.full(PKG, MOD.RELAY) + "_C"
NPC_CLS = MOD.full(PKG, MOD.NPC_BP) + "_C"
for c in (RELAY_CLS, NPC_CLS):
    assert unreal.load_object(None, c), "build 10 and 14 first: no " + c
CATALOG = ce_catalog.catalog(unreal)
W = D.NPC_WARES
ACTOR = "/Script/Engine.Actor"
INV = "/Script/ConanSandbox.ItemInventory"
CHAR = "/Script/ConanSandbox.ConanCharacter"
GS = "/Script/Engine.GameplayStatics"
GUIMC = "/Script/ConanSandbox.GUIModuleController"
HBOX = "/Script/UMG.HorizontalBox"
TABS = [("talk", "Conversation", "Talk with this merchant"), ("wares", "Wares", "What this merchant sells")]

u = Umg(MOD.BOARD_SCALE)
B, R = MOD.FONT_BOLD, MOD.FONT_REGULAR
s = Shell(u, "MERCHANT", TABS, MOD.NPC_MODULE, (B, R), badge="NPC", status="")
s.header(logo=MOD.full(PKG, MOD.LOGO_TEX))
s.sidebar()


def card(name, inner):
    u.border(name + "Fill", "#120909", 1.0, u.margin(22, 18, 22, 18), inner)
    return u.border(name, "#3a1214", 1.0, u.margin(1, 1, 1, 1), name + "Fill")


def gap(px):
    return ["Padding=%s" % u.margin(b=px)]


def page(tab):
    if tab == "talk":
        u.text("NwName", "", B, 26, "#ffffff", spacing_px=3)
        u.text("NwRole", "", B, 16, "#f0343a", spacing_px=3)
        u.text("NwLine", "", R, 20, "#f2e6e2", wrap=True)
        return [("NwName", gap(2)), ("NwRole", gap(16)), (card("NwLineCard", "NwLine"), gap(20)),
                (_text_button(u, B, "NwBrowse", "Browse wares", primary=True, h=52, px=18, pad=24),
                 ["HorizontalAlignment=HAlign_Left", "Padding=%s" % u.margin(b=10)]),
                (_text_button(u, B, "NwBye", "Farewell", h=52, px=18, pad=24), ["HorizontalAlignment=HAlign_Left"])]
    rows = []
    for k in range(W):
        u.text("NwR%dTxt" % k, "", B, 18, "#f2e6e2", wrap=True)
        u.box("HorizontalBox", "NwR%dIn" % k, [
            ("NwR%dTxt" % k, ["Size=(SizeRule=Fill)", "VerticalAlignment=VAlign_Center"]),
            (_text_button(u, B, "NwR%dBtn" % k, "Buy", primary=True, h=44, px=16, pad=20), ["VerticalAlignment=VAlign_Center"])])
        u.border("NwR%dFill" % k, "#120909", 1.0, u.margin(16, 8, 10, 8), "NwR%dIn" % k)
        u.border("NwR%d" % k, "#2a1012", 1.0, u.margin(1, 1, 1, 1), "NwR%dFill" % k, props=["Visibility=Collapsed"],
                 variable=True)
        rows.append(("NwR%d" % k, gap(8)))
    u.text("NwNone", "This merchant has nothing for sale right now.", R, 17, "#a8908a", wrap=True)
    u.text("NwMsg", "", B, 17, "#f2e6e2", wrap=True)
    return rows + [("NwNone", gap(10)), ("NwMsg", gap(14)),
                   (_text_button(u, B, "NwBack", "Back to conversation", h=44, px=16, pad=20), ["HorizontalAlignment=HAlign_Left"])]


body = s.pages(page)
s.footer()
s.root(body)
wbp, wbp_ptr = s.paste(unreal, eal, bp, PKG, MOD.NPC_WINDOW_WBP, FULL)

bel = unreal.BlueprintEditorLibrary
T = bel.get_basic_type_by_name
for var, vt in (("NwCatIds", bel.get_array_type(T("int"))), ("NwCatNames", bel.get_array_type(T("string"))),
                ("NwBest", T("real")),
                ("Npc", bel.get_object_reference_type(unreal.load_object(None, NPC_CLS))),
                ("MyRelay", bel.get_object_reference_type(unreal.load_object(None, RELAY_CLS)))):
    bel.add_member_variable(wbp, var, vt)
bel.compile_blueprint(wbp)

# ================================================================ graph
g = ir.Graph("EventGraph")
s.graph(g)
owning = lambda pos: g.call("GetOwningPlayer", UW, pos=pos)
c = _Ctx(g, u, RELAY_CLS, owning, relay_var="MyRelay")
lit = lambda v: v if isinstance(v, tuple) else (str(v), "int")
imath = lambda fn, a, b, pos: c.fn(fn, KML, {"A": lit(a), "B": lit(b)}, pos)
npc = lambda pos: c.var("Npc", "object", pos, sub=ir.obj_path(NPC_CLS))


def nvar(name, cat, pos, arr=False):
    n = g.var_get(name, cat, parent=NPC_CLS, pos=pos)
    if arr:
        n.pin(name).set("PinType.ContainerType", "Array")
    v = npc((pos[0] - 200, pos[1]))
    g.wire(v[0], v[1], n, "self", exec=False)
    return (n, name)


def grouped(v, pos):
    """10000 -> "10,000"."""
    t = c.fn("Conv_IntToText", KTXT, {"Value": v, "bUseGrouping": ("true", "bool")}, pos)
    return c.fn("Conv_TextToString", KTXT, {"InText": t}, (pos[0] + 200, pos[1]))


tick = g.event("Tick", parent=UW, pos=(0, 3800))
last = s.tick_highlight(g, tick)
c.exits = [(last, "then")]
y = 6000
missing = c.find_relay((0, y))
c.exits += missing
# ---- the nearest Owl NPC
y = 8000
pawn = g.call("GetOwningPlayerPawn", UW, pos=(0, y + 600))
c.set_var("NwBest", "real", "1000000000.0", (200, y))
clear = g.var_set("Npc", "object", ir.obj_path(NPC_CLS), pos=(500, y))
c.go(clear)
found = g.get_all_actors(NPC_CLS, pos=(800, y))
c.go(found)
each = g.foreach(ACTOR, pos=(1100, y))
g.wire(found, "then", each, "Exec")
g.wire(found, "OutActors", each, "Array", exec=False)
dist = c.fn("GetDistanceTo", ACTOR, {"self": (pawn, "ReturnValue"), "OtherActor": (each, "Array Element")}, (1400, y + 300))
closer = c.fn("Less_DoubleDouble", KML, {"A": dist, "B": c.var("NwBest", "real", (1400, y + 450))}, (1600, y + 300))
bc = g.branch(pos=(1700, y))
g.wire(each, "LoopBody", bc, "execute")
g.wire(closer[0], closer[1], bc, "Condition", exec=False)
c.exits = [(bc, "then")]
c.set_var("NwBest", "real", dist, (2000, y))
cast = g.cast(NPC_CLS, pos=(2300, y))
cast.pin("Object").typed("object", ir.obj_path(ACTOR), direction="EGPD_Input")
g.wire(each, "Array Element", cast, "Object", exec=False)
c.go(cast)
sn = g.var_set("Npc", "object", ir.obj_path(NPC_CLS), pos=(2600, y))
g.wire(cast, "AsBP Owl NPC", sn, "Npc", exec=False)
c.go(sn)
c.exits = [(each, "Completed")]
# ---- fill the pages from it
x, y = 3000, 8000
bv = c.branch(c.fn("IsValid", KSL, {"Object": npc((x, y + 300))}, (x + 200, y + 300)), (x + 200, y))
no_npc = [(bv, "else")]
c.exits = [(bv, "then")]
x += 500
c.set_text("NwName", nvar("NpcName", "string", (x, y + 600)), (x, y))
c.set_text("NwRole", nvar("NpcRole", "string", (x + 300, y + 600)), (x + 300, y))
c.set_text("NwLine", nvar("NpcLine", "string", (x + 600, y + 600)), (x + 600, y))
x += 1000
n = (g.array_len(*nvar("NpcWIds", "int", (x, y + 600), arr=True), (x + 200, y + 600), elem_cat="int"), "ReturnValue")
c.vis_if(imath("EqualEqual_IntInt", n, 0, (x + 300, y + 750)), [("NwNone", TEXT)], (x + 300, y))
x += 1000
for k in range(W):
    xx = x + 1400 * k
    b = c.branch(imath("Less_IntInt", k, n, (xx, y + 300)), (xx, y))
    c.exits = [(b, "then")]
    c.set_vis("NwR%d" % k, "/Script/UMG.Border", "Visible", (xx + 300, y))
    tid = c.at(nvar("NpcWIds", "int", (xx, y + 600), arr=True), k, "int", (xx + 200, y + 600))
    price = c.at(nvar("NpcWPrice", "int", (xx, y + 750), arr=True), k, "int", (xx + 200, y + 750))
    gold = imath("EqualEqual_IntInt", c.at(nvar("NpcWCur", "int", (xx, y + 900), arr=True), k, "int", (xx + 200, y + 900)),
                 0, (xx + 400, y + 900))
    coin = c.fn("SelectString", KML, {"A": (" %ss" % D.NPC_CURRENCIES[0][0], "string"),
                                      "B": (" %ss" % D.NPC_CURRENCIES[1][0], "string"), "bPickA": gold}, (xx + 600, y + 900))
    at = c.find(c.arr("NwCatIds", "int", (xx, y + 1050)), tid, "int", (xx + 200, y + 1050))
    name = c.fn("SelectString", KML, {
        "A": c.at(c.arr("NwCatNames", "string", (xx, y + 1200)), at, "string", (xx + 200, y + 1200)),
        "B": c.concat(["Item ", c.int_text(tid, (xx + 200, y + 1350))], (xx + 400, y + 1350)),
        "bPickA": imath("GreaterEqual_IntInt", at, 0, (xx + 400, y + 1050))}, (xx + 600, y + 1200))
    c.set_text("NwR%dTxt" % k, c.concat([name, "  -  ", grouped(price, (xx + 600, y + 600)), coin], (xx + 800, y + 750)),
               (xx + 600, y))
    shown = c.exits
    c.exits = [(b, "else")]
    c.set_vis("NwR%d" % k, "/Script/UMG.Border", "Collapsed", (xx + 300, y + 300))
    c.exits += shown
c.exits += no_npc
# ---- the server's answer to a Buy (needs the relay)
x, y = 0, 11000
br = c.branch(c.fn("IsValid", KSL, {"Object": c.relay((x, y + 300))}, (x + 200, y + 300)), (x + 200, y))
c.exits = [(br, "then")]
c.set_text("NwMsg", c.rvar("NpcBuyMsgC", "string", (x + 400, y + 300)), (x + 500, y))
c.exits += [(br, "else")]
# ---- the footer: this player's coins
x += 1000
me = c.fn("GetOwningPlayerPawn", UW, {}, (x - 200, y + 300))
pc = c.branch(c.fn("IsValid", KSL, {"Object": me}, (x, y + 300)), (x, y))
c.exits = [(pc, "then")]
bag = g.call("GetInventoryByType", INV, pos=(x + 300, y + 450))
g.wire(me[0], me[1], bag, "owner", exec=False)
g.typed_input(bag, "inventoryType", "Backpack", "byte", ir.enum_path("/Script/ConanSandbox.EInventoryType"))
coins = [c.fn("GetNumberOfItemsByTemplate", INV, {"self": (bag, "ReturnValue"), "templateID": (str(tid_), "int")},
              (x + 600, y + 300 + 150 * j)) for j, (_n, tid_) in enumerate(D.NPC_CURRENCIES)]
c.set_text("StatusText", c.concat(["Your %ss: " % D.NPC_CURRENCIES[0][0], grouped(coins[0], (x + 800, y + 300)),
                                   "      %ss: " % D.NPC_CURRENCIES[1][0], grouped(coins[1], (x + 800, y + 450))],
                                  (x + 1100, y + 300)), (x + 900, y))

# ================================================================ clicks
pages = lambda pos: (g.var_get("TabPages", "object", ir.obj_path(SWITCHER), pos=pos), "TabPages")
for k, (btn, idx) in enumerate((("NwBrowse", 1), ("NwBack", 0))):
    ev = clicked(g, btn, (0, 14000 + 300 * k))
    sai = g.call("SetActiveWidgetIndex", SWITCHER, pos=(400, 14000 + 300 * k))
    if idx:
        g.typed_input(sai, "Index", str(idx), "int")
    g.wire(ev, "then", sai, "execute")
    g.wire(*pages((200, 14150 + 300 * k)), sai, "self", exec=False)
ev = clicked(g, "NwBye", (0, 15000))
gmc = g.call("GetGUIModuleController", GUIMC, pos=(200, 15200))
tgl = g.call("ToggleModule", GUIMC, pos=(500, 15000))
g.typed_input(tgl, "ModuleName", MOD.NPC_MODULE, "name")
g.wire(ev, "then", tgl, "execute")
g.wire(gmc, "ReturnValue", tgl, "self", exec=False)
for k in range(W):
    yy = 16000 + 400 * k
    c.exits = [(clicked(g, "NwR%dBtn" % k, (0, yy)), "then")]
    bb = c.branch(c.fn("IsValid", KSL, {"Object": c.relay((200, yy + 250))}, (300, yy + 250)), (300, yy))
    c.exits = [(bb, "then")]
    c.call_relay("OwlServerNpcBuy", {"Npc": npc((500, yy + 250)),
                                     "Entry": c.fn("MakeLiteralInt", KSL, {"Value": (str(k), "int")}, (500, yy + 400))},
                 (700, yy))

# Clear + compile first (see 07)
_bp_ptr, _g_ptr = bp.find_graph(FULL, "EventGraph")
bp.clear_graph(_bp_ptr, _g_ptr)
bp.mark_structurally_modified(_bp_ptr)
bel.compile_blueprint(wbp)
rep = build.build_graph(FULL, g)
assert rep["ok"], "NPC window graph not clean: %r" % {k: rep[k] for k in (
    "dropped_nodes", "dropped_links", "orphans", "wildcards", "errors")}

cdo = unreal.get_default_object(unreal.load_object(None, FULL + "_C"))
cdo.set_editor_property("NwCatIds", [e["id"] for e in CATALOG])
cdo.set_editor_property("NwCatNames", [e["name"] for e in CATALOG])
assert len(cdo.get_editor_property("NwCatIds")) == len(CATALOG), "catalogue not stored on the CDO"
assert bp.root_widget(wbp_ptr) == s.root_ptr, "root changed during compile"
assert eal.save_asset(PATH), "save failed"
print("BUILD OK: owl-admin v%d -> %s  (%d widgets, %d wares rows, %d catalogue items)%s" % (
    MOD.VERSION, FULL, len(u.cls), W, len(CATALOG), "  [DRY RUN -- not shippable]" if PKG != MOD.OUTPUT_PKG else ""))
