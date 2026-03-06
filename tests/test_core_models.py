from pydantic import ValidationError

from acidnet.models import Intent, IntentType, NPCState, PersonaProfile, Rumor, RumorCategory


def test_persona_profile_supports_bias_fields() -> None:
    persona = PersonaProfile(
        persona_id="persona.merchant.greedy",
        archetype="merchant",
        profession="merchant",
        traits=["greedy", "chatty"],
        speech_style=["short", "pragmatic"],
        values=["profit", "reputation"],
        rumor_bias=0.25,
        trade_bias=0.8,
        conflict_bias=-0.1,
    )

    assert persona.archetype == "merchant"
    assert "profit" in persona.values


def test_intent_priority_is_bounded() -> None:
    try:
        Intent(
            intent_type=IntentType.TRADE,
            target_id="npc.baker",
            reason="Need bread before nightfall",
            priority=1.5,
        )
    except ValidationError:
        return

    raise AssertionError("Intent priority should be validated")


def test_npc_state_embeds_intent_and_rumor_ids() -> None:
    intent = Intent(
        intent_type=IntentType.SHARE_RUMOR,
        target_id="npc.cook",
        reason="Warn the cook about the grain shortage",
        priority=0.9,
    )
    npc = NPCState(
        npc_id="npc.merchant.01",
        name="Mira",
        persona_id="persona.merchant.greedy",
        profession="merchant",
        goals=["sell_food", "collect_rumors"],
        location_id="market_square",
        inventory={"bread": 3},
        hunger=22.0,
        current_intent=intent,
        known_rumor_ids=["rumor.grain.shortage.01"],
    )
    rumor = Rumor(
        rumor_id="rumor.grain.shortage.01",
        origin_npc_id="npc.farmer.01",
        content="The wheat field yield is down this week.",
        category=RumorCategory.SHORTAGE,
        confidence=0.7,
        value=0.8,
        created_tick=12,
        last_shared_tick=12,
    )

    assert npc.current_intent is not None
    assert npc.current_intent.intent_type == IntentType.SHARE_RUMOR
    assert rumor.category == RumorCategory.SHORTAGE
