"""The admin menu's Characters tab (03): the CharacterEditor board as a panel inside the menu.
Server side: ce_server.py (the relay's OwlServerCe* events and the Ce* values they send back).

Layout (board px x1.5):
    player column (CEP_ROWS rows: character name + level; the selected one highlighted) |
    selected player's name, the five sub-tab buttons, CeTabs (WidgetSwitcher):
        0 Stats: Level and Unspent points steppers, the seven attribute steppers
        1 Inventory: Backpack / Equipped / Hotbar chips, a grid of WBP_OwlCeCell (icon, stack
          count), the picked stack's bar: quantity, Remove, Grant more
        2 Item catalog: category chips, search, the first CE_CAT_MAX matches as cells, the
          picked item's bar: quantity, Grant to <player>
        3 Currency: placeholder (the next step)
        4 Log: the player's newest CE_LOG_ROWS admin changes (admin, time; the change under them)
    confirm strip (Refund / Reset ask first) | action bar: status, Refund, Reset, Apply (Stats only)

    layout(u, B, R)  -> [(widget, [slot props])] for the Characters page
    add_variables(unreal, bel, wbp, relay_cls)
    bake(cdo, entries)                                 (ce_catalog's items onto the built menu)
    tick(g, u, relay_cls, cell_cls, owning_player, entries, unlocked, on_page) -> exits
    clicks(g, u, relay_cls, owning_player)             (every button's OnClicked, OwlCePick)

Grid cells call the menu's OwlCePick(Index, Kind) (Kind 0 inventory, 1 catalog); the grids are
redrawn only when CeInvDirty / CeCatDirty is set or the search text changes.

Tick, while admin mode is unlocked and the Characters page is up:
    CeRelay = the owning player's relay (found once); every CE_ASK_SECONDS: OwlServerCeList;
    relay.CeListVer changed -> redraw the player rows; nobody (still) selected -> select the
    first; relay.CeClientVer changed -> load the editable values (CeEd*) and the log rows from
    what the server sent; then every frame: the stepper values, the confirm strip, the status
    line and the highlights. Clicks only change CeEd* (and CeDirty) or call the relay; the
    server's answer comes back through CeClientVer, so the panel shows what the game did.
"""
from bpkit import ir
import menu_defs as D
from menu_shell import button_style, framed, clicked, scroll_style

CEP_ROWS = 24
CE_LOG_ROWS = 25
CE_ASK_SECONDS = 5.0
CE_CAT_MAX = 120          # Item catalog cells shown at most (the rest: search to narrow it down)
GRID_H = 260              # the item grids' scroll height (board px)
# quantity stepper buttons: (widget suffix, glyph, step, width px, glyph px)
QTY_STEPS = (("Dec10", "-10", -10, 48, 16), ("Dec", "-", -1, 36, 22), ("Inc", "+", 1, 36, 22),
             ("Inc10", "+10", 10, 48, 16))
CE_WALLET_STEP, CE_WALLET_GRANT = 100, 1000
CUR_TAB = [k for k, (key, _l) in enumerate(D.CE_TABS) if key == "currency"][0]
TEXT, BUTTON, WIDGET = "/Script/UMG.TextBlock", "/Script/UMG.Button", "/Script/UMG.Widget"
SWITCHER = "/Script/UMG.WidgetSwitcher"
ETB, WRAP, PANEL = "/Script/UMG.EditableTextBox", "/Script/UMG.WrapBox", "/Script/UMG.PanelWidget"
SIZEBOX = "/Script/UMG.SizeBox"
KML = "/Script/Engine.KismetMathLibrary"
KSTR = "/Script/Engine.KismetStringLibrary"
KTXT = "/Script/Engine.KismetTextLibrary"
KSL = "/Script/Engine.KismetSystemLibrary"
GS = "/Script/Engine.GameplayStatics"
PSTATE = "/Script/Engine.PlayerState"
UW = "/Script/UMG.UserWidget"
LCOLOR = ir.struct_path("/Script/CoreUObject.LinearColor")
SLATEVIS = ir.enum_path("/Script/UMG.ESlateVisibility")
ROW_ON, ROW_OFF = "#3a0b0e", "#0b0606"
CHIP_ON, CHIP_OFF = "#b3121a", "#0d0606"
# editable values: (menu variable, relay variable it loads from, (min, max), widget key)
STEPPERS = ([("CeEdLevel", "CeLevel", D.CE_LEVEL, "CeLvl"), ("CeEdPoints", "CePoints", D.CE_POINTS, "CePts")]
            + [("CeEdA%d" % k, "CeA%d" % k, D.CE_ATTR, "CeAt%d" % k) for k in range(len(D.CE_ATTRS))])


# ================================================================ layout
def _button(u, name, label_name, pad, style, props=(), halign="HAlign_Center"):
    return u.widget(BUTTON, name, [style, "BackgroundColor=(R=1.000000,G=1.000000,B=1.000000,A=1.000000)",
                                   "IsFocusable=False"] + list(props),
                    [("/Script/UMG.ButtonSlot", label_name,
                      ["Padding=%s" % pad, "HorizontalAlignment=%s" % halign, "VerticalAlignment=VAlign_Center"])],
                    variable=True)


def _text_button(u, B, name, label, primary=False, h=48, px=18, pad=22, tinted=False, label_var=False):
    """The board's .btn (outline) / .btn.primary (filled). tinted: white brushes, so the graph's
    SetBackgroundColor gives the colour (a dark brush would dim the tint to nothing).
    label_var: the graph sets the label (name + "Text")."""
    u.text(name + "Text", label, B, px, "#ffffff" if primary else "#f2e6e2", spacing_px=2, variable=label_var)
    if primary:
        _button(u, name, name + "Text", u.margin(pad, 0, pad, 0), button_style(u, "#b3121a", "#d01a22", "#8a2a2e"))
        return u.sized(name + "Box", name, h=h, variable=True)     # Apply shows on the Stats tab only
    style = button_style(u, "#ffffff", "#ffffff", "#ffffff") if tinted else button_style(u, "#0d0606", "#1a0c0c", "#3a0b0e")
    _button(u, name, name + "Text", u.margin(pad, 0, pad, 0), style)
    framed(u, name + "Frame", "#5a1a1e", "#0d0606", name, u.margin())
    return u.sized(name + "Box", name + "Frame", h=h, variable=True)    # Refund/Reset hide off the Stats tab


def _step(u, B, name, glyph, w=36, px=22):
    """The board's .step, a little smaller (36px): the menu's page is narrower than the board."""
    u.text(name + "Text", glyph, B, px, "#f2e6e2", variable=False)
    _button(u, name, name + "Text", u.margin(), button_style(u, "#1a0c0c", "#3a0b0e", "#5a1a1e"))
    framed(u, name + "Frame", "#5a1a1e", "#1a0c0c", name, u.margin())
    return u.sized(name + "Box", name + "Frame", w=w, h=36)


def _cell(u, B, key, label, px=18, val_w=40):
    """The board's .cell with a stepper: label | - | value | +. (An ASCII '-': the game font has
    no U+2212 minus glyph.)"""
    u.text(key + "Lbl", label, B, px, "#ffffff", wrap=True, variable=False)
    u.text(key + "Val", "0", B, 22, "#ff5a5f")
    u.sized(key + "ValBox", key + "Val", w=val_w, halign="HAlign_Center", valign="VAlign_Center")
    row = u.box("HorizontalBox", key + "Row", [
        (key + "Lbl", ["Size=(SizeRule=Fill)", "VerticalAlignment=VAlign_Center"]),
        (_step(u, B, key + "Dec", "-"), ["Padding=%s" % u.margin(l=8), "VerticalAlignment=VAlign_Center"]),
        (key + "ValBox", ["Padding=%s" % u.margin(4, 0, 4, 0), "VerticalAlignment=VAlign_Center"]),
        (_step(u, B, key + "Inc", "+"), ["VerticalAlignment=VAlign_Center"])])
    u.border(key + "Fill", "#120909", 1.0, u.margin(12, 4, 6, 4), row)
    u.strip(key + "Acc", "#4a1a1d", u.margin(l=3))
    u.box("HorizontalBox", key + "In", [(key + "Acc", ["VerticalAlignment=VAlign_Fill"]),
                                        (key + "Fill", ["Size=(SizeRule=Fill)", "VerticalAlignment=VAlign_Fill"])])
    return u.border(key, "#2a1012", 1.0, u.margin(1, 1, 1, 1), key + "In")


def _lab(u, B, name, text):
    return u.text(name, text.upper(), B, 15, "#f0343a", spacing_px=2, variable=False)


def _chips(u, B, name, prefix, items):
    """A WrapBox of tinted chips <prefix><key> (the board's small .btn row)."""
    return u.box("WrapBox", name, [(_text_button(u, B, prefix + key, label, h=36, px=15, pad=12, tinted=True),
                                    ["Padding=%s" % u.margin(r=8, b=8)]) for key, label in items])


def _grid(u, name):
    """A WrapBox the graph fills with cells, in a scroll box of fixed height (the board's grid)."""
    u.widget("/Script/UMG.WrapBox", name, ["InnerSlotPadding=(X=%.6f,Y=%.6f)" % (8 * u.S, 8 * u.S)], [],
             variable=True)
    u.box("ScrollBox", name + "Scroll", [(name, [])], props=scroll_style(u, 6))
    return u.sized(name + "Box", name + "Scroll", h=GRID_H)


def _field(u, R, name, hint):
    """The board's .field (a text box)."""
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


def _detail(u, B, R, key, buttons):
    """The board's item bar: the picked item's name and details, a quantity stepper (CeEdQty;
    widgets <key>Q<step>) and the buttons [(name, label, primary)]."""
    u.text(key + "Name", "", B, 20, "#ffffff", wrap=True)
    u.text(key + "Meta", "", R, 16, "#b8a29c", wrap=True)
    u.text(key + "QVal", "1", B, 22, "#ff5a5f")
    u.sized(key + "QValBox", key + "QVal", w=56, halign="HAlign_Center", valign="VAlign_Center")
    steps = []
    for suffix, glyph, _delta, w, px in QTY_STEPS:
        if suffix == "Inc":
            steps.append((key + "QValBox", ["Padding=%s" % u.margin(4, 0, 4, 0), "VerticalAlignment=VAlign_Center"]))
        steps.append((_step(u, B, key + "Q" + suffix, glyph, w=w, px=px),
                      ["Padding=%s" % u.margin(r=4), "VerticalAlignment=VAlign_Center"]))
    u.text(key + "QLbl", "QUANTITY", B, 14, "#b8a29c", spacing_px=2, variable=False)
    steps.insert(0, (key + "QLbl", ["Padding=%s" % u.margin(r=10), "VerticalAlignment=VAlign_Center"]))
    u.box("HorizontalBox", key + "QRow", steps)
    u.box("WrapBox", key + "Btns", [
        (_text_button(u, B, name, label, primary=primary, h=40, px=15, pad=14, label_var=primary),
         ["Padding=%s" % u.margin(l=10, b=8)]) for name, label, primary in buttons])
    col = u.box("VerticalBox", key + "Col", [
        (key + "Name", []), (key + "Meta", ["Padding=%s" % u.margin(t=2, b=10)]),
        (key + "QRow", ["Padding=%s" % u.margin(b=10)]), (key + "Btns", ["HorizontalAlignment=HAlign_Right"])])
    u.border(key + "Fill", "#120909", 1.0, u.margin(16, 12, 16, 4), col)
    u.strip(key + "Acc", "#4a1a1d", u.margin(l=3))
    u.box("HorizontalBox", key + "In", [(key + "Acc", ["VerticalAlignment=VAlign_Fill"]),
                                        (key + "Fill", ["Size=(SizeRule=Fill)", "VerticalAlignment=VAlign_Fill"])])
    return u.border(key, "#2a1012", 1.0, u.margin(1, 1, 1, 1), key + "In")


