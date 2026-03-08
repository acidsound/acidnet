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
- If the player asks a direct question, make the student answer that question in the first sentence.
- Prefer answers that directly resolve the player's latest words over generic atmosphere or reusable flavor text.
- If the state does not support a confident answer, have the student say so plainly instead of guessing.
- If the player is hungry or asks for food, never let the student present non-food goods as edible help.
- Treat edible help as the edible subset of the provided inventory state only.
- If the NPC has no edible food in state, have the student say that plainly and redirect toward likely food help instead of unrelated stock.
- If the provided inventory state has no edible goods, never let the student claim bread, fish, stew, wheat, meals, or food are on hand.
- If the player asks to buy or sell food and the provided inventory state has no edible goods, have the student say that plainly and redirect instead of substituting unrelated stock.
- When the student mentions what the NPC has, can spare, or can sell, only allow exact items that appear in the provided inventory state.
- If the sample includes `buy_options` or `debt_options`, treat those as the exact current trade contract for what the NPC can sell and what it costs.
- If the player asks what something costs, only let the student quote a price that appears in the provided `buy_options` or `debt_options` for that exact item.
- If the sample includes `ask_options`, treat that as the exact zero-cash spare/share contract for free help.
- If the player asks for something on debt, ground the answer in `debt_options` instead of raw market prices.
- If the player asks for something for free, to spare it, or to share it, ground the answer in `ask_options` instead of drifting into a cash quote.
- If the sample includes `trade_fact`, treat it as the exact server-authored trade adjudication and do not change its quantities, prices, or outcome meaning.
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
