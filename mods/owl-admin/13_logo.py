"""owl-admin step 13: T_OwlLogo -- imports art/owl_logo.png (drawn by art/owl_logo.py) as a UI
texture for both menus' header (menu_shell.Shell.header). Runs first in the manifest: 03 and 07
reference the texture.

UI settings: no mipmaps, UserInterface2D compression (keeps the alpha edge), the UI texture
group and never streamed, so the logo is crisp and always resident.

Run with Play STOPPED:  python ue_run.py mods/owl-admin/13_logo.py
"""
import sys
for _m in list(sys.modules):
    if _m == "bpkit" or _m.startswith("bpkit."):
        sys.modules.pop(_m, None)
import unreal
import os
from bpkit import config as _cfg
MOD_DIR = os.path.join(_cfg.REPO_ROOT, "mods", "owl-admin")
sys.path.insert(0, MOD_DIR)
sys.modules.pop("oa_config", None)
import oa_config as MOD

eal = unreal.EditorAssetLibrary
assert not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor(), \
    "Play-in-Editor is running -- stop Play first"

PKG = MOD.resolve_pkg()
src = os.path.join(MOD_DIR, MOD.LOGO_PNG)
assert os.path.isfile(src), "no logo art: " + src

t = unreal.AssetImportTask()
t.set_editor_property("filename", src)
t.set_editor_property("destination_path", PKG)
t.set_editor_property("destination_name", MOD.LOGO_TEX)
t.set_editor_property("automated", True)
t.set_editor_property("replace_existing", True)
t.set_editor_property("save", False)
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([t])

tex = eal.load_asset("%s/%s" % (PKG, MOD.LOGO_TEX))
assert isinstance(tex, unreal.Texture2D), "import failed: %s" % list(t.get_editor_property("imported_object_paths") or [])
tex.set_editor_property("mip_gen_settings", unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS)
tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_EDITOR_ICON)
tex.set_editor_property("lod_group", unreal.TextureGroup.TEXTUREGROUP_UI)
tex.set_editor_property("never_stream", True)
tex.set_editor_property("srgb", True)
assert eal.save_asset(tex.get_path_name(), only_if_is_dirty=False), "could not save " + tex.get_path_name()
print("BUILD OK: %s (%dx%d)" % (tex.get_path_name(), tex.blueprint_get_size_x(), tex.blueprint_get_size_y()))
