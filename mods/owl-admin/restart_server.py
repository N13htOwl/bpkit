"""The Server Restart tab, the server side: the relay's (10) restart events. The admin menu's
Server Restart tab sends them through the admin's own relay.

    OwlServerRsSet(V0..V6)   -> OwlClientRsSaved(Ok, Msg)      admins (unlocked)
    OwlServerRsCount(Start)  -> OwlClientRsSaved(Ok, Msg)      admins (unlocked)

V<k> is menu_defs.RS_LIMITS[k]'s value (daily, time, the warnings, the sound). The server clamps
each to its limits, writes BP_OwlRestartSave (slot OwlRestart) and copies them into the
controller's (02) replicated RsVals, then raises RsVer. Start 1 begins a RS_COUNTDOWN countdown
now (the controller's RsManualEnd); 0 cancels the one on screen (a daily one is skipped through
RsSkipUntil). The controller's server tick (restart_ctrl) does the counting either way.
Owl Admin never restarts the server itself: the host's schedule does.
"""
from bpkit import ir
import menu_defs as D
from ce_server import helpers, KSL, GS

SENT_PINS = [("Ok", "bool", False), ("Msg", "string", False)]
VAL_PINS = ["V%d" % k for k in range(len(D.RS_LIMITS))]
SAVED = "Saved. The restart schedule is live for every player."
STARTED = "Countdown started: %d minutes. Players see the warnings you have on." % (D.RS_COUNTDOWN // 60)
CANCELLED = "Countdown cancelled. The banner clears for every player."


def variables(unreal, bel):
    """(name, type) for the relay: Rs* = the owner's copy the menu reads, SvRs* = the server's."""
    i, s, b = (bel.get_basic_type_by_name(t) for t in ("int", "string", "bool"))
    return [("RsOk", b), ("RsMsg", s), ("RsSavedVer", i), ("SvRsVals", bel.get_array_type(i))]


def build(R, y0):
    """Add the restart events to R.g from y0 down (R as for ce_server.build). Returns {event: net flags}."""
    g, MOD = R.g, R.MOD
    SG = MOD.full(R.PKG, MOD.RESTART_SAVEGAME) + "_C"
    flags = {}
    h = helpers(R, flags)

    def cset(prev, ctrl, name, src, pos, arr=False):
        """The controller's variable name = src (a (node, pin) or a literal int)."""
        st = g.var_set(name, "int", pos=pos, parent=R.CTRL_CLS)
        if arr:
            st.pin(name).set("PinType.ContainerType", "Array")
        g.wire(ctrl, "ReturnValue", st, "self", exec=False)
        h.wire_in(src, st, name)
        g.wire(prev[0], prev[1], st, "execute")
        return (st, "then")

    def cget(ctrl, name, pos):
        n = g.var_get(name, "int", pos=pos, parent=R.CTRL_CLS)
        g.wire(ctrl, "ReturnValue", n, "self", exec=False)
        return (n, name)

    def reply(prev, msg, pos):
        c = h.call_self("OwlClientRsSaved", SENT_PINS, pos)
        c.pin("Ok").literal("true")
        c.pin("Msg").literal(msg)
        g.wire(prev[0], prev[1], c, "execute")

    # ---- Save: the values, clamped, into the save and the controller
    y = y0
    ce = h.event("OwlServerRsSet", [(p, "int", False) for p in VAL_PINS], y, R.RUN_ON_SERVER)
    _oc, a, ok = h.unlocked(ce, y)
    p = h.arr_fn((ok, "then"), "Array_Clear", "SvRsVals", "int", (1000, y))
    for k, pin in enumerate(VAL_PINS):
        p = h.arr_fn(p, "Array_Add", "SvRsVals", "int", (1300 + 300 * k, y),
                     item=h.clamp((ce, pin), D.RS_LIMITS[k], (1300 + 300 * k, y + 450)))
    x = 1300 + 300 * len(VAL_PINS)
    crt = g.call("CreateSaveGameObject", GS, pos=(x, y))
    cp = crt.pin("SaveGameClass").typed("class", ir.obj_path("/Script/Engine.SaveGame"), direction="EGPD_Input")
    cp.set("PinType.bIsUObjectWrapper", "True")
    cp.set("DefaultObject", '"%s"' % SG)
    crt.pin("ReturnValue").typed("object", ir.obj_path(SG), direction="EGPD_Output")
    g.wire(p[0], p[1], crt, "execute")
    st = g.var_set("Vals", "int", pos=(x + 300, y), parent=SG)
    st.pin("Vals").set("PinType.ContainerType", "Array")
    g.wire(crt, "ReturnValue", st, "self", exec=False)
    src = h.get("SvRsVals", "int", (x + 300, y + 300), arr=True)
    g.wire(src[0], src[1], st, "Vals", exec=False)
    g.wire(crt, "then", st, "execute")
    sav = g.call("SaveGameToSlot", GS, pos=(x + 600, y))
    g.wire(crt, "ReturnValue", sav, "SaveGameObject", exec=False)
    g.typed_input(sav, "SlotName", MOD.RESTART_SLOT, "string")
    g.typed_input(sav, "UserIndex", "0", "int")
    g.wire(st, "then", sav, "execute")
    x += 900
    ctrl = a.controller(sav, "then", (x, y))
    p = cset((ctrl, "then"), ctrl, "RsVals", h.get("SvRsVals", "int", (x + 300, y + 300), arr=True), (x + 300, y),
             arr=True)
    p = cset(p, ctrl, "RsVer", h.op("Add_IntInt", cget(ctrl, "RsVer", (x + 500, y + 300)), "1", (x + 700, y + 300)),
             (x + 700, y))
    p = cset(p, ctrl, "RsNextCheck", "0", (x + 1000, y))          # the tick counts again at once
    reply(p, SAVED, (x + 1300, y))

    # ---- Start / cancel the countdown
    y = y0 + 1500
    ce = h.event("OwlServerRsCount", [("Start", "int", False)], y, R.RUN_ON_SERVER)
    _oc, a, ok = h.unlocked(ce, y)
    ctrl = a.controller(ok, "then", (1000, y))
    now = (g.call("FTrunc", "/Script/Engine.KismetMathLibrary", pos=(1300, y + 600)), "ReturnValue")
    g.wire(g.call("GetGameTimeInSeconds", KSL, pos=(1100, y + 600)), "ReturnValue", now[0], "A", exec=False)
    bs = h.branch((ctrl, "then"), h.op("EqualEqual_IntInt", (ce, "Start"), "1", (1300, y + 300)), (1300, y))
    # start: the end time, and no skip left over from an earlier cancel
    p = cset((bs, "then"), ctrl, "RsManualEnd", h.op("Add_IntInt", now, str(D.RS_COUNTDOWN), (1600, y + 450)),
             (1600, y))
    p = cset(p, ctrl, "RsSkipUntil", "0", (1900, y))
    p = cset(p, ctrl, "RsNextCheck", "0", (2200, y))
    reply(p, STARTED, (2500, y))
    # cancel: no manual countdown, and the daily one on screen skipped until it's past
    yc = y + 800
    p = cset((bs, "else"), ctrl, "RsManualEnd", "0", (1600, yc))
    left = h.op("Max", cget(ctrl, "RsLeft", (1700, yc + 450)), "0", (1900, yc + 450))
    skip = h.op("Add_IntInt", now, h.op("Add_IntInt", left, str(D.RS_AFTER + 5), (2100, yc + 450)), (2300, yc + 450))
    p = cset(p, ctrl, "RsSkipUntil", skip, (1900, yc))
    p = cset(p, ctrl, "RsNextCheck", "0", (2200, yc))
    reply(p, CANCELLED, (2500, yc))

    h.client_event("OwlClientRsSaved", SENT_PINS, ["RsOk", "RsMsg"], "RsSavedVer", y0 + 3000)
    return flags
