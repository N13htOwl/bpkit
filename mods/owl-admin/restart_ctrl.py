"""The Server Restart tab, the controller's (02) part: the countdown on the server, and the banner
and sound on every screen.

    variables(bel) -> [(name, type, replicated)]     defaults(cdo)
    server_tick(c, y)      entered from the server's tick; leaves c.exits for what follows
    banner(c, wcast, was, cls, y)  entered after the HUD tab's part (overlay up); leaves c.exits
    sound(c, y)            entered after banner and while the overlay is hidden

Replicated: RsVals (menu_defs.RS_LIMITS order), RsVer (+1 per save), RsLeft (seconds to the
restart the banner shows, -1 = none), RsBeep (+1 per warning reached), RsClock (the server's
clock, minutes after midnight, for the admin page). Server only: RsManualEnd / RsSkipUntil /
RsNextCheck (game seconds), RsStage (warnings reached), RsTmpLeft. This machine's: RsShown,
RsBeepSeen.

Once a second the server works out the seconds to the next restart: the daily time (on its own
clock, Now) unless it's skipped, or a manual countdown, whichever is sooner; inside RS_AFTER
after it, 0 ("restarting now"). The banner shows from the first warning that is on (with none
on: only at 0). Each warning reached (and 0) raises RsBeep, and every screen plays the sound.
"""
from bpkit import ir
import menu_defs as D

KML = "/Script/Engine.KismetMathLibrary"
KSTR = "/Script/Engine.KismetStringLibrary"
KTXT = "/Script/Engine.KismetTextLibrary"
KSL = "/Script/Engine.KismetSystemLibrary"
GS = "/Script/Engine.GameplayStatics"
TEXTBLOCK = "/Script/UMG.TextBlock"
UWIDGET = "/Script/UMG.Widget"
SLATEVIS = ir.enum_path("/Script/UMG.ESlateVisibility")
SOUNDBASE = "/Script/Engine.SoundBase"
DAY = 86400
NONE = 999999            # "no restart coming" (more than a day)
I_DAILY, I_TIME, I_WARN, I_SOUND = 0, 1, 2, 2 + len(D.RS_WARNS)


def variables(bel):
    i = bel.get_basic_type_by_name("int")
    out = [("RsVals", bel.get_array_type(i), True)]
    out += [(v, i, True) for v in ("RsVer", "RsLeft", "RsBeep", "RsClock")]
    out += [(v, i, False) for v in ("RsManualEnd", "RsSkipUntil", "RsNextCheck", "RsStage", "RsTmpLeft",
                                    "RsShown", "RsBeepSeen")]
    return out


def defaults(cdo):
    cdo.set_editor_property("RsVals", list(D.RS_DEFAULT))
    for v in ("RsLeft", "RsBeepSeen", "RsClock"):
        cdo.set_editor_property(v, -1)


def _val(c, k, pos):
    return c.at(c.arr("RsVals", "int", pos), k, "int", (pos[0] + 200, pos[1]))


def _i(c, fn, a, b, pos):
    """An int math call: a / b are (node, pin) or int literals."""
    lit = lambda v: v if isinstance(v, tuple) else (str(v), "int")
    return c.fn(fn, KML, {"A": lit(a), "B": lit(b)}, pos)


def _sel(c, a, b, pick, pos):
    lit = lambda v: v if isinstance(v, tuple) else (str(v), "int")
    return c.fn("SelectInt", KML, {"A": lit(a), "B": lit(b), "bPickA": pick}, pos)


