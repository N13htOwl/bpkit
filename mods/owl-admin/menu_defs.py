"""The Admin Restrictions Menu's content, transcribed from the design canvas board
(project/Main.dc.html: renderVals titles/hints + defs()). Pure data, no unreal import.

TABS     -- (id, title, hint) in the board's sidebar order.
SETTINGS -- the board's defs(): toggles and stepped numbers, grouped by tab.
PANELS   -- the board's special panels per tab; Step 1 shows each as a placeholder.
"""

TABS = [
    ("access", "Access & Log", "Who can open this panel, and who tried"),
    ("reports", "Bug Reports", "What players reported, newest first"),
    ("building", "Building", "Limits on structures, clans and decay"),
    ("combat", "Combat", "PvP rules and raid protection"),
    ("loot", "Items & Loot", "Chest behaviour and item restrictions"),
    ("players", "Players", "Teleport to players, and ban or unban them"),
    ("characters", "Characters", "Fix levels, stats and points"),
    ("commands", "Commands", "Player chat commands and cooldowns"),
    ("kits", "Kits", "Item bundles players claim in the player menu (Shift+I)"),
    ("trading", "Trading", "Players trade in the player menu (Shift+I). The log is below"),
    ("npcs", "NPCs", "Placed NPCs players talk to and buy from (press E on them)"),
    ("pets", "Pets", "Custom pets players can buy"),
    ("hud", "HUD", "What every player sees on screen"),
    ("restart", "Server Restart", "Warn players before a restart"),
    ("scripting", "Scripting", "Command scripts and a console, run as you"),
    ("discord", "Discord", "Send server events to a Discord channel"),
    ("cheats", "Cheats", "Powers for your own character while in admin mode. Every change is logged"),
]


def T(id, tab, label, desc, default):
    return {"id": id, "tab": tab, "label": label, "desc": desc, "type": "toggle", "default": default}


def H(st):
    """A setting kept only for its place in the saved list: no row in the menu."""
    return dict(st, hidden=True)


def N(id, tab, label, desc, lo, hi, step, unit, default):
    return {"id": id, "tab": tab, "label": label, "desc": desc, "type": "step",
            "min": lo, "max": hi, "step": step, "unit": unit, "default": default}


