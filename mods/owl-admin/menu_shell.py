"""The frame both owl-admin menus share (admin: 03, player: 07), from the Admin Restrictions
Menu board: header (brand, badge, extra buttons, Close), a sidebar of tab buttons, a
WidgetSwitcher of pages, a footer, and the matching graph (tab clicks, Close, active-tab
highlight). Each menu supplies its own page content.

    s = Shell(u, "PLAYER MENU · PRIVATE REALM", tabs, module="OwlPlayerMenu", ...)
    s.header(); s.sidebar(); s.pages(lambda tab: [(widget, [slot props]), ...]); s.footer()
    s.root("Body")                          # or a widget that wraps Body (the admin login gate)
    wbp, wbp_ptr = s.paste(eal, bp, pkg, name, full)
    g = ir.Graph("EventGraph"); s.graph(g); last = s.tick_highlight(g, tick)
"""
from bpkit import ir

CANVAS, BUTTON, SWITCHER = "/Script/UMG.CanvasPanel", "/Script/UMG.Button", "/Script/UMG.WidgetSwitcher"
GUIMC = "/Script/ConanSandbox.GUIModuleController"
KML = "/Script/Engine.KismetMathLibrary"
LCOLOR = ir.struct_path("/Script/CoreUObject.LinearColor")
TAB_ACTIVE, TAB_IDLE = "#3a0b0e", "#0b0606"


def button_style(u, normal, hovered, pressed):
    return ("WidgetStyle=(Normal=%s,Hovered=%s,Pressed=%s,NormalPadding=%s,PressedPadding=%s)"
            % (u.brush(normal), u.brush(hovered), u.brush(pressed), u.margin(), u.margin()))


def button(u, name, label_name, pad, style, halign="HAlign_Center"):
    return u.widget(BUTTON, name, [style, "BackgroundColor=(R=1.000000,G=1.000000,B=1.000000,A=1.000000)",
                                   "IsFocusable=False"],
                    [("/Script/UMG.ButtonSlot", label_name,
                      ["Padding=%s" % pad, "HorizontalAlignment=%s" % halign, "VerticalAlignment=VAlign_Center"])],
                    variable=True)


def framed(u, name, outline, fill, child, pad, line=1, alpha=1.0):
    """1px outline Border around a fill Border (the board's border:1px + background)."""
    u.border(name + "Fill", fill, alpha, pad, child)
    return u.border(name, outline, 1.0, u.margin(line, line, line, line), name + "Fill")


def scroll_style(u, thickness):
    return ["WidgetBarStyle=(NormalThumbImage=%s,HoveredThumbImage=%s,DraggedThumbImage=%s)" % (
        u.brush("#5a1a1e"), u.brush("#8a2a2e"), u.brush("#b3121a")),
        "ScrollbarThickness=(X=%.6f,Y=%.6f)" % (thickness, thickness)]


def clicked(g, btn, pos):
    """K2Node_ComponentBoundEvent for <btn>.OnClicked (format of shipped W_ServerInfo)."""
    n = g.node("K2Node_ComponentBoundEvent", [
        'DelegatePropertyName="OnClicked"',
        "DelegateOwnerClass=\"/Script/CoreUObject.Class'/Script/UMG.Button'\"",
        'ComponentPropertyName="%s"' % btn,
        "EventReference=(MemberParent=\"/Script/CoreUObject.Package'/Script/UMG'\","
        "MemberName=\"OnButtonClickedEvent__DelegateSignature\")",
        "bInternalEvent=True",
        'CustomFunctionName="BndEvt__%s_OnClicked"' % btn,
    ], base="ComponentBoundEvent", pos=pos)
    n.pin("then").typed("exec", direction="EGPD_Output")
    return n


