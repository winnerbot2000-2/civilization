from __future__ import annotations

from civsim.learning.reinforcement import apply_reinforcement
from civsim.memory.habits import transition_bias
from civsim.memory.social import remember_social
from civsim.memory.spatial import decay_spatial_memory, remember_site


def test_spatial_memory_decay_prunes_weak_entries() -> None:
    memory = {}
    remember_site(memory, "water", 10, payoff=0.8, risk=0.1, day=0, max_entries=4)
    for _ in range(800):
        decay_spatial_memory(memory, 0.01)
    assert memory == {}


def test_emotional_success_strengthens_spatial_revisit_bias() -> None:
    memory = {}
    remember_site(memory, "water", 5, payoff=1.0, risk=0.0, day=1, max_entries=4, emotional_impact=1.2, revisit_delta=0.8)
    remember_site(memory, "water", 6, payoff=1.0, risk=0.0, day=1, max_entries=4, emotional_impact=0.0, revisit_delta=0.1)
    assert memory[("water", 5)].revisit_bias > memory[("water", 6)].revisit_bias
    assert memory[("water", 5)].emotional_weight > memory[("water", 6)].emotional_weight


def test_social_harm_creates_distrust() -> None:
    edges = {}
    remember_social(edges, 2, day=1, trust_delta=0.1, emotional_impact=0.5)
    remember_social(edges, 2, day=2, harm_delta=0.4, trust_delta=-0.1, emotional_impact=1.0)
    edge = edges[2]
    assert edge.harm > 0.0
    assert edge.negative_salience > 0.0
    assert edge.trust < 0.1


def test_successful_action_sequences_form_habit_bias() -> None:
    habits = {}
    apply_reinforcement(
        habits,
        action="drink",
        outcome_score=0.8,
        rate=0.2,
        previous_action="move_to_known_site",
        context_key="good",
    )
    assert transition_bias(habits, "move_to_known_site", "drink") > 0.0
