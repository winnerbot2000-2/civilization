# Tuning Notes

The base configuration intentionally biases the simulation toward visible
proto-social behavior on small maps:

- moderate water concentration to create recurring travel corridors
- strong bad-season food pressure to make storage and sharing relevant
- child dependency long enough that caregivers matter
- low but non-zero reproduction pressure so generations appear in multi-year runs
- small path and hearth persistence bonuses to make site reuse detectable

Key parameters to tune first:

- `world.good_season_food_multiplier`
- `world.bad_season_food_multiplier`
- `world.food_regrowth_*`
- `agents.initial_population`
- `social.share_*`
- `life.child_stage_days`
- `life.base_conception_chance`
- `materials.hearth_strength_gain`