# ================================================================ server
def server_tick(c, y):
    x = 0
    now = c.fn("FTrunc", KML, {"A": c.fn("GetGameTimeInSeconds", KSL, {}, (x, y + 400))}, (x + 200, y + 400))
    due = c.branch(_i(c, "GreaterEqual_IntInt", now, c.var("RsNextCheck", "int", (x + 200, y + 550)), (x + 400, y + 400)),
                   (x + 400, y))
    skip = [(due, "else")]
    c.exits = [(due, "then")]
    c.set_var("RsNextCheck", "int", _i(c, "Add_IntInt", now, 1, (x + 600, y + 400)), (x + 700, y))
    # the server's clock
    dt = c.fn("Now", KML, {}, (x + 900, y + 600))
    hh = c.fn("GetHour", KML, {"A": dt}, (x + 1100, y + 500))
    mm = c.fn("GetMinute", KML, {"A": dt}, (x + 1100, y + 650))
    ss = c.fn("GetSecond", KML, {"A": dt}, (x + 1100, y + 800))
    c.set_var("RsClock", "int", _i(c, "Add_IntInt", _i(c, "Multiply_IntInt", hh, 60, (x + 1300, y + 500)), mm,
                                   (x + 1500, y + 500)), (x + 1000, y))
    # a manual countdown is over RS_AFTER after its end
    x = 1800
    mend = lambda pos: c.var("RsManualEnd", "int", pos)
    over = c.fn("BooleanAND", KML, {
        "A": _i(c, "Greater_IntInt", mend((x, y + 450)), 0, (x + 200, y + 450)),
        "B": _i(c, "Greater_IntInt", now, _i(c, "Add_IntInt", mend((x, y + 700)), D.RS_AFTER, (x + 200, y + 700)),
                (x + 400, y + 600))}, (x + 600, y + 450))
    bo = c.branch(over, (x + 600, y))
    c.exits = [(bo, "then")]
    c.set_var("RsManualEnd", "int", "0", (x + 900, y))
    c.exits += [(bo, "else")]
    # seconds to the daily time: ((time*60 - now) mod day + day) mod day; RS_AFTER past it -> 0
    x = 3000
    now_s = _i(c, "Add_IntInt", _i(c, "Add_IntInt", _i(c, "Multiply_IntInt", hh, 3600, (x, y + 500)),
                                   _i(c, "Multiply_IntInt", mm, 60, (x, y + 650)), (x + 200, y + 500)),
               ss, (x + 400, y + 500))
    raw = _i(c, "Subtract_IntInt", _i(c, "Multiply_IntInt", _val(c, I_TIME, (x, y + 850)), 60, (x + 400, y + 850)),
             now_s, (x + 600, y + 600))
    d = _i(c, "Percent_IntInt", _i(c, "Add_IntInt", _i(c, "Percent_IntInt", raw, DAY, (x + 800, y + 600)), DAY,
                                   (x + 1000, y + 600)), DAY, (x + 1200, y + 600))
    d_now = _sel(c, 0, d, _i(c, "Greater_IntInt", d, DAY - D.RS_AFTER, (x + 1400, y + 750)), (x + 1600, y + 600))
    d_on = c.fn("BooleanAND", KML, {
        "A": _i(c, "EqualEqual_IntInt", _val(c, I_DAILY, (x + 1200, y + 950)), 1, (x + 1500, y + 950)),
        "B": _i(c, "GreaterEqual_IntInt", now, c.var("RsSkipUntil", "int", (x + 1300, y + 1100)), (x + 1500, y + 1100))},
        (x + 1700, y + 950))
    daily = _sel(c, d_now, NONE, d_on, (x + 1900, y + 600))
    manual = _sel(c, c.fn("Max", KML, {"A": _i(c, "Subtract_IntInt", mend((x + 1500, y + 1300)), now, (x + 1700, y + 1300)),
                                       "B": ("0", "int")}, (x + 1900, y + 1300)),
                  NONE, _i(c, "Greater_IntInt", mend((x + 1700, y + 1450)), 0, (x + 1900, y + 1450)), (x + 2100, y + 1300))
    c.set_var("RsTmpLeft", "int", c.fn("Min", KML, {"A": daily, "B": manual}, (x + 2300, y + 600)), (x + 2400, y))
    # the banner window (the earliest warning that is on) and the warnings reached
    x = 5600
    left = lambda pos: c.var("RsTmpLeft", "int", pos)
    window, stage = ("0", "int"), _sel(c, 1, 0, _i(c, "LessEqual_IntInt", left((x, y + 1400)), 0, (x + 200, y + 1400)),
                                       (x + 400, y + 1400))
    for k, m in enumerate(D.RS_WARNS):
        on = _i(c, "EqualEqual_IntInt", _val(c, I_WARN + k, (x, y + 500 + 150 * k)), 1, (x + 400, y + 500 + 150 * k))
        window = c.fn("Max", KML, {"A": window, "B": _sel(c, m * 60, 0, on, (x + 600, y + 500 + 150 * k))},
                      (x + 800, y + 500 + 150 * k))
        reached = c.fn("BooleanAND", KML, {"A": on, "B": _i(c, "LessEqual_IntInt", left((x + 400, y + 1550 + 150 * k)),
                                                            m * 60, (x + 600, y + 1550 + 150 * k))},
                       (x + 800, y + 1550 + 150 * k))
        stage = _i(c, "Add_IntInt", stage, _sel(c, 1, 0, reached, (x + 1000, y + 1550 + 150 * k)),
                   (x + 1200, y + 1550 + 150 * k))
    active = _i(c, "LessEqual_IntInt", left((x + 1000, y + 400)), window, (x + 1200, y + 400))
    stage = _sel(c, stage, 0, active, (x + 1400, y + 1550))
    bb = c.branch(_i(c, "Greater_IntInt", stage, c.var("RsStage", "int", (x + 1400, y + 1700)), (x + 1600, y + 1550)),
                  (x + 1600, y))
    c.exits = [(bb, "then")]
    c.bump("RsBeep", (x + 1900, y))
    c.exits += [(bb, "else")]
    c.set_var("RsStage", "int", stage, (x + 2200, y))
    c.set_var("RsLeft", "int", _sel(c, left((x + 2300, y + 400)), -1, active, (x + 2500, y + 400)), (x + 2500, y))
    c.exits += skip


