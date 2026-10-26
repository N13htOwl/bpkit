"""The transmog catalogue, read from the game's item table at BUILD time (needs the editor).

    entries = catalog(unreal)   # [{"id", "slot", "cat", "name", "icon"}] sorted by slot, category, name

Every ItemTable row worn in one of the five transmog slots (menu_defs.TM_SLOTS: EquipLocation
3-7) is an appearance. Baked into the player menu as arrays (07), so the menu needs no
data-table reads at runtime. Names are the English text from the table's NSLOCTEXT values;
rows named through a string table (LOCTABLE, ~20, unreadable from Python here) and dev rows
("xxx_...") are skipped. About half the wearables have no icon (icon = "").
"""
import json
import re

ITEM_TABLE = "/Game/Items/ItemTable"
_NSLOC = re.compile(r'NSLOCTEXT\(\s*"[^"]*"\s*,\s*"[^"]*"\s*,\s*"((?:[^"\\]|\\.)*)"\s*\)')
_DEV_ICON = "icon_DEV_needs_icon"


def catalog(unreal):
    import menu_defs as D
    dt = unreal.load_asset(ITEM_TABLE)
    assert dt, "no item table at " + ITEM_TABLE
    lib = unreal.DataTableFunctionLibrary
    rows = [str(r) for r in lib.get_data_table_row_names(dt)]
    names = lib.get_data_table_column_as_string(dt, "Name")
    assert len(names) == len(rows), "name column doesn't line up with the rows"
    display = {}
    for r, n in zip(rows, names):
        m = _NSLOC.search(n)
        if m and m.group(1).strip():
            display[r] = m.group(1).replace('\\"', '"').strip()
    slot_of = {loc: i for i, (_k, _l, loc) in enumerate(D.TM_SLOTS)}
    cat_of = {}
    for i, (_k, _l, gui) in enumerate(D.TM_CATS):
        for gc in gui or ():
            cat_of[gc] = i
    other = [i for i, (_k, _l, gui) in enumerate(D.TM_CATS) if gui == ()][0]
    out = []
    for r in json.loads(lib.export_data_table_to_json_string(dt)):
        rid = str(r.get("Name"))               # the JSON export's "Name" key is the row name
        loc = r.get("EquipLocation")
        if loc not in slot_of or rid not in display or display[rid].lower().startswith("xxx"):
            continue
        icon = str(r.get("Icon") or "")
        if icon == "None" or _DEV_ICON in icon:
            icon = ""                          # about half the wearables have no icon: the cell shows a gem
        out.append({"id": rid, "slot": slot_of[loc], "cat": cat_of.get(str(r.get("GUICategory")), other),
                    "name": display[rid], "icon": icon})
    # item variants (tiers, epic versions) repeat a name and look: one per slot + name, the
    # one with an icon if any
    best = {}
    for e in out:
        k = (e["slot"], e["name"].lower())
        if k not in best or (e["icon"] and not best[k]["icon"]):
            best[k] = e
    return sorted(best.values(), key=lambda e: (e["slot"], e["cat"], e["name"].lower()))
