"""owl-admin step 07: WBP_OwlPlayerMenu -- the player menu (Shift+I), for every player.

The same frame as the admin menu (menu_shell), with one tab per player-facing board on the
design canvas (menu_defs.PLAYER_TABS). No login: nothing here is admin-only.

Transmog tab (the Transmog Outfits board), three columns:
    Preview      -- per slot: the chosen appearance's icon and name ("Worn gear" if none)
    Appearances  -- slot tabs (Head .. Feet), category chips + count, search, and a grid of
                    WBP_OwlTmCell (tm_cell / 11) made at runtime for the items that match
    Saved outfits-- up to TM_MAX_OUTFITS rows (name + Load), a name box + Save outfit, the status
                    line, Clear appearance, Apply look
The catalogue (tm_catalog: ~580 wearables from the game's ItemTable) is baked into the
menu's CDO as parallel arrays TmIds / TmNames / TmIcons / TmSlots / TmCats. The player's look
(TmPick: one row name per slot, "" = worn gear) and saved outfits live on the server, on the
player's relay (10), replicated to every player. Apply look / Save outfit are the relay's
server RPCs; the relay then shows the applied look on the character, for everyone.

Graph:
    Tick     -> tab highlight; find this player's relay once (MyRelay); when its TmClientVer
                changes: fill the outfit rows (and, the first time only, TmPick = its TmLook),
                mark dirty; when dirty or the search text changed: tab/chip colours, rebuild
                the grid, count, preview
    OwlTmPick(Index)       <- a cell's click: toggle that item in the current slot
    slot tab / chip / Clear / Load -> change TmSlot / TmCat / TmPick, mark dirty
    Apply look / Save outfit -> MyRelay.OwlServerTmApply / OwlServerTmSaveOutfit

Bug Report tab (the Bug Report board): bug_panel.py -- kind, title, text and the details sent with
it; Send report -> MyRelay.OwlServerBugReport; the server's answer (BugSentVer) shows the sent page.

Pet Shop tab (the Pet Shop board): pet_panel.py -- eight pets bought with the Owl wallet
(MyRelay.OwlServerPetBuy, pet_server); the pet item lands in the backpack.

Animal Masks tab (the Masks board): mask_panel.py -- nine animal-like game head pieces; Wear /
Take off sets TmPick[0] and sends the look with MyRelay.OwlServerTmApply (looks only).

Equipment tab: gear_panel.py -- what the player really wears per slot (read from the
character's CharacterLayout), with the item table's armor; read only.

All the player tabs are built.
Parent class WindowRoot + the OwlPlayerMenu row (06) make it a GUIModule like the admin menu.

Run with Play STOPPED, after 10:  python ue_run.py mods/owl-admin/07_player_menu.py
"""
import sys
for _m in list(sys.modules):
    if _m == "bpkit" or _m.startswith("bpkit."):
        sys.modules.pop(_m, None)
import unreal
import os
from bpkit import bridge as bp, ir, build, config as _cfg
sys.path.insert(0, os.path.join(_cfg.REPO_ROOT, "mods", "owl-admin"))
for _m in ("oa_config", "umg_text", "menu_defs", "menu_shell", "tm_catalog", "tm_cell", "ce_panel", "bug_panel", "pet_panel", "mask_panel", "gear_panel"):
    sys.modules.pop(_m, None)
import oa_config as MOD
import menu_defs as D
import tm_catalog
import tm_cell
import ce_panel
import bug_panel
import pet_panel
import mask_panel
import gear_panel
from umg_text import Umg
from menu_shell import Shell, button, button_style, framed, clicked, scroll_style

eal = unreal.EditorAssetLibrary
assert not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor(), \
    "Play-in-Editor is running -- stop Play first"

PKG = MOD.resolve_pkg()
PATH = "%s/%s" % (PKG, MOD.PLAYER_MENU_WBP)
FULL = MOD.full(PKG, MOD.PLAYER_MENU_WBP)
RELAY_CLS = MOD.full(PKG, MOD.RELAY) + "_C"
CELL_FULL = MOD.full(PKG, MOD.TM_CELL_WBP)
CELL_CLS = CELL_FULL + "_C"
assert unreal.load_object(None, RELAY_CLS), "build 10 first: no " + RELAY_CLS
tm_cell.ensure(unreal, eal, bp, PKG, CELL_FULL)
CATALOG = tm_catalog.catalog(unreal)
GEAR = gear_panel.catalog(unreal)
N_SLOTS = len(D.TM_SLOTS)
N_OUT = MOD.TM_MAX_OUTFITS

u = Umg(MOD.BOARD_SCALE)
B, R = MOD.FONT_BOLD, MOD.FONT_REGULAR
s = Shell(u, "PLAYER MENU", D.PLAYER_TABS, MOD.PLAYER_MODULE, (B, R),
          badge="PLAYER", status="Transmog, Pet Shop, Animal Masks, Equipment and Bug Report are ready.")
s.header(logo=MOD.full(PKG, MOD.LOGO_TEX))
s.sidebar()

TAB_ON, TAB_OFF = "#b3121a", "#150909"


# ================================================================ transmog layout
def head(name, text):
    return u.text(name, text, B, 18, "#ffffff", spacing_px=3, variable=False)


def stab(name, label, h=40, px=15, tinted=True):
    """The board's .stab: a tab-like button. tinted: white brushes the graph tints active/idle
    (slot tabs, chips); else a fixed dark style (Load)."""
    u.text(name + "Text", label.upper(), B, px, "#ffffff", spacing_px=1, variable=False)
    style = button_style(u, "#ffffff", "#ffffff", "#ffffff") if tinted else \
        button_style(u, TAB_OFF, "#2a0b0d", "#3a0b0e")
    button(u, name, name + "Text", u.margin(12, 0, 12, 0), style)
    framed(u, name + "Frame", "#4a1a1d", "#150909", name, u.margin())
    return u.sized(name + "Box", name + "Frame", h=h)


def wrap_row(name, items):
    """Buttons that flow onto more lines when the column is narrow."""
    return u.widget("/Script/UMG.WrapBox", name, ["InnerSlotPadding=(X=%.6f,Y=%.6f)" % (6 * u.S, 6 * u.S)],
                    [("/Script/UMG.WrapBoxSlot", c, []) for c in items])


def btn(name, label, primary=False):
    """The board's .btn / .btn.primary, full column width."""
    u.text(name + "Text", label.upper(), B, 15, "#ffffff", spacing_px=1, variable=False)
    if primary:
        button(u, name, name + "Text", u.margin(), button_style(u, "#b3121a", "#d01a22", "#8a2a2e"))
        return u.sized(name + "Box", name, h=48)
    button(u, name, name + "Text", u.margin(), button_style(u, "#0b0505", "#1a0c0c", "#3a0b0e"))
    framed(u, name + "Frame", "#5a1a1e", "#0b0505", name, u.margin())
    return u.sized(name + "Box", name + "Frame", h=48)


