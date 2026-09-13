"""SQLite database connection and session management."""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATA_DIR = os.environ.get("SEEDBREED_DATA_DIR", "/data")
os.makedirs(DATA_DIR, exist_ok=True)

DATABASE_URL = f"sqlite:///{DATA_DIR}/seedbreed.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_lightweight_migrations(target_engine=None):
    """Add columns introduced after a DB was first created.

    SQLAlchemy's create_all() only creates missing tables, never alters existing
    ones, so a column added to a model won't appear in an already-populated DB.
    We keep a tiny idempotent ALTER-if-missing step here rather than pull in a
    full migration framework for a single-file app.

    Must run after create_all() (so the tables exist) and before any ORM query
    touches the new columns — both entry points (seed_data and main) call it.

    `target_engine` defaults to the app engine; tests pass their own.
    """
    from sqlalchemy import text

    eng = target_engine or engine
    with eng.begin() as conn:
        seed_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(seeds)"))}
        if "seeds_remaining" not in seed_cols:
            conn.execute(text("ALTER TABLE seeds ADD COLUMN seeds_remaining INTEGER"))
            # Backfill: existing batches start with all of their quantity remaining.
            conn.execute(text(
                "UPDATE seeds SET seeds_remaining = quantity WHERE seeds_remaining IS NULL"
            ))
        if "feminized" not in seed_cols:
            conn.execute(text(
                "ALTER TABLE seeds ADD COLUMN feminized BOOLEAN NOT NULL DEFAULT 0"
            ))
        if "auto_flower" not in seed_cols:
            conn.execute(text(
                "ALTER TABLE seeds ADD COLUMN auto_flower BOOLEAN NOT NULL DEFAULT 0"
            ))

        strain_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(strains)"))}
        if "indica_pct" not in strain_cols:
            conn.execute(text("ALTER TABLE strains ADD COLUMN indica_pct FLOAT"))
        if "sativa_pct" not in strain_cols:
            conn.execute(text("ALTER TABLE strains ADD COLUMN sativa_pct FLOAT"))
        if "thc_pct" not in strain_cols:
            conn.execute(text("ALTER TABLE strains ADD COLUMN thc_pct FLOAT"))

        plant_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(plants)"))}
        if "strain_id" not in plant_cols:
            conn.execute(text("ALTER TABLE plants ADD COLUMN strain_id INTEGER"))
        if "quantity_harvested" not in plant_cols:
            conn.execute(text("ALTER TABLE plants ADD COLUMN quantity_harvested VARCHAR"))
        if "comments" not in plant_cols:
            conn.execute(text("ALTER TABLE plants ADD COLUMN comments TEXT"))
        if "issues" not in plant_cols:
            conn.execute(text("ALTER TABLE plants ADD COLUMN issues TEXT"))
        if "sex" not in plant_cols:
            conn.execute(text(
                "ALTER TABLE plants ADD COLUMN sex VARCHAR NOT NULL DEFAULT 'unknown'"
            ))

        sp_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(seed_production_events)"))}
        if "pollen_collection_id" not in sp_cols:
            conn.execute(text(
                "ALTER TABLE seed_production_events ADD COLUMN pollen_collection_id INTEGER"
            ))
