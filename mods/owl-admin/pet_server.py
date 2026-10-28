"""The Pet Shop, the server side: the relay's (10) pet events, sent by the player menu's Pet Shop
tab through the player's own relay. For every player (no admin login).

    OwlServerPetWallet()     -> OwlClientPet(Wallet, Ok, Msg)    the player's Owl wallet
    OwlServerPetBuy(Index)   -> OwlClientPet(Wallet, Ok, Msg)    buy menu_defs.PETS[Index]

The wallet is the Character Editor's: Balance in the player's BP_OwlCeSave (slot OwlCe_<net id>),
which admins set on the Characters tab. A buy needs a character and Balance >= the price; the pet
item goes into the backpack (AddItemTemplate, index -1) and only when that returns a slot (>= 0)
is the price taken, a log line added ("Bought a <pet> for <price> coins") and the save written.
The prices and ids live on the relay's class defaults (PetIds / PetPrices / PetNames, set by 10),
so a client can't change what anything costs.
"""
from bpkit import ir
import menu_defs as D
from ce_server import helpers, KSTR, GS, CS, CHAR, INV

PET_PINS = [("Wallet", "int", False), ("Ok", "bool", False), ("Msg", "string", False)]
NO_CHAR = "You need a character to buy a pet."
NO_ROOM = "No room in your inventory for the pet. Make some space and try again."


def variables(unreal, bel, ce_save_cls):
    """(name, type) for the relay: Pet* = the owner's copy the menu reads, SvPet* = the server's."""
    i, s, b = (bel.get_basic_type_by_name(t) for t in ("int", "string", "bool"))
    return [("PetWallet", i), ("PetOk", b), ("PetMsg", s), ("PetVer", i), ("SvPetBal", i),
            ("SvPetSave", bel.get_object_reference_type(ce_save_cls)),
            ("PetIds", bel.get_array_type(i)), ("PetPrices", bel.get_array_type(i)), ("PetNames", bel.get_array_type(s))]


def defaults(cdo):
    cdo.set_editor_property("PetIds", [pid for _n, pid, _p, _i in D.PETS])
    cdo.set_editor_property("PetPrices", [price for _n, _id, price, _i in D.PETS])
    cdo.set_editor_property("PetNames", [n for n, _id, _p, _i in D.PETS])