def field(name, hint):
    """The board's .field."""
    u.widget("/Script/UMG.EditableTextBox", name, [
        'HintText=INVTEXT("%s")' % u.quote(hint),
        "WidgetStyle=(BackgroundImageNormal=%s,BackgroundImageHovered=%s,BackgroundImageFocused=%s,"
        "Padding=%s,ForegroundColor=(SpecifiedColor=%s),"
        "TextStyle=(Font=%s,ColorAndOpacity=(SpecifiedColor=%s)))" % (
            u.brush("#120909"), u.brush("#1a0c0c"), u.brush("#1a0c0c"), u.margin(14, 0, 14, 0), u.lin("#f2e6e2"),
            u.font(R, 18), u.lin("#f2e6e2")),
    ], variable=True)
    framed(u, name + "Frame", "#4a1a1d", "#120909", name, u.margin())
    return u.sized(name + "Size", name + "Frame", h=44)


def column(name, items, w=None, fill="#0b0606"):
    """One of the board's three columns; clipped so a narrow window can't draw it over its
    neighbour."""
    u.box("VerticalBox", name + "List", items)
    u.border(name, fill, 1.0, u.margin(14, 16, 14, 16), name + "List", props=["Clipping=ClipToBounds"])
    return u.sized(name + "Box", name, w=w) if w else name


def gap(px):
    return ["Padding=%s" % u.margin(b=px)]


def tm_page():
    # ---- preview: one row per slot -- icon, slot label, chosen name
    rows = [(head("TmPrevHead", "Preview"), gap(14))]
    for i, (k, label, _loc) in enumerate(D.TM_SLOTS):
        u.widget("/Script/UMG.Image", "TmPrevImg_" + k, ["Brush=%s" % u.brush("#ffffff", w=40, h=40),
                                                       "Visibility=Hidden"], variable=True)
        framed(u, "TmPrevIco_" + k, "#3a1214", "#1a0c0c", "TmPrevImg_" + k, u.margin(2, 2, 2, 2))
        u.text("TmSlotLbl_" + k, label, B, 15, "#b8a29c", variable=False)
        u.text("TmSum_" + k, "Worn gear", B, 15, "#f2e6e2", wrap=True)
        u.box("VerticalBox", "TmSumTxt_" + k, [("TmSlotLbl_" + k, []), ("TmSum_" + k, [])])
        u.box("HorizontalBox", "TmPrevRow_" + k, [
            ("TmPrevIco_" + k, ["VerticalAlignment=VAlign_Center"]),
            ("TmSumTxt_" + k, ["Size=(SizeRule=Fill)", "Padding=%s" % u.margin(l=8), "VerticalAlignment=VAlign_Center"])])
        rows.append(("TmPrevRow_" + k, gap(10)))
    # side columns sized for the narrowest window the menu meets (the editor's Play viewport,
    # ~640 board px of page): the grid keeps what is left and wraps its cells to fit
    preview = column("TmPreview", rows, w=190)

    # ---- appearances
    wrap_row("TmSlotTabs", [stab("TmSlotBtn_" + k, label) for k, label, _loc in D.TM_SLOTS])
    wrap_row("TmChips", [stab("TmCatBtn_" + k, label, h=34, px=13) for k, label, _g in D.TM_CATS])
    u.text("TmCount", "", B, 15, "#b8a29c")
    u.widget("/Script/UMG.WrapBox", "TmGrid", ["InnerSlotPadding=(X=%.6f,Y=%.6f)" % (8 * u.S, 8 * u.S)], [],
             variable=True)
    u.box("ScrollBox", "TmGridScroll", [("TmGrid", [])], props=scroll_style(u, 6))
    u.sized("TmGridBox", "TmGridScroll", h=300)
    u.text("TmNote", "Every wearable item in the game can be an appearance. Pick one again to go back to "
                     "your gear's own look. Your stats do not change.", R, 15, "#b8a29c", wrap=True, variable=False)
    looks = column("TmLooks", [(head("TmLooksHead", "Appearances"), gap(12)), ("TmSlotTabs", gap(8)),
                               ("TmChips", gap(8)), ("TmCount", gap(8)), (field("TmSearch", "Search appearances"), gap(10)),
                               ("TmGridBox", gap(10)), ("TmNote", [])], fill="#000000")

    # ---- saved outfits
    rows = [(head("TmOutHead", "Saved outfits"), gap(12))]
    for i in range(N_OUT):
        u.text("TmOutName_%d" % i, "", B, 16, "#ffffff", wrap=True)
        load = stab("TmLoad_%d" % i, "Load", h=34, px=13, tinted=False)
        u.box("HorizontalBox", "TmOutIn_%d" % i, [("TmOutName_%d" % i, ["Size=(SizeRule=Fill)", "VerticalAlignment=VAlign_Center"]),
                                                  (load, ["VerticalAlignment=VAlign_Center"])])
        u.border("TmOutFill_%d" % i, "#120909", 1.0, u.margin(14, 6, 8, 6), "TmOutIn_%d" % i)
        u.strip("TmOutAcc_%d" % i, "#4a1a1d", u.margin(l=3))
        u.box("HorizontalBox", "TmOutRow_%d" % i, [("TmOutAcc_%d" % i, ["VerticalAlignment=VAlign_Fill"]),
                                                   ("TmOutFill_%d" % i, ["Size=(SizeRule=Fill)"])])
        u.widget("/Script/UMG.Border", "TmOut_%d" % i, ["Padding=%s" % u.margin(1, 1, 1, 1),
                                                       "BrushColor=%s" % u.lin("#2a1012"), "Visibility=Collapsed"],
                 [("/Script/UMG.BorderSlot", "TmOutRow_%d" % i, ["Padding=%s" % u.margin(1, 1, 1, 1)])], variable=True)
        rows.append(("TmOut_%d" % i, gap(8)))
    u.text("TmOutLbl", "NEW OUTFIT NAME", B, 15, "#f0343a", spacing_px=2, variable=False)
    rows += [("TmOutLbl", ["Padding=%s" % u.margin(t=6, b=6)]), (field("TmOutfitBox", "[Outfit name]"), gap(10)),
             (btn("TmSaveBtn", "Save outfit"), gap(18))]
    u.text("TmMsg", "", B, 15, "#d8c8c3", wrap=True)
    rows += [("TmMsg", gap(10)), (btn("TmClearBtn", "Clear appearance"), gap(10)),
             (btn("TmApplyBtn", "Apply look", primary=True), [])]
    outfits = column("TmOutfits", rows, w=210, fill="#0a0505")

    u.box("HorizontalBox", "TmBody", [(preview, ["VerticalAlignment=VAlign_Fill"]),
                                      (looks, ["Size=(SizeRule=Fill)", "VerticalAlignment=VAlign_Fill"]),
                                      (outfits, ["VerticalAlignment=VAlign_Fill"])], variable=True)
    return [("TmBody", [])]


