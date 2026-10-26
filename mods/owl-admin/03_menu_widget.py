"""owl-admin step 03: WBP_OwlAdminMenu -- the design canvas's Admin Restrictions Menu board
as a real, clickable UMG menu behind the Owl Admin login (settings not applied yet).

Layout (board px x1.5; frame from menu_shell): header (OWL ADMIN, PREVIEW badge, Lock,
Close) | Gate (WidgetSwitcher):
    0  LoginPage -- the Admin Login board: password box + Unlock (its form was never drawn on
       the canvas, so it uses the board's .field / .btn.primary styles)
    1  Body      -- sidebar of 14 tabs | one scrolling page per tab: a row per setting
                    (CheckBox or SpinBox + unit) and a placeholder card per special panel
    2  SetupPage -- first-time "set admin password" form, while the server has no password
| footer (status, Reset, Apply -- not wired yet).

Parent class: Conan's WindowRoot, so the menu is a GUIModule window (row OwlAdminMenu, 06)
and Conan's GUIModuleController owns its cursor, input, Esc and the Shift+U toggle.

Graph:
    TabBtn_<tab>.OnClicked -> TabPages.SetActiveWidgetIndex(i)
    CloseBtn.OnClicked     -> ToggleModule(OwlAdminMenu)
    UnlockBtn.OnClicked    -> run "dc OwlLogin <PasswordBox text>" as the owning player (the
                              server checks it, 04); clear the box
    SetPwBtn.OnClicked     -> run "dc OwlSetPassword <SetupBox text>" (Conan admins only); clear
    LockBtn.OnClicked      -> run "dc OwlLogout"
    Tick                   -> tab highlight; Gate = 1 if the owning player's PlayerState is in
                              BP_OwlAdminController.UnlockedPlayers (replicated from the
                              server), else 0 if its PasswordIsSet (replicated), else 2. The
                              client only READS both, so showing the settings can't be faked
                              by the client changing them.

Run with Play STOPPED, after 02:  python ue_run.py mods/owl-admin/03_menu_widget.py
"""
import sys
for _m in list(sys.modules):
    if _m == "bpkit" or _m.startswith("bpkit."):
        sys.modules.pop(_m, None)
import unreal
import os
from bpkit import bridge as bp, ir, build, config as _cfg
sys.path.insert(0, os.path.join(_cfg.REPO_ROOT, "mods", "owl-admin"))
for _m in ("oa_config", "umg_text", "menu_defs", "menu_shell"):
    sys.modules.pop(_m, None)
import oa_config as MOD
import menu_defs as D
from umg_text import Umg
from menu_shell import Shell, button, button_style, framed, clicked, SWITCHER

eal = unreal.EditorAssetLibrary
assert not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor(), \
    "Play-in-Editor is running -- stop Play first"

PKG = MOD.resolve_pkg()
PATH = "%s/%s" % (PKG, MOD.MENU_WBP)
FULL = MOD.full(PKG, MOD.MENU_WBP)
CTRL_CLS = MOD.full(PKG, MOD.CONTROLLER) + "_C"
assert unreal.load_object(None, CTRL_CLS), "run 02_controller.py first: no " + CTRL_CLS

u = Umg(MOD.BOARD_SCALE)
B, R = MOD.FONT_BOLD, MOD.FONT_REGULAR
s = Shell(u, "RESTRICTIONS · PRIVATE REALM", D.TABS, MOD.MENU_MODULE, (B, R), badge="PREVIEW",
          side_note="Preview: these settings are not applied to the game yet.",
          status="Preview build: these settings are not applied to the game yet.")

s.header(extra=[("LockBtn", "LOCK")])
s.sidebar()