SETTINGS = [
    N("cap", "building", "Structure limit per clan", "Maximum building pieces a single clan may place.", 200, 3000, 100, "", 1000),
    N("clan", "building", "Max clan size", "Largest number of members allowed in one clan.", 1, 30, 1, "", 8),
    T("safe", "building", "Block building near safe zones", "Prevents placement inside protected radius around spawn points.", True),
    T("thrall", "building", "Restrict thrall placement", "Only admins may place thralls inside claimed land.", False),
    N("decay", "building", "Decay timer multiplier", "Scales how quickly abandoned structures decay.", 0.5, 5, 0.5, "x", 1.5),
    T("pvp", "combat", "PvP enabled", "Allows players to damage each other.", True),
    T("offline", "combat", "Offline raid protection", "Structures cannot be damaged while all owners are offline.", True),
    N("ff", "combat", "Friendly fire damage", "Share of damage clan members deal to each other. 0 turns friendly fire off.", 0, 1, 0.05, "x", 0.25),
    N("sdmg", "combat", "Structure damage multiplier", "Scales damage dealt to player-built structures.", 0.5, 3, 0.5, "x", 1),
    N("resp", "combat", "Respawn cooldown", "Seconds a player must wait before respawning.", 0, 120, 10, "s", 30),
    T("chests", "loot", "Custom loot chests", "Enable chests spawned by the loot chest mod.", True),
    N("crespawn", "loot", "Chest respawn time", "Minutes before an emptied chest refills.", 5, 120, 5, "m", 30),
    N("cmax", "loot", "Chests looted per player", "Maximum chests one player may open per respawn cycle.", 1, 10, 1, "", 3),
    T("banlist", "loot", "Enforce banned item list", "Removes listed items from loot tables and crafting.", True),
    T("adminonly", "access", "Admins only", "Only accounts on the admin list can open this menu. Players are refused, except for the Transmog panel below.", True),
    T("tmplayers", "access", "Transmog open to all players", "Every player can open the Transmog panel. It is the only screen players can open.", True),
    N("lockout", "access", "Failed attempts before lockout", "Number of wrong passwords before the panel locks for that player.", 1, 10, 1, "", 3),
    T("alertfail", "access", "Alert admins on failed attempt", "Sends an on-screen notice to online admins.", True),
    T("logall", "access", "Log every login attempt", "Records successful and failed attempts in the access log below.", True),
    T("tmall", "loot", "Unlock all transmog appearances", "Every item in the game is available as an outfit appearance for all players.", True),
    T("homeon", "commands", "/home", "Lets players teleport to the home they saved.", True),
    N("homecd", "commands", "/home cooldown", "Time before a player can use /home again.", 0, 3600, 30, "s", 300),
    N("homewarm", "commands", "/home warm-up", "Time a player must stand still first. It cancels if they take damage.", 0, 30, 1, "s", 5),
    T("sethomeon", "commands", "/sethome", "Lets players save their current spot as home.", True),
    N("sethomecd", "commands", "/sethome cooldown", "Time before a player can change their home again.", 0, 3600, 30, "s", 60),
    T("tmcmd", "commands", "/transmog", "Opens the Transmog panel from chat.", True),
    T("stuckon", "commands", "/unstuck", "Moves a player who is stuck in the world to a safe spot nearby.", True),
    N("stuckcd", "commands", "/unstuck cooldown", "Time before a player can use /unstuck again.", 0, 3600, 30, "s", 600),
    N("stuckwarm", "commands", "/unstuck warm-up", "Time a player waits before being moved. It cancels if they take damage.", 0, 30, 1, "s", 10),
    T("combatblock", "commands", "Block commands in combat", "Teleport commands are refused for a short time after fighting.", True),
    T("dcrestart", "discord", "Post restart warnings", "Sends the 10, 5, 2 and 1 minute restart warnings to Discord.", True),
    T("dcfail", "discord", "Post failed admin logins", "Sends an alert when someone fails the admin password.", True),
    T("dcjoin", "discord", "Post player joins and leaves", "Sends a short note each time a player connects or disconnects.", False),
    T("dcadmin", "discord", "Post admin actions", "Sends character edits, item grants and currency changes to the admin channel.", True),
    T("dcchat", "discord", "Mirror in-game chat", "Copies global chat messages into the Discord channel.", False),
    # the old Cheats settings: the cheats are each admin's own now (cheats_server), not server-wide
    # settings. Hidden rows, kept for their places in the saved list
    H(T("chgod", "cheats", "God mode", "Your character takes no damage.", False)),
    H(T("chfly", "cheats", "Fly", "Move freely through the air and past obstacles.", False)),
    H(T("chstam", "cheats", "Infinite stamina", "Stamina never runs out.", False)),
    H(T("chneeds", "cheats", "No hunger or thirst", "Food and water stay full.", False)),
    H(T("chinvis", "cheats", "Invisible to players", "Players cannot see your character.", False)),
    H(N("chspeed", "cheats", "Move speed", "Scales how fast your character moves.", 1, 10, 1, "x", 1)),
    H(T("chcraft", "cheats", "Instant crafting", "Crafting finishes at once.", False)),
    H(T("chbuild", "cheats", "Build anywhere", "Ignore building limits and protected zones.", False)),
    H(T("chcd", "cheats", "Ignore command cooldowns", "Use /home and other commands without waiting.", False)),
    T("tradeon", "trading", "Player trading enabled", "Lets players offer items to each other in a trade window.", True),
    N("tradedist", "trading", "Max distance between traders", "Both players must be this close, in metres, to start or keep a trade open.", 2, 50, 1, "m", 10),
    N("tradeslots", "trading", "Item slots per side", "How many stacks each player can put into one trade.", 1, 12, 1, "", 12),
    N("tradecd", "trading", "Trade cooldown", "Seconds a player must wait before starting another trade.", 0, 600, 10, "s", 30),
    N("tradetimeout", "trading", "Trade request timeout", "Seconds the other player has to accept before the request expires.", 10, 120, 5, "s", 30),
    T("tradecur", "trading", "Allow coins in trades", "Players may put Owl coins (their Owl wallet) into a trade.", True),
    # hidden: no restricted item list, confirming is always required, no readable clan or combat state
    H(T("tradeblock", "trading", "Block restricted items", "Items on the restricted list cannot be traded.", True)),
    H(T("tradeconfirm", "trading", "Require both players to confirm", "Both players must press Confirm after the final offer. Changing an offer clears both confirmations.", True)),
    H(T("tradeclan", "trading", "Clan members only", "Players can only trade with members of their own clan.", False)),
    H(T("tradecombat", "trading", "Block trading in combat", "Trading is refused for a short time after taking or dealing damage.", True)),
    T("tradelog", "trading", "Log every trade", "Records who traded what, and when, in the trade log below.", True),
    T("peton", "pets", "Pet shop enabled", "Players can open the pet shop and buy companion pets with coins.", True),
    N("petmax", "pets", "Pets owned per player", "Most pets one player can own at a time.", 1, 8, 1, "", 3),
    N("petactive", "pets", "Pets out at once", "How many owned pets a player can summon together.", 1, 3, 1, "", 1),
    N("petprice", "pets", "Price multiplier", "Scales every pet price in the shop.", 0.5, 5, 0.5, "x", 1),
    T("petsell", "pets", "Allow selling pets back", "Players get part of the price back when they release a pet.", False),
    T("petdie", "pets", "Pets can die", "A pet that is killed must be bought again. When off, it only has to be summoned again after a short wait.", False),
    T("petlog", "pets", "Log pet purchases", "Records who bought which pet, and when.", True),
    H(T("tradeadmin", "trading", "Post trades to this menu", "Each finished trade appears in the trade log below, and online admins get a notice.", True)),
    T("kitson", "kits", "Kits", "Lets players claim kits in the player menu's Kits tab.", True),
    # was "kitcombat" (Block /kits in combat): Conan has no in-combat state for players. Same place in
    # the list, so a saved value stays where it is read
    T("kitlog", "kits", "Log kit claims", "Adds each claim to the player's admin log (Characters, Log).", True),
    T("kit1on", "kits", "Kit 1", "Available to claim. Name and items are set below.", True),
    N("kit1cd", "kits", "Kit 1 cooldown", "Minutes before the same player can claim Kit 1 again.", 0, 10080, 60, "m", 1440),
    T("kit2on", "kits", "Kit 2", "Available to claim. Name and items are set below.", True),
    N("kit2cd", "kits", "Kit 2 cooldown", "Minutes before the same player can claim Kit 2 again.", 0, 10080, 60, "m", 4320),
    T("kit3on", "kits", "Kit 3", "Available to claim. Name and items are set below.", False),
    N("kit3cd", "kits", "Kit 3 cooldown", "Minutes before the same player can claim Kit 3 again.", 0, 10080, 60, "m", 10080),
    N("stack", "loot", "Stack size multiplier", "Scales how many of an item fit in one slot.", 1, 10, 1, "x", 2),
    # added after v1.3: keep new settings at the end (a saved settings list is read by position)
    T("owltm", "loot", "Owl Transmog and Animal Masks", "Shows the looks players pick in the player menu. Turn off when 'Tot ! Custom' or another mod handles armor looks: saved looks are kept and come back when you turn it on.", True),
]