LOOKS_OFF = "An admin has turned off Owl Transmog and Animal Masks on this server. Your saved looks are kept."


def looks_off_note(name):
    """The card shown instead of a looks page while the admins have Owl looks off (LooksOn)."""
    u.text(name + "Text", LOOKS_OFF, B, 18, "#f2e6e2", wrap=True, variable=False)
    u.border(name, "#2a0b0d", 1.0, u.margin(20, 16, 20, 16), name + "Text", props=["Visibility=Collapsed"],
             variable=True)
    return (name, ["Padding=%s" % u.margin(b=10)])


def page(tab):
    if tab == "transmog":
        return [looks_off_note("TmOffNote")] + tm_page()
    if tab == "masks":
        return [looks_off_note("MaskOffNote")] + mask_panel.player_layout(u, B, R)
    if tab == "equipment":
        return gear_panel.player_layout(u, B, R)
    if tab == "pets":
        return pet_panel.player_layout(u, B, R)
    if tab == "bugreport":
        return bug_panel.player_layout(u, B, R)
    title = dict((t, ti) for t, ti, _h in D.PLAYER_TABS)[tab]
    return [(s.placeholder("Ph_" + tab, "%s: coming in a later step." % title), ["Padding=%s" % u.margin(t=6)])]


body = s.pages(page)
s.footer()
s.root(body)
wbp, wbp_ptr = s.paste(unreal, eal, bp, PKG, MOD.PLAYER_MENU_WBP, FULL)

# ---- variables: the baked catalogue, the look being edited, sync state
bel = unreal.BlueprintEditorLibrary
T = bel.get_basic_type_by_name
for var, vt in (("TmIds", bel.get_array_type(T("string"))), ("TmNames", bel.get_array_type(T("string"))),
                ("TmIcons", bel.get_array_type(T("string"))), ("TmSlots", bel.get_array_type(T("int"))),
                ("TmCats", bel.get_array_type(T("int"))), ("TmPick", bel.get_array_type(T("string"))),
                ("TmSlot", T("int")), ("TmCat", T("int")), ("TmSynced", T("int")), ("TmShown", T("int")),
                ("TmDirty", T("bool")), ("TmQuery", T("string")),
                ("MyRelay", bel.get_object_reference_type(unreal.load_object(None, RELAY_CLS)))):
    bel.add_member_variable(wbp, var, vt)
bug_panel.player_variables(unreal, bel, wbp)
pet_panel.player_variables(unreal, bel, wbp)
mask_panel.player_variables(unreal, bel, wbp)
gear_panel.player_variables(unreal, bel, wbp)
bel.compile_blueprint(wbp)

# ================================================================ graph
GS = "/Script/Engine.GameplayStatics"
KSL = "/Script/Engine.KismetSystemLibrary"
KML = "/Script/Engine.KismetMathLibrary"
KSTR = "/Script/Engine.KismetStringLibrary"
KTXT = "/Script/Engine.KismetTextLibrary"
UW = "/Script/UMG.UserWidget"
WIDGET = "/Script/UMG.Widget"
TEXT = "/Script/UMG.TextBlock"
IMAGE = "/Script/UMG.Image"
BUTTON = "/Script/UMG.Button"
ETB = "/Script/UMG.EditableTextBox"
WRAP = "/Script/UMG.WrapBox"
LCOLOR = ir.struct_path("/Script/CoreUObject.LinearColor")
SLATEVIS = ir.enum_path("/Script/UMG.ESlateVisibility")
TEX2D = "/Script/Engine.Texture2D"
g = ir.Graph("EventGraph")
s.graph(g)

_FOREACH_REF = ir.Graph._FOREACH_REF


def foreach_strings(pos):
    """ForEachLoop over a string array (ir.foreach only types object arrays)."""
    n = g.node("K2Node_MacroInstance", [_FOREACH_REF, 'ResolvedWildcardType=(PinCategory="string",ContainerType=Array)'],
               base="ForEachS", pos=pos)
    a = n.pin("Array"); a.dir = "EGPD_Input"
    a.set("PinType.PinCategory", '"string"'); a.set("PinType.ContainerType", "Array")
    e = n.pin("Array Element"); e.dir = "EGPD_Output"; e.set("PinType.PinCategory", '"string"')
    n.pin("Array Index").typed("int", direction="EGPD_Output")
    return n


def var(name, cat, pos, sub=None):
    return g.var_get(name, cat, sub, pos=pos)


def arr(name, cat, pos, parent=None):
    n = g.array_var(name, pos=pos, elem_cat=cat, parent=parent)
    if parent:
        g.wire(relay_get(pos), "MyRelay", n, "self", exec=False)
    return n


def relay_get(pos):
    return g.var_get("MyRelay", "object", ir.obj_path(RELAY_CLS), pos=(pos[0] - 200, pos[1] + 80))


def widget_ref(name, cls, pos):
    return g.var_get(name, "object", ir.obj_path(cls), pos=pos)


def at(array_node, array_pin, index, pos, cat):
    """array[index]; index an int literal or (node, pin)."""
    return g.array_get(array_node, array_pin, index, pos, elem_cat=cat)


def set_int(name, value, prev, prev_pin, pos):
    n = g.var_set(name, "int", pos=pos)
    if isinstance(value, tuple):
        g.wire(value[0], value[1], n, name, exec=False)
    else:
        n.pin(name).literal(str(value))
    g.wire(prev, prev_pin, n, "execute")
    return n


def set_bool(name, value, prev, prev_pin, pos):
    n = g.var_set(name, "bool", pos=pos)
    n.pin(name).literal("true" if value else "false")
    g.wire(prev, prev_pin, n, "execute")
    return n


def dirty(prev, prev_pin, pos):
    return set_bool("TmDirty", True, prev, prev_pin, pos)


def say(prev, prev_pin, text, pos):
    """TmMsg = text (a literal or a (node, pin) string)."""
    t = g.call("Conv_StringToText", KTXT, pos=(pos[0] - 250, pos[1] + 200))
    if isinstance(text, tuple):
        g.wire(text[0], text[1], t, "InString", exec=False)
    else:
        g.typed_input(t, "InString", text, "string")
    st = g.call("SetText", TEXT, pos=pos)
    g.wire(widget_ref("TmMsg", TEXT, (pos[0] - 250, pos[1] + 350)), "TmMsg", st, "self", exec=False)
    g.wire(t, "ReturnValue", st, "InText", exec=False)
    g.wire(prev, prev_pin, st, "execute")
    return st


