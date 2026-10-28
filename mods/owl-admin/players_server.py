"""The Players tab, the server side: the relay's (10) player events. The admin menu's Players tab
sends them through the admin's own relay; every one first checks the admin is unlocked.

    OwlServerPlBanList()           the admin's controller asks the game for its ban list
    OwlServerPlBan(State)          ban that player, then ask for the list again
    OwlServerPlUnban(Id, Name)     unban a banned-list entry (its UniqueNetIdRepl), then ask again
    OwlServerPlGoto(State)         the admin to that player
    OwlServerPlBring(State)        that player to the admin
    each -> OwlClientPl(Msg)       (not the list one)

Bans are Conan's own (ConanPlayerController.BanPlayer / UnbanPlayer / ServerGetBannedPlayerList,
server RPCs, called here on the admin's controller, on the server): the same list as the game's
admin panel, so a banned player can't rejoin. The game may only take them from a Conan admin; the
list then shows whether a ban took. The list itself reaches the admin's client through the
controller's SignalBannedPlayerListReady, which the admin menu binds (players_panel).
Teleports use the game's TeleportPlayerServer on the moving player's controller (its other
arguments left at their defaults), to a spot 1.5 m in front of the other player.
"""
from bpkit import ir
from ce_server import helpers, T, CPC, PSTATE, KTXT, KSL, KML

NETID = ir.struct_path("/Script/Engine.UniqueNetIdRepl")
T.setdefault("netid", ("struct", NETID))
ACTOR = "/Script/Engine.Actor"
CTRL = "/Script/Engine.Controller"
AHEAD = 150.0       # cm in front of the other player
MSG_PINS = [("Msg", "string", False)]
NO_ONE = "That player isn't online any more."
NOT_SELF = "Pick another player: that's you."


def variables(unreal, bel):
    """(name, type) for the relay: the owner's copy of the last answer."""
    return [("PlMsg", bel.get_basic_type_by_name("string")), ("PlMsgVer", bel.get_basic_type_by_name("int"))]


