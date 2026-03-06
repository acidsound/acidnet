from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class IntentType(StrEnum):
    MOVE = "move"
    TALK = "talk"
    TRADE = "trade"
    EAT = "eat"
    WORK = "work"
    REST = "rest"
    SHARE_RUMOR = "share_rumor"
    INVESTIGATE = "investigate"


class RumorCategory(StrEnum):
    ECONOMY = "economy"
    SOCIAL = "social"
    DANGER = "danger"
    SHORTAGE = "shortage"
    EVENT = "event"


class Location(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location_id: str
    name: str
    kind: str
    region_id: str = "region.greenfall"
    neighbors: list[str] = Field(default_factory=list)


class RegionNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    region_id: str
    name: str
    kind: str
    summary: str
    anchor_location_id: str | None = None
    local_location_ids: list[str] = Field(default_factory=list)
    stock_signals: dict[str, int] = Field(default_factory=dict)
    risk_level: float = Field(default=0.0, ge=0.0, le=1.0)


class RegionalRoute(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route_id: str
    from_region_id: str
    to_region_id: str
    travel_ticks: int = Field(ge=1)
    cargo_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    weather_sensitivity: float = Field(default=0.0, ge=0.0, le=1.0)
    seasonal_capacity: float = Field(default=1.0, gt=0.0)


class MarketItemState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str
    stock: int = Field(default=0, ge=0)
    base_price: int = Field(default=1, ge=1)
    current_price: int = Field(default=1, ge=1)
    spoilage_ticks: int | None = Field(default=None, ge=1)


class MarketState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: dict[str, MarketItemState] = Field(default_factory=dict)
    scarcity_index: float = Field(default=0.0, ge=0.0)


class WorldEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    event_type: str
    summary: str
    start_tick: int = Field(ge=0)
    end_tick: int | None = Field(default=None, ge=0)
    region_id: str | None = None
    route_id: str | None = None
    location_id: str | None = None


class GoalScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal_id: str
    category: str
    score: float = Field(ge=0.0)
    reason: str


class RelationshipState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    other_npc_id: str
    trust: float = Field(default=0.0, ge=-1.0, le=1.0)
    closeness: float = Field(default=0.0, ge=-1.0, le=1.0)
    fear: float = Field(default=0.0, ge=0.0, le=1.0)
    respect: float = Field(default=0.0, ge=0.0, le=1.0)


class Belief(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_id: str
    predicate: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_memory_ids: list[str] = Field(default_factory=list)


class EpisodicMemory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memory_id: str
    npc_id: str
    timestamp_tick: int = Field(ge=0)
    event_type: str
    summary: str
    entities: list[str] = Field(default_factory=list)
    location_id: str | None = None
    importance: float = Field(default=0.0, ge=0.0, le=1.0)
    sentiment: float = Field(default=0.0, ge=-1.0, le=1.0)
    tags: list[str] = Field(default_factory=list)


class Rumor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rumor_id: str
    origin_npc_id: str
    subject_id: str | None = None
    content: str
    category: RumorCategory
    confidence: float = Field(ge=0.0, le=1.0)
    value: float = Field(default=0.0, ge=0.0, le=1.0)
    distortion: float = Field(default=0.0, ge=0.0, le=1.0)
    hop_count: int = Field(default=0, ge=0)
    created_tick: int = Field(ge=0)
    last_shared_tick: int = Field(ge=0)


class PersonaProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    persona_id: str
    archetype: str
    profession: str
    traits: list[str] = Field(default_factory=list)
    speech_style: list[str] = Field(default_factory=list)
    values: list[str] = Field(default_factory=list)
    rumor_bias: float = Field(default=0.0, ge=-1.0, le=1.0)
    trade_bias: float = Field(default=0.0, ge=-1.0, le=1.0)
    conflict_bias: float = Field(default=0.0, ge=-1.0, le=1.0)


class Intent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent_type: IntentType
    target_id: str | None = None
    target_location: str | None = None
    reason: str
    dialogue: str | None = None
    priority: float = Field(default=0.5, ge=0.0, le=1.0)


class TravelState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_traveling: bool = False
    route_id: str | None = None
    origin_location_id: str | None = None
    destination_location_id: str | None = None
    ticks_remaining: int = Field(default=0, ge=0)
    risk_budget: float = Field(default=0.0, ge=0.0, le=1.0)


class NPCState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    npc_id: str
    name: str
    persona_id: str
    profession: str
    skills: list[str] = Field(default_factory=list)
    traits: list[str] = Field(default_factory=list)
    goals: list[str] = Field(default_factory=list)
    location_id: str
    home_location_id: str | None = None
    workplace_id: str | None = None
    inventory: dict[str, int] = Field(default_factory=dict)
    production_queue: dict[str, int] = Field(default_factory=dict)
    hunger: float = Field(default=0.0, ge=0.0, le=100.0)
    fatigue: float = Field(default=0.0, ge=0.0, le=100.0)
    carried_weight: float = Field(default=0.0, ge=0.0)
    carry_capacity: float = Field(default=12.0, gt=0.0)
    energy: float = Field(default=100.0, ge=0.0, le=100.0)
    money: int = Field(default=0, ge=0)
    health: float = Field(default=100.0, ge=0.0, le=100.0)
    social_status: float = Field(default=0.0, ge=0.0, le=1.0)
    is_vendor: bool = False
    travel_state: TravelState = Field(default_factory=TravelState)
    current_intent: Intent | None = None
    relationships: dict[str, RelationshipState] = Field(default_factory=dict)
    beliefs: list[Belief] = Field(default_factory=list)
    known_rumor_ids: list[str] = Field(default_factory=list)


class PlayerState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    player_id: str = "player"
    name: str = "Player"
    location_id: str
    focused_npc_id: str | None = None
    inventory: dict[str, int] = Field(default_factory=dict)
    hunger: float = Field(default=5.0, ge=0.0, le=100.0)
    fatigue: float = Field(default=0.0, ge=0.0, le=100.0)
    carried_weight: float = Field(default=0.0, ge=0.0)
    carry_capacity: float = Field(default=14.0, gt=0.0)
    money: int = Field(default=40, ge=0)
    travel_state: TravelState = Field(default_factory=TravelState)
    known_rumor_ids: list[str] = Field(default_factory=list)


class WorldState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tick: int = Field(default=0, ge=0)
    day: int = Field(default=0, ge=0)
    weather: str = "clear"
    field_stress: float = Field(default=0.0, ge=0.0, le=1.0)
    locations: dict[str, Location] = Field(default_factory=dict)
    regions: dict[str, RegionNode] = Field(default_factory=dict)
    regional_routes: list[RegionalRoute] = Field(default_factory=list)
    market: MarketState = Field(default_factory=MarketState)
    active_events: list[WorldEvent] = Field(default_factory=list)
    npc_ids: list[str] = Field(default_factory=list)