def set_pick(prev, prev_pin, slot, value, pos):
    """TmPick[slot] = value; slot an int or (node, pin); value a literal or (node, pin)."""
    n = g.array_fn("Array_Set", pos=pos, elem_cat="string")
    g.array_item_pin(n, "Item", "string")
    g.wire(arr("TmPick", "string", (pos[0] - 250, pos[1] + 200)), "TmPick", n, "TargetArray", exec=False)
    if isinstance(slot, tuple):
        g.wire(slot[0], slot[1], n, "Index", exec=False)
    else:
        g.typed_input(n, "Index", str(slot), "int")
    if isinstance(value, tuple):
        g.wire(value[0], value[1], n, "Item", exec=False)
    else:
        g.typed_input(n, "Item", value, "string")
    g.wire(prev, prev_pin, n, "execute")
    return n


def relay_valid(prev, prev_pin, pos):
    ok = g.call("IsValid", KSL, pos=(pos[0], pos[1] + 200))
    g.wire(relay_get((pos[0], pos[1] + 200)), "MyRelay", ok, "Object", exec=False)
    b = g.branch(pos=pos)
    g.wire(prev, prev_pin, b, "execute")
    g.wire(ok, "ReturnValue", b, "Condition", exec=False)
    return b


def box_text(name, pos):
    gt = g.call("GetText", ETB, pos=pos)
    g.wire(widget_ref(name, ETB, (pos[0] - 250, pos[1])), name, gt, "self", exec=False)
    ts = g.call("Conv_TextToString", KTXT, pos=(pos[0] + 250, pos[1]))
    g.wire(gt, "ReturnValue", ts, "InText", exec=False)
    return ts


NOT_CONNECTED = "Still connecting to the server. Try again in a moment."

# ---------------------------------------------------------------- clicks
y = 9000
for i, (k, _l, _loc) in enumerate(D.TM_SLOTS):          # slot tabs
    ev = clicked(g, "TmSlotBtn_" + k, (0, y))
    dirty(set_int("TmSlot", i, ev, "then", (300, y)), "then", (600, y))
    y += 250
for i, (k, _l, _g) in enumerate(D.TM_CATS):              # category chips
    ev = clicked(g, "TmCatBtn_" + k, (0, y))
    dirty(set_int("TmCat", i, ev, "then", (300, y)), "then", (600, y))
    y += 250
# (search: Tick redraws when the box's text differs from TmQuery -- OnTextChanged doesn't fire
# for a SetText, so a bound event would miss text put there other than by typing)

# OwlTmPick(Index), called by a grid cell: toggle that item in the current slot
pick = g.custom_event("OwlTmPick", pos=(0, y))
pick.set('CustomProperties UserDefinedPin (PinName="Index",PinType=(PinCategory="int"),DesiredPinDirection=EGPD_Output)')
pid = at(arr("TmIds", "string", (300, y + 300)), "TmIds", (pick, "Index"), (500, y + 300), "string")
cur = at(arr("TmPick", "string", (300, y + 450)), "TmPick", (var("TmSlot", "int", (300, y + 600)), "TmSlot"),
         (500, y + 450), "string")
same = g.call("EqualEqual_StrStr", KSTR, pos=(750, y + 400))
g.wire(pid, "Output", same, "A", exec=False)
g.wire(cur, "Output", same, "B", exec=False)
new = g.call("SelectString", KML, pos=(1000, y + 300))
g.typed_input(new, "A", "", "string")
g.wire(pid, "Output", new, "B", exec=False)
g.wire(same, "ReturnValue", new, "bPickA", exec=False)
sp = set_pick(pick, "then", (var("TmSlot", "int", (1000, y + 600)), "TmSlot"), (new, "ReturnValue"), (1250, y))
say(dirty(sp, "then", (1550, y)), "then", "", (2100, y))
y += 900

# Clear appearance: every slot back to worn gear
cev = clicked(g, "TmClearBtn", (0, y))
prev = cev
for k in range(N_SLOTS):
    prev = set_pick(prev, "then", k, "", (300 + 300 * k, y))
say(dirty(prev, "then", (300 + 300 * N_SLOTS, y)), "then", "Appearance cleared. Press Apply look to keep it.",
    (900 + 300 * N_SLOTS, y))
y += 600

# Apply look -> server
aev = clicked(g, "TmApplyBtn", (0, y))
bR = relay_valid(aev, "then", (300, y))
send = g.call("OwlServerTmApply", RELAY_CLS, pos=(650, y))
g.wire(relay_get((650, y + 200)), "MyRelay", send, "self", exec=False)
g.wire(arr("TmPick", "string", (450, y + 350)), "TmPick", send, "Look", exec=False)
g.wire(bR, "then", send, "execute")
say(send, "then", "Look applied. Your gear and stats are unchanged.", (1200, y))
say(bR, "else", NOT_CONNECTED, (1200, y + 400))
y += 900

# Save outfit -> server (name required)
oev = clicked(g, "TmSaveBtn", (0, y))
oname = box_text("TmOutfitBox", (300, y + 400))
olen = g.call("Len", KSTR, pos=(800, y + 400))
g.wire(oname, "ReturnValue", olen, "S", exec=False)
ohas = g.call("Greater_IntInt", KML, pos=(1050, y + 400))
g.wire(olen, "ReturnValue", ohas, "A", exec=False)
g.typed_input(ohas, "B", "0", "int")
bName = g.branch(pos=(1050, y))
g.wire(oev, "then", bName, "execute")
g.wire(ohas, "ReturnValue", bName, "Condition", exec=False)
say(bName, "else", "Type an outfit name first.", (1600, y + 900))
bR2 = relay_valid(bName, "then", (1300, y))
osend = g.call("OwlServerTmSaveOutfit", RELAY_CLS, pos=(1650, y))
g.wire(relay_get((1650, y + 200)), "MyRelay", osend, "self", exec=False)
g.wire(oname, "ReturnValue", osend, "Name", exec=False)
g.wire(arr("TmPick", "string", (1450, y + 350)), "TmPick", osend, "Look", exec=False)
g.wire(bR2, "then", osend, "execute")
clr = g.call("SetText", ETB, pos=(2000, y))
g.wire(widget_ref("TmOutfitBox", ETB, (1800, y + 200)), "TmOutfitBox", clr, "self", exec=False)
g.wire(osend, "then", clr, "execute")
say(clr, "then", "Outfit saved.", (2500, y))
say(bR2, "else", NOT_CONNECTED, (2500, y + 400))
y += 1100

# Load outfit i: TmPick = its five row names
for i in range(N_OUT):
    lev = clicked(g, "TmLoad_%d" % i, (0, y))
    bRl = relay_valid(lev, "then", (300, y))
    prev, prev_pin = bRl, "then"
    for k in range(N_SLOTS):
        item = at(arr("TmOutfitLooks", "string", (600 + 300 * k, y + 300), parent=RELAY_CLS), "TmOutfitLooks",
                  i * N_SLOTS + k, (650 + 300 * k, y + 450), "string")
        prev, prev_pin = set_pick(prev, prev_pin, k, (item, "Output"), (600 + 300 * k, y)), "then"
    oname_i = at(arr("TmOutfitNames", "string", (2200, y + 300), parent=RELAY_CLS), "TmOutfitNames", i,
                 (2250, y + 450), "string")
    msg = g.call("Concat_StrStr", KSTR, pos=(2500, y + 300))
    g.typed_input(msg, "A", "Loaded ", "string")
    g.wire(oname_i, "Output", msg, "B", exec=False)
    msg2 = g.call("Concat_StrStr", KSTR, pos=(2750, y + 300))
    g.wire(msg, "ReturnValue", msg2, "A", exec=False)
    g.typed_input(msg2, "B", ". Press Apply look to wear it.", "string")
    say(dirty(prev, prev_pin, (2200, y)), "then", (msg2, "ReturnValue"), (3000, y))
    y += 700

