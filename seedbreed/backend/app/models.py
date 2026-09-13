"""Database models for SeedBreed.

The data model traces a full seed-to-harvest lineage:

    Strain  -->  Seed  -->  Plant  -->  Harvest
                  ^                       |
                  |                       v
                  +--- SeedProduction <---+

A Seed has an origin (purchased / gifted / produced-by-a-plant).
A Plant comes from a Seed and lives inside a Grow.
A Grow contains one or more Groups (e.g. natural vs. chemical).
Check-ins, photos, fertilizer events, and harvests attach to plants or groups.
A Plant can produce seeds (intentional cross or accidental), which become new Seed records
with their parents linked, enabling backward and forward genetic tracing.
"""
from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, String, Text, Date, DateTime, Float, Boolean,
    ForeignKey, Enum as SqlEnum
)
from sqlalchemy.orm import relationship
import enum

from .database import Base


# ---------- Enums ----------

class SeedOrigin(str, enum.Enum):
    purchased = "purchased"
    gifted = "gifted"
    produced = "produced"   # came from a plant we grew
    unknown = "unknown"


class FertilizerType(str, enum.Enum):
    natural = "natural"
    chemical = "chemical"
    other = "other"


class SeedProductionType(str, enum.Enum):
    intentional_cross = "intentional_cross"
    accidental_pollination = "accidental_pollination"
    hermaphrodite = "hermaphrodite"
    self_pollinated = "self_pollinated"
    unknown = "unknown"


class PlantSex(str, enum.Enum):
    unknown = "unknown"
    female = "female"
    male = "male"
    hermaphrodite = "hermaphrodite"


# ---------- Core entities ----------

class Strain(Base):
    """A named variety. Parents reference other strains for lineage."""
    __tablename__ = "strains"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    breeder = Column(String, nullable=True)
    type = Column(String, nullable=True)  # indica / sativa / hybrid / etc.
    indica_pct = Column(Float, nullable=True)  # % indica (0-100)
    sativa_pct = Column(Float, nullable=True)  # % sativa (0-100)
    thc_pct = Column(Float, nullable=True)     # % THC
    parent_a_id = Column(Integer, ForeignKey("strains.id"), nullable=True)
    parent_b_id = Column(Integer, ForeignKey("strains.id"), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    parent_a = relationship("Strain", remote_side=[id], foreign_keys=[parent_a_id])
    parent_b = relationship("Strain", remote_side=[id], foreign_keys=[parent_b_id])
    seeds = relationship("Seed", back_populates="strain")


class Seed(Base):
    """An individual seed (or batch of seeds with the same origin)."""
    __tablename__ = "seeds"

    id = Column(Integer, primary_key=True)
    strain_id = Column(Integer, ForeignKey("strains.id"), nullable=False)
    origin = Column(SqlEnum(SeedOrigin), nullable=False, default=SeedOrigin.unknown)
    source_label = Column(String, nullable=True)  # e.g. seed bank, friend's name
    acquired_date = Column(Date, nullable=True)
    quantity = Column(Integer, nullable=True)  # how many seeds in this batch
    seeds_remaining = Column(Integer, nullable=True)  # how many are left (defaults to quantity)
    feminized = Column(Boolean, nullable=False, default=False)    # feminized seeds
    auto_flower = Column(Boolean, nullable=False, default=False)  # autoflowering seeds
    # If origin == "produced", link back to the plant(s) that made them:
    produced_by_event_id = Column(Integer, ForeignKey("seed_production_events.id"), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    strain = relationship("Strain", back_populates="seeds")
    plants = relationship("Plant", back_populates="seed")
    produced_by_event = relationship("SeedProductionEvent", foreign_keys=[produced_by_event_id])


class Grow(Base):
    """A growing cycle, e.g. '2026 Cannabis Grow Test'."""
    __tablename__ = "grows"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    location = Column(String, nullable=True)  # 'greenhouse tent', 'indoor', etc.
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    groups = relationship("Group", back_populates="grow", cascade="all, delete-orphan")
    plants = relationship("Plant", back_populates="grow")
    checkins = relationship("CheckIn", back_populates="grow")
    fertilizer_events = relationship("FertilizerEvent", back_populates="grow")


class Group(Base):
    """A subgroup within a grow, e.g. 'natural bed' vs. 'chemical bed'.

    This is what makes side-by-side comparison possible.
    """
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True)
    grow_id = Column(Integer, ForeignKey("grows.id"), nullable=False)
    name = Column(String, nullable=False)
    fertilizer_type = Column(SqlEnum(FertilizerType), nullable=True)
    description = Column(Text, nullable=True)  # 'PVC compost pipes + worm castings'
    identifier = Column(String, nullable=True)  # 'skull in back right corner'

    grow = relationship("Grow", back_populates="groups")
    plants = relationship("Plant", back_populates="group")


class Plant(Base):
    """A specific plant grown from a specific seed in a specific grow/group."""
    __tablename__ = "plants"

    id = Column(Integer, primary_key=True)
    label = Column(String, nullable=False)  # 'Black Patronus (left)'
    seed_id = Column(Integer, ForeignKey("seeds.id"), nullable=True)
    strain_id = Column(Integer, ForeignKey("strains.id"), nullable=True)  # direct strain link
    grow_id = Column(Integer, ForeignKey("grows.id"), nullable=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=True)
    position = Column(String, nullable=True)  # 'left', 'right', etc.
    sex = Column(SqlEnum(PlantSex), nullable=False, default=PlantSex.unknown)
    germination_date = Column(Date, nullable=True)
    transplant_date = Column(Date, nullable=True)
    flip_date = Column(Date, nullable=True)  # when switched to flower
    quantity_harvested = Column(String, nullable=True)  # free-form, e.g. '3 oz' or '5'
    comments = Column(Text, nullable=True)
    issues = Column(Text, nullable=True)  # pests, deficiencies, etc.
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    seed = relationship("Seed", back_populates="plants")
    strain = relationship("Strain", foreign_keys=[strain_id])
    grow = relationship("Grow", back_populates="plants")
    group = relationship("Group", back_populates="plants")
    checkins = relationship("CheckIn", back_populates="plant")
    harvests = relationship("Harvest", back_populates="plant")
    photos = relationship("PlantPhoto", back_populates="plant", cascade="all, delete-orphan")


# ---------- Events ----------

class CheckIn(Base):
    """An observation logged for a plant or whole grow. Attaches photos & metrics."""
    __tablename__ = "checkins"

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, default=date.today)
    plant_id = Column(Integer, ForeignKey("plants.id"), nullable=True)
    grow_id = Column(Integer, ForeignKey("grows.id"), nullable=True)
    height_inches = Column(Float, nullable=True)
    notes = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    plant = relationship("Plant", back_populates="checkins")
    grow = relationship("Grow", back_populates="checkins")
    photos = relationship("Photo", back_populates="checkin", cascade="all, delete-orphan")


