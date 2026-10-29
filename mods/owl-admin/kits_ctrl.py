"""Kits, the controller's (02) part: what is in each kit, replicated to every player.

    variables(bel) -> [(name, type, replicated)]     defaults(cdo)
    load(c, sg_cls, y)     entered at BeginPlay on the server; leaves c.exits for what follows

KitNames (one per kit, menu_defs.N_KITS), and one entry per kit item in parallel arrays: KitEKit
(which kit, 0-based), KitEIds (item template id), KitEQty, KitENames (the item's name, so the
menus don't need the item table). KitVer goes up on every change, so open menus redraw. The
relay's kit events (kits_server) change them and write the OwlKits save; BeginPlay loads it.
"""
import menu_defs as D
import oa_config as MOD
from ce_panel import KML, GS

ENTRY = (("KitEKit", "EKit", "int"), ("KitEIds", "EIds", "int"), ("KitEQty", "EQty", "int"),
         ("KitENames", "ENames", "string"))


def variables(bel):
    i, s = bel.get_basic_type_by_name("int"), bel.get_basic_type_by_name("string")
    return ([("KitNames", bel.get_array_type(s), True), ("KitVer", i, True)]
            + [(var, bel.get_array_type(i if cat == "int" else s), True) for var, _f, cat in ENTRY])


def defaults(cdo):
    cdo.set_editor_property("KitNames", list(D.KIT_NAMES))


def load(c, sg_cls, y):
    """The OwlKits save into the Kit* arrays, if its entry arrays line up (and its names, if there
    is one per kit); else the defaults stay (no items). KitVer goes up either way."""
    g = c.g
    ex = g.call("DoesSaveGameExist", GS, pos=(0, y + 300))
    g.typed_input(ex, "SlotName", MOD.KITS_SLOT, "string")
    g.typed_input(ex, "UserIndex", "0", "int")
    c.go(ex)
    b = c.branch((ex, "ReturnValue"), (250, y))
    skip = [(b, "else")]
    c.exits = [(b, "then")]
    ld = g.call("LoadGameFromSlot", GS, pos=(500, y))
    g.typed_input(ld, "SlotName", MOD.KITS_SLOT, "string")
    g.typed_input(ld, "UserIndex", "0", "int")
    c.go(ld)
    cast = g.cast(sg_cls, pos=(800, y))
    g.wire(ld, "ReturnValue", cast, "Object", exec=False)
    c.go(cast)
    skip.append((cast, "CastFailed"))
    AS = "AsBP Owl Kits Save"

    def field(name, cat, pos):
        a = g.array_var(name, pos=pos, elem_cat=cat, parent=sg_cls)
        g.wire(cast, AS, a, "self", exec=False)
        return a

    def length(name, cat, pos):
        return (g.array_len(field(name, cat, pos), name, (pos[0] + 200, pos[1]), elem_cat=cat), "ReturnValue")

    # the entry arrays all as long as EKit
    n0 = length("EKit", "int", (1000, y + 600))
    ok = None
    for k, (_v, f, cat) in enumerate(ENTRY[1:]):
        eq = c.fn("EqualEqual_IntInt", KML, {"A": length(f, cat, (1000, y + 750 + 150 * k)), "B": n0},
                  (1300, y + 750 + 150 * k))
        ok = eq if ok is None else c.fn("BooleanAND", KML, {"A": ok, "B": eq}, (1500, y + 750 + 150 * k))
    be = c.branch(ok, (1100, y))
    skip.append((be, "else"))
    c.exits = [(be, "then")]
    x = 1600
    for var, f, cat in ENTRY:
        st = g.var_set(var, cat, pos=(x, y))
        st.pin(var).set("PinType.ContainerType", "Array")
        g.wire(field(f, cat, (x - 200, y + 400)), f, st, var, exec=False)
        c.go(st)
        x += 300
    # the names, if there is one per kit
    bn = c.branch(c.fn("EqualEqual_IntInt", KML, {"A": length("Names", "string", (x, y + 600)),
                                                  "B": (str(D.N_KITS), "int")}, (x + 250, y + 600)), (x + 250, y))
    c.exits = [(bn, "then")]
    st = g.var_set("KitNames", "string", pos=(x + 550, y))
    st.pin("KitNames").set("PinType.ContainerType", "Array")
    g.wire(field("Names", "string", (x + 350, y + 400)), "Names", st, "KitNames", exec=False)
    c.go(st)
    c.exits += [(bn, "else")] + skip
    c.bump("KitVer", (x + 900, y))