# ---------------------------------------------------------------- Tick
tick = g.event("Tick", parent=UW, pos=(0, 3800))
last = s.tick_highlight(g, tick)
Y = 16000

# 1. find this player's relay once: on a client only its own exists; a listen server sees all
hasRelay = relay_valid(last, "then", (0, Y))
relays = g.get_all_actors(RELAY_CLS, pos=(300, Y + 300))
g.wire(hasRelay, "else", relays, "execute")
each = g.foreach("/Script/Engine.Actor", pos=(600, Y + 300))
g.wire(relays, "then", each, "Exec")
g.wire(relays, "OutActors", each, "Array", exec=False)
rc = g.cast(RELAY_CLS, pos=(900, Y + 300))
g.wire(each, "Array Element", rc, "Object", exec=False)
g.wire(each, "LoopBody", rc, "execute")
rown = g.call("GetOwner", "/Script/Engine.Actor", pos=(900, Y + 600))
g.wire(rc, "AsBP Owl Relay", rown, "self", exec=False)
mine = g.call("EqualEqual_ObjectObject", KML, pos=(1150, Y + 600))
g.wire(rown, "ReturnValue", mine, "A", exec=False)
g.wire(g.call("GetOwningPlayer", UW, pos=(900, Y + 750)), "ReturnValue", mine, "B", exec=False)
bMine = g.branch(pos=(1200, Y + 300))
g.wire(rc, "then", bMine, "execute")
g.wire(mine, "ReturnValue", bMine, "Condition", exec=False)
setRelay = g.var_set("MyRelay", "object", ir.obj_path(RELAY_CLS), pos=(1500, Y + 300))
g.wire(rc, "AsBP Owl Relay", setRelay, "MyRelay", exec=False)
g.wire(bMine, "then", setRelay, "execute")

# 2. the server's look/outfits changed (or first load): copy them in
X = 1900
bSync0 = relay_valid(hasRelay, "then", (X, Y))           # re-check: also entered after the search
g.wire(each, "Completed", bSync0, "execute")
rver = g.var_get("TmClientVer", "int", parent=RELAY_CLS, pos=(X, Y + 400))
g.wire(relay_get((X, Y + 400)), "MyRelay", rver, "self", exec=False)
neq = g.call("NotEqual_IntInt", KML, pos=(X + 250, Y + 400))
g.wire(rver, "TmClientVer", neq, "A", exec=False)
g.wire(var("TmSynced", "int", (X, Y + 550)), "TmSynced", neq, "B", exec=False)
bSync = g.branch(pos=(X + 300, Y))
g.wire(bSync0, "then", bSync, "execute")
g.wire(neq, "ReturnValue", bSync, "Condition", exec=False)
look_ok = g.call("EqualEqual_IntInt", KML, pos=(X + 600, Y + 400))
g.wire(g.array_len(arr("TmLook", "string", (X + 350, Y + 400), parent=RELAY_CLS), "TmLook", (X + 450, Y + 500),
                   elem_cat="string"), "ReturnValue", look_ok, "A", exec=False)
g.typed_input(look_ok, "B", str(N_SLOTS), "int")
# only the first sync takes the server's look: later ones (an outfit saved, a look applied)
# must not throw away picks the player hasn't applied yet
first = g.call("EqualEqual_IntInt", KML, pos=(X + 600, Y + 550))
g.wire(var("TmSynced", "int", (X + 400, Y + 650)), "TmSynced", first, "A", exec=False)
g.typed_input(first, "B", "0", "int")
take = g.call("BooleanAND", KML, pos=(X + 800, Y + 450))
g.wire(look_ok, "ReturnValue", take, "A", exec=False)
g.wire(first, "ReturnValue", take, "B", exec=False)
bLook = g.branch(pos=(X + 600, Y))
g.wire(bSync, "then", bLook, "execute")
g.wire(take, "ReturnValue", bLook, "Condition", exec=False)
cp = g.var_set("TmPick", "string", pos=(X + 900, Y))
cp.pin("TmPick").set("PinType.ContainerType", "Array")
g.wire(arr("TmLook", "string", (X + 700, Y + 250), parent=RELAY_CLS), "TmLook", cp, "TmPick", exec=False)
g.wire(bLook, "then", cp, "execute")
# outfit rows: row i shown with its name if the server has that many
X += 1200
names_len = g.array_len(arr("TmOutfitNames", "string", (X, Y + 600), parent=RELAY_CLS), "TmOutfitNames",
                        (X + 200, Y + 700), elem_cat="string")
entries = [(cp, "then"), (bLook, "else")]
for i in range(N_OUT):
    x = X + i * 900
    lt = g.call("Less_IntInt", KML, pos=(x, Y + 400))
    g.typed_input(lt, "A", str(i), "int")
    g.wire(names_len, "ReturnValue", lt, "B", exec=False)
    b = g.branch(pos=(x, Y))
    for e, ep in entries:
        g.wire(e, ep, b, "execute")
    g.wire(lt, "ReturnValue", b, "Condition", exec=False)
    nm = at(arr("TmOutfitNames", "string", (x + 150, Y + 600), parent=RELAY_CLS), "TmOutfitNames", i,
            (x + 300, Y + 600), "string")
    tt = g.call("Conv_StringToText", KTXT, pos=(x + 450, Y + 450))
    g.wire(nm, "Output", tt, "InString", exec=False)
    st = g.call("SetText", TEXT, pos=(x + 300, Y - 200))
    g.wire(widget_ref("TmOutName_%d" % i, TEXT, (x + 150, Y - 50)), "TmOutName_%d" % i, st, "self", exec=False)
    g.wire(tt, "ReturnValue", st, "InText", exec=False)
    g.wire(b, "then", st, "execute")
    entries = []
    for vis, src, sy in (("Visible", st, Y - 200), ("Collapsed", b, Y + 200)):
        sv = g.call("SetVisibility", WIDGET, pos=(x + 600, sy))
        g.typed_input(sv, "InVisibility", vis, "byte", SLATEVIS)
        g.wire(widget_ref("TmOut_%d" % i, "/Script/UMG.Border", (x + 450, sy + 150)), "TmOut_%d" % i, sv, "self",
               exec=False)
        g.wire(src, "then" if src is st else "else", sv, "execute")
        entries.append((sv, "then"))