# Settings Conan itself can change, so APPLY puts them into effect at once. id -> (server
# setting, how): "ini" = ServerSettings.SetServerSetting (native; also writes the server's
# ServerSettings.ini), "bp" = a variable on BP_ServerSettings (not in the ini; the controller
# re-applies the saved value at BeginPlay). Names verified in PIE 2026-10-26 (GetServerSetting /
# the BP's properties). Every other setting is saved by APPLY but has no game feature behind it yet.
LIVE = {
    "pvp": ("PVPEnabled", "ini"),
    "clan": ("ClanMaxSize", "ini"),
    "decay": ("BuildingDecayTimeMultiplier", "ini"),
    "sdmg": ("StructureDamageMultiplier", "bp"),
    "ff": ("FriendlyFireDamageMultiplier", "bp"),
}


def index(setting_id):
    """Position of a setting in SETTINGS = its slot in the applied-settings array."""
    return [s["id"] for s in SETTINGS].index(setting_id)


def bounds(st):
    """(min, max) a value is clamped to: 0..1 for toggles."""
    return (0, 1) if st["type"] == "toggle" else (st["min"], st["max"])


# The player menu (Shift+I): the canvas's player-facing boards, one tab each. Step 1 shows
# each as a placeholder card; they get built out one board at a time.
PLAYER_TABS = [
    ("transmog", "Transmog Outfits", "Change how your gear looks"),
    ("pets", "Pet Shop", "Buy companion pets with coins"),
    ("masks", "Animal Masks", "Wear an animal mask"),
    ("equipment", "Equipment", "Your gear and armor"),
    ("kits", "Kits", "Claim the kits the admins set up"),
    ("trade", "Trade", "Swap items with a player near you"),
    ("bugreport", "Bug Report", "Tell the admins about a problem"),
]

