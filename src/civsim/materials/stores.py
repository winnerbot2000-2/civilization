from __future__ import annotations


def store_food(site, amount: float, capacity: float) -> float:
    capacity_left = max(0.0, capacity - site.communal_food)
    stored = min(amount, capacity_left)
    site.communal_food += stored
    return stored


def take_food(site, amount: float) -> float:
    taken = min(amount, site.communal_food)
    site.communal_food -= taken
    return taken