X += N_OUT * 900
synced = g.var_set("TmSynced", "int", pos=(X, Y))
g.wire(rver, "TmClientVer", synced, "TmSynced", exec=False)
for e, ep in entries:
    g.wire(e, ep, synced, "execute")
syncDone = dirty(synced, "then", (X + 300, Y))

# 3. dirty (or the search text changed) -> redraw: tab + chip colours, the grid, the count, the preview
X += 700
q_now = box_text("TmSearch", (X - 300, Y + 500))
q_new = g.call("NotEqual_StrStr", KSTR, pos=(X + 250, Y + 500))
g.wire(q_now, "ReturnValue", q_new, "A", exec=False)
g.wire(var("TmQuery", "string", (X, Y + 650)), "TmQuery", q_new, "B", exec=False)
redraw = g.call("BooleanOR", KML, pos=(X + 450, Y + 300))
g.wire(var("TmDirty", "bool", (X + 250, Y + 300)), "TmDirty", redraw, "A", exec=False)
g.wire(q_new, "ReturnValue", redraw, "B", exec=False)
bDirty = g.branch(pos=(X + 500, Y))
for e, ep in ((syncDone, "then"), (bSync, "else"), (bSync0, "else")):
    g.wire(e, ep, bDirty, "execute")
g.wire(redraw, "ReturnValue", bDirty, "Condition", exec=False)
setq = g.var_set("TmQuery", "string", pos=(X + 800, Y))
g.wire(q_now, "ReturnValue", setq, "TmQuery", exec=False)
g.wire(bDirty, "then", setq, "execute")
prev, prev_pin = setq, "then"
X += 1100
for group, cur_var, items in (("TmSlotBtn_", "TmSlot", D.TM_SLOTS), ("TmCatBtn_", "TmCat", D.TM_CATS)):
    for i, item in enumerate(items):
        eq = g.call("EqualEqual_IntInt", KML, pos=(X, Y + 400))
        g.wire(var(cur_var, "int", (X - 200, Y + 400)), cur_var, eq, "A", exec=False)
        g.typed_input(eq, "B", str(i), "int")
        sel = g.call("SelectColor", KML, pos=(X, Y + 600))
        g.typed_input(sel, "A", u.lin(TAB_ON), "struct", LCOLOR)
        g.typed_input(sel, "B", u.lin(TAB_OFF), "struct", LCOLOR)
        g.wire(eq, "ReturnValue", sel, "bPickA", exec=False)
        sbc = g.call("SetBackgroundColor", BUTTON, pos=(X, Y))
        g.wire(widget_ref(group + item[0], BUTTON, (X - 200, Y - 150)), group + item[0], sbc, "self", exec=False)
        g.wire(sel, "ReturnValue", sbc, "InBackgroundColor", exec=False)
        g.wire(prev, prev_pin, sbc, "execute")
        prev, prev_pin = sbc, "then"
        X += 300
clear = g.call("ClearChildren", "/Script/UMG.PanelWidget", pos=(X, Y))
g.wire(widget_ref("TmGrid", WRAP, (X - 200, Y + 200)), "TmGrid", clear, "self", exec=False)
g.wire(prev, prev_pin, clear, "execute")
zero = set_int("TmShown", 0, clear, "then", (X + 300, Y))
X += 600
loop = foreach_strings((X, Y))
g.wire(zero, "then", loop, "Exec")
g.wire(arr("TmIds", "string", (X - 250, Y + 250)), "TmIds", loop, "Array", exec=False)
ix = (loop, "Array Index")
# match: slot, category (0 = all), search (empty = all)
slot_i = at(arr("TmSlots", "int", (X, Y + 600)), "TmSlots", ix, (X + 200, Y + 600), "int")
m_slot = g.call("EqualEqual_IntInt", KML, pos=(X + 450, Y + 600))
g.wire(slot_i, "Output", m_slot, "A", exec=False)
g.wire(var("TmSlot", "int", (X + 200, Y + 750)), "TmSlot", m_slot, "B", exec=False)
cat_i = at(arr("TmCats", "int", (X, Y + 900)), "TmCats", ix, (X + 200, Y + 900), "int")
m_cat = g.call("EqualEqual_IntInt", KML, pos=(X + 450, Y + 900))
g.wire(cat_i, "Output", m_cat, "A", exec=False)
g.wire(var("TmCat", "int", (X + 200, Y + 1050)), "TmCat", m_cat, "B", exec=False)
all_cat = g.call("EqualEqual_IntInt", KML, pos=(X + 450, Y + 1050))
g.wire(var("TmCat", "int", (X + 200, Y + 1150)), "TmCat", all_cat, "A", exec=False)
g.typed_input(all_cat, "B", "0", "int")
ok_cat = g.call("BooleanOR", KML, pos=(X + 700, Y + 950))
g.wire(m_cat, "ReturnValue", ok_cat, "A", exec=False)
g.wire(all_cat, "ReturnValue", ok_cat, "B", exec=False)
query = box_text("TmSearch", (X, Y + 1300))
qlen = g.call("Len", KSTR, pos=(X + 500, Y + 1300))
g.wire(query, "ReturnValue", qlen, "S", exec=False)
no_q = g.call("EqualEqual_IntInt", KML, pos=(X + 700, Y + 1300))
g.wire(qlen, "ReturnValue", no_q, "A", exec=False)
g.typed_input(no_q, "B", "0", "int")
name_i = at(arr("TmNames", "string", (X, Y + 1500)), "TmNames", ix, (X + 200, Y + 1500), "string")
has_q = g.call("Contains", KSTR, pos=(X + 500, Y + 1500))
g.wire(name_i, "Output", has_q, "SearchIn", exec=False)
g.wire(query, "ReturnValue", has_q, "Substring", exec=False)
ok_q = g.call("BooleanOR", KML, pos=(X + 950, Y + 1350))
g.wire(no_q, "ReturnValue", ok_q, "A", exec=False)
g.wire(has_q, "ReturnValue", ok_q, "B", exec=False)
ok1 = g.call("BooleanAND", KML, pos=(X + 1150, Y + 800))
g.wire(m_slot, "ReturnValue", ok1, "A", exec=False)
g.wire(ok_cat, "ReturnValue", ok1, "B", exec=False)
ok = g.call("BooleanAND", KML, pos=(X + 1350, Y + 900))
g.wire(ok1, "ReturnValue", ok, "A", exec=False)
g.wire(ok_q, "ReturnValue", ok, "B", exec=False)
bShow = g.branch(pos=(X + 1400, Y))
g.wire(loop, "LoopBody", bShow, "execute")
g.wire(ok, "ReturnValue", bShow, "Condition", exec=False)
# a cell for it
mk = g.create_widget(CELL_CLS, pos=(X + 1700, Y))
g.wire(g.call("GetOwningPlayer", UW, pos=(X + 1500, Y + 250)), "ReturnValue", mk, "OwningPlayer", exec=False)
g.wire(bShow, "then", mk, "execute")
prev = mk
selfref = g.node("K2Node_Self", [], base="Self", pos=(X + 1800, Y + 500))
selfref.pin("self").typed("object", direction="EGPD_Output")
cur_pick = at(arr("TmPick", "string", (X + 1700, Y + 900)), "TmPick", (var("TmSlot", "int", (X + 1700, Y + 1050)), "TmSlot"),
              (X + 1900, Y + 900), "string")