# Transmog (player menu): the five appearance slots -- (key, tab label, ItemTable EquipLocation:
# the EquipmentSlots enum, 3 HEAD .. 7 FEET) -- and the category chips -- (key, label, the
# GUICategory values they show; None = all, () = everything not in another chip). The design
# board's Armor / Clothing / Cosmetic chips don't exist in the game's data; these are its real
# categories.
TM_SLOTS = [("head", "Head", 3), ("chest", "Chest", 4), ("hands", "Hands", 5), ("legs", "Legs", 6),
            ("feet", "Feet", 7)]
TM_CATS = [("all", "All", None), ("light", "Light", ["LightArmor"]), ("medium", "Medium", ["MediumArmor"]),
           ("heavy", "Heavy", ["HeavyArmor"]), ("other", "Other", ())]
# Where a slot's appearance lands on the character, per slot key: (the item's SlotType in
# /Game/Items/EquipmentVariationTable, the CharacterMeshLayout member that holds its item id)
TM_LAYOUT = {"head": ("Helmet", "Helmet"), "chest": ("Upperbody", "UpperBody"), "hands": ("Hands", "Hands"),
             "legs": ("Lowerbody", "LowerBody"), "feet": ("Feet", "Feet")}

# Character editor (admin menu, Characters tab). The seven attributes in the game's order --
# (shown name from /Game/UI/Inventory/Attributes/AttributeDisplayData, the ECharIntStatID entry).
CE_ATTRS = [("Strength", "AttributeMight"), ("Agility", "AttributeAthleticism"), ("Vitality", "AttributeHealth"),
            ("Grit", "AttributeStamina"), ("Authority", "AttributeLeadership"),
            ("Expertise", "AttributeEncumbrance"), ("Survival", "AttributeMetabolism")]
CE_TABS = [("stats", "Stats"), ("inventory", "Inventory"), ("items", "Item catalog"), ("currency", "Currency"),
           ("log", "Log")]
CE_LEVEL = (1, 60)
CE_POINTS = (0, 99)
CE_ATTR = (0, 20)
CE_QTY = (1, 999)
CE_WALLET_MAX = 999999999
# Inventories the Inventory tab lists -- (EInventoryType entry, label). A slot is sent as
# kind * 1000 + slot, kind = the index here.
CE_INVS = [("Backpack", "Backpack"), ("Equipment", "Equipped"), ("ShortcutBar", "Hotbar")]
# Item catalog chips -- (key, label, ItemTable GUICategory values; None = all)
CE_ITEM_CATS = [("all", "All", None), ("weapon", "Weapons", ["Weapon"]),
                ("armor", "Armor", ["Armor", "LightArmor", "MediumArmor", "HeavyArmor"]),
                ("resource", "Resources", ["Material", "Component"]), ("consumable", "Consumables", ["Consumable"])]