def build(R, y0):
    """Add the player events to R.g from y0 down (R as for ce_server.build). Returns {event: net flags}."""
    g = R.g
    flags = {}
    h = helpers(R, flags)

    def reply(prev, msg, pos):
        """OwlClientPl(msg): msg a literal or a (node, pin) string."""
        c = h.call_self("OwlClientPl", MSG_PINS, pos)
        h.wire_in(msg, c, "Msg", "string")
        g.wire(prev[0], prev[1], c, "execute")
        return c

    def ask_list(prev, oc, pos):
        n = g.call("ServerGetBannedPlayerList", CPC, pos=pos)
        g.wire(oc, "AsConan Player Controller", n, "self", exec=False)
        g.wire(prev[0], prev[1], n, "execute")
        return (n, "then")

    def name_of(state_src, pos):
        n = g.call("GetPlayerName", PSTATE, pos=pos)
        g.wire(state_src[0], state_src[1], n, "self", exec=False)
        return (n, "ReturnValue")

    def admin_state(oc, pos):
        n = g.var_get("PlayerState", "object", ir.obj_path(PSTATE), parent=CTRL, pos=pos)
        g.wire(oc, "AsConan Player Controller", n, "self", exec=False)
        return (n, "PlayerState")

    def pawn_of_ctrl(oc, pos):
        n = g.call("K2_GetPawn", CTRL, pos=pos)
        g.wire(oc, "AsConan Player Controller", n, "self", exec=False)
        return (n, "ReturnValue")

    def not_self(prev, ce, oc, y):
        """Branch: the target isn't the admin (else the NOT_SELF reply). Carry on from "then"."""
        same = h.op("EqualEqual_ObjectObject", (ce, "State"), admin_state(oc, (1000, y + 500)), (1250, y + 450))
        b = h.branch(prev, same, (1300, y))
        reply((b, "then"), NOT_SELF, (1600, y + 900))
        return (b, "else")

    def spot(pawn, pos):
        """pawn's location + its forward vector * AHEAD (pure)."""
        x, y = pos
        loc = g.call("K2_GetActorLocation", ACTOR, pos=(x, y))
        g.wire(pawn[0], pawn[1], loc, "self", exec=False)
        fwd = g.call("GetActorForwardVector", ACTOR, pos=(x, y + 150))
        g.wire(pawn[0], pawn[1], fwd, "self", exec=False)
        sc = g.call("Multiply_VectorFloat", KML, pos=(x + 250, y + 150))
        g.wire(fwd, "ReturnValue", sc, "A", exec=False)
        g.typed_input(sc, "B", str(AHEAD), "real")
        add = g.call("Add_VectorVector", KML, pos=(x + 500, y))
        g.wire(loc, "ReturnValue", add, "A", exec=False)
        g.wire(sc, "ReturnValue", add, "B", exec=False)
        return (add, "ReturnValue")

    def teleport(prev, ctrl_src, mover, dest, pos):
        """ctrl_src's TeleportPlayerServer(dest, the mover's own rotation)."""
        x, y = pos
        rot = g.call("K2_GetActorRotation", ACTOR, pos=(x, y + 300))
        g.wire(mover[0], mover[1], rot, "self", exec=False)
        t = g.call("TeleportPlayerServer", CPC, pos=(x + 300, y))
        g.wire(ctrl_src[0], ctrl_src[1], t, "self", exec=False)
        g.wire(dest[0], dest[1], t, "TargetLocation", exec=False)
        g.wire(rot, "ReturnValue", t, "TargetRotation", exec=False)
        g.wire(prev[0], prev[1], t, "execute")
        return (t, "then")

    def valid(prev, obj, pos, msg):
        """Branch on IsValid(obj): carry on from "then"; else reply msg."""
        iv = g.call("IsValid", KSL, pos=(pos[0], pos[1] + 300))
        g.wire(obj[0], obj[1], iv, "Object", exec=False)
        b = h.branch(prev, (iv, "ReturnValue"), pos)
        reply((b, "else"), msg, (pos[0] + 300, pos[1] + 900))
        return (b, "then")

    # ---- the ban list
    y = y0
    ce = h.event("OwlServerPlBanList", [], y, R.RUN_ON_SERVER)
    oc, _a, ok = h.unlocked(ce, y)
    ask_list((ok, "then"), oc, (1000, y))

    # ---- ban
    y = y0 + 1500
    ce = h.event("OwlServerPlBan", [("State", "state", False)], y, R.RUN_ON_SERVER)
    oc, _a, ok = h.unlocked(ce, y)
    p = valid((ok, "then"), (ce, "State"), (900, y), NO_ONE)
    p = not_self(p, ce, oc, y)
    nid = g.call("BP_GetUniqueId", PSTATE, pos=(1700, y + 300))
    g.wire(ce, "State", nid, "self", exec=False)
    name = name_of((ce, "State"), (1700, y + 450))
    nick = g.call("Conv_StringToText", KTXT, pos=(1950, y + 450))
    g.wire(name[0], name[1], nick, "InString", exec=False)
    ban = g.call("BanPlayer", CPC, pos=(2000, y))
    g.wire(oc, "AsConan Player Controller", ban, "self", exec=False)
    g.wire(nid, "ReturnValue", ban, "PlayerNetId", exec=False)
    g.wire(nick, "ReturnValue", ban, "PlayerNickName", exec=False)
    g.wire(p[0], p[1], ban, "execute")
    p = ask_list((ban, "then"), oc, (2300, y))
    reply(p, h.text(["Ban sent for ", name_of((ce, "State"), (2400, y + 600)),
                     ". Check the banned list: if they aren't on it, the game wants a Conan admin."],
                    (2600, y + 450)), (2600, y))

    # ---- unban
    y = y0 + 3000
    ce = h.event("OwlServerPlUnban", [("Id", "netid", False), ("Name", "string", False)], y, R.RUN_ON_SERVER)
    oc, _a, ok = h.unlocked(ce, y)
    un = g.call("UnbanPlayer", CPC, pos=(1000, y))
    g.wire(oc, "AsConan Player Controller", un, "self", exec=False)
    g.wire(ce, "Id", un, "PlayerNetId", exec=False)
    g.wire(ok, "then", un, "execute")
    p = ask_list((un, "then"), oc, (1300, y))
    reply(p, h.text(["Unbanned ", (ce, "Name"), ". They can join again."], (1600, y + 450)), (1600, y))

    # ---- go to a player
    y = y0 + 4500
    ce = h.event("OwlServerPlGoto", [("State", "state", False)], y, R.RUN_ON_SERVER)
    oc, _a, ok = h.unlocked(ce, y)
    p = valid((ok, "then"), (ce, "State"), (900, y), NO_ONE)
    p = not_self(p, ce, oc, y)
    them = g.call("GetPawn", PSTATE, pos=(1700, y + 300))
    g.wire(ce, "State", them, "self", exec=False)
    me = pawn_of_ctrl(oc, (1700, y + 600))
    p = valid(p, (them, "ReturnValue"), (1900, y), "That player has no character right now.")
    p = valid(p, me, (2200, y), "You need a character to teleport.")
    p = teleport(p, (oc, "AsConan Player Controller"), me, spot((them, "ReturnValue"), (2300, y + 900)), (2500, y))
    reply(p, h.text(["Teleported to ", name_of((ce, "State"), (3000, y + 600)), "."], (3100, y + 450)), (3100, y))

    # ---- bring a player here
    y = y0 + 6500
    ce = h.event("OwlServerPlBring", [("State", "state", False)], y, R.RUN_ON_SERVER)
    oc, _a, ok = h.unlocked(ce, y)
    p = valid((ok, "then"), (ce, "State"), (900, y), NO_ONE)
    p = not_self(p, ce, oc, y)
    them = g.call("GetPawn", PSTATE, pos=(1700, y + 300))
    g.wire(ce, "State", them, "self", exec=False)
    me = pawn_of_ctrl(oc, (1700, y + 600))
    p = valid(p, (them, "ReturnValue"), (1900, y), "That player has no character right now.")
    p = valid(p, me, (2200, y), "You need a character to bring someone to you.")
    tc = g.call("GetController", "/Script/Engine.Pawn", pos=(2400, y + 300))
    g.wire(them, "ReturnValue", tc, "self", exec=False)
    cc = g.cast(CPC, pos=(2500, y))
    g.wire(tc, "ReturnValue", cc, "Object", exec=False)
    g.wire(p[0], p[1], cc, "execute")
    reply((cc, "CastFailed"), NO_ONE, (2800, y + 900))
    p = teleport((cc, "then"), (cc, "AsConan Player Controller"), (them, "ReturnValue"), spot(me, (2600, y + 900)),
                 (2800, y))
    reply(p, h.text(["Brought ", name_of((ce, "State"), (3300, y + 600)), " to you."], (3400, y + 450)), (3400, y))

    h.client_event("OwlClientPl", MSG_PINS, ["PlMsg"], "PlMsgVer", y0 + 8500)
    return flags
