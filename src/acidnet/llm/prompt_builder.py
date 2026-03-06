from __future__ import annotations

from acidnet.llm.protocols import DialogueContext


def build_system_prompt(context: DialogueContext) -> str:
    return """You are a small NPC dialogue model inside a village simulation.

Respond as exactly one NPC.
Stay grounded in the supplied state.
Do not invent inventory, map facts, rumors, or relationships not present in context.
Keep the answer compact and game-usable.
Do not explain your reasoning.
"""


def build_user_prompt(context: DialogueContext) -> str:
    memories = [memory.summary for memory in context.salient_memories[:3]]
    beliefs = [f"{belief.subject_id}:{belief.predicate}:{belief.confidence:.2f}" for belief in context.salient_beliefs[:4]]
    rumors = [rumor.content for rumor in context.visible_rumors[:3]]
    return f"""NPC:
- name: {context.npc.name}
- profession: {context.npc.profession}
- traits: {", ".join(context.persona.traits) or "none"}
- speech_style: {", ".join(context.persona.speech_style) or "none"}
- values: {", ".join(context.persona.values) or "none"}

World:
- day: {context.world.day}
- tick: {context.world.tick}
- weather: {context.world.weather}
- location: {context.location.name}
- npc_hunger: {context.npc.hunger:.1f}
- player_hunger: {context.player.hunger:.1f}
- relationship_score_to_player: {context.relationship_score:.2f}

Beliefs:
{beliefs or ["none"]}

Memories:
{memories or ["none"]}

Rumors:
{rumors or ["none"]}

Interaction:
- mode: {context.interaction_mode}
- player_prompt: {context.player_prompt}

Output one short in-character reply only.
"""