is_sel = g.call("EqualEqual_StrStr", KSTR, pos=(X + 2150, Y + 900))
g.wire(cur_pick, "Output", is_sel, "A", exec=False)
g.wire(loop, "Array Element", is_sel, "B", exec=False)
icon_i = at(arr("TmIcons", "string", (X + 1700, Y + 1250)), "TmIcons", ix, (X + 1900, Y + 1250), "string")
cx = X + 2000
for name, cat, src in (("Index", "int", ix), ("Menu", "object", (selfref, "self")),
                       ("IconPath", "string", (icon_i, "Output")), ("Label", "string", (name_i, "Output")),
                       ("Selected", "bool", (is_sel, "ReturnValue"))):
    sub = ir.obj_path(UW) if cat == "object" else None
    sv = g.var_set(name, cat, sub, pos=(cx, Y), parent=CELL_CLS)
    g.wire(mk, "ReturnValue", sv, "self", exec=False)
    g.wire(src[0], src[1], sv, name, exec=False)
    g.wire(prev, "then", sv, "execute")
    prev = sv
    cx += 300
add = g.call("AddChildToWrapBox", WRAP, pos=(cx, Y))
g.wire(widget_ref("TmGrid", WRAP, (cx - 200, Y + 200)), "TmGrid", add, "self", exec=False)
g.wire(mk, "ReturnValue", add, "Content", exec=False)
g.wire(prev, "then", add, "execute")
inc = g.call("Add_IntInt", KML, pos=(cx + 300, Y + 200))
g.wire(var("TmShown", "int", (cx + 100, Y + 200)), "TmShown", inc, "A", exec=False)
g.typed_input(inc, "B", "1", "int")
set_int("TmShown", (inc, "ReturnValue"), add, "then", (cx + 300, Y))

# after the loop: the count, then the preview + summary per slot
X = cx + 900
cnt = g.call("Conv_IntToString", KSTR, pos=(X - 250, Y + 300))
g.wire(var("TmShown", "int", (X - 450, Y + 300)), "TmShown", cnt, "InInt", exec=False)
ctext = g.call("Concat_StrStr", KSTR, pos=(X, Y + 300))
g.wire(cnt, "ReturnValue", ctext, "A", exec=False)
g.typed_input(ctext, "B", " appearances · all unlocked", "string")
ct = g.call("Conv_StringToText", KTXT, pos=(X + 250, Y + 300))
g.wire(ctext, "ReturnValue", ct, "InString", exec=False)
setc = g.call("SetText", TEXT, pos=(X + 250, Y))
g.wire(widget_ref("TmCount", TEXT, (X, Y + 150)), "TmCount", setc, "self", exec=False)
g.wire(ct, "ReturnValue", setc, "InText", exec=False)
g.wire(loop, "Completed", setc, "execute")
entries = [(setc, "then")]
X += 600
for k, (key, _label, _loc) in enumerate(D.TM_SLOTS):
    # the chosen row name -> its catalogue index (clamped: "" isn't found)
    pk = at(arr("TmPick", "string", (X, Y + 400)), "TmPick", k, (X + 200, Y + 400), "string")
    fnd = g.array_fn("Array_Find", pos=(X + 450, Y + 400), elem_cat="string")
    g.array_item_pin(fnd, "ItemToFind", "string")
    fnd.pin("ReturnValue").typed("int", direction="EGPD_Output")
    g.wire(arr("TmIds", "string", (X + 250, Y + 550)), "TmIds", fnd, "TargetArray", exec=False)
    g.wire(pk, "Output", fnd, "ItemToFind", exec=False)
    idx = g.call("Max", KML, pos=(X + 700, Y + 400))
    g.wire(fnd, "ReturnValue", idx, "A", exec=False)
    g.typed_input(idx, "B", "0", "int")
    found = g.call("GreaterEqual_IntInt", KML, pos=(X + 700, Y + 600))
    g.wire(fnd, "ReturnValue", found, "A", exec=False)
    g.typed_input(found, "B", "0", "int")
    nm = at(arr("TmNames", "string", (X + 700, Y + 750)), "TmNames", (idx, "ReturnValue"), (X + 900, Y + 750), "string")
    label = g.call("SelectString", KML, pos=(X + 1150, Y + 600))
    g.wire(nm, "Output", label, "A", exec=False)
    g.typed_input(label, "B", "Worn gear", "string")
    g.wire(found, "ReturnValue", label, "bPickA", exec=False)
    lt = g.call("Conv_StringToText", KTXT, pos=(X + 1400, Y + 600))
    g.wire(label, "ReturnValue", lt, "InString", exec=False)
    st = g.call("SetText", TEXT, pos=(X + 1400, Y))
    g.wire(widget_ref("TmSum_" + key, TEXT, (X + 1200, Y + 150)), "TmSum_" + key, st, "self", exec=False)
    g.wire(lt, "ReturnValue", st, "InText", exec=False)
    for e, ep in entries:
        g.wire(e, ep, st, "execute")
    # its icon, if it has one
    ic = at(arr("TmIcons", "string", (X + 700, Y + 900)), "TmIcons", (idx, "ReturnValue"), (X + 900, Y + 900), "string")
    iclen = g.call("Len", KSTR, pos=(X + 1150, Y + 900))
    g.wire(ic, "Output", iclen, "S", exec=False)
    hasic = g.call("Greater_IntInt", KML, pos=(X + 1400, Y + 900))
    g.wire(iclen, "ReturnValue", hasic, "A", exec=False)
    g.typed_input(hasic, "B", "0", "int")
    showic = g.call("BooleanAND", KML, pos=(X + 1650, Y + 750))
    g.wire(found, "ReturnValue", showic, "A", exec=False)
    g.wire(hasic, "ReturnValue", showic, "B", exec=False)
    bIc = g.branch(pos=(X + 1700, Y))
    g.wire(st, "then", bIc, "execute")
    g.wire(showic, "ReturnValue", bIc, "Condition", exec=False)
    path = g.call("MakeSoftObjectPath", KSL, pos=(X + 1700, Y + 1100))
    g.wire(ic, "Output", path, "PathString", exec=False)
    ref = g.call("Conv_SoftObjPathToSoftObjRef", KSL, pos=(X + 1950, Y + 1100))
    g.wire(path, "ReturnValue", ref, "SoftObjectPath", exec=False)
    ld = g.call("LoadAsset_Blocking", KSL, pos=(X + 2000, Y))
    g.wire(ref, "ReturnValue", ld, "Asset", exec=False)
    g.wire(bIc, "then", ld, "execute")
    tc = g.cast(TEX2D, pos=(X + 2300, Y))
    g.wire(ld, "ReturnValue", tc, "Object", exec=False)
    g.wire(ld, "then", tc, "execute")
    sb = g.call("SetBrushFromTexture", IMAGE, pos=(X + 2600, Y))
    g.wire(widget_ref("TmPrevImg_" + key, IMAGE, (X + 2400, Y + 200)), "TmPrevImg_" + key, sb, "self", exec=False)
    g.wire(tc, "AsTexture 2D", sb, "Texture", exec=False)
    g.wire(tc, "then", sb, "execute")
    ends = []
    for vis, srcs, sy in (("Visible", [(sb, "then")], Y), ("Hidden", [(bIc, "else"), (tc, "CastFailed")], Y + 300)):
        sv = g.call("SetVisibility", WIDGET, pos=(X + 2900, sy))
        g.typed_input(sv, "InVisibility", vis, "byte", SLATEVIS)
        g.wire(widget_ref("TmPrevImg_" + key, IMAGE, (X + 2700, sy + 150)), "TmPrevImg_" + key, sv, "self", exec=False)
        for e, ep in srcs:
            g.wire(e, ep, sv, "execute")
        ends.append((sv, "then"))
    entries = ends                                       # both continue into the next slot
    X += 3400
