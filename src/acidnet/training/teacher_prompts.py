from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TeacherConfig:
    teacher_model: str = "gpt-5.3"
    world_name: str = "acidnet village"


def teacher_system_prompt(config: TeacherConfig) -> str:
    return f"""You are the teacher model for {config.world_name}.

Your job is to create compact, high-signal supervision for an NPC persona/dialogue student model.

Rules:
- Stay tightly grounded in the provided world state.
- Preserve persona consistency, relationship signals, hunger pressure, and rumor context.
- Do not invent map facts, inventory values, or hidden world state.
- Output only valid JSON matching the requested schema.
- Prefer concise, game-usable dialogue over essay-like prose.
- If the NPC should refuse, stall, misdirect, or speak cautiously, do so in-character.
"""


def dialogue_user_prompt(sample: dict) -> str:
    return f"""Task: Generate one training example for the NPC dialogue student.

Return JSON with this schema:
{{
  "task": "dialogue",
  "npc_id": "...",
  "persona_summary": "...",
  "situation_summary": "...",
  "player_prompt": "...",
  "interaction_goal": "...",
  "target_style_tags": ["..."],
  "response": "...",
  "memory_write": {{
    "summary": "...",
    "importance": 0.0
  }}
}}

World sample:
{sample}
"""


def planner_user_prompt(sample: dict) -> str:
    return f"""Task: Generate one training example for the NPC planner student.

Return JSON with this schema:
{{
  "task": "planner",
  "npc_id": "...",
  "top_goal": "...",
  "intent": {{
    "intent_type": "move|talk|trade|eat|work|rest|share_rumor|investigate",
    "target_id": "...",
    "target_location": "...",
    "reason": "...",
    "dialogue": "...",
    "priority": 0.0
  }},
  "memory_write": {{
    "summary": "...",
    "importance": 0.0
  }}
}}

Planner requirements:
- Keep the intent physically executable inside the provided world state.
- If the NPC is hungry or under rumor-driven pressure, reflect that in the chosen top goal.
- Dialogue is optional and should stay short enough for a game UI.

World sample:
{sample}
"""
