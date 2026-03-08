from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from acidnet.simulator.models import Belief, EpisodicMemory, Location, NPCState, PersonaProfile, PlayerState, Rumor, WorldState


class DialogueTradeOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item: str
    quantity: int = Field(ge=0)
    price: int | None = Field(default=None, ge=0)


class DialogueTradeFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    item: str | None = None
    quantity: int = Field(default=1, ge=0)
    available_quantity: int = Field(default=0, ge=0)
    listed_unit_price: int | None = Field(default=None, ge=0)
    debt_unit_price: int | None = Field(default=None, ge=0)
    offered_total_gold: int | None = None
    minimum_total_gold: int | None = Field(default=None, ge=0)
    accepted_total_gold: int | None = Field(default=None, ge=0)
    counter_total_gold: int | None = Field(default=None, ge=0)
    error_code: str | None = None
    stock: list[DialogueTradeOption] = Field(default_factory=list)


class DialogueContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    npc: NPCState
    persona: PersonaProfile
    player: PlayerState
    world: WorldState
    location: Location
    interaction_mode: str
    player_prompt: str
    system_prompt: str | None = None
    relationship_score: float = 0.0
    salient_beliefs: list[Belief] = Field(default_factory=list)
    salient_memories: list[EpisodicMemory] = Field(default_factory=list)
    visible_rumors: list[Rumor] = Field(default_factory=list)
    buy_options: list[DialogueTradeOption] = Field(default_factory=list)
    sell_options: list[DialogueTradeOption] = Field(default_factory=list)
    ask_options: list[DialogueTradeOption] = Field(default_factory=list)
    give_options: list[DialogueTradeOption] = Field(default_factory=list)
    debt_options: list[DialogueTradeOption] = Field(default_factory=list)
    trade_fact: DialogueTradeFact | None = None


class DialogueResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    adapter_name: str
    latency_ms: float = Field(default=0.0, ge=0.0)
    used_memory_ids: list[str] = Field(default_factory=list)
    used_rumor_ids: list[str] = Field(default_factory=list)


class DialogueModelAdapter(Protocol):
    def prepare(self) -> str | None:
        """Prepare any runtime resources needed before the first dialogue turn."""

    def generate(self, context: DialogueContext) -> DialogueResult:
        """Return an NPC utterance for the current interaction context."""
