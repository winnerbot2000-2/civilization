from __future__ import annotations


def clamp_trait(value: float) -> float:
    return max(0.0, min(1.0, value))


def inherit_traits(parent_a, parent_b, rng, sigma: float) -> dict[str, float]:
    child_traits: dict[str, float] = {}
    for name in ("boldness", "sociability", "patience", "curiosity", "aggression", "attachment_strength"):
        base = (getattr(parent_a.traits, name) + getattr(parent_b.traits, name)) * 0.5
        child_traits[name] = clamp_trait(base + rng.gauss(0.0, sigma))
    return child_traits
