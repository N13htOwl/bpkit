"""Kits, the server side: the relay's (10) kit events.

Admins (unlocked; the admin menu's Kits tab and Characters, Item catalog):
    OwlServerKitAdd(Kit, Id, Qty, Name)   one entry onto a kit (at most menu_defs.KIT_MAX_ITEMS)
    OwlServerKitRemove(Entry)             an entry, by its place in the controller's Kit* arrays
    OwlServerKitName(Kit, Name)           rename a kit (trimmed, at most KIT_NAME_MAX characters)
    each -> OwlClientKitAdmin(Msg)
Every player (the player menu's Kits tab):
    OwlServerKitStatus()      -> OwlClientKitStatus(Left): per kit, minutes until it can be
                                 claimed: 0 ready, -1 kit off, -2 kits off, -3 kit empty
    OwlServerKitClaim(Kit)    -> OwlClientKit(Ok, Msg), then the status again

The kits live on the controller (kits_ctrl: KitNames, KitEKit / KitEIds / KitEQty / KitENames,
replicated) and in the OwlKits save, written after each change. The kit settings are the menu's
(menu_defs "kitson", "kitlog", kit<n>on, kit<n>cd), read from the controller's AppliedSettings,
or their defaults while no settings were ever saved. A player's claims: OwlKit_<net id>, Last =
the minute (Unix time / 60) of each kit's last claim. A claim is refused, before anything is
given, unless the backpack has the room every item needs (GetSpaceNeededForItems summed against
GetFreeSpaceCount); then each item is added with AddItemTemplate. With "kitlog" on, the claim is
added to the player's admin log (their OwlCe save, if they have one).
"""
from bpkit import ir
import menu_defs as D
from ce_server import helpers, KSTR, KTXT, KSL, KML, GS, CHAR, INV, CS
from ce_panel import _Ctx

ENTRY = (("KitEKit", "int"), ("KitEIds", "int"), ("KitEQty", "int"), ("KitENames", "string"))
SAVE_FIELDS = (("KitNames", "Names", "string"), ("KitEKit", "EKit", "int"), ("KitEIds", "EIds", "int"),
               ("KitEQty", "EQty", "int"), ("KitENames", "ENames", "string"))
OK_PINS = [("Ok", "bool", False), ("Msg", "string", False)]
MSG_PINS = [("Msg", "string", False)]
LEFT_PINS = [("Left", "int", True)]
N = D.N_KITS
KIT_ON = [D.index("kit%don" % (k + 1)) for k in range(N)]
KIT_CD = [D.index("kit%dcd" % (k + 1)) for k in range(N)]
KITS_ON, KIT_LOG = D.index("kitson"), D.index("kitlog")
DEF = {st["id"]: st["default"] for st in D.SETTINGS}
NO_CHAR = "You need a character to claim a kit."
LEFT_TEXT = {-2: "Kits are turned off on this server.", -1: "This kit is turned off.", -3: "This kit is empty."}


def variables(unreal, bel):
    """(name, type) for the relay: Kit* = the owner's copy of the answers, SvKit* = the server's."""
    i, s, b = (bel.get_basic_type_by_name(t) for t in ("int", "string", "bool"))
    ints = bel.get_array_type(i)
    return [("KitOk", b), ("KitMsg", s), ("KitMsgVer", i), ("KitAMsg", s), ("KitAMsgVer", i),
            ("KitLeft", ints), ("KitLeftVer", i),
            ("SvKitOn", ints), ("SvKitCd", ints), ("SvKitCnt", ints), ("SvKitLeft", ints), ("SvKitLog", b),
            ("SvKitN", i), ("SvKitNow", i), ("SvKitNeed", i), ("SvKitSlot", s),
            ("SvKitClaim", bel.get_object_reference_type(unreal.SaveGame.static_class()))]


