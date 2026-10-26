"""Metadata for the owl-admin mod -- the Owl Admin (Beta) screens from the design canvas,
rebuilt as real Conan UMG widgets.

OUTPUT_PKG must be the mod's own content root (/Game/Mods/<ModName>) so the cook
tags the assets "(Mod Asset)". The OwlAdmin mod must exist in the DevKit (Mods tool ->
create) and be the ACTIVE mod for that package to be writable; build steps fall back
to /Game/_Scratch/OwlAdmin with a DRY RUN banner when it isn't.
"""

OUTPUT_PKG = "/Game/Mods/OwlAdmin"
SCRATCH_PKG = "/Game/_Scratch/OwlAdmin"

ALERTS_WBP = "WBP_OwlAlerts"          # HUD board: server alert banner + notice cards

# The canvas boards are drawn at 1280x720; UMG lays out at a 1080p reference (DPI
# scale 1.0), so board px * 1.5 = UMG units. UMG font Size is in points (px * 0.75).
BOARD_SCALE = 1.5

FONT_BOLD = "/Game/Fonts/Kelson_Sans_Bold.Kelson_Sans_Bold"         # board: Rajdhani 700
FONT_REGULAR = "/Game/Fonts/Kelson_Sans_Regular.Kelson_Sans_Regular"  # board: Rajdhani 500

VERSION = 1


def full(pkg, name):
    """'/Game/.../Name.Name' object path for an asset NAME in package pkg."""
    return "%s/%s.%s" % (pkg, name, name)
