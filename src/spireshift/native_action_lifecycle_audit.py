"""Compiler-derived lifecycle inventory with explicit findings and coverage limits."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

MUTATIONS = {
    "ForceClick",
    "EmitSignal",
    "EnqueueManualUse",
    "RequestEnqueue",
    "EnqueueWithoutSynchronizing",
    "TryManualPlay",
    "OnTryPurchaseWrapper",
    "Choose",
    "TrySetResult",
    "SetResult",
    "EndTurn",
    "PickRelicLocally",
    "SkipRelicLocally",
    "ChooseLocalOption",
    "ResolveReward",
    "ResolvePendingByIndices",
    "EnterMapCoord",
    "EnterRoom",
    "EnterNextAct",
    "SetDrawOrder",
    "SetPlayer",
    "StartRun",
    "LoadSave",
    "SaveCheckpoint",
    "CleanUp",
    "Discard",
    "ForceToMap",
}

CLI_FAMILIES = {
    "select_map_node": "map_travel",
    "play_card": "combat_card",
    "end_turn": "turn_transition",
    "choose_option": "event_and_rest",
    "select_card_reward_alternative": "card_reward",
    "select_card_reward": "card_reward",
    "skip_card_reward": "card_reward",
    "select_reward": "reward_claim",
    "skip_rewards": "reward_claim",
    "open_treasure": "treasure",
    "select_treasure_relic": "treasure",
    "skip_treasure_relic": "treasure",
    "buy_card": "shop_purchase",
    "buy_relic": "shop_purchase",
    "buy_potion": "shop_purchase",
    "remove_card": "shop_removal",
    "open_shop": "shop_presentation",
    "close_shop": "shop_presentation",
    "leave_shop": "shop_presentation",
    "select_bundle": "bundle_choice",
    "select_cards": "card_selection",
    "skip_select": "card_selection",
    "use_potion": "potion_use",
    "discard_potion": "potion_discard",
    "leave_room": "room_departure",
    "proceed": "room_act_and_ending_transition",
}
CONNECTOR_FILES = {
    "CardBundleSelectionSurfaceReader.cs": "bundle_choice",
    "CardRewardSurfaceReader.cs": "card_reward",
    "CharacterSelectSurfaceReader.cs": "startup",
    "CombatHandCardSelectionSurfaceReader.cs": "card_selection",
    "CombatTurnSurfaceReader.cs": "combat_card_potion_and_turn",
    "DeckEnchantSurfaceReader.cs": "card_selection",
    "EventDialogueSurfaceReader.cs": "event",
    "EventOptionSurfaceReader.cs": "event",
    "GameOverSurfaceReader.cs": "ending_presentation",
    "MapNavigationSurfaceReader.cs": "map_travel",
    "MenuSurfaceReaders.cs": "startup",
    "RewardClaimSurfaceReader.cs": "reward_claim_and_discard",
    "ShopSurfaceReaders.cs": "shop_purchase_and_presentation",
    "TreasureRoomSurfaceReader.cs": "treasure",
    "TutorialModalSurfaceReader.cs": "tutorial",
    "AtomicCardSelection.cs": "atomic_selection_orchestration",
    "NativeCombatPileSelection.cs": "card_selection",
    "NativeDeckCardSelection.cs": "card_selection",
    "NativeDeckTransformSelection.cs": "card_selection",
    "NativeDeckUpgradeSelection.cs": "card_selection",
    "NativeGeneratedCardChoice.cs": "card_selection",
    "NativeRestSite.cs": "rest",
    "NativeSimpleCardSelection.cs": "card_selection",
    "NativeInputResult.cs": "receipt_construction",
    "NativeNonCombatPotions.cs": "global_potion_use_and_discard",
    "NativePotionUseTransition.cs": "potion_acceptance_and_completion",
    "NativeUiActionRuntime.cs": "dispatch_and_current_binding_validation",
    "ActionSubmission.cs": "authority_snapshot_and_delivery_protocol",
}
COMPLETION = {
    "combat_card_potion_and_turn": (
        "native queue empty, effect inactive, actionable local play phase;"
        " required selections are separate owners"
    ),
    "map_travel": (
        "native travel transition plus current room/context; source-pinned tutorial-entry guard"
    ),
    "tutorial": "exact modal dismissal; map modal also waits for native room entry",
    "treasure": (
        "native complete Take/Skip menu and current treasure stage; "
        "selected effect still needs paired witness"
    ),
    "rest": "current native option completion or its exact card picker, then native rest/map owner",
    "atomic_selection_orchestration": (
        "accepted root, exact intermediate controls, matching semantic successor proof"
    ),
    "card_selection": (
        "exact current picker; native confirm/cancel and required parent-operation resumption"
    ),
    "card_reward": "native reward selector and resulting card/deck/public successor",
    "bundle_choice": "preview/confirmation receipts and exact bundle completion proof",
    "reward_claim_and_discard": (
        "native reward owner, discard action queue, and reward Proceed completion macro"
    ),
    "ending_presentation": (
        "explicit native terminal facts, Continue receipt and full native summary proof"
    ),
    "startup": (
        "exact current screen then mounted seeded run; isolated profile and shutdown/reset proof"
    ),
    "global_potion_use_and_discard": (
        "exact native action identity plus terminal CompletionTask; allow "
        "only proven required choice"
    ),
    "potion_acceptance_and_completion": (
        "same-run accepted action, completion/cancellation task, fault latch and owned child choice"
    ),
    "shop_purchase_and_presentation": (
        "native task started; complete effect barrier is NOT tracked by this adapter"
    ),
    "event": (
        "native option task is indirect through UI; current "
        "modal/selection/finished-event owner supplies observable boundary"
    ),
    "receipt_construction": (
        "receipt states delivery only; it is not an effect-completion certificate"
    ),
    "dispatch_and_current_binding_validation": (
        "routes to exact current handler; completion belongs to that handler and observer"
    ),
    "authority_snapshot_and_delivery_protocol": (
        "runtime, lease, snapshot and binding validated once; uncertain submission never retried"
    ),
}


def methods(layer: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {**method, "file": file["path"]} for file in layer["files"] for method in file["methods"]
    ]


def command_rows(layer: dict[str, Any]) -> list[dict[str, Any]]:
    all_methods = methods(layer)
    entry = next(m for m in all_methods if m["name"] == "ExecuteAction")
    rows = []
    for switch in entry["switches"]:
        if switch["expression"] != "action":
            continue
        for arm in switch["arms"]:
            for label in arm["labels"]:
                match = re.fullmatch(r'case "([a-z_]+)":', label)
                if match is None:
                    continue
                action = match[1]
                if action not in CLI_FAMILIES:
                    raise ValueError(f"Unreviewed CLI action: {action}")
                targets = [n for n in arm["calls"] if n.startswith("Do")]
                if len(targets) != 1:
                    raise ValueError(f"Unknown CLI dispatch shape: {action}")
                target = next(m for m in all_methods if m["name"] == targets[0])
                rows.append(
                    {
                        "action": action,
                        "family": CLI_FAMILIES[action],
                        "method": target["id"],
                        "source_sha256": target["sha256"],
                        "source_line": target["first_line"],
                        "native_calls": target["calls"],
                        "awaits": target["awaits"],
                        "exception_handlers": target["source"].count("catch"),
                        "source_changed_from_upstream": None,
                        "coverage": "source_reviewed_effect_evidence_is_separate",
                    }
                )
    return rows


def audit_inventory(inventory: dict[str, Any]) -> dict[str, Any]:
    layers = {layer["layer"]: layer for layer in inventory["layers"]}
    if set(layers) != {
        "original_CLI",
        "our_CLI56",
        "original_Connector",
        "our_Connector27",
        "our_Connector29",
    }:
        raise ValueError("Require all original and custom execution layers")
    original, current = command_rows(layers["original_CLI"]), command_rows(layers["our_CLI56"])
    before = {r["action"]: r for r in original}
    for row in current:
        row["source_changed_from_upstream"] = row["source_sha256"] != before.get(
            row["action"], {}
        ).get("source_sha256")
    connector = {}
    for name in ["original_Connector", "our_Connector27", "our_Connector29"]:
        entries = []
        for method in methods(layers[name]):
            if method["return_type"] != "NativeInputResult":
                continue
            file = Path(method["file"]).name
            if file not in CONNECTOR_FILES:
                raise ValueError(f"Unreviewed Connector delivery path: {method['id']}")
            family = CONNECTOR_FILES[file]
            calls = sorted(set(method["calls"]) & MUTATIONS)
            entries.append(
                {
                    "method": method["id"],
                    "file": method["file"],
                    "line": method["first_line"],
                    "source_sha256": method["sha256"],
                    "family": family,
                    "mutation_calls": calls,
                    "all_calls": method["calls"],
                    "delivery_is_effect_completion": False,
                    "completion_contract": COMPLETION[family],
                    "coverage": "source_reviewed_not_universal_live_effect_qualification",
                    "review_flag": "untracked_shop_task"
                    if "OnTryPurchaseWrapper" in method["calls"]
                    else None,
                }
            )
        connector[name] = entries
    control = {}
    for name, layer in layers.items():
        control[name] = [
            {
                "method": m["id"],
                "source_sha256": m["sha256"],
                "mutation_calls": sorted(set(m["calls"]) & MUTATIONS),
                "scope": "support_admin_or_legacy_not_an_ordinary_policy_action",
            }
            for m in methods(layer)
            if set(m["calls"]) & MUTATIONS
            and m["return_type"] != "NativeInputResult"
            and not m["name"].startswith("Do")
        ]
    return {
        "schema_version": "action-lifecycle-source-audit-v1",
        "scope": (
            "all_declared_CLI_actions_all_Connector_delivery_methods_and_support_mutation_sites"
        ),
        "original_CLI_actions": original,
        "our_CLI_actions": current,
        "Connector_methods": connector,
        "support_admin_legacy_mutation_sites": control,
        "compiler_layers": {
            name: {"files": len(layer["files"]), "methods": len(methods(layer))}
            for name, layer in layers.items()
        },
        "findings": [
            {
                "id": "CLI-UPSTREAM-01",
                "owner": "original_CLI",
                "status": "historical_replaced_in_our_CLI",
                "detail": (
                    "Potion-use failure or unconsumed bottle could trigger manual "
                    "discard; direct enqueue bypassed EnqueueManualUse."
                ),
            },
            {
                "id": "CLI-UPSTREAM-02",
                "owner": "original_CLI",
                "status": "historical_replaced_in_our_CLI",
                "detail": (
                    "Event/selection/end-turn recovery contains forced map/reset "
                    "behavior; it is not qualification evidence for the original CLI."
                ),
            },
            {
                "id": "CONNECTOR-POTION-01",
                "owner": "our_Connector27",
                "status": "fixed_in_Connector29",
                "detail": (
                    "Noncombat use acknowledged enqueue while bottle removal preceded "
                    "heal; exact native action/task now gates unrelated successor "
                    "input."
                ),
            },
            {
                "id": "CONNECTOR-POTION-02",
                "owner": "our_Connector27",
                "status": "fixed_in_Connector29",
                "detail": (
                    "Pending discard expired on bottle removal or action-state label "
                    "alone; now requires native terminal completion/cancellation task."
                ),
            },
            {
                "id": "CONNECTOR-SHOP-01",
                "owner": "original_and_custom_Connector",
                "status": "open_source_risk_requires_targeted_qualification",
                "detail": (
                    "Purchase/removal starts native async task and returns delivery. "
                    "Current shop readiness does not retain that task. Existing passed"
                    " effects do not prove every delayed pickup/hook."
                ),
            },
            {
                "id": "UI-CALLBACK-01",
                "owner": "original_and_custom_Connector",
                "status": "source_reviewed_content_interactions_not_exhaustive",
                "detail": (
                    "UI ForceClick/EmitSignal delivery requires actual next-"
                    "owner/effect evidence; readiness of a button alone never "
                    "certifies every callback is finished."
                ),
            },
        ],
        "all_mechanic_interactions_proven": False,
        "source_inventory_is_live_qualification": False,
    }