def build(R, y0):
    """Add the kit events to R.g from y0 down (R as for ce_server.build). Returns {event: net flags}."""
    g, MOD = R.g, R.MOD
    KITS_SG = MOD.full(R.PKG, MOD.KITS_SAVEGAME) + "_C"
    CLAIM_SG = MOD.full(R.PKG, MOD.KITCLAIM_SAVEGAME) + "_C"
    CE_SG = MOD.full(R.PKG, MOD.CE_SAVEGAME) + "_C"
    CTRL = R.CTRL_CLS
    SAVEOBJ = ir.obj_path("/Script/Engine.SaveGame")
    flags = {}
    h = helpers(R, flags)
    c = _Ctx(g, None, None, None)
    lit = lambda v: v if isinstance(v, tuple) else (str(v), "int")
    imath = lambda fn, a, b, pos: c.fn(fn, KML, {"A": lit(a), "B": lit(b)}, pos)

    def controller(pos):
        """GetActorOfClass(controller) from the exits; returns its (node, pin)."""
        gac = R.Auth(g, CTRL, R.SG_CLS, MOD.SAVE_SLOT, None).controller(c.exits[0][0], c.exits[0][1], pos)
        for e, ep in c.exits[1:]:
            g.wire(e, ep, gac, "execute")
        c.exits = [(gac, "then")]
        return (gac, "ReturnValue")

    def cvar(ctrl, name, cat, pos, arr=False):
        n = g.var_get(name, cat, parent=CTRL, pos=pos)
        if arr:
            n.pin(name).set("PinType.ContainerType", "Array")
        g.wire(ctrl[0], ctrl[1], n, "self", exec=False)
        return (n, name)

    def mine(name, cat, pos):
        return h.get(name, cat, pos, arr=True)

    def at(arr, idx, cat, pos):
        return (g.array_get(arr[0], arr[1], idx, pos, elem_cat=cat), "Output")

    def arr_call(fn, arr, pos, cat="int", item=None, index=None):
        """Array_Add / Array_Clear / Array_Set / Array_Remove (by index) on arr, in the exec chain."""
        n = g.array_fn(fn, pos=pos, elem_cat=cat)
        g.wire(arr[0], arr[1], n, "TargetArray", exec=False)
        if index is not None:
            ip = "IndexToRemove" if fn == "Array_Remove" else "Index"
            n.pin(ip).typed("int", direction="EGPD_Input")
            h.wire_in(index, n, ip)
        if item is not None:
            pin = "Item" if fn == "Array_Set" else "NewItem"
            g.array_item_pin(n, pin, cat)
            h.wire_in(item, n, pin, cat)
        return c.go(n)

    def bump_ctrl(ctrl, pos):
        st = g.var_set("KitVer", "int", parent=CTRL, pos=pos)
        g.wire(ctrl[0], ctrl[1], st, "self", exec=False)
        h.wire_in(imath("Add_IntInt", cvar(ctrl, "KitVer", "int", (pos[0], pos[1] + 300)), 1, (pos[0] + 200, pos[1] + 300)),
                  st, "KitVer")
        return c.go(st)

    def save_kits(ctrl, pos):
        """A fresh OwlKits save from the controller's arrays."""
        x, y = pos
        crt = g.call("CreateSaveGameObject", GS, pos=(x, y))
        cp = crt.pin("SaveGameClass").typed("class", SAVEOBJ, direction="EGPD_Input")
        cp.set("PinType.bIsUObjectWrapper", "True")
        cp.set("DefaultObject", '"%s"' % KITS_SG)
        crt.pin("ReturnValue").typed("object", ir.obj_path(KITS_SG), direction="EGPD_Output")
        c.go(crt)
        for k, (var, field, cat) in enumerate(SAVE_FIELDS):
            st = g.var_set(field, cat, pos=(x + 300 * (k + 1), y), parent=KITS_SG)
            st.pin(field).set("PinType.ContainerType", "Array")
            g.wire(crt, "ReturnValue", st, "self", exec=False)
            g.wire(*cvar(ctrl, var, cat, (x + 300 * (k + 1), y + 300), arr=True), st, field, exec=False)
            c.go(st)
        sav = g.call("SaveGameToSlot", GS, pos=(x + 300 * (len(SAVE_FIELDS) + 1), y))
        g.wire(crt, "ReturnValue", sav, "SaveGameObject", exec=False)
        g.typed_input(sav, "SlotName", MOD.KITS_SLOT, "string")
        g.typed_input(sav, "UserIndex", "0", "int")
        c.go(sav)

    def reply_admin(msg, pos):
        call = h.call_self("OwlClientKitAdmin", MSG_PINS, pos)
        h.wire_in(msg, call, "Msg", "string")
        c.go(call)

    def reply(ok, msg, pos):
        call = h.call_self("OwlClientKit", OK_PINS, pos)
        call.pin("Ok").literal("true" if ok else "false")
        h.wire_in(msg, call, "Msg", "string")
        c.go(call)

    def kit_idx(src, pos):
        return h.clamp(src, (0, N - 1), pos)

    def kit_name(ctrl, kit, pos):
        return at(cvar(ctrl, "KitNames", "string", pos, arr=True), kit, "string", (pos[0] + 200, pos[1]))

    def admin_event(name, pins, y):
        ce = h.event(name, pins, y, R.RUN_ON_SERVER)
        oc, a, ok = h.unlocked(ce, y)
        c.exits = [(ok, "then")]
        return ce, oc

    # ================================================================ admins
    # ---- add an entry
    y = y0
    ce, _oc = admin_event("OwlServerKitAdd", [("Kit", "int", False), ("Id", "int", False), ("Qty", "int", False),
                                              ("Name", "string", False)], y)
    ctrl = controller((1000, y))
    kit = kit_idx((ce, "Kit"), (1200, y + 900))
    # how many entries the kit has now
    c.set_var("SvKitN", "int", "0", (1300, y))
    each = c.foreach("int", cvar(ctrl, "KitEKit", "int", (1400, y + 300), arr=True), (1600, y))
    bm = c.branch(imath("EqualEqual_IntInt", (each, "Array Element"), kit, (1900, y + 300)), (1900, y))
    c.exits = [(bm, "then")]
    c.set_var("SvKitN", "int", imath("Add_IntInt", c.var("SvKitN", "int", (2100, y + 300)), 1, (2300, y + 300)), (2200, y))
    c.exits = [(each, "Completed")]
    bf = c.branch(imath("Less_IntInt", c.var("SvKitN", "int", (2500, y + 300)), D.KIT_MAX_ITEMS, (2700, y + 300)), (2700, y))
    c.exits = [(bf, "else")]
    reply_admin(h.text([kit_name(ctrl, kit, (2900, y + 900)), " is full: %d items at most." % D.KIT_MAX_ITEMS],
                       (3100, y + 900)), (3000, y + 600))
    c.exits = [(bf, "then")]
    x = 3000
    qty = h.clamp((ce, "Qty"), (1, 9999), (x, y + 900))
    for k, ((var, cat), src) in enumerate(zip(ENTRY, (kit, (ce, "Id"), qty, (ce, "Name")))):
        arr_call("Array_Add", cvar(ctrl, var, cat, (x + 300 * k, y + 300), arr=True), (x + 300 * k, y), cat, item=src)
    x += 1300
    bump_ctrl(ctrl, (x, y))
    save_kits(ctrl, (x + 300, y))
    reply_admin(h.text(["Added ", (ce, "Name"), " x", qty + ("int",), " to ", kit_name(ctrl, kit, (x + 2500, y + 900)), "."],
                       (x + 2600, y + 900)), (x + 2600, y))

    # ---- remove an entry
    y = y0 + 2000
    ce, _oc = admin_event("OwlServerKitRemove", [("Entry", "int", False)], y)
    ctrl = controller((1000, y))
    n = (g.array_len(*cvar(ctrl, "KitEKit", "int", (1100, y + 500), arr=True), (1300, y + 500), elem_cat="int"),
         "ReturnValue")
    okidx = c.fn("BooleanAND", KML, {"A": imath("GreaterEqual_IntInt", (ce, "Entry"), 0, (1500, y + 400)),
                                     "B": imath("Less_IntInt", (ce, "Entry"), n, (1500, y + 550))}, (1700, y + 450))
    bi = c.branch(okidx, (1500, y))
    c.exits = [(bi, "else")]
    reply_admin("That item isn't in the kit any more.", (1800, y + 600))
    c.exits = [(bi, "then")]
    x = 1800
    for k, (var, cat) in enumerate(ENTRY):
        arr_call("Array_Remove", cvar(ctrl, var, cat, (x + 300 * k, y + 300), arr=True), (x + 300 * k, y), cat,
                 index=(ce, "Entry"))
    x += 1300
    bump_ctrl(ctrl, (x, y))
    save_kits(ctrl, (x + 300, y))
    reply_admin("Removed.", (x + 2600, y))

    # ---- rename a kit
    y = y0 + 3500
    ce, _oc = admin_event("OwlServerKitName", [("Kit", "int", False), ("Name", "string", False)], y)
    ctrl = controller((1000, y))
    kit = kit_idx((ce, "Kit"), (1200, y + 900))
    trimmed = c.fn("Left", KSTR, {"SourceString": c.fn("Trim", KSTR, {"SourceString": (ce, "Name")}, (1200, y + 600)),
                                  "Count": (str(D.KIT_NAME_MAX), "int")}, (1400, y + 600))
    be = c.branch(imath("Greater_IntInt", c.fn("Len", KSTR, {"S": trimmed}, (1600, y + 450)), 0, (1800, y + 450)), (1800, y))
    c.exits = [(be, "else")]
    reply_admin("Type a name for the kit first.", (2100, y + 600))
    c.exits = [(be, "then")]
    arr_call("Array_Set", cvar(ctrl, "KitNames", "string", (2100, y + 300), arr=True), (2100, y), "string",
             item=trimmed, index=kit)
    bump_ctrl(ctrl, (2400, y))
    save_kits(ctrl, (2700, y))
    reply_admin(h.text(["Renamed to ", trimmed, "."], (5000, y + 600)), (5000, y))

    # ================================================================ players
    def kit_settings(ctrl, pos):
        """SvKitOn (1/0 per kit, with "kitson") and SvKitCd (minutes per kit), SvKitLog: from the
        controller's AppliedSettings when it holds every setting, else the defaults."""
        x, y = pos
        applied = lambda p: cvar(ctrl, "AppliedSettings", "string", p, arr=True)
        full = imath("GreaterEqual_IntInt", (g.array_len(*applied((x, y + 300)), (x + 200, y + 300), elem_cat="string"),
                                             "ReturnValue"), len(D.SETTINGS), (x + 400, y + 300))
        b = c.branch(full, (x + 400, y))
        ends = []
        for side, live in (("then", True), ("else", False)):
            c.exits = [(b, side)]
            yy = y + (0 if live else 1500)
            xx = x + 700
            arr_call("Array_Clear", mine("SvKitOn", "int", (xx, yy + 300)), (xx, yy))
            arr_call("Array_Clear", mine("SvKitCd", "int", (xx + 300, yy + 300)), (xx + 300, yy))
            xx += 600

            def val(index, pos):
                """the setting at index as an int (StringToDouble, rounded)."""
                s = at(applied(pos), index, "string", (pos[0] + 200, pos[1]))
                return c.fn("Round", KML, {"A": c.fn("Conv_StringToDouble", KSTR, {"InString": s}, (pos[0] + 400, pos[1]))},
                            (pos[0] + 600, pos[1]))

            for k in range(N):
                if live:
                    on = imath("Multiply_IntInt", val(KITS_ON, (xx, yy + 600)), val(KIT_ON[k], (xx, yy + 800)),
                               (xx + 800, yy + 700))
                    cd = val(KIT_CD[k], (xx, yy + 1000))
                else:
                    on = str(int(DEF["kitson"] and DEF["kit%don" % (k + 1)]))
                    cd = str(int(DEF["kit%dcd" % (k + 1)]))
                arr_call("Array_Add", mine("SvKitOn", "int", (xx + 900, yy + 300)), (xx + 900, yy), item=on)
                arr_call("Array_Add", mine("SvKitCd", "int", (xx + 1200, yy + 300)), (xx + 1200, yy), item=cd)
                xx += 1500
            if live:
                c.set_var("SvKitLog", "bool", imath("Greater_IntInt", val(KIT_LOG, (xx, yy + 600)), 0, (xx + 800, yy + 600)),
                          (xx, yy))
                c.set_var("SvKitN", "int", val(KITS_ON, (xx + 300, yy + 900)), (xx + 300, yy))   # "kitson" alone
            else:
                c.set_var("SvKitLog", "bool", "true" if DEF["kitlog"] else "false", (xx, yy))
                c.set_var("SvKitN", "int", str(int(DEF["kitson"])), (xx + 300, yy))
            ends += c.exits
        c.exits = ends

    def counts(ctrl, pos):
        """SvKitCnt: entries per kit."""
        x, y = pos
        arr_call("Array_Clear", mine("SvKitCnt", "int", (x, y + 300)), (x, y))
        for k in range(N):
            arr_call("Array_Add", mine("SvKitCnt", "int", (x + 300 + 300 * k, y + 300)), (x + 300 + 300 * k, y), item="0")
        x += 300 + 300 * N
        each = c.foreach("int", cvar(ctrl, "KitEKit", "int", (x, y + 300), arr=True), (x + 200, y))
        kk = kit_idx((each, "Array Element"), (x + 400, y + 600))
        arr_call("Array_Set", mine("SvKitCnt", "int", (x + 500, y + 300)), (x + 600, y), item=imath(
            "Add_IntInt", at(mine("SvKitCnt", "int", (x + 500, y + 750)), kk, "int", (x + 700, y + 750)), 1, (x + 900, y + 750)),
            index=kk)
        c.exits = [(each, "Completed")]

    def claim_save(oc, pos):
        """SvKitClaim = the player's OwlKit_<net id> save (a new one if none), its Last padded to
        a value per kit; SvKitSlot = its slot."""
        x, y = pos
        slot = (R.save_slot(oc, (x, y + 600), prefix=MOD.KITCLAIM_SLOT_PREFIX), "ReturnValue")
        c.set_var("SvKitSlot", "string", slot, (x, y))
        slot = h.get("SvKitSlot", "string", (x + 300, y + 450))
        sc, missing = h.load(c.exits, slot, CLAIM_SG, (x + 300, y))
        have = g.var_set("SvKitClaim", "object", SAVEOBJ, pos=(x + 1400, y))
        g.wire(sc, h.save_as(CLAIM_SG), have, "SvKitClaim", exec=False)
        g.wire(sc, "then", have, "execute")
        crt = g.call("CreateSaveGameObject", GS, pos=(x + 1100, y + 500))
        cp = crt.pin("SaveGameClass").typed("class", SAVEOBJ, direction="EGPD_Input")
        cp.set("PinType.bIsUObjectWrapper", "True")
        cp.set("DefaultObject", '"%s"' % CLAIM_SG)
        crt.pin("ReturnValue").typed("object", ir.obj_path(CLAIM_SG), direction="EGPD_Output")
        for e, ep in missing:
            g.wire(e, ep, crt, "execute")
        new = g.var_set("SvKitClaim", "object", SAVEOBJ, pos=(x + 1400, y + 500))
        g.wire(crt, "ReturnValue", new, "SvKitClaim", exec=False)
        g.wire(crt, "then", new, "execute")
        c.exits = [(have, "then"), (new, "then")]
        x += 1700
        cast = g.cast(CLAIM_SG, pos=(x, y))
        g.wire(*claim_obj((x - 200, y + 300)), cast, "Object", exec=False)
        c.go(cast)
        AS = h.save_as(CLAIM_SG)
        last = lambda p: _last(cast, AS, p)
        for k in range(N):
            bk = c.branch(imath("EqualEqual_IntInt", (g.array_len(*last((x + 300 + 600 * k, y + 450)),
                                                                   (x + 500 + 600 * k, y + 450), elem_cat="int"),
                                                      "ReturnValue"), k, (x + 600 + 600 * k, y + 450)),
                          (x + 300 + 600 * k, y))
            c.exits = [(bk, "then")]
            arr_call("Array_Add", last((x + 600 + 600 * k, y + 300)), (x + 600 + 600 * k, y), item="0")
            c.exits += [(bk, "else")]
        return cast, AS

    def claim_obj(pos):
        return (g.var_get("SvKitClaim", "object", SAVEOBJ, pos=pos), "SvKitClaim")

    def _last(cast, AS, pos):
        n = g.var_get("Last", "int", parent=CLAIM_SG, pos=pos)
        n.pin("Last").set("PinType.ContainerType", "Array")
        g.wire(cast, AS, n, "self", exec=False)
        return (n, "Last")

    def now_minute(pos):
        x, y = pos
        ts = c.fn("ToUnixTimestamp", KML, {"Time": c.fn("UtcNow", KML, {}, (x, y))}, (x + 200, y))
        mins = c.fn("Divide_Int64Int64", KML, {"A": ts, "B": ("60", "int64")}, (x + 400, y))
        return c.fn("Conv_Int64ToInt", KML, {"InInt": mins}, (x + 600, y))

    def status(cast, AS, pos):
        """SvKitLeft per kit (see the module docstring), from SvKitOn / SvKitCd / SvKitCnt, the
        claim save's Last and SvKitNow."""
        x, y = pos
        c.set_var("SvKitNow", "int", now_minute((x, y + 400)), (x, y))
        arr_call("Array_Clear", mine("SvKitLeft", "int", (x + 300, y + 300)), (x + 300, y))
        x += 600
        now = lambda p: c.var("SvKitNow", "int", p)
        for k in range(N):
            xx = x + 1600 * k
            last = at(_last(cast, AS, (xx, y + 600)), k, "int", (xx + 200, y + 600))
            due = imath("Add_IntInt", last, at(mine("SvKitCd", "int", (xx, y + 750)), k, "int", (xx + 200, y + 750)),
                        (xx + 400, y + 650))
            wait = c.fn("SelectInt", KML, {"A": imath("Max", imath("Subtract_IntInt", due, now((xx + 400, y + 900)),
                                                                   (xx + 600, y + 800)), 0, (xx + 800, y + 800)),
                                           "B": ("0", "int"),
                                           "bPickA": imath("Greater_IntInt", last, 0, (xx + 600, y + 950))},
                        (xx + 1000, y + 700))
            filled = c.fn("SelectInt", KML, {"A": wait, "B": ("-3", "int"),
                                             "bPickA": imath("Greater_IntInt", at(mine("SvKitCnt", "int", (xx, y + 1100)), k,
                                                                                   "int", (xx + 200, y + 1100)), 0,
                                                             (xx + 400, y + 1100))}, (xx + 1200, y + 900))
            off = c.fn("SelectInt", KML, {"A": ("-1", "int"), "B": ("-2", "int"),
                                          "bPickA": imath("Greater_IntInt", c.var("SvKitN", "int", (xx, y + 1300)), 0,
                                                          (xx + 200, y + 1300))}, (xx + 1200, y + 1250))
            left = c.fn("SelectInt", KML, {"A": filled, "B": off,
                                           "bPickA": imath("Greater_IntInt", at(mine("SvKitOn", "int", (xx, y + 1450)), k,
                                                                                 "int", (xx + 200, y + 1450)), 0,
                                                           (xx + 400, y + 1450))}, (xx + 1400, y + 1100))
            arr_call("Array_Add", mine("SvKitLeft", "int", (xx + 1300, y + 300)), (xx + 1300, y), item=left)

    def gather(oc, y):
        """settings, counts, the claim save and the status, in that order; returns (cast, AS)."""
        ctrl = controller((1000, y))
        kit_settings(ctrl, (1300, y))
        counts(ctrl, (8500, y))
        cast, AS = claim_save(oc, (10500, y))
        status(cast, AS, (14500, y))
        return ctrl, cast, AS

    def send_status(pos):
        call = h.call_self("OwlClientKitStatus", LEFT_PINS, pos)
        g.wire(*mine("SvKitLeft", "int", (pos[0] - 200, pos[1] + 300)), call, "Left", exec=False)
        c.go(call)

    # ---- status
    y = y0 + 5000
    ce = h.event("OwlServerKitStatus", [], y, R.RUN_ON_SERVER)
    oc = R.owner_pc(ce, "then", (300, y))
    c.exits = [(oc, "then")]
    gather(oc, y)
    send_status((20000, y))

    # ---- claim
    y = y0 + 9000
    ce = h.event("OwlServerKitClaim", [("Kit", "int", False)], y, R.RUN_ON_SERVER)
    oc = R.owner_pc(ce, "then", (300, y))
    c.exits = [(oc, "then")]
    ctrl, cast, AS = gather(oc, y)
    kit = kit_idx((ce, "Kit"), (20000, y + 900))
    left = at(mine("SvKitLeft", "int", (20000, y + 600)), kit, "int", (20200, y + 600))
    x = 20500
    # not ready: say why
    br = c.branch(imath("EqualEqual_IntInt", left, 0, (x, y + 300)), (x, y))
    c.exits = [(br, "else")]
    xx = x + 300
    for code, msg in LEFT_TEXT.items():
        bc = c.branch(imath("EqualEqual_IntInt", left, code, (xx, y + 1300)), (xx, y + 1000))
        c.exits = [(bc, "then")]
        reply(False, msg, (xx + 300, y + 1300))
        c.exits = [(bc, "else")]
        xx += 700
    hours = imath("Divide_IntInt", left, 60, (xx, y + 1500))
    reply(False, h.text(["Ready again in ", hours + ("int",), "h ", imath("Percent_IntInt", left, 60, (xx, y + 1650)) + ("int",),
                         "m."], (xx + 200, y + 1500)), (xx + 300, y + 1000))
    # ready: a character with the room for every item of the kit
    c.exits = [(br, "then")]
    pawn = g.call("K2_GetPawn", "/Script/Engine.Controller", pos=(x + 300, y + 300))
    g.wire(oc, "AsConan Player Controller", pawn, "self", exec=False)
    chc = g.cast(CHAR, pos=(x + 300, y))
    g.wire(pawn, "ReturnValue", chc, "Object", exec=False)
    c.go(chc)
    c.exits = [(chc, "CastFailed")]
    reply(False, NO_CHAR, (x + 600, y + 700))
    c.exits = [(chc, "then")]
    inv = g.call("GetInventoryByType", INV, pos=(x + 600, y + 400))
    g.wire(chc, "AsConan Character", inv, "owner", exec=False)
    g.typed_input(inv, "inventoryType", "Backpack", "byte", ir.enum_path(CS + "EInventoryType"))
    x += 900
    c.set_var("SvKitNeed", "int", "0", (x, y))
    eks = lambda p: cvar(ctrl, "KitEKit", "int", p, arr=True)
    each = c.foreach("int", eks((x + 200, y + 300)), (x + 400, y))
    bm = c.branch(imath("EqualEqual_IntInt", (each, "Array Element"), kit, (x + 700, y + 300)), (x + 700, y))
    c.exits = [(bm, "then")]
    need = c.fn("GetSpaceNeededForItems", INV, {"self": (inv, "ReturnValue"),
                                                "templateID": at(cvar(ctrl, "KitEIds", "int", (x + 800, y + 600), arr=True),
                                                                 (each, "Array Index"), "int", (x + 1000, y + 600)),
                                                "count": at(cvar(ctrl, "KitEQty", "int", (x + 800, y + 750), arr=True),
                                                            (each, "Array Index"), "int", (x + 1000, y + 750))},
                (x + 1200, y + 600))
    c.set_var("SvKitNeed", "int", imath("Add_IntInt", c.var("SvKitNeed", "int", (x + 1200, y + 450)), need,
                                        (x + 1400, y + 450)), (x + 1000, y))
    c.exits = [(each, "Completed")]
    x += 1700
    free = c.fn("GetFreeSpaceCount", INV, {"self": (inv, "ReturnValue")}, (x, y + 600))
    bs = c.branch(imath("LessEqual_IntInt", c.var("SvKitNeed", "int", (x, y + 450)), free, (x + 200, y + 450)), (x + 200, y))
    c.exits = [(bs, "else")]
    reply(False, h.text(["Not enough room in your backpack: this kit needs ", h.get("SvKitNeed", "int", (x + 300, y + 1600))
                         + ("int",), " free slots, you have ", free + ("int",), "."], (x + 400, y + 1500)), (x + 500, y + 1000))
    c.exits = [(bs, "then")]
    x += 600
    # give every item of the kit
    each = c.foreach("int", eks((x, y + 300)), (x + 200, y))
    bm = c.branch(imath("EqualEqual_IntInt", (each, "Array Element"), kit, (x + 500, y + 300)), (x + 500, y))
    c.exits = [(bm, "then")]
    ad = g.call("AddItemTemplate", INV, pos=(x + 800, y))
    g.wire(inv, "ReturnValue", ad, "self", exec=False)
    g.wire(*at(cvar(ctrl, "KitEIds", "int", (x + 600, y + 400), arr=True), (each, "Array Index"), "int", (x + 800, y + 400)),
           ad, "templateID", exec=False)
    g.typed_input(ad, "index", "-1", "int")
    g.typed_input(ad, "context", MOD.CE_CONTEXT, "name")
    g.wire(*at(cvar(ctrl, "KitEQty", "int", (x + 600, y + 550), arr=True), (each, "Array Index"), "int", (x + 800, y + 550)),
           ad, "quantity", exec=False)
    c.go(ad)
    c.exits = [(each, "Completed")]
    x += 1300
    # the claim's minute into the player's save
    arr_call("Array_Set", _last(cast, AS, (x, y + 300)), (x + 200, y), item=c.var("SvKitNow", "int", (x, y + 450)), index=kit)
    sav = g.call("SaveGameToSlot", GS, pos=(x + 500, y))
    g.wire(*claim_obj((x + 300, y + 300)), sav, "SaveGameObject", exec=False)
    g.wire(*h.get("SvKitSlot", "string", (x + 300, y + 450)), sav, "SlotName", exec=False)
    g.typed_input(sav, "UserIndex", "0", "int")
    c.go(sav)
    x += 800
    # "kitlog": a line in the player's admin log, if they have a CE save
    bl = c.branch(c.var("SvKitLog", "bool", (x, y + 300)), (x, y))
    done = [(bl, "else")]
    ce_slot = (R.save_slot(oc, (x + 300, y + 900), prefix=MOD.CE_SLOT_PREFIX), "ReturnValue")
    lc, nolog = h.load([(bl, "then")], ce_slot, CE_SG, (x + 300, y))
    done += nolog
    p = h.set_line((lc, "then"), oc, ["Claimed ", kit_name(ctrl, kit, (x + 1300, y + 900))], (x + 1300, y))
    add = g.array_fn("Array_Add", pos=(x + 3000, y), elem_cat="string")
    g.array_item_pin(add, "NewItem", "string")
    lg = g.var_get("Log", "string", parent=CE_SG, pos=(x + 2800, y + 300))
    lg.pin("Log").set("PinType.ContainerType", "Array")
    g.wire(lc, h.save_as(CE_SG), lg, "self", exec=False)
    g.wire(lg, "Log", add, "TargetArray", exec=False)
    g.wire(*h.get("SvLine", "string", (x + 2800, y + 450)), add, "NewItem", exec=False)
    g.wire(p[0], p[1], add, "execute")
    lsav = g.call("SaveGameToSlot", GS, pos=(x + 3300, y))
    g.wire(lc, h.save_as(CE_SG), lsav, "SaveGameObject", exec=False)
    g.wire(ce_slot[0], ce_slot[1], lsav, "SlotName", exec=False)
    g.typed_input(lsav, "UserIndex", "0", "int")
    g.wire(add, "then", lsav, "execute")
    c.exits = done + [(lsav, "then")]
    x += 3600
    reply(True, h.text(["Claimed ", kit_name(ctrl, kit, (x, y + 900)), ". The items are in your backpack."],
                       (x + 200, y + 900)), (x + 300, y))
    # and the new status: the cooldown starts now
    status(cast, AS, (x + 600, y))
    send_status((x + 6000, y))

    h.client_event("OwlClientKit", OK_PINS, ["KitOk", "KitMsg"], "KitMsgVer", y0 + 12000)
    h.client_event("OwlClientKitAdmin", MSG_PINS, ["KitAMsg"], "KitAMsgVer", y0 + 12500)
    h.client_event("OwlClientKitStatus", LEFT_PINS, ["KitLeft"], "KitLeftVer", y0 + 13000)
    return flags