def build(R, y0):
    """Add the pet events to R.g from y0 down (R as for ce_server.build). Returns {event: net flags}."""
    g, MOD = R.g, R.MOD
    CE_SG = MOD.full(R.PKG, MOD.CE_SAVEGAME) + "_C"
    SAVE = ir.obj_path(CE_SG)
    flags = {}
    h = helpers(R, flags)

    def reply(prevs, ok, msg, pos):
        c = h.call_self("OwlClientPet", PET_PINS, pos)
        bal = h.get("SvPetBal", "int", (pos[0] - 200, pos[1] + 300))
        g.wire(bal[0], bal[1], c, "Wallet", exec=False)
        c.pin("Ok").literal("true" if ok else "false")
        h.wire_in(msg, c, "Msg", "string")
        for p in prevs:
            g.wire(p[0], p[1], c, "execute")

    def wallet(prev, oc, pos):
        """SvPetBal (+ SvPetSave) from the owner's CE save; 0 (and no save) without one."""
        x, y = pos
        slot = (R.save_slot(oc, (x, y + 600), prefix=MOD.CE_SLOT_PREFIX), "ReturnValue")
        sc, missing = h.load([prev], slot, CE_SG, (x, y))
        p = (sc, "then")
        st = g.var_set("SvPetSave", "object", SAVE, pos=(x + 1100, y))
        g.wire(sc, h.save_as(CE_SG), st, "SvPetSave", exec=False)
        g.wire(p[0], p[1], st, "execute")
        bal = h.get("Balance", "int", (x + 1400, y + 250), parent=CE_SG)
        g.wire(sc, h.save_as(CE_SG), bal[0], "self", exec=False)
        have = h.setv((st, "then"), "SvPetBal", "int", bal, (x + 1400, y))
        none = g.var_set("SvPetBal", "int", pos=(x + 1400, y + 500))
        none.pin("SvPetBal").typed("int", direction="EGPD_Input").literal("0")
        for e, ep in missing:
            g.wire(e, ep, none, "execute")
        return [have, (none, "then")], slot

    # ---- the wallet
    y = y0
    ce = h.event("OwlServerPetWallet", [], y, R.RUN_ON_SERVER)
    oc = R.owner_pc(ce, "then", (300, y))
    ends, _slot = wallet((oc, "then"), oc, (600, y))
    reply(ends, True, "", (2400, y))

    # ---- buy
    y = y0 + 1500
    ce = h.event("OwlServerPetBuy", [("Index", "int", False)], y, R.RUN_ON_SERVER)
    oc = R.owner_pc(ce, "then", (300, y))
    pawn = g.call("K2_GetPawn", "/Script/Engine.Controller", pos=(600, y + 300))
    g.wire(oc, "AsConan Player Controller", pawn, "self", exec=False)
    chc = g.cast(CHAR, pos=(600, y))
    g.wire(pawn, "ReturnValue", chc, "Object", exec=False)
    g.wire(oc, "then", chc, "execute")
    idx = h.clamp((ce, "Index"), (0, len(D.PETS) - 1), (900, y + 900))

    def pet(name, cat, pos):
        a = h.get(name, cat, pos, arr=True)
        return (g.array_get(a[0], a[1], idx, (pos[0] + 200, pos[1]), elem_cat=cat), "Output")

    ends, slot = wallet((chc, "then"), oc, (900, y))
    price = pet("PetPrices", "int", (2400, y + 600))
    enough = h.branch(ends[0], h.op("GreaterEqual_IntInt", h.get("SvPetBal", "int", (2400, y + 450)), price,
                                    (2700, y + 450)), (2700, y))
    g.wire(ends[1][0], ends[1][1], enough, "execute")
    poor = h.text(["Not enough coins. This pet costs ", price + ("int",), "; you have ",
                   h.get("SvPetBal", "int", (2900, y + 1300)) + ("int",), "."], (2900, y + 1200))
    reply([(enough, "else")], False, poor, (3000, y + 900))
    # the pet into the backpack; only a slot back (>= 0) counts as bought
    inv = g.call("GetInventoryByType", INV, pos=(3000, y + 300))
    g.wire(chc, "AsConan Character", inv, "owner", exec=False)
    g.typed_input(inv, "inventoryType", "Backpack", "byte", ir.enum_path(CS + "EInventoryType"))
    ad = g.call("AddItemTemplate", INV, pos=(3300, y))
    g.wire(inv, "ReturnValue", ad, "self", exec=False)
    pid = pet("PetIds", "int", (3000, y + 600))
    g.wire(pid[0], pid[1], ad, "templateID", exec=False)
    g.typed_input(ad, "index", "-1", "int")
    g.typed_input(ad, "context", MOD.CE_CONTEXT, "name")
    g.typed_input(ad, "quantity", "1", "int")
    g.wire(enough, "then", ad, "execute")
    added = h.branch((ad, "then"), h.op("GreaterEqual_IntInt", (ad, "ReturnValue"), "0", (3600, y + 300)), (3600, y))
    reply([(added, "else")], False, NO_ROOM, (3900, y + 900))
    # paid: the new balance into the save, a log line, the save written
    p = h.setv((added, "then"), "SvPetBal", "int",
               h.op("Subtract_IntInt", h.get("SvPetBal", "int", (3800, y + 300)), price, (4000, y + 300)), (3900, y))
    sv = lambda pos: (g.var_get("SvPetSave", "object", SAVE, pos=pos), "SvPetSave")
    sb = g.var_set("Balance", "int", parent=CE_SG, pos=(4200, y))
    s0 = sv((4000, y + 450))
    g.wire(s0[0], s0[1], sb, "self", exec=False)
    nb = h.get("SvPetBal", "int", (4000, y + 600))
    g.wire(nb[0], nb[1], sb, "Balance", exec=False)
    g.wire(p[0], p[1], sb, "execute")
    name = pet("PetNames", "string", (4300, y + 900))
    p = h.set_line((sb, "then"), oc, ["Bought a ", name, " for ", price + ("int",), " coins"], (4500, y))
    add = g.array_fn("Array_Add", pos=(6200, y), elem_cat="string")
    g.array_item_pin(add, "NewItem", "string")
    lg = g.var_get("Log", "string", parent=CE_SG, pos=(6000, y + 300))
    lg.pin("Log").set("PinType.ContainerType", "Array")
    s1 = sv((5800, y + 300))
    g.wire(s1[0], s1[1], lg, "self", exec=False)
    g.wire(lg, "Log", add, "TargetArray", exec=False)
    g.wire(*h.get("SvLine", "string", (6000, y + 450)), add, "NewItem", exec=False)
    g.wire(p[0], p[1], add, "execute")
    sav = g.call("SaveGameToSlot", GS, pos=(6500, y))
    s2 = sv((6300, y + 300))
    g.wire(s2[0], s2[1], sav, "SaveGameObject", exec=False)
    g.wire(slot[0], slot[1], sav, "SlotName", exec=False)
    g.typed_input(sav, "UserIndex", "0", "int")
    g.wire(add, "then", sav, "execute")
    done = h.text(["Bought! The ", name, " is in your inventory. Place it to call it out."], (6800, y + 600))
    reply([(sav, "then")], True, done, (6900, y))
    reply([(chc, "CastFailed")], False, NO_CHAR, (900, y + 1500))

    h.client_event("OwlClientPet", PET_PINS, ["PetWallet", "PetOk", "PetMsg"], "PetVer", y0 + 4000)
    return flags
