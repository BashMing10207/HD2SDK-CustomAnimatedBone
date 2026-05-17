from .virtual_skeleton import VirtualSkeleton
from ..utils.constants import UnitID, IkSkeletonID, AnimationID, StateMachineID, RagdollProfileID, PhysicsID
from ..utils.logger import PrettyPrint

class ChainPatcher:
    """
    Orchestrates the patching of multiple dependent binary assets based on a
    Virtual Skeleton (the Single Source of Truth).
    """
    def __init__(self, virtual_skeleton: VirtualSkeleton, name_to_index: dict, toc_manager, unit_id: int, patch_animations: bool = True):
        self.virtual_skeleton = virtual_skeleton
        self.name_to_index = name_to_index
        self.toc_manager = toc_manager
        self.unit_id = unit_id
        self.new_bone_count = len(virtual_skeleton)
        self.patch_animations = patch_animations

    def run(self):
        """Executes the chain-patching process for all relevant assets."""
        PrettyPrint("Starting Chain-Patching process...", "info")

        unit_entry = self.toc_manager.GetEntryByLoadArchive(self.unit_id, UnitID)
        if not unit_entry:
            raise RuntimeError(f"Could not find unit entry for ID: {self.unit_id}")
        if not unit_entry.IsLoaded:
            unit_entry.Load(False, False)

        unit_data = unit_entry.LoadedData

        # 1. Patch IK Skeleton
        if unit_data.BonesRef != 0:
            self._patch_dependent_asset(unit_data.BonesRef, IkSkeletonID, "ik_skeleton")

        # 2. Patch assets referenced by the State Machine (Animations, Ragdolls)
        if unit_data.StateMachineRef != 0:
            sm_entry = self.toc_manager.GetEntry(unit_data.StateMachineRef, StateMachineID, SearchAll=True)
            if sm_entry:
                if not sm_entry.IsLoaded:
                    sm_entry.Load(False, False)

                # Patch Animations (optional)
                if self.patch_animations:
                    PrettyPrint("Animation patching is enabled, processing animations...", "info")
                    for anim_id in sm_entry.LoadedData.animation_ids:
                        self._patch_dependent_asset(anim_id, AnimationID, "animation")
                else:
                    PrettyPrint("Animation patching is disabled by user setting. Skipping animation patching.", "info")

                # Patch Ragdolls from State Machine
                PrettyPrint("Processing ragdolls from state machine...", "info")
                for ragdoll_item in sm_entry.LoadedData.ragdolls:
                    if ragdoll_item.unk_hash != 0: # This hash is the ID of the .ragdoll_profile
                        self._patch_dependent_asset(ragdoll_item.unk_hash, RagdollProfileID, "ragdoll_profile")
            else:
                PrettyPrint(f"No StateMachine found for ref {unit_data.StateMachineRef}. Skipping animation and ragdoll patching.", "warn")




        # 3. Patch Physics. Assume it shares the same ID as the unit.
        PrettyPrint("Processing physics, assuming same ID as unit...", "info")
        self._patch_dependent_asset(self.unit_id, PhysicsID, "physics")

        PrettyPrint("Chain-Patching process finished.", "info")

    def _patch_dependent_asset(self, file_id: int, type_id: int, asset_name: str):
        """Generic helper to find, load, sync, and save a dependent asset."""
        PrettyPrint(f"-> Processing {asset_name} (ID: {file_id})", "info")
        entry = self.toc_manager.GetEntryByLoadArchive(file_id, type_id)
        if not entry:
            # This is not an error, many units don't have all asset types.
            PrettyPrint(f"  - FIND: FAILED. Entry not found in archives. Skipping.", "info")
            return

        PrettyPrint(f"  - FIND: SUCCESS. Found entry.", "success")

        if not entry.IsLoaded:
            entry.Load(False, False)

        if not hasattr(entry.LoadedData, 'sync_with_skeleton'):
            PrettyPrint(f"Asset '{asset_name}' ({file_id}) has no sync_with_skeleton method. Skipping.", "warn")
            return

        PrettyPrint(f"  - PATCH: Attempting to sync with virtual skeleton...", "info")
        if entry.LoadedData.sync_with_skeleton(self.virtual_skeleton):
            PrettyPrint(f"  - PATCH: SUCCESS. Asset was modified.", "success")
            PrettyPrint(f"  - SAVE: Attempting to save modified asset data into patch entry...", "info")
            try:
                entry.Save()
                PrettyPrint(f"  - SAVE: SUCCESS. Asset data is ready to be written to the patch file.", "success")
            except Exception as e:
                PrettyPrint(f"  - SAVE: FAILED. An error occurred during the save process: {e}", "error")
        else:
            PrettyPrint(f"  - PATCH: SKIPPED. Asset was not modified or an error occurred. No changes will be saved.", "info")