undirty = g.var_set("TmDirty", "bool", pos=(X, Y))
undirty.pin("TmDirty").literal("false")
for e, ep in entries:
    g.wire(e, ep, undirty, "execute")

# ---------------------------------------------------------------- Bug Report tab (bug_panel)
_bug = ce_panel._Ctx(g, u, RELAY_CLS, lambda pos: g.call("GetOwningPlayer", UW, pos=pos), relay_var="MyRelay")
_bug.exits = [(undirty, "then"), (bDirty, "else")]
bug_panel.player_tick(_bug, 40000)
pet_panel.player_tick(_bug, 45000)            # then the Pet Shop tab's
mask_panel.player_tick(_bug, 48000)           # then the Animal Masks tab's
gear_panel.player_tick(_bug, 75000)           # then the Equipment tab's
# then: the admins turned Owl looks off (the controller's LooksOn) -> the Transmog and Animal Masks
# pages show a note instead of their content (a controller not here yet counts as on)
CTRL_CLS = MOD.full(PKG, MOD.CONTROLLER) + "_C"
_lg = g.call("GetActorOfClass", GS, pos=(0, 80000))
_ap = _lg.pin("ActorClass").typed("class", ir.obj_path("/Script/Engine.Actor"), direction="EGPD_Input")
_ap.set("PinType.bIsUObjectWrapper", "True")
_ap.set("DefaultObject", '"%s"' % CTRL_CLS)
_lg.pin("ReturnValue").typed("object", ir.obj_path(CTRL_CLS), direction="EGPD_Output")
_bug.go(_lg)
_bc = _bug.branch(_bug.fn("IsValid", KSL, {"Object": (_lg, "ReturnValue")}, (300, 80300)), (300, 80000))
_no_ctl = [(_bc, "else")]
_bug.exits = [(_bc, "then")]
_lon = g.var_get("LooksOn", "bool", parent=CTRL_CLS, pos=(500, 80400))
g.wire(_lg, "ReturnValue", _lon, "self", exec=False)
_bug.vis_if((_lon, "LooksOn"), [("TmBody", "/Script/UMG.HorizontalBox"), ("MaskBody", "/Script/UMG.HorizontalBox")],
            (700, 80000))
_bug.vis_if(_bug.fn("Not_PreBool", KML, {"A": (_lon, "LooksOn")}, (1500, 80400)),
            [("TmOffNote", "/Script/UMG.Border"), ("MaskOffNote", "/Script/UMG.Border")], (1700, 80000))
_bug.exits += _no_ctl
bug_panel.player_clicks(ce_panel._Ctx(g, u, RELAY_CLS, lambda pos: g.call("GetOwningPlayer", UW, pos=pos),
                                      relay_var="MyRelay"), 50000)
pet_panel.player_clicks(ce_panel._Ctx(g, u, RELAY_CLS, lambda pos: g.call("GetOwningPlayer", UW, pos=pos),
                                      relay_var="MyRelay"), 60000)
mask_panel.player_clicks(ce_panel._Ctx(g, u, RELAY_CLS, lambda pos: g.call("GetOwningPlayer", UW, pos=pos),
                                       relay_var="MyRelay"), 65000)

# Clear + compile first, or a rebuild renames the pasted OwlTmPick event (see 02); 11 then
# rebuilds the cell, whose call to it went stale
_bp_ptr, _g_ptr = bp.find_graph(FULL, "EventGraph")
bp.clear_graph(_bp_ptr, _g_ptr)
bp.mark_structurally_modified(_bp_ptr)
bel.compile_blueprint(wbp)

rep = build.build_graph(FULL, g)
assert rep["ok"], "player menu graph not clean: %r" % {k: rep[k] for k in (
    "dropped_nodes", "dropped_links", "orphans", "wildcards", "errors")}
assert unreal.find_object(None, FULL + "_C:OwlTmPick"), "OwlTmPick missing after build (renamed on paste?)"

# ---- the baked catalogue + defaults on the CDO
gen = unreal.load_object(None, FULL + "_C")
assert gen, "no generated class"
cdo = unreal.get_default_object(gen)
cdo.set_editor_property("TmIds", [e["id"] for e in CATALOG])
cdo.set_editor_property("TmNames", [e["name"] for e in CATALOG])
cdo.set_editor_property("TmIcons", [e["icon"] for e in CATALOG])
cdo.set_editor_property("TmSlots", [e["slot"] for e in CATALOG])
cdo.set_editor_property("TmCats", [e["cat"] for e in CATALOG])
cdo.set_editor_property("TmPick", [""] * N_SLOTS)
cdo.set_editor_property("TmDirty", True)
bug_panel.bake_player(cdo)
pet_panel.bake_player(cdo)
mask_panel.bake_player(cdo)
gear_panel.bake_player(cdo, GEAR)
assert len(cdo.get_editor_property("TmIds")) == len(CATALOG), "catalogue not stored on the CDO"
assert bp.root_widget(wbp_ptr) == s.root_ptr, "root changed during compile"
assert eal.save_asset(PATH), "save failed"
print("BUILD OK: owl-admin v%d -> %s  (%d widgets, %d tabs, %d appearances)%s" % (
    MOD.VERSION, FULL, len(u.cls), len(D.PLAYER_TABS), len(CATALOG),
    "  [DRY RUN -- not shippable]" if PKG != MOD.OUTPUT_PKG else ""))