class Photo(Base):
    """An uploaded photo attached to a check-in."""
    __tablename__ = "photos"

    id = Column(Integer, primary_key=True)
    checkin_id = Column(Integer, ForeignKey("checkins.id"), nullable=False)
    filename = Column(String, nullable=False)   # stored relative path
    caption = Column(String, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    checkin = relationship("CheckIn", back_populates="photos")


class PlantPhoto(Base):
    """An uploaded photo attached directly to a plant."""
    __tablename__ = "plant_photos"

    id = Column(Integer, primary_key=True)
    plant_id = Column(Integer, ForeignKey("plants.id"), nullable=False)
    filename = Column(String, nullable=False)   # stored relative path
    caption = Column(String, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    plant = relationship("Plant", back_populates="photos")


class FertilizerEvent(Base):
    """Track every fertilizer application — your monthly cadence becomes data."""
    __tablename__ = "fertilizer_events"

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, default=date.today)
    grow_id = Column(Integer, ForeignKey("grows.id"), nullable=False)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=True)
    product = Column(String, nullable=False)  # 'Fox Farm Happy Frog All-Purpose'
    amount = Column(String, nullable=True)
    stage = Column(String, nullable=True)     # 'veg' / 'flower'
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    grow = relationship("Grow", back_populates="fertilizer_events")
    group = relationship("Group")


class Harvest(Base):
    """Yield record for a specific plant."""
    __tablename__ = "harvests"

    id = Column(Integer, primary_key=True)
    plant_id = Column(Integer, ForeignKey("plants.id"), nullable=False)
    harvest_date = Column(Date, nullable=False, default=date.today)
    wet_weight_g = Column(Float, nullable=True)
    dry_weight_g = Column(Float, nullable=True)
    quality_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    plant = relationship("Plant", back_populates="harvests")


class SeedProductionEvent(Base):
    """Records seeds produced from one or two parent plants.

    parent_a_plant_id is the mother (seed bearer).
    parent_b_plant_id is the father (pollen donor) — can be null for self/herm/unknown.
    A linked Seed record is created with origin='produced' and produced_by_event_id set,
    completing the bidirectional lineage.
    """
    __tablename__ = "seed_production_events"

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, default=date.today)
    parent_a_plant_id = Column(Integer, ForeignKey("plants.id"), nullable=False)
    parent_b_plant_id = Column(Integer, ForeignKey("plants.id"), nullable=True)
    event_type = Column(SqlEnum(SeedProductionType), nullable=False)
    seed_count = Column(Integer, nullable=True)
    new_strain_name = Column(String, nullable=True)  # if you're naming the cross
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    parent_a = relationship("Plant", foreign_keys=[parent_a_plant_id])
    parent_b = relationship("Plant", foreign_keys=[parent_b_plant_id])
