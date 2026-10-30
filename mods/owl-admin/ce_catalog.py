"""The character editor's item catalogue, read from the game's item table at BUILD time (needs
the editor).

    entries = catalog(unreal)   # [{"id", "cat", "name", "icon"}] sorted by name

Every ItemTable row with an English name (tm_catalog's NSLOCTEXT reading, or the string table a
LOCTABLE name points at; dev rows "xx..." are skipped). cat = the menu_defs.CE_ITEM_CATS index its GUICategory belongs to, or -1 (shown only
under All). Baked into the admin menu as arrays (03), so the Item catalog tab can search and
the Inventory tab can name what a player carries, with no data-table reads at runtime.
"""
import json

import re

from tm_catalog import ITEM_TABLE, _NSLOC, item_icon

_LOCTABLE = re.compile(r'LOCTABLE\("([^"]+)",\s*"([^"]+)"\)')


def _table_name(unreal, raw):
    """A name kept in a string table (LOCTABLE("<table>", "<key>"), e.g. the Anvil Keeper gear), or ""."""
    m = _LOCTABLE.search(raw)
    if not m:
        return ""
    return (unreal.StringTableLibrary.get_table_entry_source_string(m.group(1), m.group(2)) or "").strip()


def catalog(unreal):
    import menu_defs as D
    dt = unreal.load_asset(ITEM_TABLE)
    assert dt, "no item table at " + ITEM_TABLE
    lib = unreal.DataTableFunctionLibrary
    cat_of = {}
    for i, (_k, _l, gui) in enumerate(D.CE_ITEM_CATS):
        for gc in gui or ():
            cat_of[gc] = i
    # the JSON export's "Name" key is the row name, so the display name comes from the column
    names = dict(zip([str(n) for n in lib.get_data_table_row_names(dt)],
                     lib.get_data_table_column_as_string(dt, "Name")))
    entries = []
    for r in json.loads(lib.export_data_table_to_json_string(dt)):
        rid = str(r.get("Name"))
        if not rid.isdigit():
            continue                           # the game adds items by template id = the row name
        raw = names.get(rid, "")
        m = _NSLOC.search(raw)
        name = m.group(1).replace('\\"', '"').strip() if m else _table_name(unreal, raw)
        if not name or name.lower().startswith("xx"):
            continue
        entries.append({"id": int(rid), "cat": cat_of.get(str(r.get("GUICategory")), -1), "name": name,
                        "icon": item_icon(r)})
    return sorted(entries, key=lambda e: (e["name"].lower(), e["id"]))