# ================================================================ every screen
def banner(c, wcast, was, widget_cls, y):
    """While RsLeft >= 0 the alert banner shows the countdown (over the HUD tab's alert); when it
    ends, HudSeen = -1 so the HUD tab's part puts its own alert back next tick."""
    g, x = c.g, 0

    def part(name, cls, pos):
        n = g.var_get(name, "object", ir.obj_path(cls), parent=widget_cls, pos=pos)
        g.wire(wcast, was, n, "self", exec=False)
        return (n, name)

    left = lambda pos: c.var("RsLeft", "int", pos)
    bl = c.branch(_i(c, "GreaterEqual_IntInt", left((x, y + 300)), 0, (x + 200, y + 300)), (x + 200, y))
    c.exits = [(bl, "then")]
    mins = _i(c, "Divide_IntInt", _i(c, "Add_IntInt", left((x + 300, y + 600)), 59, (x + 500, y + 600)), 60,
              (x + 700, y + 600))
    s = lambda v: (v, "string")
    in_min = c.concat([s("Server will restart in "), c.fn("Conv_IntToString", KSTR, {"InInt": mins}, (x + 900, y + 600)),
                       c.fn("SelectString", KML, {"A": s(" minute."), "B": s(" minutes."),
                                                  "bPickA": _i(c, "EqualEqual_IntInt", mins, 1, (x + 900, y + 750))},
                            (x + 1100, y + 750))], (x + 1300, y + 600))
    in_sec = c.concat([s("Server will restart in "),
                       c.fn("Conv_IntToString", KSTR, {"InInt": left((x + 700, y + 950))}, (x + 900, y + 950)),
                       s(" seconds.")], (x + 1300, y + 950))
    msg = c.fn("SelectString", KML, {"A": in_sec, "B": in_min,
                                     "bPickA": _i(c, "Less_IntInt", left((x + 1300, y + 1100)), 60, (x + 1500, y + 1100))},
               (x + 1800, y + 800))
    msg = c.fn("SelectString", KML, {"A": s("Server is restarting now."), "B": msg,
                                     "bPickA": _i(c, "EqualEqual_IntInt", left((x + 1800, y + 1100)), 0,
                                                  (x + 2000, y + 1100))}, (x + 2200, y + 800))
    st = g.call("SetText", TEXTBLOCK, pos=(x + 2400, y))
    w = part("AlertText", TEXTBLOCK, (x + 2200, y + 300))
    g.wire(w[0], w[1], st, "self", exec=False)
    g.wire(c.fn("Conv_StringToText", KTXT, {"InString": msg}, (x + 2400, y + 800))[0], "ReturnValue", st, "InText",
           exec=False)
    c.go(st)
    sv = g.call("SetVisibility", UWIDGET, pos=(x + 2700, y))
    g.typed_input(sv, "InVisibility", "HitTestInvisible", "byte", SLATEVIS)
    w = part("AlertOutline", UWIDGET, (x + 2500, y + 300))
    g.wire(w[0], w[1], sv, "self", exec=False)
    c.go(sv)
    c.set_var("RsShown", "int", "1", (x + 3000, y))
    shown = c.exits
    # over: hand the banner back to the HUD tab, once
    c.exits = [(bl, "else")]
    bw = c.branch(_i(c, "EqualEqual_IntInt", c.var("RsShown", "int", (x + 200, y + 1400)), 1, (x + 400, y + 1400)),
                  (x + 400, y + 1300))
    c.exits = [(bw, "then")]
    c.set_var("RsShown", "int", "0", (x + 700, y + 1300))
    c.set_var("HudSeen", "int", "-1", (x + 1000, y + 1300))
    c.exits += shown + [(bw, "else")]