class Shell:
    def __init__(self, u, subtitle, tabs, module, fonts, badge="PREVIEW", side_note=None, status=""):
        self.u, self.subtitle, self.tabs, self.module = u, subtitle, tabs, module
        self.B, self.R = fonts
        self.badge, self.side_note, self.status = badge, side_note, status

    # ------------------------------------------------------------ layout
    def header(self, extra=()):
        """extra: [(button name, label)] shown left of Close (e.g. the admin Lock button)."""
        u, B = self.u, self.B
        u.text("BrandTitle", "OWL ADMIN", B, 28, "#ffffff", spacing_px=4)
        u.text("BetaText", "BETA", B, 15, "#ffffff", spacing_px=3)
        u.border("BetaBadge", "#b3121a", 1.0, u.margin(10, 3, 10, 3), "BetaText")
        u.box("HorizontalBox", "BrandRow", [("BrandTitle", ["VerticalAlignment=VAlign_Center"]),
                                            ("BetaBadge", ["Padding=%s" % u.margin(l=12),
                                                           "VerticalAlignment=VAlign_Center"])])
        u.text("BrandSub", self.subtitle, B, 15, "#f0343a", spacing_px=3)
        u.box("VerticalBox", "Brand", [("BrandRow", []), ("BrandSub", ["Padding=%s" % u.margin(t=2)])])
        u.text("BadgeText", self.badge, B, 18, "#f2e6e2", spacing_px=1)
        framed(u, "Badge", "#5a1a1e", "#150909", "BadgeText", u.margin(16, 8, 16, 8))
        row = [("Brand", ["Size=(SizeRule=Fill)", "VerticalAlignment=VAlign_Center"]),
               ("Badge", ["VerticalAlignment=VAlign_Center"])]
        for name, label in extra:
            u.text(name + "Text", label, B, 18, "#f2e6e2", spacing_px=2, variable=False)
            button(u, name, name + "Text", u.margin(18, 0, 18, 0), button_style(u, "#150909", "#3a0b0e", "#b3121a"))
            framed(u, name + "Frame", "#5a1a1e", "#150909", name, u.margin())
            u.sized(name + "Box", name + "Frame", h=44)
            row.append((name + "Box", ["Padding=%s" % u.margin(l=12), "VerticalAlignment=VAlign_Center"]))
        u.text("CloseText", "X", B, 22, "#f2e6e2")
        button(u, "CloseBtn", "CloseText", u.margin(), button_style(u, "#150909", "#3a0b0e", "#b3121a"))
        u.sized("CloseBox", "CloseBtn", w=44, h=44)
        row.append(("CloseBox", ["Padding=%s" % u.margin(l=20), "VerticalAlignment=VAlign_Center"]))
        u.box("HorizontalBox", "HeaderRow", row)
        u.border("Header", "#140909", 1.0, u.margin(28, 0, 28, 0), "HeaderRow")
        u.sized("HeaderBox", "Header", h=76)
        u.strip("HeaderLine", "#b3121a", u.margin(t=2))

    def sidebar(self):
        # 36px tabs in a ScrollBox: 14 admin tabs at the board's 56px don't fit a 1080p screen
        u, B, R = self.u, self.B, self.R
        tab_items = []
        for tab, title, _hint in self.tabs:
            u.text("TabTxt_" + tab, title.upper(), B, 17, "#d8c8c3", spacing_px=1.5, variable=False)
            button(u, "TabBtn_" + tab, "TabTxt_" + tab, u.margin(20, 0, 20, 0),
                   button_style(u, "#ffffff", "#ffffff", "#ffffff"), halign="HAlign_Left")
            u.sized("TabBox_" + tab, "TabBtn_" + tab, h=36)
            tab_items.append(("TabBox_" + tab, ["Padding=%s" % u.margin(b=2), "HorizontalAlignment=HAlign_Fill"]))
        u.box("ScrollBox", "TabScroll", tab_items, props=scroll_style(u, 4))
        side = [("TabScroll", ["Size=(SizeRule=Fill)", "HorizontalAlignment=HAlign_Fill"])]
        if self.side_note:
            u.strip("SideNoteLine", "#2a1012", u.margin(t=1))
            u.text("SideNote", self.side_note, R, 15, "#a8908a", wrap=True, variable=False)
            side += [("SideNoteLine", ["HorizontalAlignment=HAlign_Fill"]),
                     ("SideNote", ["Padding=%s" % u.margin(20, 12, 20, 12)])]
        u.box("VerticalBox", "SideList", side)
        u.border("Sidebar", "#0b0606", 1.0, u.margin(t=12), "SideList")
        u.sized("SidebarBox", "Sidebar", w=240)
        u.strip("SidebarLine", "#3a1214", u.margin(l=1))

    def pages(self, content):
        """content(tab) -> [(widget, [VerticalBox slot props])] below the page title. Builds
        the TabPages switcher and the Body (sidebar | pages); returns "Body"."""
        u, B, R = self.u, self.B, self.R
        page_ids = []
        for tab, title, hint in self.tabs:
            u.text("PgTitle_" + tab, title.upper(), B, 22, "#ffffff", spacing_px=3, variable=False)
            u.text("PgHint_" + tab, hint, R, 16, "#a8908a", variable=False)
            u.box("HorizontalBox", "PgHead_" + tab, [
                ("PgTitle_" + tab, ["VerticalAlignment=VAlign_Bottom"]),
                ("PgHint_" + tab, ["Size=(SizeRule=Fill)", "HorizontalAlignment=HAlign_Right",
                                   "VerticalAlignment=VAlign_Bottom"]),
            ])
            items = [("PgHead_" + tab, ["Padding=%s" % u.margin(b=14)])] + list(content(tab))
            u.box("VerticalBox", "PgList_" + tab, items)
            u.box("ScrollBox", "Page_" + tab, [("PgList_" + tab, [])], props=scroll_style(u, 6))
            page_ids.append("Page_" + tab)
        u.widget(SWITCHER, "TabPages", ["ActiveWidgetIndex=0"],
                 [("/Script/UMG.WidgetSwitcherSlot", pid, ["HorizontalAlignment=HAlign_Fill",
                                                           "VerticalAlignment=VAlign_Fill"])
                  for pid in page_ids], variable=True)
        u.border("Content", "#000000", 0.0, u.margin(28, 24, 28, 24), "TabPages")
        return u.box("HorizontalBox", "Body", [("SidebarBox", ["VerticalAlignment=VAlign_Fill"]),
                                               ("SidebarLine", ["VerticalAlignment=VAlign_Fill"]),
                                               ("Content", ["Size=(SizeRule=Fill)", "VerticalAlignment=VAlign_Fill"])])

    def placeholder(self, name, text):
        """A 'coming in a later step' card."""
        u = self.u
        u.text(name + "_Txt", text, self.R, 17, "#b8a29c", wrap=True, variable=False)
        return framed(u, name, "#4a1a1d", "#0b0505", name + "_Txt", u.margin(16, 16, 16, 16))

    def footer(self, buttons=()):
        """buttons: [(name, label, primary)] on the right of the status line."""
        u, B = self.u, self.B
        row = [("StatusText", ["Size=(SizeRule=Fill)", "VerticalAlignment=VAlign_Center"])]
        u.text("StatusText", self.status, B, 18, "#f2e6e2")
        for i, (name, label, primary) in enumerate(buttons):
            u.text(name + "Text", label, B, 19, "#ffffff" if primary else "#f2e6e2", spacing_px=2, variable=False)
            if primary:
                button(u, name, name + "Text", u.margin(36, 0, 36, 0), button_style(u, "#b3121a", "#d01a22", "#8a2a2e"))
                u.sized(name + "Box", name, h=48)
            else:
                button(u, name, name + "Text", u.margin(28, 0, 28, 0), button_style(u, "#0d0606", "#1a0c0c", "#3a0b0e"))
                framed(u, name + "Frame", "#5a1a1e", "#0d0606", name, u.margin())
                u.sized(name + "Box", name + "Frame", h=48)
            row.append((name + "Box", ["Padding=%s" % u.margin(l=12 if i else 0), "VerticalAlignment=VAlign_Center"]))
        u.box("HorizontalBox", "FooterRow", row, variable=True)   # the admin menu hides it while locked
        u.border("Footer", "#0d0606", 1.0, u.margin(28, 0, 28, 0), "FooterRow")
        u.sized("FooterBox", "Footer", h=76)
        u.strip("FooterLine", "#b3121a", u.margin(t=2))

    def root(self, body):
        u = self.u
        u.box("VerticalBox", "MenuLayout", [
            ("HeaderBox", ["HorizontalAlignment=HAlign_Fill"]),
            ("HeaderLine", ["HorizontalAlignment=HAlign_Fill"]),
            (body, ["Size=(SizeRule=Fill)", "HorizontalAlignment=HAlign_Fill"]),
            ("FooterLine", ["HorizontalAlignment=HAlign_Fill"]),
            ("FooterBox", ["HorizontalAlignment=HAlign_Fill"]),
        ])
        u.border("MenuBg", "#0b0505", 1.0, u.margin(), "MenuLayout")
        u.border("MenuFrame", "#5a1a1e", 1.0, u.margin(2, 2, 2, 2), "MenuBg")
        u.widget(CANVAS, "MenuRoot", [], [("/Script/UMG.CanvasPanelSlot", "MenuFrame", [
            "LayoutData=(Offsets=(Left=0.000000,Top=0.000000,Right=0.000000,Bottom=0.000000),"
            "Anchors=(Minimum=(X=0.000000,Y=0.000000),Maximum=(X=1.000000,Y=1.000000)))"])])

    # ------------------------------------------------------------ build
    def paste(self, unreal, eal, bp, pkg, name, full):
        """Paste into a WindowRoot WBP (a GUIModule window), set the root, compile, verify."""
        from umg_text import prepare_wbp, verify_tree
        u = self.u
        wbp, wbp_ptr = prepare_wbp(eal, bp, pkg, name, full, parent=unreal.WindowRoot)
        pasted = bp.import_widgets(wbp_ptr, u.render())
        print("pasted %d/%d widgets" % (pasted, len(u.cls)))
        assert pasted == len(u.cls), "paste dropped widgets"
        root = bp.find_object("MenuRoot", outer=bp.widget_tree(wbp_ptr))
        assert root and bp.set_root_widget(wbp_ptr, root), "could not set MenuRoot as the root"
        bp.mark_structurally_modified(wbp_ptr)
        unreal.BlueprintEditorLibrary.compile_blueprint(wbp)     # widget variables exist before the graph
        missing, loose = verify_tree(bp, wbp_ptr, u.cls, "MenuRoot")
        print("widgets in tree: %d | missing: %s | unparented: %s"
              % (len(bp.tree_widgets(wbp_ptr)), missing or "(none)", loose or "(none)"))
        assert not missing and not loose, "widget tree not clean"
        self.root_ptr = root
        return wbp, wbp_ptr

    # ------------------------------------------------------------ graph
    def graph(self, g):
        """Tab clicks -> TabPages page i; Close -> ToggleModule(module) (the controller closes
        the window and hands the mouse back)."""
        pages = g.var_get("TabPages", "object", ir.obj_path(SWITCHER), pos=(300, -200))
        for i, (tab, _t, _h) in enumerate(self.tabs):
            ev = clicked(g, "TabBtn_" + tab, (0, i * 200))
            sai = g.call("SetActiveWidgetIndex", SWITCHER, pos=(400, i * 200))
            g.typed_input(sai, "Index", str(i), "int")
            g.wire(ev, "then", sai, "execute")
            g.wire(pages, "TabPages", sai, "self", exec=False)
        cev = clicked(g, "CloseBtn", (0, 3200))
        gmc = g.call("GetGUIModuleController", GUIMC, pos=(200, 3400))
        tgl = g.call("ToggleModule", GUIMC, pos=(500, 3200))
        g.typed_input(tgl, "ModuleName", self.module, "name")
        g.wire(cev, "then", tgl, "execute")
        g.wire(gmc, "ReturnValue", tgl, "self", exec=False)

    def tick_highlight(self, g, prev, prev_pin="then", y=3800):
        """Each TabBtn's background = active colour if its page is showing. Chained after
        (prev, prev_pin); returns the last node (exec out "then")."""
        u = self.u
        idx = g.call("GetActiveWidgetIndex", SWITCHER, pos=(200, y + 200))
        g.wire(g.var_get("TabPages", "object", ir.obj_path(SWITCHER), pos=(0, y + 200)), "TabPages", idx, "self",
               exec=False)
        for i, (tab, _t, _h) in enumerate(self.tabs):
            x = 500 + i * 350
            eq = g.call("EqualEqual_IntInt", KML, pos=(x, y + 400))
            g.wire(idx, "ReturnValue", eq, "A", exec=False)
            g.typed_input(eq, "B", str(i), "int")
            sel = g.call("SelectColor", KML, pos=(x, y + 600))
            g.typed_input(sel, "A", u.lin(TAB_ACTIVE), "struct", LCOLOR)
            g.typed_input(sel, "B", u.lin(TAB_IDLE), "struct", LCOLOR)
            g.wire(eq, "ReturnValue", sel, "bPickA", exec=False)
            sbc = g.call("SetBackgroundColor", BUTTON, pos=(x, y))
            g.wire(g.var_get("TabBtn_" + tab, "object", ir.obj_path(BUTTON), pos=(x, y - 150)), "TabBtn_" + tab,
                   sbc, "self", exec=False)
            g.wire(sel, "ReturnValue", sbc, "InBackgroundColor", exec=False)
            g.wire(prev, prev_pin, sbc, "execute")
            prev, prev_pin = sbc, "then"
        return prev
