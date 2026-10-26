"""Designer clipboard text for owl-admin widget trees, plus the create-or-empty-in-place
step every owl-admin WBP build shares. Text building is pure Python; prepare_wbp() needs
the editor.

    u = Umg(scale=1.5)
    u.text("Title", "Hello", FONT, 22, "#ffffff")
    u.widget("/Script/UMG.CanvasPanel", "Root", [], [("/Script/UMG.CanvasPanelSlot", "Title", [...])])
    text = u.render()        # root (last emitted) first, as the designer exports it

Children are emitted before their parents so every Content= reference has a known class.
Sizes passed in are design-canvas px; scale turns them into UMG units.
"""


class Umg:
    def __init__(self, scale):
        self.S = scale
        self.cls = {}          # widget name -> class path, for Content= references
        self.blocks = []

    # ---- values
    @staticmethod
    def lin(hex_, a=1.0):
        """CSS sRGB hex -> UE FLinearColor text (UMG colours are linear)."""
        def c(v):
            v /= 255.0
            return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
        r, g, b = (int(hex_[i:i + 2], 16) for i in (1, 3, 5))
        return "(R=%.6f,G=%.6f,B=%.6f,A=%.6f)" % (c(r), c(g), c(b), a)

    def margin(self, l=0, t=0, r=0, b=0):
        S = self.S
        return "(Left=%.6f,Top=%.6f,Right=%.6f,Bottom=%.6f)" % (l * S, t * S, r * S, b * S)

    def brush(self, hex_, a=1.0, w=None, h=None):
        """A solid-colour brush (no texture, drawn as an image). The texture is cleared
        explicitly: brush text is applied over the style's default brush, and UE5's default
        CheckBox brushes draw their tick from an image FILE (ResourceName), not a
        ResourceObject, so leaving either out keeps the tick under the tint."""
        size = ",ImageSize=(X=%.6f,Y=%.6f)" % (w * self.S, h * self.S) if w else ""
        return "(DrawAs=Image,ResourceObject=None,ResourceName=\"\",TintColor=(SpecifiedColor=%s)%s)" % (
            self.lin(hex_, a), size)

    def font(self, path, px, spacing_px=0):
        em = int(round(1000.0 * spacing_px / px)) if spacing_px else 0
        return """(FontObject="/Script/Engine.Font'%s'",Size=%.6f,LetterSpacing=%d)""" % (
            path, px * self.S * 0.75, em)

    @staticmethod
    def quote(s):
        return s.replace("\\", "\\\\").replace('"', '\\"')

    # ---- widgets
    def widget(self, cls, name, props=(), children=(), variable=None):
        """Emit one widget object. children = [(slot_cls, child_name, [slot props]), ...].
        variable: True/False to force bIsVariable (default: TextBlocks only)."""
        self.cls[name] = cls
        out = ['Begin Object Class=%s Name="%s"' % (cls, name)]
        slots = []
        for i, (slot_cls, child, sprops) in enumerate(children):
            sname = "%s_Slot%d" % (name, i)
            slots.append((slot_cls, sname))
            out += ['   Begin Object Class=%s Name="%s"' % (slot_cls, sname), "   End Object"]
        for (slot_cls, sname), (_, child, sprops) in zip(slots, children):
            out.append('   Begin Object Name="%s"' % sname)
            out += ["      " + p for p in sprops]
            out.append("""      Parent="%s'%s'\"""" % (cls, name))
            out.append("""      Content="%s'%s'\"""" % (self.cls[child], child))
            out.append("   End Object")
        out += ["   " + p for p in props]
        out += ["""   Slots(%d)="%s'%s'\"""" % (i, sc, sn) for i, (sc, sn) in enumerate(slots)]
        is_var = cls.endswith("TextBlock") if variable is None else variable
        out += ["   bIsVariable=%s" % is_var, '   DisplayLabel="%s"' % name, "End Object"]
        self.blocks.append("\n".join(out))
        return name

    def text(self, name, s, font, px, hex_, spacing_px=0, wrap=False, variable=None):
        return self.widget("/Script/UMG.TextBlock", name, [
            'Text=INVTEXT("%s")' % self.quote(s),
            "Font=%s" % self.font(font, px, spacing_px),
            "ColorAndOpacity=(SpecifiedColor=%s)" % self.lin(hex_),
        ] + (["AutoWrapText=True"] if wrap else []), variable=variable)

    def border(self, name, hex_, a, pad, child, halign="HAlign_Fill", valign="VAlign_Fill", props=(), variable=None):
        return self.widget("/Script/UMG.Border", name, [
            "HorizontalAlignment=%s" % halign, "VerticalAlignment=%s" % valign,
            "Padding=%s" % pad, "BrushColor=%s" % self.lin(hex_, a)] + list(props),
            [("/Script/UMG.BorderSlot", child,
              ["Padding=%s" % pad, "HorizontalAlignment=%s" % halign, "VerticalAlignment=%s" % valign])],
            variable=variable)

    def strip(self, name, hex_, pad):
        """A solid bar: a childless Border whose padding is its size."""
        return self.widget("/Script/UMG.Border", name, ["Padding=%s" % pad, "BrushColor=%s" % self.lin(hex_)])

    def box(self, kind, name, items, props=(), variable=None):
        """VerticalBox/HorizontalBox/ScrollBox; items = [(child, [slot props])]."""
        return self.widget("/Script/UMG.%s" % kind, name, list(props),
                           [("/Script/UMG.%sSlot" % kind, c, p) for c, p in items], variable=variable)

    def sized(self, name, child, w=None, h=None, halign="HAlign_Fill", valign="VAlign_Fill"):
        props = []
        if w is not None:
            props += ["WidthOverride=%.6f" % (w * self.S), "bOverride_WidthOverride=True"]
        if h is not None:
            props += ["HeightOverride=%.6f" % (h * self.S), "bOverride_HeightOverride=True"]
        return self.widget("/Script/UMG.SizeBox", name, props, [
            ("/Script/UMG.SizeBoxSlot", child, ["HorizontalAlignment=%s" % halign, "VerticalAlignment=%s" % valign])])

    def render(self):
        return "\n".join(reversed(self.blocks))


