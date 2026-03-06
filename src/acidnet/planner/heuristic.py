from __future__ import annotations

from acidnet.models import Intent, IntentType
from acidnet.planner.protocols import Planner, PlannerContext, PlannerResult


class HeuristicPlanner(Planner):
    """Maps pre-scored runtime goals to a single structured intent."""

    def plan(self, context: PlannerContext) -> PlannerResult:
        for goal in context.top_goals:
            if goal.startswith("eat:"):
                return PlannerResult(
                    intent=Intent(
                        intent_type=IntentType.EAT,
                        target_id=goal.split(":", 1)[1],
                        reason="Hunger is the top priority right now.",
                        priority=0.95,
                    ),
                    planner_name="heuristic",
                    used_persona_tokens=context.persona.traits,
                )
            if goal.startswith("trade_food:"):
                vendor_id = goal.split(":", 1)[1]
                return PlannerResult(
                    intent=Intent(
                        intent_type=IntentType.TRADE,
                        target_id=vendor_id,
                        reason="Need to secure food before hunger becomes dangerous.",
                        priority=0.9,
                    ),
                    planner_name="heuristic",
                    used_persona_tokens=context.persona.values,
                )
            if goal.startswith("share_rumor:"):
                target_id = goal.split(":", 1)[1]
                return PlannerResult(
                    intent=Intent(
                        intent_type=IntentType.SHARE_RUMOR,
                        target_id=target_id,
                        reason="This information looks socially valuable.",
                        priority=0.82,
                    ),
                    planner_name="heuristic",
                    used_persona_tokens=context.persona.traits,
                )
            if goal.startswith("move:"):
                location_id = goal.split(":", 1)[1]
                return PlannerResult(
                    intent=Intent(
                        intent_type=IntentType.MOVE,
                        target_location=location_id,
                        reason="Need to reach a better place for the next task.",
                        priority=0.7,
                    ),
                    planner_name="heuristic",
                    used_persona_tokens=context.persona.values,
                )
            if goal.startswith("work:"):
                return PlannerResult(
                    intent=Intent(
                        intent_type=IntentType.WORK,
                        reason="Routine work keeps the village stable.",
                        priority=0.6,
                    ),
                    planner_name="heuristic",
                    used_persona_tokens=context.persona.values,
                )

        return PlannerResult(
            intent=Intent(
                intent_type=IntentType.REST,
                reason="No urgent need outranks conserving effort.",
                priority=0.3,
            ),
            planner_name="heuristic",
            used_persona_tokens=context.persona.traits,
        )
