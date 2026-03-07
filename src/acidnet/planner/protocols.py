from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from acidnet.simulator.models import Belief, Intent, NPCState, PersonaProfile, Rumor


class PlannerContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    npc: NPCState
    persona: PersonaProfile
    top_goals: list[str] = Field(default_factory=list)
    salient_beliefs: list[Belief] = Field(default_factory=list)
    visible_rumors: list[Rumor] = Field(default_factory=list)
    nearby_entity_ids: list[str] = Field(default_factory=list)
    allowed_intents: list[str] = Field(default_factory=list)


class PlannerResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Intent
    planner_name: str
    used_persona_tokens: list[str] = Field(default_factory=list)


class Planner(Protocol):
    def plan(self, context: PlannerContext) -> PlannerResult:
        """Return the next high-level intent for an NPC."""