def _inventory_page(u, B, R):
    _chips(u, B, "CeInvChips", "CeInvTab_", [(key, label) for key, label in D.CE_INVS])
    u.text("CeInvCount", "", B, 16, "#b8a29c")
    return u.box("VerticalBox", "CePgInv", [
        ("CeInvChips", ["Padding=%s" % u.margin(b=4)]),
        ("CeInvCount", ["Padding=%s" % u.margin(b=8)]),
        (_grid(u, "CeInvGrid"), ["Padding=%s" % u.margin(b=12)]),
        (_detail(u, B, R, "CeInvBar", [("CeInvRemove", "Remove", False), ("CeInvGrant", "Grant more", True)]), [])])


def _currency_page(u, B, R):
    """Wallet (steps of CE_WALLET_STEP, Grant / Clear), accepted currencies (toggles), NPC prices."""
    rows = [(_lab(u, B, "CeWalLab", "Owl wallet"), ["Padding=%s" % u.margin(b=8)]),
            (_cell(u, B, "CeBal", "Balance", val_w=130), ["Padding=%s" % u.margin(b=8)])]
    u.box("WrapBox", "CeBalBtns", [
        (_text_button(u, B, "CeBalGrant", "Grant %s" % "{:,}".format(CE_WALLET_GRANT), h=40, px=15, pad=14),
         ["Padding=%s" % u.margin(l=10, b=8)]),
        (_text_button(u, B, "CeBalClear", "Clear wallet", h=40, px=15, pad=14), ["Padding=%s" % u.margin(l=10, b=8)])])
    rows += [("CeBalBtns", ["HorizontalAlignment=HAlign_Right", "Padding=%s" % u.margin(b=10)]),
             (_lab(u, B, "CeCurLab", "Currencies accepted in trades"), ["Padding=%s" % u.margin(b=8)])]
    for k, (label, _id) in enumerate(D.CE_CURRENCIES):
        key = "CeCur%d" % k
        u.text(key + "Lbl", label, B, 19, "#ffffff", wrap=True, variable=False)
        u.box("HorizontalBox", key + "Row", [
            (key + "Lbl", ["Size=(SizeRule=Fill)", "VerticalAlignment=VAlign_Center"]),
            (_text_button(u, B, key + "Btn", "Off", h=40, px=15, pad=14, tinted=True, label_var=True),
             ["VerticalAlignment=VAlign_Center"])])
        u.border(key + "Fill", "#120909", 1.0, u.margin(14, 6, 8, 6), key + "Row")
        u.strip(key + "Acc", "#4a1a1d", u.margin(l=3))
        u.box("HorizontalBox", key, [(key + "Acc", ["VerticalAlignment=VAlign_Fill"]),
                                     (key + "Fill", ["Size=(SizeRule=Fill)", "VerticalAlignment=VAlign_Fill"])])
        rows.append((key, ["Padding=%s" % u.margin(b=8)]))
    rows += [(_lab(u, B, "CePriceLab", "Trade prices"), ["Padding=%s" % u.margin(t=6, b=8)]),
             (_cell(u, B, "CeSell", "NPC sell price (what players pay)", px=17, val_w=70), ["Padding=%s" % u.margin(b=8)]),
             (_cell(u, B, "CeBuy", "NPC buy price (what players get)", px=17, val_w=70), ["Padding=%s" % u.margin(b=8)])]
    u.text("CeEconNote", "Saved for the server. There is no trading system yet, so the currencies and prices "
                         "don't change any trades for now.", R, 15, "#b8a29c", wrap=True, variable=False)
    rows.append(("CeEconNote", []))
    return u.box("VerticalBox", "CePgCur", rows)


def _catalog_page(u, B, R):
    _chips(u, B, "CeCatChips", "CeCatTab_", [(key, label) for key, label, _gui in D.CE_ITEM_CATS])
    u.text("CeCatCount", "", B, 16, "#b8a29c", wrap=True)
    return u.box("VerticalBox", "CePgCat", [
        ("CeCatChips", ["Padding=%s" % u.margin(b=4)]),
        (_field(u, R, "CeCatSearch", "Search all items"), ["Padding=%s" % u.margin(b=8)]),
        ("CeCatCount", ["Padding=%s" % u.margin(b=8)]),
        (_grid(u, "CeCatGrid"), ["Padding=%s" % u.margin(b=12)]),
        (_detail(u, B, R, "CeCatBar", [("CeCatKit%d" % k, "Add to Kit %d" % (k + 1), False) for k in range(D.N_KITS)]
                 + [("CeCatGrant", "Grant to player", True)]), [])])     # Add to Kit: kits_panel.catalog_clicks


