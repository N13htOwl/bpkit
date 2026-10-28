"""The player menu's Equipment tab (07): what the player really wears, read only. A row
per menu_defs.TM_SLOTS slot (game icon, slot, item name, its armor) and the armor total.

    catalog(unreal) -> [{"id", "name", "icon", "armor"}]   (BUILD time, needs the editor)
    player_layout(u, B, R) -> [(widget, slot props)]     player_variables(unreal, bel, wbp)
    bake_player(cdo, entries)    player_tick(c, y)
    (c: ce_panel._Ctx on MyRelay)

No server code and nothing to click. The tick reads the relay's TmPawn (the player's character):
BasePlayerChar_C.CharacterLayout -> MeshLayout holds the worn item's id per slot (menu_defs.
TM_LAYOUT; -1 / -2 when empty) -- the real gear: transmog and masks only change a copy of it
(10). Names, icons and armor come from every worn ItemTable row (EquipLocation 3-7), baked onto
the menu (GearIds, GearNames, GearIcons, GearArmor); the rows only change when the ids do (GearKey).
The armor is the table's ArmourValue for the item, so it leaves out what the live character
adds (durability, perks).
"""
import json

import menu_defs as D
from bpkit import ir
from ce_panel import _lab, KML, KSL, KSTR
from tm_catalog import ITEM_TABLE, _NSLOC, item_icon
from pet_panel import _i

CHAR_CLS = "/Game/Characters/BasePlayerChar.BasePlayerChar_C"
PAWN = "/Script/Engine.Pawn"
CS = "/Script/ConanSandbox."
LAYOUT, MESHL = CS + "CharacterLayout", CS + "CharacterMeshLayout"
IMAGE = "/Script/UMG.Image"
WIDGET = "/Script/UMG.Widget"
TEX2D = "/Script/Engine.Texture2D"
SLATEVIS = ir.enum_path("/Script/UMG.ESlateVisibility")
ARMOR_KEY = "ArmourValue"     # the table's spelling
NONE_WORN = "Nothing worn"
NOTE = "This is the gear you really wear. Transmog and Animal Masks only change how it looks."


# ================================================================ catalogue (build time)
def catalog(unreal):
    dt = unreal.load_asset(ITEM_TABLE)
    assert dt, "no item table at " + ITEM_TABLE
    lib = unreal.DataTableFunctionLibrary
    names = dict(zip([str(n) for n in lib.get_data_table_row_names(dt)],
                     lib.get_data_table_column_as_string(dt, "Name")))
    locs = {loc for _k, _l, loc in D.TM_SLOTS}
    out = []
    for r in json.loads(lib.export_data_table_to_json_string(dt)):
        rid = str(r.get("Name"))
        m = _NSLOC.search(names.get(rid, ""))
        if r.get("EquipLocation") not in locs or not m or not m.group(1).strip():
            continue
        out.append({"id": rid, "name": m.group(1).replace('\\"', '"').strip(), "icon": item_icon(r),
                    "armor": int(round(float(r.get(ARMOR_KEY) or 0)))})
    return out


