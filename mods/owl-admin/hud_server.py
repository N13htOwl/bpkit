"""The HUD tab, the server side: the relay's (10) HUD event. The admin menu's HUD tab sends it
through the admin's own relay.

    OwlServerHudSet(On0..On4, T0..T2)  -> OwlClientHudSaved(Ok, Msg)      admins (unlocked)

On<k> is 1/0 for menu_defs.HUD_ITEMS[k], T<j> the text of HUD_TEXTS[j]. The server keeps 1/0
only, trims each text and cuts it to its item's limit, writes BP_OwlHudSave (slot OwlHud, the
whole save each time) and copies the values into the controller's (02) replicated HudOn /
HudText, then raises HudVer: every player's HUD (the controller's tick, on each client) and every
open admin menu pick them up from there. The controller loads the same save at BeginPlay.
"""
from bpkit import ir
import menu_defs as D
from ce_server import helpers, KSTR, GS

SENT_PINS = [("Ok", "bool", False), ("Msg", "string", False)]
ON_PINS = ["On%d" % k for k in range(len(D.HUD_ITEMS))]
TEXT_PINS = ["T%d" % j for j in range(len(D.HUD_TEXTS))]
SAVED = "Saved. Every player's HUD shows it now."


def variables(unreal, bel):
    """(name, type) for the relay: Hud* = the owner's copy the menu reads, SvHud* = the server's."""
    i, s, b = (bel.get_basic_type_by_name(t) for t in ("int", "string", "bool"))
    arr = bel.get_array_type
    return [("HudOk", b), ("HudMsg", s), ("HudSavedVer", i), ("SvHudOn", arr(i)), ("SvHudText", arr(s))]


def build(R, y0):
    """Add the HUD event to R.g from y0 down (R as for ce_server.build). Returns {event: net flags}."""
    g, MOD = R.g, R.MOD
    SG = MOD.full(R.PKG, MOD.HUD_SAVEGAME) + "_C"
    flags = {}
    h = helpers(R, flags)
    y = y0
    ce = h.event("OwlServerHudSet", [(p, "int", False) for p in ON_PINS] + [(p, "string", False) for p in TEXT_PINS],
                 y, R.RUN_ON_SERVER)
    _oc, a, ok = h.unlocked(ce, y)
    # the values, cleaned: 1/0 each, texts trimmed and cut to their limits
    p = h.arr_fn((ok, "then"), "Array_Clear", "SvHudOn", "int", (1000, y))
    for k, pin in enumerate(ON_PINS):
        p = h.arr_fn(p, "Array_Add", "SvHudOn", "int", (1300 + 300 * k, y),
                     item=h.clamp((ce, pin), (0, 1), (1300 + 300 * k, y + 450)))
    x = 1300 + 300 * len(ON_PINS)
    p = h.arr_fn(p, "Array_Clear", "SvHudText", "string", (x, y))
    for j, pin in enumerate(TEXT_PINS):
        limit = [n for _k, _l, _d, n in D.HUD_ITEMS][j]
        tr = g.call("Trim", KSTR, pos=(x + 300 + 400 * j, y + 450))
        g.wire(ce, pin, tr, "SourceString", exec=False)
        lf = g.call("Left", KSTR, pos=(x + 300 + 400 * j, y + 600))
        g.wire(tr, "ReturnValue", lf, "SourceString", exec=False)
        g.typed_input(lf, "Count", str(limit), "int")
        p = h.arr_fn(p, "Array_Add", "SvHudText", "string", (x + 300 + 400 * j, y), item=(lf, "ReturnValue"))
    # the save: a fresh object holding both arrays, written over the old one
    x += 300 + 400 * len(TEXT_PINS)
    crt = g.call("CreateSaveGameObject", GS, pos=(x, y))
    cp = crt.pin("SaveGameClass").typed("class", ir.obj_path("/Script/Engine.SaveGame"), direction="EGPD_Input")
    cp.set("PinType.bIsUObjectWrapper", "True")
    cp.set("DefaultObject", '"%s"' % SG)
    crt.pin("ReturnValue").typed("object", ir.obj_path(SG), direction="EGPD_Output")
    g.wire(p[0], p[1], crt, "execute")
    p = (crt, "then")
    for k, (field, var, t) in enumerate((("On", "SvHudOn", "int"), ("Text", "SvHudText", "string"))):
        st = g.var_set(field, t, pos=(x + 300 + 300 * k, y), parent=SG)
        st.pin(field).set("PinType.ContainerType", "Array")
        g.wire(crt, "ReturnValue", st, "self", exec=False)
        src = h.get(var, t, (x + 300 + 300 * k, y + 300), arr=True)
        g.wire(src[0], src[1], st, field, exec=False)
        g.wire(p[0], p[1], st, "execute")
        p = (st, "then")
    sav = g.call("SaveGameToSlot", GS, pos=(x + 1000, y))
    g.wire(crt, "ReturnValue", sav, "SaveGameObject", exec=False)
    g.typed_input(sav, "SlotName", MOD.HUD_SLOT, "string")
    g.typed_input(sav, "UserIndex", "0", "int")
    g.wire(p[0], p[1], sav, "execute")
    # the controller's replicated copy, then its version: every HUD and admin menu reloads
    x += 1300
    ctrl = a.controller(sav, "then", (x, y))
    p = (ctrl, "then")
    for k, (field, var, t) in enumerate((("HudOn", "SvHudOn", "int"), ("HudText", "SvHudText", "string"))):
        st = g.var_set(field, t, pos=(x + 300 + 300 * k, y), parent=R.CTRL_CLS)
        st.pin(field).set("PinType.ContainerType", "Array")
        g.wire(ctrl, "ReturnValue", st, "self", exec=False)
        src = h.get(var, t, (x + 300 + 300 * k, y + 300), arr=True)
        g.wire(src[0], src[1], st, field, exec=False)
        g.wire(p[0], p[1], st, "execute")
        p = (st, "then")
    cur = g.var_get("HudVer", "int", parent=R.CTRL_CLS, pos=(x + 900, y + 300))
    g.wire(ctrl, "ReturnValue", cur, "self", exec=False)
    inc = h.op("Add_IntInt", (cur, "HudVer"), "1", (x + 1100, y + 300))
    sv = g.var_set("HudVer", "int", pos=(x + 1000, y), parent=R.CTRL_CLS)
    g.wire(ctrl, "ReturnValue", sv, "self", exec=False)
    g.wire(inc[0], inc[1], sv, "HudVer", exec=False)
    g.wire(p[0], p[1], sv, "execute")
    c = h.call_self("OwlClientHudSaved", SENT_PINS, (x + 1300, y))
    c.pin("Ok").literal("true")
    c.pin("Msg").literal(SAVED)
    g.wire(sv, "then", c, "execute")
    h.client_event("OwlClientHudSaved", SENT_PINS, ["HudOk", "HudMsg"], "HudSavedVer", y + 1500)
    return flags