def prepare_wbp(eal, bp, pkg, name, full, parent=None):
    """Load the WBP at pkg/name (creating it if absent) and empty its widget tree in place.
    Edit-in-place because other assets reference the class and delete + recreate leaves a
    stale redirector; old widgets go to the transient package (never saved) so a fresh
    paste keeps its exact names. parent: the native parent class (default UserWidget); an
    existing WBP is reparented to it. Returns (wbp, wbp_ptr)."""
    import re
    import unreal
    parent = parent or unreal.UserWidget
    path = "%s/%s" % (pkg, name)
    wbp = eal.load_asset(path)        # load_asset, not does_asset_exist (unreliable)
    if wbp is None:
        factory = unreal.WidgetBlueprintFactory()
        factory.set_editor_property("parent_class", parent)
        wbp = unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, pkg, unreal.WidgetBlueprint, factory)
        assert wbp, "create_asset failed for " + path
    elif not isinstance(unreal.get_default_object(unreal.load_object(None, full + "_C")), parent):
        unreal.BlueprintEditorLibrary.reparent_blueprint(wbp, parent)
        print("reparented %s to %s" % (name, parent.__name__))
    wbp_ptr = bp.find_object(full)
    old = bp.tree_widgets(wbp_ptr)
    if old:
        transient = unreal.find_object(None, "/Engine/Transient")
        assert transient, "transient package not found"
        bp.set_root_widget(wbp_ptr, 0)
        for w in old:
            wname = re.match(r'Begin Object Class=\S+ Name="([^"]+)"', bp.export_widgets([w])).group(1)
            obj = unreal.find_object(None, "%s:WidgetTree.%s" % (full, wname))
            assert obj and obj.rename(None, transient), "could not move old widget out: " + wname
        print("emptied the existing tree: moved %d old widgets to the transient package" % len(old))
    left = bp.tree_widgets(wbp_ptr)
    assert not left, "tree still has %d widgets; expected it empty" % len(left)
    return wbp, wbp_ptr


def verify_tree(bp, wbp_ptr, expected_names, root_name):
    """Every expected widget present, none unparented except the root. Returns (missing, loose)."""
    import re
    ws = bp.tree_widgets(wbp_ptr)
    names = {re.match(r'Begin Object Class=\S+ Name="([^"]+)"', bp.export_widgets([w])).group(1) for w in ws}
    held = set(re.findall(r"""Content="[^']*'([^']+)'""", bp.export_widgets(ws)))
    return sorted(set(expected_names) - names), sorted(names - held - {root_name})