# ================================================================ layout
def player_layout(u, B, R):
    rows = [(_lab(u, B, "GearWorn", "What you're wearing"), ["Padding=%s" % u.margin(b=10)])]
    for k, label, _loc in D.TM_SLOTS:
        r = "GearRow_" + k
        u.widget(IMAGE, r + "Img", ["Brush=%s" % u.brush("#ffffff", w=56, h=56), "Visibility=Hidden"], variable=True)
        u.sized(r + "ImgBox", r + "Img", w=56, h=56)
        u.border(r + "Ico", "#1a0c0c", 1.0, u.margin(2, 2, 2, 2), r + "ImgBox")
        u.border(r + "IcoFrame", "#3a1214", 1.0, u.margin(1, 1, 1, 1), r + "Ico")
        u.text(r + "Slot", label.upper(), B, 13, "#b8a29c", spacing_px=1, variable=False)
        u.text(r + "Name", NONE_WORN, B, 17, "#f2e6e2", wrap=True)
        u.text(r + "Armor", "", B, 16, "#ff5a5f")
        u.box("VerticalBox", r + "Txt", [(r + "Slot", []), (r + "Name", [])])
        u.box("HorizontalBox", r + "In", [
            (r + "IcoFrame", ["VerticalAlignment=VAlign_Center"]),
            (r + "Txt", ["Size=(SizeRule=Fill)", "Padding=%s" % u.margin(l=12, r=8), "VerticalAlignment=VAlign_Center"]),
            (r + "Armor", ["VerticalAlignment=VAlign_Center"])])
        u.border(r, "#0f0707", 1.0, u.margin(10, 8, 12, 8), r + "In")
        rows.append((r, ["Padding=%s" % u.margin(b=6)]))
    u.box("VerticalBox", "GearLeft", rows)
    u.text("GearTotal", "0", B, 40, "#ffffff")
    u.text("GearNote", NOTE, R, 16, "#d8c8c3", wrap=True, variable=False)
    u.box("VerticalBox", "GearRightIn", [
        (_lab(u, B, "GearArmorLbl", "Armor total"), []),
        ("GearTotal", ["Padding=%s" % u.margin(t=2, b=12)]),
        ("GearNote", [])])
    u.border("GearRight", "#0b0606", 1.0, u.margin(20, 16, 20, 16), "GearRightIn")
    u.border("GearRightFrame", "#3a1214", 1.0, u.margin(1, 1, 1, 1), "GearRight")
    u.sized("GearRightBox", "GearRightFrame", w=280)
    u.box("HorizontalBox", "GearBody", [("GearLeft", ["Size=(SizeRule=Fill)", "Padding=%s" % u.margin(r=12)]),
                                        ("GearRightBox", ["VerticalAlignment=VAlign_Top"])])
    return [("GearBody", [])]


def player_variables(unreal, bel, wbp):
    s, i = bel.get_basic_type_by_name("string"), bel.get_basic_type_by_name("int")
    for var, t in (("GearKey", s), ("GearSum", i), ("GearIds", bel.get_array_type(s)),
                   ("GearNames", bel.get_array_type(s)), ("GearIcons", bel.get_array_type(s)),
                   ("GearArmor", bel.get_array_type(i))):
        bel.add_member_variable(wbp, var, t)


def bake_player(cdo, entries):
    for var, key in (("GearIds", "id"), ("GearNames", "name"), ("GearIcons", "icon"), ("GearArmor", "armor")):
        cdo.set_editor_property(var, [e[key] for e in entries])
    cdo.set_editor_property("GearKey", "")


# ================================================================ tick
def _struct(g, kind, spath, pos):
    """A K2Node_BreakStruct of a native struct (10's struct_node)."""
    n = g.node("K2Node_%sStruct" % kind, ['StructType="%s"' % ir.struct_path(spath)], base=kind + "Struct", pos=pos)
    n.pin(spath.split(".")[-1]).typed("struct", ir.struct_path(spath), direction="EGPD_Input")
    return n


def _icon(c, widget, path, show, pos):
    """widget shows the texture at path when show, else is hidden (07's preview icons)."""
    g, (x, y) = c.g, pos
    b = c.branch(show, (x, y))
    sp = c.fn("MakeSoftObjectPath", KSL, {"PathString": path}, (x, y + 400))
    ref = c.fn("Conv_SoftObjPathToSoftObjRef", KSL, {"SoftObjectPath": sp}, (x + 250, y + 400))
    c.exits = [(b, "then")]
    ld = g.call("LoadAsset_Blocking", KSL, pos=(x + 300, y))
    g.wire(ref[0], ref[1], ld, "Asset", exec=False)
    c.go(ld)
    tc = g.cast(TEX2D, pos=(x + 600, y))
    g.wire(ld, "ReturnValue", tc, "Object", exec=False)
    c.go(tc)
    sb = g.call("SetBrushFromTexture", IMAGE, pos=(x + 900, y))
    w = c.widget(widget, IMAGE, (x + 700, y + 200))
    g.wire(w[0], w[1], sb, "self", exec=False)
    g.wire(tc, "AsTexture 2D", sb, "Texture", exec=False)
    c.go(sb)
    ends = []
    for vis, srcs, sy in (("Visible", [(sb, "then")], y), ("Hidden", [(b, "else"), (tc, "CastFailed")], y + 300)):
        c.exits = srcs
        c.set_vis(widget, IMAGE, vis, (x + 1200, sy))
        ends += c.exits
    c.exits = ends