def setting_rows(tab):
    items = []
    for st in [x for x in D.SETTINGS if x["tab"] == tab]:
        r = "R_" + st["id"]
        u.text(r + "_Lbl", st["label"], B, 20, "#ffffff", variable=False)
        u.text(r + "_Desc", st["desc"], R, 16, "#b8a29c", wrap=True, variable=False)
        u.box("VerticalBox", r + "_Txt", [(r + "_Lbl", []), (r + "_Desc", ["Padding=%s" % u.margin(t=3)])])
        ctl = "Set_" + st["id"]
        if st["type"] == "toggle":
            u.widget("/Script/UMG.CheckBox", ctl, [
                "CheckedState=%s" % ("Checked" if st["default"] else "Unchecked"),
                "WidgetStyle=(UncheckedImage=%s,UncheckedHoveredImage=%s,UncheckedPressedImage=%s,"
                "CheckedImage=%s,CheckedHoveredImage=%s,CheckedPressedImage=%s,"
                "BackgroundImage=(DrawAs=NoDrawType),BackgroundHoveredImage=(DrawAs=NoDrawType),"
                "BackgroundPressedImage=(DrawAs=NoDrawType),Padding=%s)" % (
                    u.brush("#1a0c0c", w=76, h=44), u.brush("#3a0b0e", w=76, h=44), u.brush("#5a1a1e", w=76, h=44),
                    u.brush("#b3121a", w=76, h=44), u.brush("#d01a22", w=76, h=44), u.brush("#ff4a50", w=76, h=44),
                    u.margin()),
                "IsFocusable=False"], variable=True)
            # 1px outline so an OFF toggle (#1a0c0c) still reads against the row fill (#120909)
            control = u.border(r + "_TglFrame", "#5a1a1e", 1.0, u.margin(1, 1, 1, 1), ctl,
                               halign="HAlign_Center", valign="VAlign_Center")
        else:
            frac = 1 if st["step"] < 1 else 0
            u.widget("/Script/UMG.SpinBox", ctl, [
                "Value=%.6f" % st["default"],
                "MinValue=%.6f" % st["min"], "MaxValue=%.6f" % st["max"],
                "MinSliderValue=%.6f" % st["min"], "MaxSliderValue=%.6f" % st["max"],
                "bOverride_MinValue=True", "bOverride_MaxValue=True",
                "bOverride_MinSliderValue=True", "bOverride_MaxSliderValue=True",
                "Delta=%.6f" % st["step"], "bAlwaysUsesDeltaSnap=True",
                "MinFractionalDigits=%d" % frac, "MaxFractionalDigits=%d" % frac,
                "Font=%s" % u.font(B, 24),
                "Justification=Center",
                # no fill bar (it drew value-within-range as a dark slab) and no drag-arrows glyph:
                # a flat box like the board's value field; hover lightens it to show it's draggable
                "WidgetStyle=(BackgroundBrush=%s,HoveredBackgroundBrush=%s,"
                "ActiveFillBrush=(DrawAs=NoDrawType,ResourceObject=None),"
                "InactiveFillBrush=(DrawAs=NoDrawType,ResourceObject=None),"
                "ArrowsImage=(DrawAs=NoDrawType,ResourceObject=None),"
                "ForegroundColor=(SpecifiedColor=%s),TextPadding=%s)" % (
                    u.brush("#1a0c0c"), u.brush("#3a0b0e"), u.lin("#ff5a5f"), u.margin(8, 4, 8, 4)),
                "ForegroundColor=(SpecifiedColor=%s)" % u.lin("#ff5a5f"),
            ], variable=True)
            u.sized(r + "_Size", ctl, w=160, h=44)
            unit = {"x": "×"}.get(st["unit"], st["unit"])
            u.text(r + "_Unit", unit, B, 20, "#ff5a5f", variable=False)
            control = u.box("HorizontalBox", r + "_Ctl", [
                (r + "_Size", ["VerticalAlignment=VAlign_Center"]),
                (r + "_Unit", ["Padding=%s" % u.margin(l=8), "VerticalAlignment=VAlign_Center"]),
            ])
            control = u.sized(r + "_CtlBox", control, w=200, halign="HAlign_Left")
        u.box("HorizontalBox", r + "_In", [
            (r + "_Txt", ["Size=(SizeRule=Fill)", "VerticalAlignment=VAlign_Center"]),
            (control, ["Padding=%s" % u.margin(l=24), "VerticalAlignment=VAlign_Center"]),
        ])
        u.border(r + "_Fill", "#120909", 1.0, u.margin(20, 14, 20, 14), r + "_In")
        u.strip(r + "_Acc", "#4a1a1d", u.margin(l=3))
        u.box("HorizontalBox", r + "_Row", [(r + "_Acc", ["VerticalAlignment=VAlign_Fill"]),
                                             (r + "_Fill", ["Size=(SizeRule=Fill)", "VerticalAlignment=VAlign_Fill"])])
        u.border(r, "#2a1012", 1.0, u.margin(1, 1, 1, 1), r + "_Row")
        items.append((r, ["Padding=%s" % u.margin(b=10)]))
    for i, panel in enumerate(D.PANELS.get(tab, [])):
        p = s.placeholder("Ph_%s_%d" % (tab, i), "%s: coming in a later step." % panel)
        items.append((p, ["Padding=%s" % u.margin(t=6, b=10)]))
    return items