# Currencies accepted in trades -- (label, ItemTable id; 0 = the Owl wallet). Saved, no effect yet.
CE_CURRENCIES = [("Owl wallet", 0), ("Gold Coin", 11066), ("Silver Coin", 11065)]
# Bug report kinds (the Bug Report board's chips)
BUG_CATS = ["Interface", "Items", "NPCs", "Loot chests", "Crash", "Other"]
BUG_TITLE_MAX, BUG_TEXT_MAX = 80, 1000   # characters kept from a report's title / text
# The HUD tab: (key, label, description, text limit or None). Order is fixed: it's the index into
# the controller's HudOn, and the text items come first, so their index is also HudText's.
HUD_ITEMS = [
    ("alert", "Server alert banner", "The red banner at the top of every player's screen.", 80),
    ("notice", "Server notice card", "A card on the left, under the health bars.", 120),
    ("restrict", "Restriction card", "A second card under the notice, for a rule in force.", 120),
    ("players", "Players online", "A live count of the players on the server, above the hotbar.", None),
    ("hint", "Player menu hint", "\"Shift+I  Player menu\" above the hotbar, for new players.", None),
]
HUD_TEXTS = [k for k, _l, _d, n in HUD_ITEMS if n]
assert HUD_TEXTS == [k for k, _l, _d, _n in HUD_ITEMS[:len(HUD_TEXTS)]], "HUD text items must come first"
# The Server Restart tab. Owl Admin only warns: the host's own schedule restarts the server (set
# it to the same time). Its saved values, one int each, in this order (the controller's RsVals):
#   0 daily (1/0), 1 the restart time (minutes after midnight, the SERVER's clock),
#   2..5 the RS_WARNS warnings (1/0 each), 6 the sound (index into RS_SOUNDS)
RS_WARNS = [10, 5, 2, 1]                  # minutes before the restart
RS_SOUNDS = [("Horn", "/Game/Sound/Music/misc_elements/Horns/sfx_horn_Cue.sfx_horn_Cue"),
             ("Bell", "/Game/Sound/SFX/Store/Bazaar_Placeables/bazaar_nem_alarm_bell_ring_Cue."
                      "bazaar_nem_alarm_bell_ring_Cue"),
             ("Alarm", "/Game/Sound/Music/The_Purge/sfx_music_purge_warning_cue.sfx_music_purge_warning_cue"),
             ("Silent", None)]
RS_LIMITS = [(0, 1), (0, 1439)] + [(0, 1)] * len(RS_WARNS) + [(0, len(RS_SOUNDS) - 1)]
RS_DEFAULT = [0, 240] + [1] * len(RS_WARNS) + [0]   # off; 4:00 AM; every warning; the horn
RS_STEP = 15             # minutes per click of the time's - / +
RS_COUNTDOWN = 600       # seconds: Start restart countdown
RS_AFTER = 180           # seconds "Restarting now" stays up (the host should have restarted by then)
# The Pet Shop (player menu): (name, ItemTable id of the grown, tamed pet, price in Owl wallet coins,
# its icon). Buying puts the pet item in the backpack; the player places it like any tamed pet.
# Every id is a ThrallItem with a SpawnTemplateID and the Item.Pet.Grownup tag (checked 2026-10-28).
_PI = "/Game/UI/Textures/Icons/"
PETS = [("Feral Dog", 19184, 500, _PI + "Items/icon_wilddog_01.icon_wilddog_01"),
        ("Wolf", 19145, 1500, _PI + "Pets/icon_pet_Wolf.icon_pet_Wolf"),
        ("Panther", 19149, 1500, _PI + "Pets/icon_pet_Panther.icon_pet_Panther"),
        ("Jaguar", 19146, 2000, _PI + "Pets/icon_pet_Jaguar.icon_pet_Jaguar"),
        ("Lion", 19097, 2500, _PI + "Items/icon_lion.icon_lion"),
        ("Tiger", 19147, 3500, _PI + "Pets/icon_pet_Tiger.icon_pet_Tiger"),
        ("Greater Wolf", 19126, 4000, _PI + "Pets/icon_pet_Wolf_Alpha.icon_pet_Wolf_Alpha"),
        ("Greater Bear", 19127, 6000, _PI + "Pets/icon_pet_Bear_Alpha.icon_pet_Bear_Alpha")]
