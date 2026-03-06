from __future__ import annotations

import ast
import re
from dataclasses import asdict, dataclass


WORD_RE = re.compile(r"[a-zA-Z']+")


@dataclass(frozen=True, slots=True)
class DialogueRewardBreakdown:
    total_score: float
    grounded_score: float
    brevity_score: float
    rumor_score: float
    pressure_score: float
    metadata: dict[str, object]


def score_dialogue_response_from_prompt(user_prompt: str, response_text: str) -> DialogueRewardBreakdown:
    sample = extract_world_sample(user_prompt)
    return score_dialogue_response(sample, response_text)


def score_dialogue_response(sample: dict, response_text: str) -> DialogueRewardBreakdown:
    normalized = response_text.lower()
    words = WORD_RE.findall(normalized)
    word_count = len(words)

    location_name = str(sample["location"]["name"]).lower()
    weather = str(sample["world"]["weather"]).lower()
    profession = str(sample["npc"]["profession"]).lower()
    hunger = float(sample["npc"]["hunger"])
    rumors = [str(item).lower() for item in sample["npc"].get("known_rumors", [])]

    grounded_hits = 0
    for token in {location_name, weather, profession}:
        if token and token in normalized:
            grounded_hits += 1
    grounded_score = min(1.0, grounded_hits / 2.0)

    if 8 <= word_count <= 80:
        brevity_score = 1.0
    elif 4 <= word_count <= 120:
        brevity_score = 0.6
    else:
        brevity_score = 0.2

    rumor_score = 0.0
    if rumors:
        rumor_score = 1.0 if any(_overlap_ratio(normalized, rumor) >= 0.2 for rumor in rumors[:2]) else 0.2
    else:
        rumor_score = 0.7

    pressure_terms = {"food", "bread", "hunger", "market", "weather", "scarcity", "grain"}
    pressure_hit = any(term in normalized for term in pressure_terms)
    pressure_score = 1.0 if (hunger >= 45 and pressure_hit) else 0.7 if hunger < 45 else 0.2

    total_score = round(
        grounded_score * 0.35 + brevity_score * 0.2 + rumor_score * 0.25 + pressure_score * 0.2,
        3,
    )
    return DialogueRewardBreakdown(
        total_score=total_score,
        grounded_score=round(grounded_score, 3),
        brevity_score=round(brevity_score, 3),
        rumor_score=round(rumor_score, 3),
        pressure_score=round(pressure_score, 3),
        metadata={
            "word_count": word_count,
            "location_name": sample["location"]["name"],
            "weather": sample["world"]["weather"],
            "profession": sample["npc"]["profession"],
        },
    )


def reward_breakdown_to_dict(breakdown: DialogueRewardBreakdown) -> dict[str, object]:
    return asdict(breakdown)


def extract_world_sample(user_prompt: str) -> dict:
    marker = "World sample:"
    _, sample_text = user_prompt.split(marker, 1)
    return ast.literal_eval(sample_text.strip())


def _overlap_ratio(response_text: str, reference_text: str) -> float:
    response_tokens = set(WORD_RE.findall(response_text))
    reference_tokens = set(WORD_RE.findall(reference_text))
    if not reference_tokens:
        return 0.0
    return len(response_tokens & reference_tokens) / len(reference_tokens)