body = s.pages(setting_rows)


def form_page(page, title, hint, box, hidden, btn, label, note, placeholder="Password"):
    """A centred one-field form (the Admin Login board's .field + .btn.primary styles)."""
    u.text(page + "Title", title, B, 30, "#ffffff", spacing_px=4, variable=False)
    u.text(page + "Hint", hint, R, 18, "#b8a29c", wrap=True, variable=False)
    u.widget("/Script/UMG.EditableTextBox", box, [
        'HintText=INVTEXT("%s")' % placeholder,
        "IsPassword=%s" % hidden,
        "WidgetStyle=(BackgroundImageNormal=%s,BackgroundImageHovered=%s,BackgroundImageFocused=%s,"
        "Padding=%s,ForegroundColor=(SpecifiedColor=%s),"
        "TextStyle=(Font=%s,ColorAndOpacity=(SpecifiedColor=%s)))" % (
            u.brush("#120909"), u.brush("#1a0c0c"), u.brush("#1a0c0c"), u.margin(16, 0, 16, 0), u.lin("#f2e6e2"),
            u.font(R, 22, spacing_px=3), u.lin("#f2e6e2")),
    ], variable=True)
    framed(u, box + "Frame", "#4a1a1d", "#120909", box, u.margin())
    u.sized(box + "Size", box + "Frame", h=52)
    u.text(btn + "Text", label, B, 20, "#ffffff", spacing_px=2, variable=False)
    button(u, btn, btn + "Text", u.margin(), button_style(u, "#b3121a", "#d01a22", "#8a2a2e"))
    u.sized(btn + "Size", btn, h=52)
    u.text(page + "Note", note, R, 15, "#a8908a", wrap=True, variable=False)
    u.box("VerticalBox", page + "Form", [
        (page + "Title", ["HorizontalAlignment=HAlign_Center"]),
        (page + "Hint", ["Padding=%s" % u.margin(t=8, b=24), "HorizontalAlignment=HAlign_Center"]),
        (box + "Size", ["Padding=%s" % u.margin(b=12), "HorizontalAlignment=HAlign_Fill"]),
        (btn + "Size", ["Padding=%s" % u.margin(b=20), "HorizontalAlignment=HAlign_Fill"]),
        (page + "Note", ["HorizontalAlignment=HAlign_Fill"]),
    ])
    u.sized(page + "Wrap", page + "Form", w=420, halign="HAlign_Center", valign="VAlign_Center")
    return u.border(page + "Page", "#0b0505", 1.0, u.margin(), page + "Wrap",
                    halign="HAlign_Center", valign="VAlign_Center")


# Gate 0: login. Gate 2: first-time setup, shown while the server reports no password (PasswordIsSet).
login = form_page("Login", "ADMIN LOGIN", "Enter the Owl Admin password to unlock admin mode.",
                  "PasswordBox", True, "UnlockBtn", "UNLOCK",
                  "The server checks the password. Forgot it? A Conan admin can set a new one in the console: "
                  "dc OwlSetPassword <password>")
setup = form_page("Setup", "SET ADMIN PASSWORD",
                  "No Owl Admin password is set yet. Choose one: one word, capitals matter.",
                  "SetupBox", False, "SetPwBtn", "SET PASSWORD",
                  "Only a Conan server admin can set it (single player counts as admin). "
                  "You're unlocked straight away; everyone else logs in with it.", placeholder="New password")
