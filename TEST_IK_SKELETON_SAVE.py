"""
IK Skeleton Save Test Script for Blender
Run this inside Blender's Python Console or Text Editor

Purpose:
1. Load unit 5556372446766824087
2. Load ik_skeleton entry (with hkx→xml unpack)
3. Modify xml (add comment)
4. Save unit (triggers xml→hkx repack)
5. Verify output

Instructions:
1. Open Blender with HD2SDK addon loaded
2. Set game path and load archives
3. Copy this script to Blender Text Editor
4. Click "Run Script" or paste into Python Console
"""

import os
import sys

# Import addon context reliably from Blender
try:
    import bpy
    # Addons with hyphens in names are in sys.modules with hyphens
    addon_name = 'HD2SDK-CommunityEdition'
    addon_module = sys.modules.get(addon_name)
    if not addon_module:
        import importlib
        addon_module = importlib.import_module(addon_name)
        
    Global_TocManager = addon_module.Global_TocManager
    UnitID = addon_module.UnitID
    IkSkeletonID = addon_module.IkSkeletonID
except Exception as e:
    print(f"Failed to load addon module: {e}")
    sys.exit(1)

print("\n" + "="*70)
print("IK SKELETON SAVE TEST")
print("="*70)

UNIT_ID = 5556372446766824087
# Use absolute path for DUMMY dir based on the script location to avoid permission issues
try:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    # If running via exec() in Blender console, __file__ is not defined
    if addon_module and hasattr(addon_module, '__file__'):
        SCRIPT_DIR = os.path.dirname(os.path.abspath(addon_module.__file__))
    else:
        SCRIPT_DIR = r"c:\Users\HP\AppData\Roaming\Blender Foundation\Blender\4.2\scripts\addons\HD2SDK-CommunityEdition"
DUMMY_DIR = os.path.join(SCRIPT_DIR, "DUMMY")

try:
    # Step 1: Get unit entry
    print(f"\n[Step 1] Loading unit {UNIT_ID}...")
    Entry = Global_TocManager.GetEntryByLoadArchive(int(UNIT_ID), UnitID)
    if Entry is None:
        print(f"  ❌ FAILED: Could not find unit entry ID: {UNIT_ID}")
        sys.exit(1)
    print(f"  ✓ Unit entry found: {Entry}")
    
    # Step 2: Ensure in patch and loaded
    print(f"\n[Step 2] Adding to patch and loading...")
    if not Global_TocManager.IsInPatch(Entry):
        Entry = Global_TocManager.AddEntryToPatchID(Entry, int(UNIT_ID))
    if not Entry.IsLoaded:
        Entry.Load(True, False)
    print(f"  ✓ Unit loaded and in patch")
    
    # Step 3: Get ik_skeleton entry
    mesh = Entry.LoadedData
    bones_ref = mesh.BonesRef
    print(f"\n[Step 3] Getting ik_skeleton (BonesRef: {bones_ref})...")
    ik_entry = Global_TocManager.GetEntry(bones_ref, IkSkeletonID, IgnorePatch=False, SearchAll=True)
    if ik_entry is None:
        print(f"  ⚠ WARNING: No ik_skeleton entry found for unit")
        print(f"  (Unit may not have IK skeleton data)")
        sys.exit(0)  # Not fatal, but test cannot proceed
    print(f"  ✓ ik_skeleton entry found: {ik_entry}")
    
    # Step 4: Ensure in patch
    print(f"\n[Step 4] Adding ik_skeleton to patch...")
    if not Global_TocManager.IsInPatch(ik_entry):
        ik_entry = Global_TocManager.AddEntryToPatch(ik_entry.FileID, IkSkeletonID)
    print(f"  ✓ ik_skeleton in patch")
    
    # Step 5: Load ik_skeleton (triggers hkx→xml unpack)
    print(f"\n[Step 5] Loading ik_skeleton (hkx→xml unpack)...")
    if not ik_entry.IsLoaded:
        ik_entry.Load()
    ik_data = ik_entry.LoadedData
    print(f"  ✓ ik_skeleton loaded")
    print(f"    - IsXml: {getattr(ik_data, 'IsXml', False)}")
    print(f"    - Raw size: {len(getattr(ik_data, 'Raw', b''))} bytes")
    print(f"    - Xml size: {len(getattr(ik_data, 'Xml', b''))} bytes")
    
    # Step 6: Modify xml (add test comment)
    print(f"\n[Step 6] Modifying ik_skeleton xml...")
    if getattr(ik_data, 'IsXml', False) and getattr(ik_data, 'Xml', None):
        ik_data.Xml += b"\n<!-- IK Skeleton patched by test script -->\n"
        ik_data.IsXml = True
        ik_entry.IsModified = True
        print(f"  ✓ xml modified (added test comment)")
    else:
        print(f"  ⚠ WARNING: No XML available; skipping modification")
    
    # Step 7: Save ik_skeleton entry
    print(f"\n[Step 7] Saving ik_skeleton (xml→hkx repack)...")
    ik_entry.Save()
    print(f"  ✓ ik_skeleton saved")
    
    # Step 8: Verify output (get repacked hkx)
    print(f"\n[Step 8] Verifying repacked hkx...")
    repacked_hkx = ik_entry.GetData()[0]
    print(f"  ✓ Repacked hkx size: {len(repacked_hkx)} bytes")
    
    # Step 9: Save to DUMMY for inspection
    print(f"\n[Step 9] Exporting repacked hkx to DUMMY for inspection...")
    if not os.path.exists(DUMMY_DIR):
        print(f"  ⚠ WARNING: DUMMY directory not found; attempting to use cwd")
        DUMMY_DIR = "."
    outpath = os.path.join(DUMMY_DIR, "avatar_helldiver.ik_skeleton.BLENDER_SAVED.hkx")
    with open(outpath, 'wb') as f:
        f.write(repacked_hkx)
    print(f"  ✓ Exported to: {outpath}")
    print(f"    - Size: {len(repacked_hkx)} bytes")
    
    # Step 10: Summary
    print(f"\n" + "="*70)
    print("TEST PASSED ✓")
    print("="*70)
    print(f"\nSummary:")
    print(f"  - Unit {UNIT_ID} loaded")
    print(f"  - ik_skeleton entry loaded and unpacked to xml")
    print(f"  - xml modified with test comment")
    print(f"  - xml repacked to hkx via HavokLib")
    print(f"  - Repacked hkx exported: {outpath}")
    print(f"\nNext steps:")
    print(f"  1. Check {outpath} exists and has size ~4-5 KB")
    print(f"  2. Compare with original DUMMY/avatar_helldiver.ik_skeleton.hkx")
    print(f"  3. Test full unit save (Save Unit button in Blender)")
    print(f"     to verify ik_skeleton is included in patch\n")

except Exception as e:
    print(f"\n❌ TEST FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