def layout(u, B, R):
    """The Characters page's content: [(widget, [VerticalBox slot props])]."""
    # player column
    rows = []
    for i in range(CEP_ROWS):
        u.text("CePName%d" % i, "", B, 19, "#ffffff")
        u.text("CePMeta%d" % i, "", R, 15, "#b8a29c")
        u.box("VerticalBox", "CePTxt%d" % i, [("CePName%d" % i, []), ("CePMeta%d" % i, ["Padding=%s" % u.margin(t=2)])])
        _button(u, "CeP%d" % i, "CePTxt%d" % i, u.margin(18, 10, 18, 10), button_style(u, "#ffffff", "#ffffff", "#ffffff"),
                props=["Visibility=Collapsed"], halign="HAlign_Left")
        rows.append(("CeP%d" % i, ["Padding=%s" % u.margin(b=2), "HorizontalAlignment=HAlign_Fill"]))
    u.text("CeNoPlayers", "Asking the server for the players online...", R, 16, "#a8908a", wrap=True)
    rows.append(("CeNoPlayers", ["Padding=%s" % u.margin(18, 10, 18, 10)]))
    u.box("VerticalBox", "CePList", rows)
    u.border("CePCol", "#0b0606", 1.0, u.margin(t=12, b=12), "CePList", valign="VAlign_Top")
    u.sized("CePColBox", "CePCol", w=170)
    u.strip("CePColLine", "#3a1214", u.margin(l=1))

    # head: the selected player's name, the log note under it
    u.text("CeSelName", "NO PLAYER SELECTED", B, 22, "#ffffff", spacing_px=3)
    u.text("CeSelHint", "Every change is saved to the admin log", R, 16, "#b8a29c", variable=False)
    u.box("VerticalBox", "CeHead", [("CeSelName", []), ("CeSelHint", ["Padding=%s" % u.margin(t=2)])])
    # sub-tab buttons: a WrapBox, so they go onto a second line on a narrow screen
    chips = []
    for k, (key, label) in enumerate(D.CE_TABS):
        chips.append((_text_button(u, B, "CeTab_" + key, label, h=40, px=16, pad=14, tinted=True),
                      ["Padding=%s" % u.margin(r=8, b=8)]))
    u.box("WrapBox", "CeTabBar", chips)

    # Stats page
    top = u.box("HorizontalBox", "CeTop", [
        (_cell(u, B, "CeLvl", "Level"), ["Size=(SizeRule=Fill)", "Padding=%s" % u.margin(r=5)]),
        (_cell(u, B, "CePts", "Unspent points"), ["Size=(SizeRule=Fill)", "Padding=%s" % u.margin(l=5)])])
    grid = []
    for r in range(0, len(D.CE_ATTRS), 2):
        pair = []
        for k in (r, r + 1):
            if k < len(D.CE_ATTRS):
                pair.append((_cell(u, B, "CeAt%d" % k, D.CE_ATTRS[k][0], px=17),
                             ["Size=(SizeRule=Fill)", "Padding=%s" % u.margin(l=5 if k % 2 else 0, r=0 if k % 2 else 5)]))
            else:
                u.widget("/Script/UMG.Spacer", "CeAtPad")
                pair.append(("CeAtPad", ["Size=(SizeRule=Fill)", "Padding=%s" % u.margin(l=5)]))
        grid.append((u.box("HorizontalBox", "CeAtRow%d" % (r // 2), pair), ["Padding=%s" % u.margin(b=10)]))
    stats = u.box("VerticalBox", "CePgStats", [
        (top, ["Padding=%s" % u.margin(b=14)]),
        (_lab(u, B, "CeAttrLab", "Attributes"), ["Padding=%s" % u.margin(b=10)])] + grid)

    later = [_inventory_page(u, B, R), _catalog_page(u, B, R), _currency_page(u, B, R)]

    # Log page
    log = [(_lab(u, B, "CeLogLab", "Admin changes for this player"), ["Padding=%s" % u.margin(b=4)])]
    for k in range(CE_LOG_ROWS):
        u.text("CeLgT%d" % k, "", B, 16, "#b8a29c")
        u.text("CeLgA%d" % k, "", B, 17, "#ffffff", props=["Clipping=ClipToBounds"])    # a long name stops short of the time
        u.text("CeLgX%d" % k, "", R, 17, "#f2e6e2", wrap=True)
        # admin + time on top, the change full width under them (the page is too narrow for 3 columns)
        u.box("HorizontalBox", "CeLgTop%d" % k, [
            ("CeLgA%d" % k, ["Size=(SizeRule=Fill)", "VerticalAlignment=VAlign_Center"]),
            ("CeLgT%d" % k, ["Padding=%s" % u.margin(l=12), "VerticalAlignment=VAlign_Center"])])
        u.box("VerticalBox", "CeLgIn%d" % k, [
            ("CeLgTop%d" % k, []),
            ("CeLgX%d" % k, ["Padding=%s" % u.margin(t=4)])])
        u.border("CeLgFill%d" % k, "#120909", 1.0, u.margin(14, 8, 14, 8), "CeLgIn%d" % k)
        u.strip("CeLgAcc%d" % k, "#4a1a1d", u.margin(l=3))
        u.box("HorizontalBox", "CeLg%d" % k, [("CeLgAcc%d" % k, ["VerticalAlignment=VAlign_Fill"]),
                                             ("CeLgFill%d" % k, ["Size=(SizeRule=Fill)", "VerticalAlignment=VAlign_Fill"])],
              props=["Visibility=Collapsed"], variable=True)
        log.append(("CeLg%d" % k, ["Padding=%s" % u.margin(b=6)]))
    u.text("CeLogEmpty", "No admin changes for this player yet.", R, 17, "#a8908a")
    log.append(("CeLogEmpty", ["Padding=%s" % u.margin(t=4)]))
    logpg = u.box("VerticalBox", "CePgLog", log)

    u.widget(SWITCHER, "CeTabs", ["ActiveWidgetIndex=0"],
             [("/Script/UMG.WidgetSwitcherSlot", w, ["HorizontalAlignment=HAlign_Fill", "VerticalAlignment=VAlign_Top"])
              for w in [stats] + later + [logpg]], variable=True)

    # confirm strip (the board's role=alert row): the question, the buttons under it on the right
    u.text("CeAskText", "", B, 19, "#ffffff", wrap=True)
    u.box("HorizontalBox", "CeConfirmBtns", [
        (_text_button(u, B, "CeCancel", "Cancel", h=40), ["VerticalAlignment=VAlign_Center"]),
        (_text_button(u, B, "CeConfirm", "Confirm", primary=True, h=40), ["Padding=%s" % u.margin(l=12),
                                                                          "VerticalAlignment=VAlign_Center"])])
    cb = u.box("VerticalBox", "CeConfirmRow", [
        ("CeAskText", ["Padding=%s" % u.margin(b=10)]),
        ("CeConfirmBtns", ["HorizontalAlignment=HAlign_Right"])])
    u.border("CeConfirmFill", "#1a0809", 1.0, u.margin(18, 12, 18, 12), cb)
    u.strip("CeConfirmAcc", "#e5242b", u.margin(l=6))
    u.box("HorizontalBox", "CeConfirmIn", [("CeConfirmAcc", ["VerticalAlignment=VAlign_Fill"]),
                                           ("CeConfirmFill", ["Size=(SizeRule=Fill)", "VerticalAlignment=VAlign_Fill"])])
    u.border("CeConfirmBar", "#b3121a", 1.0, u.margin(1, 1, 1, 1), "CeConfirmIn",
             props=["Visibility=Collapsed"], variable=True)

    # action bar (the board's footer): the status line, the buttons under it on the right
    u.text("CeStatus", "No changes", B, 18, "#f2e6e2", spacing_px=1, wrap=True)
    u.box("WrapBox", "CeActBtns", [
        (_text_button(u, B, "CeRefund", "Refund attributes", h=44, px=16, pad=16), ["Padding=%s" % u.margin(l=10, b=8)]),
        (_text_button(u, B, "CeReset", "Reset to level 1", h=44, px=16, pad=16), ["Padding=%s" % u.margin(l=10, b=8)]),
        (_text_button(u, B, "CeApply", "Apply changes", primary=True, h=44, px=16, pad=16),
         ["Padding=%s" % u.margin(l=10, b=8)])])
    u.box("VerticalBox", "CeActions", [("CeStatus", ["Padding=%s" % u.margin(b=10)]),
                                       ("CeActBtns", ["HorizontalAlignment=HAlign_Right"])])
    u.strip("CeActLine", "#b3121a", u.margin(t=2))

    main = u.box("VerticalBox", "CeMain", [
        ("CeHead", ["Padding=%s" % u.margin(b=14)]),
        ("CeTabBar", ["Padding=%s" % u.margin(b=14)]),
        ("CeTabs", ["Padding=%s" % u.margin(b=14)]),
        ("CeConfirmBar", ["Padding=%s" % u.margin(b=14)]),
        ("CeActLine", ["Padding=%s" % u.margin(b=12)]),
        ("CeActions", [])])
    u.box("HorizontalBox", "CePanel", [
        ("CePColBox", ["VerticalAlignment=VAlign_Fill"]),
        ("CePColLine", ["VerticalAlignment=VAlign_Fill"]),
        (main, ["Size=(SizeRule=Fill)", "Padding=%s" % u.margin(l=16), "VerticalAlignment=VAlign_Top"])])
    return [("CePanel", [])]


def add_variables(unreal, bel, wbp, relay_cls):
    i, b, s = (bel.get_basic_type_by_name(t) for t in ("int", "bool", "string"))
    for var, t in ([("CeRelay", bel.get_object_reference_type(relay_cls)),
                    ("CeSelState", bel.get_object_reference_type(unreal.PlayerState.static_class())),
                    ("CeSeenVer", i), ("CeSeenList", i), ("CeAskAt", bel.get_basic_type_by_name("real")),
                    ("CeConfirmKind", i), ("CeDirty", b), ("CePending", b), ("CeMsg", s), ("CeSelNameStr", s),
                    # Inventory: the chip (CE_INVS index), the picked slot (as the relay's CeInvSlots
                    # holds it; -1 none), redraw flag, cells drawn
                    ("CeInvKind", i), ("CeInvSel", i), ("CeInvDirty", b), ("CeInvShown", i),
                    # Item catalog: the chip, the picked catalogue index, redraw flag, the search
                    # it last drew, cells drawn and matches
                    ("CeCatKind", i), ("CeCatSel", i), ("CeCatDirty", b), ("CeCatQuery", s), ("CeCatShown", i),
                    ("CeCatMatches", i), ("CeEdQty", i),
                    # Currency: the edited wallet, accepted currencies (0/1 per CE_CURRENCIES), price
                    # quarters; unapplied edits; the relay CeEconVer last loaded
                    ("CeEdWallet", i), ("CeEdCurOn", bel.get_array_type(i)), ("CeEdSellQ", i), ("CeEdBuyQ", i),
                    ("CeCurDirty", b), ("CeSeenEcon", i),
                    # the baked catalogue (bake())
                    ("CeCatIds", bel.get_array_type(i)), ("CeCatNames", bel.get_array_type(s)),
                    ("CeCatIcons", bel.get_array_type(s)), ("CeCatCats", bel.get_array_type(i))]
                   + [(v, i) for v, _src, _lim, _key in STEPPERS]):
        bel.add_member_variable(wbp, var, t)


def bake(cdo, entries):
    """The catalogue (ce_catalog) and the starting values, onto the built menu's CDO."""
    cdo.set_editor_property("CeCatIds", [e["id"] for e in entries])
    cdo.set_editor_property("CeCatNames", [e["name"] for e in entries])
    cdo.set_editor_property("CeCatIcons", [e["icon"] for e in entries])
    cdo.set_editor_property("CeCatCats", [e["cat"] for e in entries])
    for var, v in (("CeInvSel", -1), ("CeCatSel", -1), ("CeEdQty", 1), ("CeInvDirty", True), ("CeCatDirty", True),
                   ("CeEdCurOn", [0] * len(D.CE_CURRENCIES)), ("CeEdSellQ", 4), ("CeEdBuyQ", 4)):
        cdo.set_editor_property(var, v)
    assert len(cdo.get_editor_property("CeCatIds")) == len(entries), "catalogue not stored on the CDO"


# ================================================================ graph helpers
class _Ctx:
    """Graph building with a running exec position (exits). relay_var: the menu variable that
    holds the owning player's relay (bug_panel uses this class too)."""
    def __init__(self, g, u, relay_cls, owning_player, relay_var="CeRelay"):
        self.g, self.u, self.RELAY, self.owning_player = g, u, relay_cls, owning_player
        self.relay_var = relay_var
        self.exits = []

    # exec flow: every exit in self.exits goes into the next node
    def go(self, node, pin="execute"):
        for e in self.exits:
            self.g.wire(e[0], e[1], node, pin)
        self.exits = [(node, "then")]
        return node

    def branch(self, cond, pos):
        b = self.g.branch(pos=pos)
        self.go(b)
        self.g.wire(cond[0], cond[1], b, "Condition", exec=False)
        return b

    # values
    def widget(self, name, cls=TEXT, pos=(0, 0)):
        return (self.g.var_get(name, "object", ir.obj_path(cls), pos=pos), name)

    def var(self, name, cat="int", pos=(0, 0), sub=None):
        return (self.g.var_get(name, cat, sub, pos=pos), name)

    def relay(self, pos):
        return (self.g.var_get(self.relay_var, "object", ir.obj_path(self.RELAY), pos=pos), self.relay_var)

    def find_relay(self, pos):
        """From the current exits: if the relay variable isn't set, look for the owning player's
        relay (a listen server sees every player's) and keep it. Leaves the exits where it is
        valid; returns the exits where it still isn't."""
        g, (x, y) = self.g, pos
        rv = self.branch(self.fn("IsValid", KSL, {"Object": self.relay((x - 200, y + 250))}, (x, y + 250)), (x, y))
        self.exits = [(rv, "else")]
        relays = g.get_all_actors(self.RELAY, pos=(x + 300, y + 400))
        self.go(relays)
        each = g.foreach("/Script/Engine.Actor", pos=(x + 600, y + 400))
        g.wire(relays, "then", each, "Exec")
        g.wire(relays, "OutActors", each, "Array", exec=False)
        cast = g.cast(self.RELAY, pos=(x + 900, y + 400))
        g.wire(each, "Array Element", cast, "Object", exec=False)
        g.wire(each, "LoopBody", cast, "execute")
        owner = g.call("GetOwner", "/Script/Engine.Actor", pos=(x + 900, y + 650))
        g.wire(cast, "AsBP Owl Relay", owner, "self", exec=False)
        mine = self.fn("EqualEqual_ObjectObject", KML, {"A": (owner, "ReturnValue"),
                                                        "B": (self.owning_player((x + 900, y + 800)), "ReturnValue")},
                       (x + 1150, y + 650))
        self.exits = [(cast, "then")]
        bm = self.branch(mine, (x + 1200, y + 400))
        self.exits = [(bm, "then")]
        sr = g.var_set(self.relay_var, "object", ir.obj_path(self.RELAY), pos=(x + 1500, y + 400))
        g.wire(cast, "AsBP Owl Relay", sr, self.relay_var, exec=False)
        self.go(sr)
        self.exits = [(each, "Completed")]
        rv2 = self.branch(self.fn("IsValid", KSL, {"Object": self.relay((x + 1500, y + 800))}, (x + 1700, y + 800)),
                          (x + 1800, y + 400))
        self.exits = [(rv, "then"), (rv2, "then")]
        return [(rv2, "else")]

    def rvar(self, name, cat, pos, arr=False, sub=None):
        n = self.g.var_get(name, cat, sub, parent=self.RELAY, pos=pos)
        if arr:
            n.pin(name).set("PinType.ContainerType", "Array")
        r = self.relay((pos[0] - 200, pos[1]))
        self.g.wire(r[0], r[1], n, "self", exec=False)
        return (n, name)

    def fn(self, name, lib, ins, pos, out="ReturnValue"):
        """A pure call: ins = {pin: (node, pin) or (literal, category[, sub-type])}."""
        n = self.g.call(name, lib, pos=pos)
        for p, v in ins.items():
            if isinstance(v[0], str):
                self.g.typed_input(n, p, *v)
            else:
                self.g.wire(v[0], v[1], n, p, exec=False)
        return (n, out)

    def split(self, src, pos):
        """ParseIntoArray(src, "|") keeping empty fields, so field N stays field N. The
        CullEmptyStrings pin is const: a typed-in 'false' was reset to its 'true' default when
        the node was rebuilt (a report with no server name came out shifted by one), so a
        MakeLiteralBool is wired into it instead."""
        g = self.g
        parts = g.call("ParseIntoArray", KSTR, pos=pos)
        g.wire(src[0], src[1], parts, "SourceString", exec=False)
        g.typed_input(parts, "Delimiter", "|", "string")
        keep = self.fn("MakeLiteralBool", KSL, {"Value": ("false", "bool")}, (pos[0] - 200, pos[1] + 200))
        g.wire(keep[0], keep[1], parts, "CullEmptyStrings", exec=False)
        parts.pin("ReturnValue").typed("string", direction="EGPD_Output", container="Array")
        return parts

    def set_var(self, name, cat, src, pos, sub=None):
        n = self.g.var_set(name, cat, sub, pos=pos)
        if isinstance(src, tuple):
            self.g.wire(src[0], src[1], n, name, exec=False)
        else:
            n.pin(name).typed(cat, sub, direction="EGPD_Input").literal(src)
        return self.go(n)

    def set_text(self, widget, src, pos):
        """widget.SetText(src): src a (node, pin) string or a literal."""
        t = self.g.call("Conv_StringToText", KTXT, pos=(pos[0], pos[1] + 200))
        if isinstance(src, tuple):
            self.g.wire(src[0], src[1], t, "InString", exec=False)
        else:
            self.g.typed_input(t, "InString", src, "string")
        st = self.g.call("SetText", TEXT, pos=pos)
        w = self.widget(widget, pos=(pos[0] - 200, pos[1] + 350))
        self.g.wire(w[0], w[1], st, "self", exec=False)
        self.g.wire(t, "ReturnValue", st, "InText", exec=False)
        return self.go(st)

    def set_vis(self, widget, cls, vis, pos):
        sv = self.g.call("SetVisibility", WIDGET, pos=pos)
        self.g.typed_input(sv, "InVisibility", vis, "byte", SLATEVIS)
        w = self.widget(widget, cls, pos=(pos[0] - 200, pos[1] + 200))
        self.g.wire(w[0], w[1], sv, "self", exec=False)
        return self.go(sv)

    def vis_if(self, cond, widgets, pos, on="Visible"):
        """widgets visible when cond, else collapsed; [(name, cls)]."""
        b = self.branch(cond, pos)
        ends = []
        for k, (pin, vis) in enumerate((("then", on), ("else", "Collapsed"))):
            self.exits = [(b, pin)]
            for j, (w, cls) in enumerate(widgets):
                self.set_vis(w, cls, vis, (pos[0] + 300 + 300 * j, pos[1] + 300 * k))
            ends += self.exits
        self.exits = ends

    def color(self, widget, cond, on, off, pos):
        sel = self.fn("SelectColor", KML, {"A": (self.u.lin(on), "struct", LCOLOR),
                                           "B": (self.u.lin(off), "struct", LCOLOR), "bPickA": cond},
                      (pos[0], pos[1] + 250))
        sc =self.g.call("SetBackgroundColor", BUTTON, pos=pos)
        w = self.widget(widget, BUTTON, pos=(pos[0] - 200, pos[1] + 400))
        self.g.wire(w[0], w[1], sc, "self", exec=False)
        self.g.wire(sel[0], sel[1], sc, "InBackgroundColor", exec=False)
        return self.go(sc)

    def call_relay(self, event, ins, pos):
        c = self.g.call(event, self.RELAY, pos=pos)
        r = self.relay((pos[0] - 200, pos[1] + 250))
        self.g.wire(r[0], r[1], c, "self", exec=False)
        for p, v in ins.items():
            self.g.wire(v[0], v[1], c, p, exec=False)
        return self.go(c)

    def int_text(self, src, pos, prefix=""):
        s = self.fn("Conv_IntToString", KSTR, {"InInt": src}, pos)
        return self.fn("Concat_StrStr", KSTR, {"A": (prefix, "string"), "B": s}, (pos[0] + 200, pos[1])) if prefix else s

    def concat(self, parts, pos):
        """Strings joined: parts are (node, pin) or literal strings."""
        acc = parts[0] if isinstance(parts[0], tuple) else (parts[0], "string")
        for k, p in enumerate(parts[1:]):
            acc = self.fn("Concat_StrStr", KSTR, {"A": acc, "B": p if isinstance(p, tuple) else (p, "string")},
                          (pos[0] + 200 * k, pos[1]))
        return acc

    def items_text(self, n, pos):
        """"<n> items" ("1 item")."""
        word = self.fn("SelectString", KML, {"A": (" item", "string"), "B": (" items", "string"),
                                             "bPickA": self.fn("EqualEqual_IntInt", KML, {"A": n, "B": ("1", "int")},
                                                               (pos[0], pos[1] + 150))}, (pos[0] + 200, pos[1] + 150))
        return self.concat([self.int_text(n, pos), word], (pos[0] + 400, pos[1]))

    def arr(self, name, cat, pos):
        """One of the menu's own array variables."""
        return (self.g.array_var(name, pos=pos, elem_cat=cat), name)

    def at(self, array, index, cat, pos):
        return (self.g.array_get(array[0], array[1], index, pos, elem_cat=cat), "Output")

    def find(self, array, item, cat, pos):
        f = self.g.array_fn("Array_Find", pos=pos, elem_cat=cat)
        self.g.array_item_pin(f, "ItemToFind", cat)
        f.pin("ReturnValue").typed("int", direction="EGPD_Output")
        self.g.wire(array[0], array[1], f, "TargetArray", exec=False)
        self.g.wire(item[0], item[1], f, "ItemToFind", exec=False)
        return (f, "ReturnValue")

    def foreach(self, cat, array, pos):
        """ForEachLoop over an int/string array (ir.foreach only types object arrays), entered
        from the current exits. Leaves exits on LoopBody; Completed is the caller's."""
        n = self.g.node("K2Node_MacroInstance", [ir.Graph._FOREACH_REF,
                                                 'ResolvedWildcardType=(PinCategory="%s",ContainerType=Array)' % cat],
                        base="ForEach", pos=pos)
        a = n.pin("Array"); a.dir = "EGPD_Input"
        a.set("PinType.PinCategory", '"%s"' % cat); a.set("PinType.ContainerType", "Array")
        e = n.pin("Array Element"); e.dir = "EGPD_Output"; e.set("PinType.PinCategory", '"%s"' % cat)
        n.pin("Array Index").typed("int", direction="EGPD_Output")
        self.g.wire(array[0], array[1], n, "Array", exec=False)
        self.go(n, "Exec")
        self.exits = [(n, "LoopBody")]
        return n

    def box_text(self, name, pos):
        gt = self.fn("GetText", ETB, {"self": self.widget(name, ETB, (pos[0] - 200, pos[1]))}, pos)
        return self.fn("Conv_TextToString", KTXT, {"InText": gt}, (pos[0] + 200, pos[1]))

    def clear(self, grid, pos):
        n = self.g.call("ClearChildren", PANEL, pos=pos)
        w = self.widget(grid, WRAP, (pos[0] - 200, pos[1] + 200))
        self.g.wire(w[0], w[1], n, "self", exec=False)
        return self.go(n)

    def bump(self, name, pos):
        self.set_var(name, "int", self.fn("Add_IntInt", KML, {"A": self.var(name, "int", (pos[0], pos[1] + 200)),
                                                              "B": ("1", "int")}, (pos[0] + 150, pos[1] + 200)), pos)


# ================================================================ tick
def tick(g, u, relay_cls, cell_cls, owning_player, entries, unlocked, on_page, y=20000):
    """The per-frame work, entered from each (node, exec pin) in entries; returns the exits."""
    c = _Ctx(g, u, relay_cls, owning_player)
    c.exits = list(entries)
    out = []
    # only while unlocked and on the Characters page
    b = c.branch(c.fn("BooleanAND", KML, {"A": unlocked, "B": on_page}, (0, y + 250)), (200, y))
    out.append((b, "else"))
    c.exits = [(b, "then")]
    # the owning player's relay, found once (a listen server sees every player's)
    rv = c.branch(c.fn("IsValid", KSL, {"Object": c.relay((300, y + 250))}, (500, y + 250)), (500, y))
    c.exits = [(rv, "else")]
    relays = g.get_all_actors(relay_cls, pos=(800, y + 400))
    c.go(relays)
    each = g.foreach("/Script/Engine.Actor", pos=(1100, y + 400))
    g.wire(relays, "then", each, "Exec")
    g.wire(relays, "OutActors", each, "Array", exec=False)
    cast = g.cast(relay_cls, pos=(1400, y + 400))
    g.wire(each, "Array Element", cast, "Object", exec=False)
    g.wire(each, "LoopBody", cast, "execute")
    owner = g.call("GetOwner", "/Script/Engine.Actor", pos=(1400, y + 650))
    g.wire(cast, "AsBP Owl Relay", owner, "self", exec=False)
    mine = c.fn("EqualEqual_ObjectObject", KML, {"A": (owner, "ReturnValue"),
                                                 "B": (owning_player((1400, y + 800)), "ReturnValue")}, (1650, y + 650))
    c.exits = [(cast, "then")]
    bm = c.branch(mine, (1700, y + 400))
    c.exits = [(bm, "then")]
    sr = g.var_set("CeRelay", "object", ir.obj_path(relay_cls), pos=(2000, y + 400))
    g.wire(cast, "AsBP Owl Relay", sr, "CeRelay", exec=False)
    c.go(sr)
    c.exits = [(each, "Completed")]
    rv2 = c.branch(c.fn("IsValid", KSL, {"Object": c.relay((2000, y + 800))}, (2200, y + 800)), (2300, y + 400))
    out.append((rv2, "else"))
    c.exits = [(rv, "then"), (rv2, "then")]

    # every CE_ASK_SECONDS: OwlServerCeList
    x = 2600
    now = c.fn("GetGameTimeInSeconds", KSL, {}, (x, y + 300))
    due = c.fn("Greater_DoubleDouble", KML, {"A": now, "B": c.var("CeAskAt", "real", (x, y + 450))}, (x + 250, y + 300))
    bd = c.branch(due, (x + 250, y))
    c.exits = [(bd, "then")]
    c.set_var("CeAskAt", "real", c.fn("Add_DoubleDouble", KML, {"A": now, "B": (str(CE_ASK_SECONDS), "real")},
                                      (x + 500, y + 300)), (x + 550, y))
    c.call_relay("OwlServerCeList", {}, (x + 850, y))
    # the trade settings, until the server has sent them once (Store = false only reads)
    be = c.branch(c.fn("EqualEqual_IntInt", KML, {"A": c.rvar("CeEconVer", "int", (x + 900, y + 450)), "B": ("0", "int")},
                       (x + 1100, y + 450)), (x + 1100, y))
    c.exits = [(be, "then")]
    c.call_relay("OwlServerCeEconomy", {"CurOn": c.arr("CeEdCurOn", "int", (x + 1200, y + 600)),
                                        "SellQ": c.var("CeEdSellQ", "int", (x + 1200, y + 750)),
                                        "BuyQ": c.var("CeEdBuyQ", "int", (x + 1200, y + 900))}, (x + 1400, y))
    c.exits += [(be, "else"), (bd, "else")]

    # the player list changed: redraw the rows
    x = 3800
    lv = c.rvar("CeListVer", "int", (x, y + 300))
    bl = c.branch(c.fn("NotEqual_IntInt", KML, {"A": lv, "B": c.var("CeSeenList", "int", (x, y + 450))},
                       (x + 250, y + 300)), (x + 250, y))
    c.exits = [(bl, "then")]
    names = lambda pos: c.rvar("CeNames", "string", pos, arr=True)
    for i in range(CEP_ROWS):
        xi = x + 550 + 1300 * i
        ln = g.array_len(names((xi, y + 600))[0], "CeNames", (xi + 200, y + 600), elem_cat="string")
        bi = c.branch(c.fn("Less_IntInt", KML, {"A": (str(i), "int"), "B": (ln, "ReturnValue")}, (xi + 200, y + 450)),
                      (xi, y))
        c.exits = [(bi, "then")]
        c.set_vis("CeP%d" % i, BUTTON, "Visible", (xi + 250, y))
        nm = g.array_get(names((xi + 400, y + 750))[0], "CeNames", i, (xi + 550, y + 750), elem_cat="string")
        c.set_text("CePName%d" % i, (nm, "Output"), (xi + 550, y))
        lvls = c.rvar("CeLevels", "int", (xi + 700, y + 900), arr=True)
        li = g.array_get(lvls[0], "CeLevels", i, (xi + 850, y + 900), elem_cat="int")
        meta = c.int_text((li, "Output"), (xi + 850, y + 1050), prefix="Level ")
        c.set_text("CePMeta%d" % i, meta, (xi + 850, y))
        ends = c.exits
        c.exits = [(bi, "else")]
        c.set_vis("CeP%d" % i, BUTTON, "Collapsed", (xi + 250, y + 300))
        c.exits += ends
    ln0 = g.array_len(names((x, y + 1300))[0], "CeNames", (x + 200, y + 1300), elem_cat="string")
    c.vis_if(c.fn("EqualEqual_IntInt", KML, {"A": (ln0, "ReturnValue"), "B": ("0", "int")}, (x + 400, y + 1300)),
             [("CeNoPlayers", TEXT)], (x + 550 + 1300 * CEP_ROWS, y))
    c.set_var("CeSeenList", "int", c.rvar("CeListVer", "int", (x + 1000 + 1300 * CEP_ROWS, y + 300)),
              (x + 1300 + 1300 * CEP_ROWS, y))
    c.exits += [(bl, "else")]

    # nobody selected, or they left: select the first player
    y2 = y + 3000
    states = lambda pos: c.rvar("CeStates", "object", pos, arr=True, sub=ir.obj_path(PSTATE))
    find = g.array_fn("Array_Find", pos=(300, y2 + 300), elem_cat="object", elem_sub=ir.obj_path(PSTATE))
    g.array_item_pin(find, "ItemToFind", "object", ir.obj_path(PSTATE))
    find.pin("ReturnValue").typed("int", direction="EGPD_Output")
    st0 = states((0, y2 + 300))
    g.wire(st0[0], st0[1], find, "TargetArray", exec=False)
    sel0 = c.var("CeSelState", "object", (0, y2 + 450), sub=ir.obj_path(PSTATE))
    g.wire(sel0[0], sel0[1], find, "ItemToFind", exec=False)
    gone = c.fn("Less_IntInt", KML, {"A": (find, "ReturnValue"), "B": ("0", "int")}, (550, y2 + 300))
    lst = g.array_len(states((300, y2 + 500))[0], "CeStates", (550, y2 + 500), elem_cat="object",
                      elem_sub=ir.obj_path(PSTATE))
    some = c.fn("Greater_IntInt", KML, {"A": (lst, "ReturnValue"), "B": ("0", "int")}, (750, y2 + 500))
    ba = c.branch(c.fn("BooleanAND", KML, {"A": gone, "B": some}, (900, y2 + 400)), (900, y2))
    c.exits = [(ba, "then")]
    first = g.array_get(states((1000, y2 + 600))[0], "CeStates", 0, (1200, y2 + 600), elem_cat="object",
                        elem_sub=ir.obj_path(PSTATE))
    _select(c, (first, "Output"), (1200, y2))
    c.exits += [(ba, "else")]

    # the selected player's data arrived: load the editable values and the log
    x = 3000
    cv = c.rvar("CeClientVer", "int", (x, y2 + 300))
    bv = c.branch(c.fn("NotEqual_IntInt", KML, {"A": cv, "B": c.var("CeSeenVer", "int", (x, y2 + 450))},
                       (x + 250, y2 + 300)), (x + 250, y2))
    c.exits = [(bv, "then")]
    for j, (mine_, src, _lim, _key) in enumerate(STEPPERS):
        c.set_var(mine_, "int", c.rvar(src, "int", (x + 500 + 300 * j, y2 + 300)), (x + 500 + 300 * j, y2))
    x += 500 + 300 * len(STEPPERS)
    c.set_var("CeDirty", "bool", "false", (x, y2))
    # the name: the target's row in the list (the list holds the names)
    tfind = g.array_fn("Array_Find", pos=(x + 300, y2 + 400), elem_cat="object", elem_sub=ir.obj_path(PSTATE))
    g.array_item_pin(tfind, "ItemToFind", "object", ir.obj_path(PSTATE))
    tfind.pin("ReturnValue").typed("int", direction="EGPD_Output")
    st1 = states((x + 100, y2 + 400))
    g.wire(st1[0], st1[1], tfind, "TargetArray", exec=False)
    tgt = c.rvar("CeTarget", "object", (x + 100, y2 + 550), sub=ir.obj_path(PSTATE))
    g.wire(tgt[0], tgt[1], tfind, "ItemToFind", exec=False)
    bn = c.branch(c.fn("GreaterEqual_IntInt", KML, {"A": (tfind, "ReturnValue"), "B": ("0", "int")},
                       (x + 550, y2 + 400)), (x + 600, y2))
    c.exits = [(bn, "then")]
    nm = g.array_get(names((x + 600, y2 + 700))[0], "CeNames", (tfind, "ReturnValue"), (x + 800, y2 + 700),
                     elem_cat="string")
    c.set_var("CeSelNameStr", "string", (nm, "Output"), (x + 900, y2))
    c.exits += [(bn, "else")]
    up = c.fn("ToUpper", KSTR, {"SourceString": c.var("CeSelNameStr", "string", (x + 1100, y2 + 400))}, (x + 1300, y2 + 400))
    c.set_text("CeSelName", up, (x + 1300, y2))
    # status: what we sent is done, or just showing their values
    msg = c.fn("SelectString", KML, {"A": ("Done. The server made the change, and it is logged.", "string"),
                                     "B": ("Showing the player's values from the server.", "string"),
                                     "bPickA": c.var("CePending", "bool", (x + 1500, y2 + 500))}, (x + 1700, y2 + 400))
    c.set_var("CeMsg", "string", msg, (x + 1800, y2))
    c.set_var("CePending", "bool", "false", (x + 2100, y2))
    c.set_var("CeInvDirty", "bool", "true", (x + 2100, y2 + 300))     # their inventory came with it
    # and their wallet (kept while there are unapplied Currency edits)
    c.set_var("CeEdWallet", "int", c.fn("SelectInt", KML, {"A": c.var("CeEdWallet", "int", (x + 2000, y2 + 600)),
                                                           "B": c.rvar("CeWallet", "int", (x + 2000, y2 + 750)),
                                                           "bPickA": c.var("CeCurDirty", "bool", (x + 2000, y2 + 900))},
                                        (x + 2200, y2 + 600)), (x + 2200, y2 + 300))
    # log rows: newest first
    x += 2400
    log = lambda pos: c.rvar("CeLog", "string", pos, arr=True)
    for k in range(CE_LOG_ROWS):
        xk = x + 1500 * k
        ln = g.array_len(log((xk, y2 + 600))[0], "CeLog", (xk + 200, y2 + 600), elem_cat="string")
        bk = c.branch(c.fn("Less_IntInt", KML, {"A": (str(k), "int"), "B": (ln, "ReturnValue")}, (xk + 200, y2 + 450)),
                      (xk, y2))
        c.exits = [(bk, "then")]
        c.set_vis("CeLg%d" % k, "/Script/UMG.HorizontalBox", "Visible", (xk + 250, y2))
        at = c.fn("Subtract_IntInt", KML, {"A": (ln, "ReturnValue"), "B": (str(k + 1), "int")}, (xk + 400, y2 + 750))
        line = g.array_get(log((xk + 400, y2 + 900))[0], "CeLog", at, (xk + 600, y2 + 900), elem_cat="string")
        parts = c.split((line, "Output"), (xk + 800, y2 + 900))
        for f, wname in enumerate(("CeLgT%d", "CeLgA%d", "CeLgX%d")):
            piece = g.array_get(parts, "ReturnValue", f, (xk + 1000, y2 + 1000 + 150 * f), elem_cat="string")
            c.set_text(wname % k, (piece, "Output"), (xk + 500 + 300 * f, y2))
        ends = c.exits
        c.exits = [(bk, "else")]
        c.set_vis("CeLg%d" % k, "/Script/UMG.HorizontalBox", "Collapsed", (xk + 250, y2 + 300))
        c.exits += ends
    x += 1500 * CE_LOG_ROWS
    lnl = g.array_len(log((x, y2 + 600))[0], "CeLog", (x + 200, y2 + 600), elem_cat="string")
    c.vis_if(c.fn("EqualEqual_IntInt", KML, {"A": (lnl, "ReturnValue"), "B": ("0", "int")}, (x + 400, y2 + 600)),
             [("CeLogEmpty", TEXT)], (x + 400, y2))
    c.set_var("CeSeenVer", "int", c.rvar("CeClientVer", "int", (x + 900, y2 + 300)), (x + 1000, y2))
    c.exits += [(bv, "else")]

    # every frame: values, confirm strip, status, highlights
    y3 = y + 6000
    for j, (mine_, _src, _lim, key) in enumerate(STEPPERS):
        c.set_text(key + "Val", c.int_text(c.var(mine_, "int", (300 * j, y3 + 450)), (300 * j, y3 + 600)), (300 * j, y3))
    x = 300 * len(STEPPERS) + 300
    kind = c.var("CeConfirmKind", "int", (x, y3 + 300))
    c.vis_if(c.fn("Greater_IntInt", KML, {"A": kind, "B": ("0", "int")}, (x + 200, y3 + 300)),
             [("CeConfirmBar", "/Script/UMG.Border")], (x + 300, y3))
    who = c.var("CeSelNameStr", "string", (x + 900, y3 + 500))
    refund_q = c.fn("Concat_StrStr", KSTR, {"A": c.fn("Concat_StrStr", KSTR, {"A": ("Refund all of ", "string"), "B": who},
                                                    (x + 1100, y3 + 500)),
                                            "B": ("'s attribute points?", "string")}, (x + 1300, y3 + 500))
    reset_q = c.fn("Concat_StrStr", KSTR, {"A": c.fn("Concat_StrStr", KSTR, {"A": ("Reset ", "string"), "B": who},
                                                   (x + 1100, y3 + 650)),
                                           "B": (" to level 1 and clear all attributes?", "string")}, (x + 1300, y3 + 650))
    is_refund = c.fn("EqualEqual_IntInt", KML, {"A": kind, "B": ("1", "int")}, (x + 1300, y3 + 800))
    q = c.fn("SelectString", KML, {"A": refund_q, "B": reset_q, "bPickA": is_refund}, (x + 1500, y3 + 600))
    c.set_text("CeAskText", q, (x + 1600, y3))
    st = c.fn("SelectString", KML, {"A": ("Unapplied changes. Press Apply to send them.", "string"),
                                    "B": c.var("CeMsg", "string", (x + 1800, y3 + 500)),
                                    "bPickA": c.fn("BooleanOR", KML, {"A": c.var("CeDirty", "bool", (x + 1600, y3 + 650)),
                                                                      "B": c.var("CeCurDirty", "bool", (x + 1600, y3 + 800))},
                                                   (x + 1800, y3 + 650))}, (x + 2000, y3 + 500))
    c.set_text("CeStatus", st, (x + 2000, y3))
    # player row highlight: the selected player's row
    x += 2400
    sf = g.array_fn("Array_Find", pos=(x, y3 + 400), elem_cat="object", elem_sub=ir.obj_path(PSTATE))
    g.array_item_pin(sf, "ItemToFind", "object", ir.obj_path(PSTATE))
    sf.pin("ReturnValue").typed("int", direction="EGPD_Output")
    st2 = states((x - 200, y3 + 400))
    g.wire(st2[0], st2[1], sf, "TargetArray", exec=False)
    sel2 = c.var("CeSelState", "object", (x - 200, y3 + 550), sub=ir.obj_path(PSTATE))
    g.wire(sel2[0], sel2[1], sf, "ItemToFind", exec=False)
    for i in range(CEP_ROWS):
        eq = c.fn("EqualEqual_IntInt", KML, {"A": (sf, "ReturnValue"), "B": (str(i), "int")}, (x + 300 * i, y3 + 600))
        c.color("CeP%d" % i, eq, ROW_ON, ROW_OFF, (x + 300 * i, y3))
    # sub-tab chips + Refund/Reset only on the Stats tab
    x += 300 * CEP_ROWS
    ti = c.fn("GetActiveWidgetIndex", SWITCHER, {"self": c.widget("CeTabs", SWITCHER, (x, y3 + 600))}, (x + 200, y3 + 600))
    for k, (key, _label) in enumerate(D.CE_TABS):
        eq = c.fn("EqualEqual_IntInt", KML, {"A": ti, "B": (str(k), "int")}, (x + 300 * k, y3 + 800))
        c.color("CeTab_" + key, eq, CHIP_ON, CHIP_OFF, (x + 300 * k, y3))
    x += 300 * len(D.CE_TABS)
    on_stats = c.fn("EqualEqual_IntInt", KML, {"A": ti, "B": ("0", "int")}, (x, y3 + 300))
    c.vis_if(on_stats, [("CeRefundBox", SIZEBOX), ("CeResetBox", SIZEBOX)], (x + 200, y3))
    # Apply: the Stats values, or the Currency values
    on_cur = c.fn("EqualEqual_IntInt", KML, {"A": ti, "B": (str(CUR_TAB), "int")}, (x + 900, y3 + 450))
    c.vis_if(c.fn("BooleanOR", KML, {"A": on_stats, "B": on_cur}, (x + 1100, y3 + 300)),
             [("CeApplyBox", SIZEBOX)], (x + 1100, y3))
    _items(c, cell_cls, y + 9000)
    _currency(c, y + 16500)
    return out + c.exits


# ================================================================ Currency (tick)
def _quarters(c, q, pos):
    """A price multiplier in quarters as text: 5 -> "1.25x"."""
    x, y = pos
    frac = c.fn("Percent_IntInt", KML, {"A": q, "B": ("4", "int")}, (x, y + 150))
    is_ = lambda n, yy: c.fn("EqualEqual_IntInt", KML, {"A": frac, "B": (str(n), "int")}, (x + 200, yy))
    fs = c.fn("SelectString", KML, {"A": (".50", "string"), "B": (".75", "string"), "bPickA": is_(2, y + 600)}, (x + 400, y + 600))
    fs = c.fn("SelectString", KML, {"A": (".25", "string"), "B": fs, "bPickA": is_(1, y + 450)}, (x + 600, y + 450))
    fs = c.fn("SelectString", KML, {"A": (".00", "string"), "B": fs, "bPickA": is_(0, y + 300)}, (x + 800, y + 300))
    whole = c.int_text(c.fn("Divide_IntInt", KML, {"A": q, "B": ("4", "int")}, (x, y)), (x + 200, y))
    return c.concat([whole, fs, "x"], (x + 1000, y))


def _currency(c, y):
    g = c.g
    # the trade settings arrived: load them (kept while there are unapplied Currency edits)
    new = c.fn("NotEqual_IntInt", KML, {"A": c.rvar("CeEconVer", "int", (0, y + 300)),
                                        "B": c.var("CeSeenEcon", "int", (0, y + 450))}, (200, y + 300))
    clean = c.fn("Not_PreBool", KML, {"A": c.var("CeCurDirty", "bool", (0, y + 600))}, (200, y + 600))
    b = c.branch(c.fn("BooleanAND", KML, {"A": new, "B": clean}, (400, y + 400)), (400, y))
    skip = [(b, "else")]
    c.exits = [(b, "then")]
    cp = g.var_set("CeEdCurOn", "int", pos=(700, y))
    cp.pin("CeEdCurOn").set("PinType.ContainerType", "Array")
    src = c.rvar("CeCurOn", "int", (600, y + 250), arr=True)
    g.wire(src[0], src[1], cp, "CeEdCurOn", exec=False)
    c.go(cp)
    # one entry per currency (nothing saved yet: none accepted)
    for k in range(len(D.CE_CURRENCIES)):
        xk = 1000 + 600 * k
        ln = g.array_len(c.arr("CeEdCurOn", "int", (xk, y + 450))[0], "CeEdCurOn", (xk + 200, y + 450), elem_cat="int")
        bk = c.branch(c.fn("Less_IntInt", KML, {"A": (ln, "ReturnValue"), "B": (str(len(D.CE_CURRENCIES)), "int")},
                           (xk + 200, y + 300)), (xk, y))
        c.exits = [(bk, "then")]
        add = g.array_fn("Array_Add", pos=(xk + 300, y), elem_cat="int")
        g.array_item_pin(add, "NewItem", "int")
        add.pin("ReturnValue").typed("int", direction="EGPD_Output")
        a = c.arr("CeEdCurOn", "int", (xk + 100, y + 200))
        g.wire(a[0], a[1], add, "TargetArray", exec=False)
        c.go(add)
        c.exits += [(bk, "else")]
    x = 1000 + 600 * len(D.CE_CURRENCIES)
    c.set_var("CeEdSellQ", "int", c.rvar("CeSellQ", "int", (x, y + 300)), (x, y))
    c.set_var("CeEdBuyQ", "int", c.rvar("CeBuyQ", "int", (x + 300, y + 300)), (x + 300, y))
    c.set_var("CeSeenEcon", "int", c.rvar("CeEconVer", "int", (x + 600, y + 300)), (x + 600, y))
    c.exits += skip

    # every frame: the values and the currency toggles
    y += 1500
    bal = c.fn("Conv_IntToText", KTXT, {"Value": c.var("CeEdWallet", "int", (0, y + 300))}, (200, y + 300))
    c.set_text("CeBalVal", c.fn("Conv_TextToString", KTXT, {"InText": bal}, (400, y + 300)), (400, y))
    c.set_text("CeSellVal", _quarters(c, c.var("CeEdSellQ", "int", (500, y + 500)), (700, y + 500)), (900, y))
    c.set_text("CeBuyVal", _quarters(c, c.var("CeEdBuyQ", "int", (1500, y + 500)), (1700, y + 500)), (1900, y))
    x = 2900
    for k in range(len(D.CE_CURRENCIES)):
        xk = x + 700 * k
        on = c.fn("EqualEqual_IntInt", KML, {"A": c.at(c.arr("CeEdCurOn", "int", (xk, y + 600)), k, "int",
                                                       (xk + 150, y + 600)),
                                             "B": ("1", "int")}, (xk + 300, y + 600))
        c.color("CeCur%dBtn" % k, on, CHIP_ON, CHIP_OFF, (xk, y))
        c.set_text("CeCur%dBtnText" % k, c.fn("SelectString", KML, {"A": ("Accepted", "string"), "B": ("Off", "string"),
                                                                    "bPickA": on}, (xk + 300, y + 750)), (xk + 300, y))


# ================================================================ Inventory + Item catalog (tick)
def _lookup(c, item_id, pos):
    """(name, icon path) for a template id: the catalogue's, or "Item <id>" and no icon."""
    x, y = pos
    f = c.find(c.arr("CeCatIds", "int", (x - 200, y)), item_id, "int", (x, y))
    found = c.fn("GreaterEqual_IntInt", KML, {"A": f, "B": ("0", "int")}, (x + 250, y + 150))
    at = c.fn("Max", KML, {"A": f, "B": ("0", "int")}, (x + 250, y))
    name = c.fn("SelectString", KML, {"A": c.at(c.arr("CeCatNames", "string", (x + 250, y + 300)), at, "string",
                                                 (x + 450, y + 300)),
                                      "B": c.int_text(item_id, (x + 450, y + 450), prefix="Item "),
                                      "bPickA": found}, (x + 700, y + 300))
    icon = c.fn("SelectString", KML, {"A": c.at(c.arr("CeCatIcons", "string", (x + 250, y + 600)), at, "string",
                                                 (x + 450, y + 600)),
                                      "B": ("", "string"), "bPickA": found}, (x + 700, y + 600))
    return name, icon


def _add_cell(c, cell_cls, grid, index, kind, icon, label, selected, count, shown, pos):
    """A cell for one item: create it, set its variables, add it to the grid, count it."""
    g = c.g
    x, y = pos
    mk = g.create_widget(cell_cls, pos=(x, y))
    g.wire(c.owning_player((x - 200, y + 250)), "ReturnValue", mk, "OwningPlayer", exec=False)
    c.go(mk)
    me = g.node("K2Node_Self", [], base="Self", pos=(x + 100, y + 500))
    me.pin("self").typed("object", direction="EGPD_Output")
    sets = [("Index", "int", index), ("Menu", "object", (me, "self")), ("IconPath", "string", icon),
            ("Label", "string", label), ("Selected", "bool", selected)]
    if kind:                    # Kind 0 is the default (a pasted literal 0 isn't needed)
        sets.append(("Kind", "int", str(kind)))
    if count:
        sets.append(("Count", "string", count))
    cx = x + 300
    for name, cat, src in sets:
        sv = g.var_set(name, cat, ir.obj_path(UW) if cat == "object" else None, pos=(cx, y), parent=cell_cls)
        g.wire(mk, "ReturnValue", sv, "self", exec=False)
        if isinstance(src, tuple):
            g.wire(src[0], src[1], sv, name, exec=False)
        else:
            sv.pin(name).typed(cat, direction="EGPD_Input").literal(src)
        c.go(sv)
        cx += 300
    add = g.call("AddChildToWrapBox", WRAP, pos=(cx, y))
    w = c.widget(grid, WRAP, (cx - 200, y + 200))
    g.wire(w[0], w[1], add, "self", exec=False)
    g.wire(mk, "ReturnValue", add, "Content", exec=False)
    c.go(add)
    c.bump(shown, (cx + 300, y))


def _items(c, cell_cls, y):
    g = c.g
    # ---- Inventory grid, when the data came (CeInvDirty) or the chip / pick changed
    b = c.branch(c.var("CeInvDirty", "bool", (0, y + 250)), (200, y))
    skip = [(b, "else")]
    c.exits = [(b, "then")]
    c.set_var("CeInvDirty", "bool", "false", (400, y))
    c.clear("CeInvGrid", (700, y))
    c.set_var("CeInvShown", "int", "0", (1000, y))
    loop = c.foreach("int", c.rvar("CeInvSlots", "int", (1100, y + 300), arr=True), (1300, y))
    ix, slot = (loop, "Array Index"), (loop, "Array Element")
    kind = c.fn("Divide_IntInt", KML, {"A": slot, "B": ("1000", "int")}, (1500, y + 300))
    c.branch(c.fn("EqualEqual_IntInt", KML, {"A": kind, "B": c.var("CeInvKind", "int", (1500, y + 450))},
                  (1700, y + 300)), (1700, y))
    item = c.at(c.rvar("CeInvIds", "int", (1800, y + 600), arr=True), ix, "int", (2000, y + 600))
    cnt = c.at(c.rvar("CeInvCounts", "int", (1800, y + 750), arr=True), ix, "int", (2000, y + 750))
    name, icon = _lookup(c, item, (2200, y + 900))
    count = c.fn("SelectString", KML, {"A": c.fn("Conv_IntToString", KSTR, {"InInt": cnt}, (2200, y + 1600)),
                                       "B": ("", "string"),
                                       "bPickA": c.fn("Greater_IntInt", KML, {"A": cnt, "B": ("1", "int")},
                                                      (2200, y + 1750))}, (2450, y + 1600))
    sel = c.fn("EqualEqual_IntInt", KML, {"A": slot, "B": c.var("CeInvSel", "int", (2200, y + 1900))}, (2450, y + 1900))
    _add_cell(c, cell_cls, "CeInvGrid", ix, 0, icon, name, sel, count, "CeInvShown", (2000, y))
    c.exits = [(loop, "Completed")]
    shown = c.var("CeInvShown", "int", (4800, y + 300))
    txt = c.fn("SelectString", KML, {"A": ("Nothing here.", "string"),
                                     "B": c.items_text(shown, (4900, y + 450)),
                                     "bPickA": c.fn("EqualEqual_IntInt", KML, {"A": shown, "B": ("0", "int")},
                                                    (5100, y + 300))}, (5400, y + 300))
    c.set_text("CeInvCount", txt, (5400, y))
    c.exits += skip

    # ---- Item catalog grid, when the chip / pick changed or the search text differs from the last drawn
    y += 2500
    q_now = c.box_text("CeCatSearch", (0, y + 450))
    redraw = c.fn("BooleanOR", KML, {"A": c.var("CeCatDirty", "bool", (200, y + 300)),
                                     "B": c.fn("NotEqual_StrStr", KSTR, {"A": q_now, "B": c.var("CeCatQuery", "string",
                                                                                               (300, y + 600))},
                                               (500, y + 450))}, (700, y + 300))
    b = c.branch(redraw, (700, y))
    skip = [(b, "else")]
    c.exits = [(b, "then")]
    c.set_var("CeCatDirty", "bool", "false", (900, y))
    c.set_var("CeCatQuery", "string", c.box_text("CeCatSearch", (900, y + 450)), (1200, y))
    c.clear("CeCatGrid", (1500, y))
    c.set_var("CeCatShown", "int", "0", (1800, y))
    c.set_var("CeCatMatches", "int", "0", (2100, y))
    loop = c.foreach("int", c.arr("CeCatIds", "int", (2200, y + 300)), (2400, y))
    ix = (loop, "Array Index")
    ck = c.var("CeCatKind", "int", (2500, y + 450))
    m_cat = c.fn("BooleanOR", KML, {
        "A": c.fn("EqualEqual_IntInt", KML, {"A": ck, "B": ("0", "int")}, (2700, y + 450)),
        "B": c.fn("EqualEqual_IntInt", KML, {"A": c.at(c.arr("CeCatCats", "int", (2500, y + 600)), ix, "int",
                                                       (2700, y + 600)),
                                             "B": c.var("CeCatKind", "int", (2700, y + 750))}, (2900, y + 600))},
        (3100, y + 450))
    query = lambda pos: c.var("CeCatQuery", "string", pos)
    name = c.at(c.arr("CeCatNames", "string", (2500, y + 900)), ix, "string", (2700, y + 900))
    m_q = c.fn("BooleanOR", KML, {
        "A": c.fn("EqualEqual_IntInt", KML, {"A": c.fn("Len", KSTR, {"S": query((2500, y + 1050))}, (2700, y + 1050)),
                                             "B": ("0", "int")}, (2900, y + 1050)),
        "B": c.fn("Contains", KSTR, {"SearchIn": name, "Substring": query((2700, y + 1200))}, (2900, y + 1200))},
        (3100, y + 1050))
    c.branch(c.fn("BooleanAND", KML, {"A": m_cat, "B": m_q}, (3300, y + 600)), (3300, y))
    c.bump("CeCatMatches", (3500, y))
    c.branch(c.fn("Less_IntInt", KML, {"A": c.var("CeCatShown", "int", (3700, y + 300)),
                                       "B": (str(CE_CAT_MAX), "int")}, (3900, y + 300)), (3900, y))
    icon = c.at(c.arr("CeCatIcons", "string", (4000, y + 600)), ix, "string", (4200, y + 600))
    sel = c.fn("EqualEqual_IntInt", KML, {"A": ix, "B": c.var("CeCatSel", "int", (4000, y + 750))}, (4200, y + 750))
    _add_cell(c, cell_cls, "CeCatGrid", ix, 1, icon, name, sel, None, "CeCatShown", (4200, y))
    c.exits = [(loop, "Completed")]
    shown = lambda pos: c.var("CeCatShown", "int", pos)
    matches = lambda pos: c.var("CeCatMatches", "int", pos)
    capped = c.concat(["Showing ", c.int_text(shown((7000, y + 450)), (7200, y + 450)), " of ",
                       c.int_text(matches((7000, y + 600)), (7200, y + 600)), " items. Search to narrow it down."],
                      (7400, y + 450))
    plain = c.items_text(matches((7000, y + 800)), (7200, y + 800))
    some = c.fn("SelectString", KML, {"A": capped, "B": plain,
                                      "bPickA": c.fn("Greater_IntInt", KML, {"A": matches((7600, y + 950)),
                                                                             "B": shown((7600, y + 1100))},
                                                     (7800, y + 950))}, (8200, y + 600))
    txt = c.fn("SelectString", KML, {"A": ("No items match.", "string"), "B": some,
                                     "bPickA": c.fn("EqualEqual_IntInt", KML, {"A": matches((8200, y + 900)),
                                                                               "B": ("0", "int")}, (8400, y + 900))},
               (8600, y + 600))
    c.set_text("CeCatCount", txt, (8600, y))
    c.exits += skip

    # ---- every frame: the item bars, quantities, chip highlights
    y += 2500
    for k, key in enumerate(("CeInvBar", "CeCatBar")):
        c.set_text(key + "QVal", c.int_text(c.var("CeEdQty", "int", (300 * k, y + 450)), (300 * k, y + 600)), (300 * k, y))
    # the inventory pick: found in what the server sent? (a branch: an empty array can't be read)
    p = c.find(c.rvar("CeInvSlots", "int", (800, y + 300), arr=True), c.var("CeInvSel", "int", (800, y + 450)), "int",
               (1000, y + 300))
    bf = c.branch(c.fn("GreaterEqual_IntInt", KML, {"A": p, "B": ("0", "int")}, (1200, y + 300)), (1200, y))
    c.exits = [(bf, "then")]
    item = c.at(c.rvar("CeInvIds", "int", (1300, y + 600), arr=True), p, "int", (1500, y + 600))
    cnt = c.at(c.rvar("CeInvCounts", "int", (1300, y + 750), arr=True), p, "int", (1500, y + 750))
    name, _icon = _lookup(c, item, (1700, y + 900))
    c.set_text("CeInvBarName", name, (1700, y))
    c.set_text("CeInvBarMeta", c.concat(["Stack of ", c.int_text(cnt, (2000, y + 1700)), "  ·  item id ",
                                         c.int_text(item, (2000, y + 1850))], (2300, y + 1700)), (2300, y))
    ends = c.exits
    c.exits = [(bf, "else")]
    c.set_text("CeInvBarName", "Pick an item", (1700, y + 300))
    c.set_text("CeInvBarMeta", "Remove some of a stack, or grant more of it.", (2000, y + 300))
    c.exits += ends
    # the catalog pick (-1: none; the catalogue is never empty, so index 0 stands in)
    x = 2800
    cs = c.var("CeCatSel", "int", (x, y + 300))
    has = c.fn("GreaterEqual_IntInt", KML, {"A": cs, "B": ("0", "int")}, (x + 200, y + 450))
    at = c.fn("Max", KML, {"A": cs, "B": ("0", "int")}, (x + 200, y + 300))
    nm = c.at(c.arr("CeCatNames", "string", (x + 200, y + 600)), at, "string", (x + 400, y + 600))
    c.set_text("CeCatBarName", c.fn("SelectString", KML, {"A": nm, "B": ("Pick an item", "string"), "bPickA": has},
                                    (x + 600, y + 450)), (x + 600, y))
    cid = c.at(c.arr("CeCatIds", "int", (x + 600, y + 900)), at, "int", (x + 800, y + 900))
    meta = c.fn("SelectString", KML, {"A": c.int_text(cid, (x + 900, y + 1050), prefix="Item id "),
                                      "B": ("Search or browse, then grant it to the player.", "string"),
                                      "bPickA": has}, (x + 1100, y + 900))
    c.set_text("CeCatBarMeta", meta, (x + 1100, y))
    c.set_text("CeCatGrantText", c.concat(["Grant to ", c.var("CeSelNameStr", "string", (x + 1300, y + 450))],
                                          (x + 1500, y + 450)), (x + 1500, y))
    # chips
    x += 1900
    for k, (key, _label) in enumerate(D.CE_INVS):
        eq = c.fn("EqualEqual_IntInt", KML, {"A": c.var("CeInvKind", "int", (x + 300 * k, y + 900)),
                                             "B": (str(k), "int")}, (x + 300 * k, y + 800))
        c.color("CeInvTab_" + key, eq, CHIP_ON, CHIP_OFF, (x + 300 * k, y))
    x += 300 * len(D.CE_INVS)
    for k, (key, _label, _gui) in enumerate(D.CE_ITEM_CATS):
        eq = c.fn("EqualEqual_IntInt", KML, {"A": c.var("CeCatKind", "int", (x + 300 * k, y + 900)),
                                             "B": (str(k), "int")}, (x + 300 * k, y + 800))
        c.color("CeCatTab_" + key, eq, CHIP_ON, CHIP_OFF, (x + 300 * k, y))


def _select(c, state_src, pos):
    """CeSelState = state; ask the server for their data; clear any confirm."""
    x, y = pos
    c.set_var("CeSelState", "object", state_src, (x, y), sub=ir.obj_path(PSTATE))
    c.set_var("CeConfirmKind", "int", "0", (x + 300, y))
    c.set_var("CePending", "bool", "false", (x + 600, y))
    c.set_var("CeMsg", "string", "Loading the player's values...", (x + 900, y))
    c.set_var("CeInvSel", "int", "-1", (x + 900, y + 150))
    c.call_relay("OwlServerCeGet", {"State": c.var("CeSelState", "object", (x + 1000, y + 300),
                                                    sub=ir.obj_path(PSTATE))}, (x + 1200, y))


# ================================================================ clicks
def clicks(g, u, relay_cls, owning_player, y=30000):
    c = _Ctx(g, u, relay_cls, owning_player)
    ready = lambda pos: c.fn("IsValid", KSL, {"Object": c.relay((pos[0] - 200, pos[1]))}, pos)
    # player rows
    for i in range(CEP_ROWS):
        yi = y + 400 * i
        c.exits = [(clicked(g, "CeP%d" % i, (0, yi)), "then")]
        b = c.branch(ready((300, yi + 200)), (300, yi))
        c.exits = [(b, "then")]
        st = g.array_get(c.rvar("CeStates", "object", (500, yi + 250), arr=True, sub=ir.obj_path(PSTATE))[0],
                         "CeStates", i, (700, yi + 250), elem_cat="object", elem_sub=ir.obj_path(PSTATE))
        _select(c, (st, "Output"), (700, yi))
    y += 400 * CEP_ROWS
    # sub-tabs
    for k, (key, _label) in enumerate(D.CE_TABS):
        c.exits = [(clicked(g, "CeTab_" + key, (0, y + 300 * k)), "then")]
        sai = g.call("SetActiveWidgetIndex", SWITCHER, pos=(300, y + 300 * k))
        g.typed_input(sai, "Index", str(k), "int")
        w = c.widget("CeTabs", SWITCHER, (100, y + 300 * k + 150))
        g.wire(w[0], w[1], sai, "self", exec=False)
        c.go(sai)
        c.set_var("CeConfirmKind", "int", "0", (600, y + 300 * k))
    y += 300 * len(D.CE_TABS)
    # steppers
    for j, (mine, _src, lim, key) in enumerate(STEPPERS):
        for d, (suffix, delta) in enumerate((("Dec", "-1"), ("Inc", "1"))):
            yj = y + 600 * j + 300 * d
            c.exits = [(clicked(g, key + suffix, (0, yj)), "then")]
            add = c.fn("Add_IntInt", KML, {"A": c.var(mine, "int", (200, yj + 200)), "B": (delta, "int")}, (400, yj + 200))
            cl = c.fn("Clamp", KML, {"Value": add, "Min": (str(lim[0]), "int"), "Max": (str(lim[1]), "int")},
                      (600, yj + 200))
            c.set_var(mine, "int", cl, (800, yj))
            c.set_var("CeDirty", "bool", "true", (1100, yj))
    y += 600 * len(STEPPERS)
    # Refund / Reset ask first; Cancel; Confirm
    for k, (btn, kind) in enumerate((("CeRefund", "1"), ("CeReset", "2"), ("CeCancel", "0"))):
        c.exits = [(clicked(g, btn, (0, y + 300 * k)), "then")]
        c.set_var("CeConfirmKind", "int", kind, (300, y + 300 * k))
    y += 1000
    selected = lambda pos: c.var("CeSelState", "object", pos, sub=ir.obj_path(PSTATE))
    ok = lambda pos: c.fn("BooleanAND", KML, {"A": ready((pos[0], pos[1] + 150)),
                                              "B": c.fn("IsValid", KSL, {"Object": selected((pos[0] - 200, pos[1] + 300))},
                                                        (pos[0], pos[1] + 300))}, pos)
    c.exits = [(clicked(g, "CeConfirm", (0, y)), "then")]
    b = c.branch(ok((300, y + 300)), (300, y))
    c.exits = [(b, "then")]
    br = c.branch(c.fn("EqualEqual_IntInt", KML, {"A": c.var("CeConfirmKind", "int", (500, y + 450)), "B": ("1", "int")},
                       (700, y + 450)), (700, y))
    c.exits = [(br, "then")]
    c.call_relay("OwlServerCeRefund", {"State": selected((900, y + 300))}, (1000, y))
    ends = c.exits
    c.exits = [(br, "else")]
    c.call_relay("OwlServerCeReset", {"State": selected((900, y + 600))}, (1000, y + 400))
    c.exits += ends
    _sent(c, (1400, y))
    y += 1200
    # Apply: the Currency values on the Currency tab, else the Stats values
    c.exits = [(clicked(g, "CeApply", (0, y)), "then")]
    b = c.branch(ok((300, y + 300)), (300, y))
    c.exits = [(b, "then")]
    ti = c.fn("GetActiveWidgetIndex", SWITCHER, {"self": c.widget("CeTabs", SWITCHER, (300, y + 600))}, (500, y + 600))
    bt = c.branch(c.fn("EqualEqual_IntInt", KML, {"A": ti, "B": (str(CUR_TAB), "int")}, (700, y + 600)), (700, y))
    c.exits = [(bt, "else")]
    ins = {"State": selected((800, y + 300)), "Level": c.var("CeEdLevel", "int", (800, y + 450)),
           "Points": c.var("CeEdPoints", "int", (800, y + 600))}
    for k in range(len(D.CE_ATTRS)):
        ins["A%d" % k] = c.var("CeEdA%d" % k, "int", (800, y + 750 + 150 * k))
    c.call_relay("OwlServerCeApply", ins, (1000, y))
    c.set_var("CeDirty", "bool", "false", (1300, y))
    ends = c.exits
    # Currency: the wallet (only if it changed: each set is a log line), then the trade settings
    c.exits = [(bt, "then")]
    yc = y + 2000
    bw = c.branch(c.fn("NotEqual_IntInt", KML, {"A": c.var("CeEdWallet", "int", (800, yc + 300)),
                                                "B": c.rvar("CeWallet", "int", (800, yc + 450))}, (1000, yc + 300)),
                  (1000, yc))
    c.exits = [(bw, "then")]
    c.call_relay("OwlServerCeWallet", {"State": selected((1100, yc + 300)),
                                       "Balance": c.var("CeEdWallet", "int", (1100, yc + 450))}, (1300, yc))
    c.exits += [(bw, "else")]
    eco = c.g.call("OwlServerCeEconomy", c.RELAY, pos=(1700, yc))
    g.typed_input(eco, "Store", "true", "bool")
    r = c.relay((1500, yc + 250))
    g.wire(r[0], r[1], eco, "self", exec=False)
    for k, (p, v) in enumerate((("CurOn", c.arr("CeEdCurOn", "int", (1500, yc + 400))),
                                ("SellQ", c.var("CeEdSellQ", "int", (1500, yc + 550))),
                                ("BuyQ", c.var("CeEdBuyQ", "int", (1500, yc + 700))))):
        g.wire(v[0], v[1], eco, p, exec=False)
    c.go(eco)
    c.set_var("CeCurDirty", "bool", "false", (2000, yc))
    c.exits += ends
    _sent(c, (2300, y))
    _item_clicks(c, ok, selected, y + 4000)
    _currency_clicks(c, y + 12000)


def _currency_clicks(c, y):
    g = c.g

    def change(btn, var, value, pos):
        """btn click -> var = value ((node, pin)); CeCurDirty."""
        c.exits = [(clicked(g, btn, pos), "then")]
        c.set_var(var, "int", value(pos), (pos[0] + 600, pos[1]))
        c.set_var("CeCurDirty", "bool", "true", (pos[0] + 900, pos[1]))

    def step(var, delta, lim):
        return lambda pos: c.fn("Clamp", KML, {
            "Value": c.fn("Add_IntInt", KML, {"A": c.var(var, "int", (pos[0] + 100, pos[1] + 200)),
                                              "B": (str(delta), "int")}, (pos[0] + 300, pos[1] + 200)),
            "Min": (str(lim[0]), "int"), "Max": (str(lim[1]), "int")}, (pos[0] + 500, pos[1] + 200))

    wal = (0, D.CE_WALLET_MAX)
    for btn, var, value in (("CeBalDec", "CeEdWallet", step("CeEdWallet", -CE_WALLET_STEP, wal)),
                            ("CeBalInc", "CeEdWallet", step("CeEdWallet", CE_WALLET_STEP, wal)),
                            ("CeBalGrant", "CeEdWallet", step("CeEdWallet", CE_WALLET_GRANT, wal)),
                            ("CeSellDec", "CeEdSellQ", step("CeEdSellQ", -1, D.CE_SELL_Q)),
                            ("CeSellInc", "CeEdSellQ", step("CeEdSellQ", 1, D.CE_SELL_Q)),
                            ("CeBuyDec", "CeEdBuyQ", step("CeEdBuyQ", -1, D.CE_BUY_Q)),
                            ("CeBuyInc", "CeEdBuyQ", step("CeEdBuyQ", 1, D.CE_BUY_Q))):
        change(btn, var, value, (0, y))
        y += 400
    # Clear wallet: 0 (a pasted literal 0 is the pin's default, so it sticks)
    c.exits = [(clicked(g, "CeBalClear", (0, y)), "then")]
    c.set_var("CeEdWallet", "int", "0", (600, y))
    c.set_var("CeCurDirty", "bool", "true", (900, y))
    y += 400
    # currency toggles: CeEdCurOn[k] = 1 - CeEdCurOn[k]
    for k in range(len(D.CE_CURRENCIES)):
        c.exits = [(clicked(g, "CeCur%dBtn" % k, (0, y)), "then")]
        cur = c.at(c.arr("CeEdCurOn", "int", (100, y + 300)), k, "int", (300, y + 300))
        flip = c.fn("Subtract_IntInt", KML, {"A": ("1", "int"), "B": cur}, (500, y + 300))
        st = g.array_fn("Array_Set", pos=(700, y), elem_cat="int")
        g.array_item_pin(st, "Item", "int")
        a = c.arr("CeEdCurOn", "int", (500, y + 450))
        g.wire(a[0], a[1], st, "TargetArray", exec=False)
        if k:
            g.typed_input(st, "Index", str(k), "int")
        g.wire(flip[0], flip[1], st, "Item", exec=False)
        c.go(st)
        c.set_var("CeCurDirty", "bool", "true", (1000, y))
        y += 400


def _item_clicks(c, ok, selected, y):
    g = c.g
    # chips: Inventory (CE_INVS) and Item catalog (CE_ITEM_CATS)
    for grp, kvar, flag, keys in (("CeInvTab_", "CeInvKind", "CeInvDirty", [k for k, _l in D.CE_INVS]),
                                  ("CeCatTab_", "CeCatKind", "CeCatDirty", [k for k, _l, _g in D.CE_ITEM_CATS])):
        for k, key in enumerate(keys):
            c.exits = [(clicked(g, grp + key, (0, y)), "then")]
            c.set_var(kvar, "int", str(k), (300, y))
            c.set_var(flag, "bool", "true", (600, y))
            y += 300
    # quantity steppers (both bars share CeEdQty)
    for bar in ("CeInvBar", "CeCatBar"):
        for suffix, _glyph, delta, _w, _px in QTY_STEPS:
            c.exits = [(clicked(g, bar + "Q" + suffix, (0, y)), "then")]
            add = c.fn("Add_IntInt", KML, {"A": c.var("CeEdQty", "int", (200, y + 200)), "B": (str(delta), "int")},
                       (400, y + 200))
            c.set_var("CeEdQty", "int", c.fn("Clamp", KML, {"Value": add, "Min": (str(D.CE_QTY[0]), "int"),
                                                           "Max": (str(D.CE_QTY[1]), "int")}, (600, y + 200)), (800, y))
            y += 300
    y += 300

    def pick_first(pos):
        c.set_var("CeMsg", "string", "Pick an item first.", pos)

    # Inventory: Remove (the picked stack's slot) / Grant more (its item), CeEdQty of it
    for btn, event in (("CeInvRemove", "OwlServerCeRemove"), ("CeInvGrant", "OwlServerCeGrant")):
        c.exits = [(clicked(g, btn, (0, y)), "then")]
        p = c.find(c.rvar("CeInvSlots", "int", (100, y + 600), arr=True), c.var("CeInvSel", "int", (100, y + 750)),
                   "int", (300, y + 600))
        b = c.branch(c.fn("BooleanAND", KML, {"A": ok((300, y + 300)),
                                              "B": c.fn("GreaterEqual_IntInt", KML, {"A": p, "B": ("0", "int")},
                                                        (500, y + 600))}, (600, y + 300)), (600, y))
        c.exits = [(b, "then")]
        ins = {"State": selected((700, y + 300)), "Qty": c.var("CeEdQty", "int", (700, y + 450))}
        if event == "OwlServerCeRemove":
            ins["Slot"] = c.var("CeInvSel", "int", (700, y + 600))
        else:
            ins["TemplateId"] = c.at(c.rvar("CeInvIds", "int", (700, y + 750), arr=True), p, "int", (900, y + 750))
        c.call_relay(event, ins, (1000, y))
        _sent(c, (1300, y))
        ends = c.exits
        c.exits = [(b, "else")]
        pick_first((1000, y + 400))
        c.exits += ends
        y += 1200
    # Item catalog: Grant to <player>
    c.exits = [(clicked(g, "CeCatGrant", (0, y)), "then")]
    cs = lambda pos: c.var("CeCatSel", "int", pos)
    b = c.branch(c.fn("BooleanAND", KML, {"A": ok((300, y + 300)),
                                          "B": c.fn("GreaterEqual_IntInt", KML, {"A": cs((300, y + 600)), "B": ("0", "int")},
                                                    (500, y + 600))}, (600, y + 300)), (600, y))
    c.exits = [(b, "then")]
    c.call_relay("OwlServerCeGrant", {"State": selected((700, y + 300)), "Qty": c.var("CeEdQty", "int", (700, y + 450)),
                                      "TemplateId": c.at(c.arr("CeCatIds", "int", (700, y + 600)), cs((700, y + 750)),
                                                         "int", (900, y + 600))}, (1000, y))
    _sent(c, (1300, y))
    ends = c.exits
    c.exits = [(b, "else")]
    pick_first((1000, y + 400))
    c.exits += ends
    y += 1200

    # OwlCePick(Index, Kind), called by a grid cell (12): Kind 0 = the Inventory grid (Index into
    # the relay's CeInv* arrays), 1 = the Item catalog (Index into CeCat*)
    ev = g.custom_event("OwlCePick", pos=(0, y))
    for pin in ("Index", "Kind"):
        ev.set('CustomProperties UserDefinedPin (PinName="%s",PinType=(PinCategory="int"),'
               'DesiredPinDirection=EGPD_Output)' % pin)
    c.exits = [(ev, "then")]
    b = c.branch(c.fn("EqualEqual_IntInt", KML, {"A": (ev, "Kind"), "B": ("0", "int")}, (300, y + 300)), (300, y))
    c.exits = [(b, "then")]
    c.set_var("CeInvSel", "int", c.at(c.rvar("CeInvSlots", "int", (400, y + 450), arr=True), (ev, "Index"), "int",
                                      (600, y + 450)), (600, y))
    c.set_var("CeInvDirty", "bool", "true", (900, y))
    c.exits = [(b, "else")]
    c.set_var("CeCatSel", "int", (ev, "Index"), (600, y + 700))
    c.set_var("CeCatDirty", "bool", "true", (900, y + 700))


def _sent(c, pos):
    c.set_var("CeConfirmKind", "int", "0", pos)
    c.set_var("CePending", "bool", "true", (pos[0] + 300, pos[1]))
    c.set_var("CeMsg", "string", "Sending to the server...", (pos[0] + 600, pos[1]))