u.widget(SWITCHER, "Gate", ["ActiveWidgetIndex=0"],
         [("/Script/UMG.WidgetSwitcherSlot", w, ["HorizontalAlignment=HAlign_Fill", "VerticalAlignment=VAlign_Fill"])
          for w in (login, body, setup)], variable=True)

s.footer(buttons=[("ResetBtn", "RESET", False), ("ApplyBtn", "APPLY RESTRICTIONS", True)])
s.root("Gate")
wbp, wbp_ptr = s.paste(unreal, eal, bp, PKG, MOD.MENU_WBP, FULL)

# ================================================================ graph
GS = "/Script/Engine.GameplayStatics"
KSL = "/Script/Engine.KismetSystemLibrary"
KML = "/Script/Engine.KismetMathLibrary"
KSTR = "/Script/Engine.KismetStringLibrary"
KTXT = "/Script/Engine.KismetTextLibrary"
UW = "/Script/UMG.UserWidget"
ETB = "/Script/UMG.EditableTextBox"
PSTATE = "/Script/Engine.PlayerState"
g = ir.Graph("EventGraph")
s.graph(g)


def owning_player(pos):
    return g.call("GetOwningPlayer", UW, pos=pos)


def run_command(prev, prev_pin, command_node_pin, pos):
    """ExecuteConsoleCommand(<command>) as the owning player. command_node_pin: (node, pin) or a literal."""
    ex = g.call("ExecuteConsoleCommand", KSL, pos=pos)
    if isinstance(command_node_pin, str):
        g.typed_input(ex, "Command", command_node_pin, "string")
    else:
        g.wire(command_node_pin[0], command_node_pin[1], ex, "Command", exec=False)
    g.wire(owning_player((pos[0] - 250, pos[1] + 200)), "ReturnValue", ex, "SpecificPlayer", exec=False)
    g.wire(prev, prev_pin, ex, "execute")
    return ex


def submit_box(btn, box, command, y):
    """<btn> click -> run "<command> <box text>" as the owning player, then clear the box."""
    ev = clicked(g, btn, (0, y))
    gt = g.call("GetText", ETB, pos=(250, y + 200))
    g.wire(g.var_get(box, "object", ir.obj_path(ETB), pos=(0, y + 200)), box, gt, "self", exec=False)
    ts = g.call("Conv_TextToString", KTXT, pos=(500, y + 200))
    g.wire(gt, "ReturnValue", ts, "InText", exec=False)
    cat = g.call("Concat_StrStr", KSTR, pos=(750, y + 200))
    g.typed_input(cat, "A", command + " ", "string")
    g.wire(ts, "ReturnValue", cat, "B", exec=False)
    ex = run_command(ev, "then", (cat, "ReturnValue"), (1000, y))
    clr = g.call("SetText", ETB, pos=(1300, y))
    g.wire(g.var_get(box, "object", ir.obj_path(ETB), pos=(1100, y + 200)), box, clr, "self", exec=False)
    g.wire(ex, "then", clr, "execute")


# Unlock: the server checks the password. Set password: the server saves it (Conan admins only).
submit_box("UnlockBtn", "PasswordBox", "dc OwlLogin", 5200)
submit_box("SetPwBtn", "SetupBox", "dc OwlSetPassword", 6200)

# Lock: "dc OwlLogout"
lev = clicked(g, "LockBtn", (0, 5800))
run_command(lev, "then", "dc OwlLogout", (400, 5800))

