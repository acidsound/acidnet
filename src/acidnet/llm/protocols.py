from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from acidnet.models import Belief, EpisodicMemory, Location, NPCState, PersonaProfile, PlayerState, Rumor, WorldState


class DialogueContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    npc: NPCState
    persona: PersonaProfile
    player: PlayerState
    world: WorldState
    location: Location
    interaction_mode: str
    player_prompt: str
    relationship_score: float = 0.0
    salient_beliefs: list[Belief] = Field(default_factory=list)
    salient_memories: list[EpisodicMemory] = Field(default_factory=list)
    visible_rumors: list[Rumor] = Field(default_factory=list)


class DialogueResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    adapter_name: str
    latency_ms: float = Field(default=0.0, ge=0.0)
    used_memory_ids: list[str] = Field(default_factory=list)
    used_rumor_ids: list[str] = Field(default_factory=list)


class DialogueModelAdapter(Protocol):
    def generate(self, context: DialogueContext) -> DialogueResult:
        """Return an NPC utterance for the current interaction context."""