# Animal Masks (player menu): the design's masks (Owl, Fox, Raven, ...) don't exist in Conan, so these
# are the game's most animal-like head pieces -- (name, ItemTable row = a Transmog head appearance,
# icon: the row's Icon, else its IconLayers[0]). Wearing one sets the Transmog Head slot (looks only).
_AR = _PI + "Armor/"
MASKS = [("Aspect of the Wolf", "91331", _AR + "icon_greatwolf_helm.icon_greatwolf_helm"),
         ("Aspect of the Bat", "91337", _AR + "icon_batdemon_helm.icon_batdemon_helm"),
         ("Aspect of Jhil", "91336", _AR + "icon_jhil_helm.icon_jhil_helm"),
         ("Hyena Skull Helmet", "52551", _AR + "icon_dogs_helmet.icon_dogs_helmet"),
         ("Reptilian Helm", "52016", _AR + "icon_crocodile_armor_headpiece.icon_crocodile_armor_headpiece"),
         ("Wild Druid Helm", "95000", _AR + "icon_druid_headDress.icon_druid_headDress"),
         ("The Horned Helmet", "92107", _AR + "icon_heavy_plated_leather_helmet_v2.icon_heavy_plated_leather_helmet_v2"),
         ("Scorpion Helm", "92108", _AR + "icon_stygian_M_helmet.icon_stygian_M_helmet"),
         ("Cimmerian Fur Helmet", "52566", _AR + "icon_cimmerian_M_helmet.icon_cimmerian_M_helmet")]
# Kits (admin menu Kits tab + Characters, Item catalog: Add to Kit; player menu Kits tab). The kit
# settings are menu SETTINGS: "kitson", "kitlog", then kit<n>on / kit<n>cd for n = 1..N_KITS, in that order.
N_KITS = 3
KIT_NAMES = ["Kit 1", "Kit 2", "Kit 3"]   # until an admin renames them
KIT_MAX_ITEMS = 12                        # entries per kit
KIT_NAME_MAX = 24                         # characters
N_SCRIPTS = 5                             # the Scripting tab's command scripts
SCRIPT_LINES = 8                          # one console command each
SCRIPT_NAME_MAX = 24                      # characters
TRADE_MAX = 12                            # stacks per side of a trade (the tradeslots setting's top)
TRADE_BAG_ROWS = 40                       # backpack rows the Trade tab lists
TRADE_NEAR_ROWS = 8                       # nearby players it lists
TRADE_LOG_MAX = 200                       # lines kept in OwlTrades
TRADE_LOG_ROWS = 30                       # lines the admin Trading page shows (newest first)
# NPCs (npc_server, 14_npc, the NPC window and the admin NPC editor)
N_NPCS = 6                                # custom NPCs on a server
NPC_WARES = 8                             # wares per NPC
NPC_GEAR = 20                             # equipment slots copied from the placing admin (0..NPC_GEAR-1)
NPC_NAME_MAX = 24                         # characters, name and role
NPC_LINE_MAX = 200                        # characters of dialogue
NPC_TALK_DIST = 500                       # cm: how close a player must be to buy
NPC_CURRENCIES = [("Gold Coin", 11066), ("Silver Coin", 11065)]   # what wares are priced in (item ids)
NPC_PRICE_MAX = 1000000
CE_SELL_Q = (1, 40)   # NPC sell price, in quarters: 0.25x .. 10x
CE_BUY_Q = (1, 16)    # NPC buy price: 0.25x .. 4x

# Cheats (cheats_server, cheats_panel): (key, label, what it does). The move speed is separate
# (x1..CH_SPEED_MAX). Fly, invisibility and instant crafting have no safe hook in the game.
CHEATS = [
    ("god", "God mode", "You take no damage."),
    ("needs", "No hunger or thirst", "Food and water stop going down."),
    ("stam", "Infinite stamina", "Your stamina stays full."),
    ("free", "Free building", "Building pieces cost no materials."),
]
CH_SPEED_MAX = 5

PANELS = {
    "access": ["Access log"],
    "discord": ["Discord webhook"],
}