# Tick: tab highlight, then the login gate
tick = g.event("Tick", parent=UW, pos=(0, 3800))
last = s.tick_highlight(g, tick)
gac = g.call("GetActorOfClass", GS, pos=(5500, 3800))
ap = gac.pin("ActorClass").typed("class", ir.obj_path("/Script/Engine.Actor"), direction="EGPD_Input")
ap.set("PinType.bIsUObjectWrapper", "True")
ap.set("DefaultObject", '"%s"' % CTRL_CLS)
g.wire(last, "then", gac, "execute")
# GetActorOfClass already returns the controller's type (a cast is flagged as redundant)
gac.pin("ReturnValue").typed("object", ir.obj_path(CTRL_CLS), direction="EGPD_Output")
valid = g.call("IsValid", KSL, pos=(5800, 4000))
g.wire(gac, "ReturnValue", valid, "Object", exec=False)
found = g.branch(pos=(5800, 3800))
g.wire(gac, "then", found, "execute")
g.wire(valid, "ReturnValue", found, "Condition", exec=False)
arr = g.array_var("UnlockedPlayers", pos=(5800, 4100), elem_cat="object", elem_sub=ir.obj_path(PSTATE),
                  parent=CTRL_CLS)
g.wire(gac, "ReturnValue", arr, "self", exec=False)
ps = g.var_get("PlayerState", "object", ir.obj_path(PSTATE), parent="/Script/Engine.Controller", pos=(5800, 4300))
g.wire(owning_player((5550, 4300)), "ReturnValue", ps, "self", exec=False)
has = g.array_fn("Array_Contains", pos=(6100, 4100), elem_cat="object", elem_sub=ir.obj_path(PSTATE))
g.array_item_pin(has, "ItemToFind", "object", ir.obj_path(PSTATE))
g.wire(arr, "UnlockedPlayers", has, "TargetArray", exec=False)
g.wire(ps, "PlayerState", has, "ItemToFind", exec=False)
# unlocked -> 1 (settings); else password set -> 0 (login); else 2 (first-time setup)
pwset = g.var_get("PasswordIsSet", "bool", parent=CTRL_CLS, pos=(6100, 4400))
g.wire(gac, "ReturnValue", pwset, "self", exec=False)
locked = g.call("SelectInt", KML, pos=(6400, 4400))
g.typed_input(locked, "A", "0", "int")
g.typed_input(locked, "B", "2", "int")
g.wire(pwset, "PasswordIsSet", locked, "bPickA", exec=False)
pick = g.call("SelectInt", KML, pos=(6400, 4100))
g.typed_input(pick, "A", "1", "int")
g.wire(locked, "ReturnValue", pick, "B", exec=False)
g.wire(has, "ReturnValue", pick, "bPickA", exec=False)
for i, (pin, idx) in enumerate((("then", None), ("else", "0"))):
    sai = g.call("SetActiveWidgetIndex", SWITCHER, pos=(6700, 3800 + i * 300))
    g.wire(g.var_get("Gate", "object", ir.obj_path(SWITCHER), pos=(6500, 3700 + i * 300)), "Gate", sai, "self",
           exec=False)
    if idx is None:
        g.wire(pick, "ReturnValue", sai, "Index", exec=False)
    else:
        g.typed_input(sai, "Index", idx, "int")
    g.wire(found, pin, sai, "execute")

rep = build.build_graph(FULL, g)
assert rep["ok"], "menu graph not clean: %r" % {k: rep[k] for k in ("dropped_nodes", "dropped_links", "orphans", "wildcards", "errors")}

# ================================================================ verify
gen = unreal.load_object(None, FULL + "_C")
assert gen, "no generated class"
assert bp.root_widget(wbp_ptr) == s.root_ptr, "root changed during compile"
pw = bp.export_widgets([bp.find_object("PasswordBox", outer=bp.widget_tree(wbp_ptr))])
assert "IsPassword=True" in pw, "PasswordBox lost IsPassword:\n" + pw
spin = bp.export_widgets([bp.find_object("Set_cap", outer=bp.widget_tree(wbp_ptr))])
print("SpinBox readback (Set_cap):", [l.strip() for l in spin.splitlines()
                                      if any(k in l for k in ("Value=", "Delta="))][:2])
assert eal.save_asset(PATH), "save failed"
print("BUILD OK: owl-admin v%d -> %s  (%d widgets, %d tabs, %d settings, login gate)%s" % (
    MOD.VERSION, FULL, len(u.cls), len(D.TABS), len(D.SETTINGS),
    "  [DRY RUN -- not shippable]" if PKG != MOD.OUTPUT_PKG else ""))
