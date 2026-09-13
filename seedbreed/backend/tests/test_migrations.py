"""run_lightweight_migrations() must add columns that pre-date this release
and be safe to run repeatedly."""
import os

from sqlalchemy import create_engine, text

from app.database import run_lightweight_migrations


def _old_schema_engine(tmp_path):
    """A DB whose plants / seed_production_events tables lack the new columns."""
    eng = create_engine(f"sqlite:///{os.path.join(tmp_path, 'old.db')}")
    with eng.begin() as conn:
        conn.execute(text("CREATE TABLE seeds (id INTEGER PRIMARY KEY, quantity INTEGER)"))
        conn.execute(text("CREATE TABLE strains (id INTEGER PRIMARY KEY, name VARCHAR)"))
        conn.execute(text("CREATE TABLE plants (id INTEGER PRIMARY KEY, label VARCHAR NOT NULL)"))
        conn.execute(text(
            "CREATE TABLE seed_production_events (id INTEGER PRIMARY KEY, "
            "parent_a_plant_id INTEGER NOT NULL, parent_b_plant_id INTEGER)"
        ))
        conn.execute(text("INSERT INTO plants (label) VALUES ('legacy')"))
    return eng


def _cols(eng, table):
    with eng.begin() as conn:
        return {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}


def test_migration_adds_plant_sex_with_unknown_default(tmp_path):
    eng = _old_schema_engine(tmp_path)
    run_lightweight_migrations(eng)
    assert "sex" in _cols(eng, "plants")
    with eng.begin() as conn:
        assert conn.execute(text("SELECT sex FROM plants")).scalar_one() == "unknown"


def test_migration_adds_pollen_collection_id_to_events(tmp_path):
    eng = _old_schema_engine(tmp_path)
    run_lightweight_migrations(eng)
    assert "pollen_collection_id" in _cols(eng, "seed_production_events")


def test_migration_is_idempotent(tmp_path):
    eng = _old_schema_engine(tmp_path)
    run_lightweight_migrations(eng)
    run_lightweight_migrations(eng)  # must not raise "duplicate column"
    assert "sex" in _cols(eng, "plants")