def sound(c, y):
    """A new RsBeep: play the chosen sound -- unless this machine just joined (RsBeepSeen -1) or the
    countdown is already over."""
    g, x = c.g, 0
    beep = lambda pos: c.var("RsBeep", "int", pos)
    bn = c.branch(_i(c, "NotEqual_IntInt", beep((x, y + 300)), c.var("RsBeepSeen", "int", (x, y + 450)),
                     (x + 200, y + 300)), (x + 200, y))
    out = [(bn, "else")]
    c.exits = [(bn, "then")]
    play = c.fn("BooleanAND", KML, {
        "A": _i(c, "GreaterEqual_IntInt", c.var("RsBeepSeen", "int", (x + 300, y + 450)), 0, (x + 500, y + 450)),
        "B": _i(c, "GreaterEqual_IntInt", c.var("RsLeft", "int", (x + 300, y + 600)), 0, (x + 500, y + 600))},
        (x + 700, y + 450))
    bp_ = c.branch(play, (x + 700, y))
    c.exits = [(bp_, "then")]
    play_chosen(c, _val(c, I_SOUND, (x + 900, y + 600)), (x + 1000, y))
    c.exits += [(bp_, "else")]
    c.set_var("RsBeepSeen", "int", beep((x + 3000, y + 300)), (x + 3200, y))
    c.exits += out


def play_chosen(c, idx, pos):
    """PlaySound2D of menu_defs.RS_SOUNDS[idx] (nothing for Silent), from the current exits."""
    g, (x, y) = c.g, pos
    for k, (_label, path) in enumerate(D.RS_SOUNDS):
        if not path:
            continue
        b = c.branch(_i(c, "EqualEqual_IntInt", idx, k, (x, y + 300)), (x + 200, y))
        c.exits = [(b, "then")]
        ps = g.call("PlaySound2D", GS, pos=(x + 450, y))
        sp = ps.pin("Sound").typed("object", ir.obj_path(SOUNDBASE), direction="EGPD_Input")
        sp.set("DefaultObject", '"%s"' % path)
        c.go(ps)
        c.exits += [(b, "else")]
        x += 700
