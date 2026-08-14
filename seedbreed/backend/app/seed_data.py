"""Seed the database with one example grow so a fresh install isn't empty.

Idempotent — safe to run on an existing DB. Skips items that already exist.
Run manually inside the container if you want to reset/restore:
    docker exec -it seedbreed python -m app.seed_data
"""
from datetime import date
from .database import SessionLocal, Base, engine, run_lightweight_migrations
from . import models

Base.metadata.create_all(bind=engine)
run_lightweight_migrations()


def get_or_create(db, model, defaults=None, **lookup):
    obj = db.query(model).filter_by(**lookup).first()
    if obj:
        return obj, False
    params = {**lookup, **(defaults or {})}
    obj = model(**params)
    db.add(obj)
    db.flush()
    return obj, True


def main():
    db = SessionLocal()
    try:
        # ---- Strains ----
        sa, _ = get_or_create(db, models.Strain, name="Example Strain A",
                              defaults={"type": "hybrid"})
        sb, _ = get_or_create(db, models.Strain, name="Example Strain B",
                              defaults={"type": "hybrid"})

        # ---- Seeds (one batch per strain) ----
        sa_seed, _ = get_or_create(
            db, models.Seed, strain_id=sa.id,
            defaults={"origin": models.SeedOrigin.purchased, "quantity": 2,
                      "notes": "Example seed batch"},
        )
        sb_seed, _ = get_or_create(
            db, models.Seed, strain_id=sb.id,
            defaults={"origin": models.SeedOrigin.purchased, "quantity": 2,
                      "notes": "Example seed batch"},
        )

        # ---- Grow ----
        grow, created = get_or_create(
            db, models.Grow, name="Example Grow",
            defaults={
                "start_date": date(2026, 1, 1),
                "location": "Example location",
                "notes": "Comparing natural vs. chemical fertilization across two "
                         "groups, same strains in both, as a demo of the comparison "
                         "feature. Edit or delete this grow once you're ready to "
                         "log your own.",
            },
        )

        if created:
            g1 = models.Group(
                grow_id=grow.id, name="Group 1 (Natural)",
                fertilizer_type=models.FertilizerType.natural,
                description="Example natural-fertilizer group",
                identifier="Group 1",
            )
            g2 = models.Group(
                grow_id=grow.id, name="Group 2 (Chemical)",
                fertilizer_type=models.FertilizerType.chemical,
                description="Example chemical-fertilizer group",
                identifier="Group 2",
            )
            db.add_all([g1, g2])
            db.flush()
        else:
            g1 = db.query(models.Group).filter_by(grow_id=grow.id,
                                                  name="Group 1 (Natural)").first()
            g2 = db.query(models.Group).filter_by(grow_id=grow.id,
                                                  name="Group 2 (Chemical)").first()

        # ---- Plants ----
        plant_specs = [
            ("Strain A (G1 left)",  sa_seed.id, g1.id, "left"),
            ("Strain B (G1 right)", sb_seed.id, g1.id, "right"),
            ("Strain A (G2 left)",  sa_seed.id, g2.id, "left"),
            ("Strain B (G2 right)", sb_seed.id, g2.id, "right"),
        ]
        for label, seed_id, group_id, pos in plant_specs:
            get_or_create(
                db, models.Plant, label=label,
                defaults={
                    "seed_id": seed_id, "grow_id": grow.id, "group_id": group_id,
                    "position": pos,
                    "germination_date": date(2026, 1, 1),
                    "transplant_date": date(2026, 2, 15),
                },
            )

        db.commit()
        print("Seed data ready.")
        print(f"  Grow: {grow.name} (id={grow.id})")
        print(f"  Plants: {db.query(models.Plant).filter_by(grow_id=grow.id).count()}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