def player_tick(c, y):
    """Entered from c.exits; leaves c.exits for whatever follows."""
    g, x = c.g, 0
    bv = c.branch(c.fn("IsValid", KSL, {"Object": c.relay((x, y + 300))}, (x + 200, y + 300)), (x + 200, y))
    out = [(bv, "else")]
    c.exits = [(bv, "then")]
    cast = g.cast(CHAR_CLS, pos=(x + 500, y))
    pawn = c.rvar("TmPawn", "object", (x + 400, y + 250), sub=ir.obj_path(PAWN))
    g.wire(pawn[0], pawn[1], cast, "Object", exec=False)
    c.go(cast)
    out.append((cast, "CastFailed"))
    lay = g.var_get("CharacterLayout", "struct", ir.struct_path(LAYOUT), parent=CHAR_CLS, pos=(x + 500, y + 450))
    g.wire(cast, "AsBase Player Char", lay, "self", exec=False)
    brk = _struct(g, "Break", LAYOUT, (x + 800, y + 450))
    g.wire(lay, "CharacterLayout", brk, "CharacterLayout", exec=False)
    brk.pin("MeshLayout").typed("struct", ir.struct_path(MESHL), direction="EGPD_Output")
    brkM = _struct(g, "Break", MESHL, (x + 1100, y + 450))
    g.wire(brk, "MeshLayout", brkM, "CharacterMeshLayout", exec=False)
    ids = []
    for k, _l, _loc in D.TM_SLOTS:
        m = D.TM_LAYOUT[k][1]
        brkM.pin(m).typed("int", direction="EGPD_Output")
        ids.append(c.fn("Conv_IntToString", KSTR, {"InInt": (brkM, m)}, (x + 1400, y + 450 + 150 * len(ids))))
    # only when an id changed
    parts = []
    for s in ids:
        parts += [s, "|"]
    key = c.concat(parts, (x + 1700, y + 450))
    same = c.branch(c.fn("EqualEqual_StrStr", KSTR, {"A": key, "B": c.var("GearKey", "string", (x + 3700, y + 650))},
                         (x + 3900, y + 450)), (x + 4000, y))
    out.append((same, "then"))
    c.exits = [(same, "else")]
    c.set_var("GearKey", "string", key, (x + 4300, y))
    c.set_var("GearSum", "int", "0", (x + 4600, y))
    x += 5000
    for n, (k, _l, _loc) in enumerate(D.TM_SLOTS):
        r = "GearRow_" + k
        found = c.find(c.arr("GearIds", "string", (x, y + 600)), ids[n], "string", (x + 200, y + 600))
        idx = c.fn("Max", KML, {"A": found, "B": ("0", "int")}, (x + 400, y + 750))   # -1 would log a warning
        has = _i(c, "GreaterEqual_IntInt", found, 0, (x + 400, y + 600))
        name = c.at(c.arr("GearNames", "string", (x + 400, y + 900)), idx, "string", (x + 600, y + 900))
        c.set_text(r + "Name", c.fn("SelectString", KML, {"A": name, "B": (NONE_WORN, "string"), "bPickA": has},
                                    (x + 800, y + 600)), (x + 600, y))
        armor = c.fn("SelectInt", KML, {"A": c.at(c.arr("GearArmor", "int", (x + 400, y + 1050)), idx, "int",
                                                  (x + 600, y + 1050)),
                                        "B": ("0", "int"), "bPickA": has}, (x + 800, y + 1050))
        c.set_text(r + "Armor", c.fn("SelectString", KML, {"A": c.int_text(armor, (x + 1000, y + 1050)),
                                                           "B": ("", "string"),
                                                           "bPickA": _i(c, "Greater_IntInt", armor, 0,
                                                                        (x + 1000, y + 1200))},
                                     (x + 1400, y + 1050)), (x + 900, y))
        c.set_var("GearSum", "int", c.fn("Add_IntInt", KML, {"A": c.var("GearSum", "int", (x + 1200, y + 1350)),
                                                             "B": armor}, (x + 1400, y + 1350)), (x + 1200, y))
        icon = c.at(c.arr("GearIcons", "string", (x + 1300, y + 700)), idx, "string", (x + 1500, y + 700))
        show = c.fn("BooleanAND", KML, {"A": has, "B": _i(c, "Greater_IntInt",
                                                         c.fn("Len", KSTR, {"S": icon}, (x + 1700, y + 850)), 0,
                                                         (x + 1900, y + 850))}, (x + 2100, y + 700))
        _icon(c, r + "Img", icon, show, (x + 1600, y))
        x += 3200
    c.set_text("GearTotal", c.int_text(c.var("GearSum", "int", (x, y + 300)), (x + 200, y + 300)), (x, y))
    c.exits += out
