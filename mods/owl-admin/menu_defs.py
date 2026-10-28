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
    ("players", "Players", "Per-player restrictions"),
    ("characters", "Characters", "Fix levels, stats and points"),
    ("commands", "Commands", "Player chat commands and cooldowns"),
    ("kits", "Kits", "Item bundles players can claim with /kits"),
    ("trading", "Trading", "Rules for players trading items with each other"),
    ("pets", "Pets", "Custom pets players can buy"),
    ("hud", "HUD", "What every player sees on screen"),
    ("restart", "Server Restart", "Warn players before a restart"),
    ("scripting", "Scripting", "Write and run admin scripts"),
    ("discord", "Discord", "Send server events to a Discord channel"),
    ("cheats", "Cheats", "Admin-only powers for your own character. Every use is logged"),
]


def T(id, tab, label, desc, default):
    return {"id": id, "tab": tab, "label": label, "desc": desc, "type": "toggle", "default": default}


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
    T("chgod", "cheats", "God mode", "Your character takes no damage.", False),
    T("chfly", "cheats", "Fly", "Move freely through the air and past obstacles.", False),
    T("chstam", "cheats", "Infinite stamina", "Stamina never runs out.", False),
    T("chneeds", "cheats", "No hunger or thirst", "Food and water stay full.", False),
    T("chinvis", "cheats", "Invisible to players", "Players cannot see your character.", False),
    N("chspeed", "cheats", "Move speed", "Scales how fast your character moves.", 1, 10, 1, "x", 1),
    T("chcraft", "cheats", "Instant crafting", "Crafting finishes at once.", False),
    T("chbuild", "cheats", "Build anywhere", "Ignore building limits and protected zones.", False),
    T("chcd", "cheats", "Ignore command cooldowns", "Use /home and other commands without waiting.", False),
    T("tradeon", "trading", "Player trading enabled", "Lets players offer items to each other in a trade window.", True),
    N("tradedist", "trading", "Max distance between traders", "Both players must be this close, in metres, to start or keep a trade open.", 2, 50, 1, "m", 10),
    N("tradeslots", "trading", "Item slots per side", "How many different items each player can put into one trade.", 1, 24, 1, "", 12),
    N("tradecd", "trading", "Trade cooldown", "Seconds a player must wait before starting another trade.", 0, 600, 10, "s", 30),
    N("tradetimeout", "trading", "Trade request timeout", "Seconds the other player has to accept before the request expires.", 10, 120, 5, "s", 30),
    T("tradecur", "trading", "Allow currency in trades", "Players may put coins or other currency into a trade.", True),
    T("tradeblock", "trading", "Block restricted items", "Items on the restricted list cannot be traded.", True),
    T("tradeconfirm", "trading", "Require both players to confirm", "Both players must press Confirm after the final offer. Changing an offer clears both confirmations.", True),
    T("tradeclan", "trading", "Clan members only", "Players can only trade with members of their own clan.", False),
    T("tradecombat", "trading", "Block trading in combat", "Trading is refused for a short time after taking or dealing damage.", True),
    T("tradelog", "trading", "Log every trade", "Records who traded what, and when, for admins to review.", True),
    T("peton", "pets", "Pet shop enabled", "Players can open the pet shop and buy companion pets with coins.", True),
    N("petmax", "pets", "Pets owned per player", "Most pets one player can own at a time.", 1, 8, 1, "", 3),
    N("petactive", "pets", "Pets out at once", "How many owned pets a player can summon together.", 1, 3, 1, "", 1),
    N("petprice", "pets", "Price multiplier", "Scales every pet price in the shop.", 0.5, 5, 0.5, "x", 1),
    T("petsell", "pets", "Allow selling pets back", "Players get part of the price back when they release a pet.", False),
    T("petdie", "pets", "Pets can die", "A pet that is killed must be bought again. When off, it only has to be summoned again after a short wait.", False),
    T("petlog", "pets", "Log pet purchases", "Records who bought which pet, and when.", True),
    T("tradeadmin", "trading", "Post trades to this menu", "Each finished trade appears in the trade log below, and online admins get a notice.", True),
    T("kitson", "kits", "/kits", "Lets players open the kit list and claim a kit.", True),
    T("kitcombat", "kits", "Block /kits in combat", "Kits cannot be claimed right after fighting.", True),
    T("kit1on", "kits", "Kit 1", "Available to claim. Name and items are set below.", True),
    N("kit1cd", "kits", "Kit 1 cooldown", "Minutes before the same player can claim Kit 1 again.", 0, 10080, 60, "m", 1440),
    T("kit2on", "kits", "Kit 2", "Available to claim. Name and items are set below.", True),
    N("kit2cd", "kits", "Kit 2 cooldown", "Minutes before the same player can claim Kit 2 again.", 0, 10080, 60, "m", 4320),
    T("kit3on", "kits", "Kit 3", "Available to claim. Name and items are set below.", False),
    N("kit3cd", "kits", "Kit 3 cooldown", "Minutes before the same player can claim Kit 3 again.", 0, 10080, 60, "m", 10080),
    N("stack", "loot", "Stack size multiplier", "Scales how many of an item fit in one slot.", 1, 10, 1, "x", 2),
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
    ("equipment", "Equipment & Owl Mask", "Your gear and the Owl Mask"),
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
CE_SELL_Q = (1, 40)   # NPC sell price, in quarters: 0.25x .. 10x
CE_BUY_Q = (1, 16)    # NPC buy price: 0.25x .. 4x

PANELS = {
    "access": ["Access log"],
    "players": ["Per-player restrictions (build, mute, PvP, ban)"],
    "kits": ["Kit contents editor"],
    "trading": ["Trade log"],
    "restart": ["Restart schedule, player alerts and alert sound"],
    "scripting": ["Script editor and console"],
    "discord": ["Discord webhook"],
    "cheats": ["Teleport", "Spawn items"],
}
