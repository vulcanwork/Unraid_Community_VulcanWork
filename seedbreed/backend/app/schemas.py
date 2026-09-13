"""Pydantic schemas for API I/O."""
from datetime import datetime, date
from datetime import date as date_type  # use for fields literally named `date`
from typing import Optional, List
from pydantic import BaseModel, ConfigDict

from .models import SeedOrigin, FertilizerType, SeedProductionType, PlantSex


class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- Auth ----------

class LoginRequest(BaseModel):
    username: str
    password: str


# ---------- Strain ----------

class StrainCreate(BaseModel):
    name: str
    breeder: Optional[str] = None
    type: Optional[str] = None
    indica_pct: Optional[float] = None
    sativa_pct: Optional[float] = None
    thc_pct: Optional[float] = None
    parent_a_id: Optional[int] = None
    parent_b_id: Optional[int] = None
    notes: Optional[str] = None


class StrainUpdate(BaseModel):
    """Partial update — only provided fields are changed."""
    name: Optional[str] = None
    breeder: Optional[str] = None
    type: Optional[str] = None
    indica_pct: Optional[float] = None
    sativa_pct: Optional[float] = None
    thc_pct: Optional[float] = None
    parent_a_id: Optional[int] = None
    parent_b_id: Optional[int] = None
    notes: Optional[str] = None


class StrainOut(ORMBase):
    id: int
    name: str
    breeder: Optional[str]
    type: Optional[str]
    indica_pct: Optional[float]
    sativa_pct: Optional[float]
    thc_pct: Optional[float]
    parent_a_id: Optional[int]
    parent_b_id: Optional[int]
    notes: Optional[str]
    created_at: datetime


# ---------- Seed ----------

class SeedCreate(BaseModel):
    strain_id: int
    origin: SeedOrigin = SeedOrigin.unknown
    source_label: Optional[str] = None
    acquired_date: Optional[date] = None
    quantity: Optional[int] = None
    seeds_remaining: Optional[int] = None
    feminized: bool = False
    auto_flower: bool = False
    notes: Optional[str] = None


class SeedUpdate(BaseModel):
    """Partial update — only provided fields are changed."""
    strain_id: Optional[int] = None
    origin: Optional[SeedOrigin] = None
    source_label: Optional[str] = None
    acquired_date: Optional[date] = None
    quantity: Optional[int] = None
    seeds_remaining: Optional[int] = None
    feminized: Optional[bool] = None
    auto_flower: Optional[bool] = None
    notes: Optional[str] = None


class SeedOut(ORMBase):
    id: int
    strain_id: int
    origin: SeedOrigin
    source_label: Optional[str]
    acquired_date: Optional[date]
    quantity: Optional[int]
    seeds_remaining: Optional[int]
    feminized: bool
    auto_flower: bool
    produced_by_event_id: Optional[int]
    notes: Optional[str]
    created_at: datetime
    strain_name: Optional[str] = None


# ---------- Grow ----------

class GroupCreate(BaseModel):
    name: str
    fertilizer_type: Optional[FertilizerType] = None
    description: Optional[str] = None
    identifier: Optional[str] = None


class GroupOut(ORMBase):
    id: int
    grow_id: int
    name: str
    fertilizer_type: Optional[FertilizerType]
    description: Optional[str]
    identifier: Optional[str]


class GrowCreate(BaseModel):
    name: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    groups: Optional[List[GroupCreate]] = None


class GrowUpdate(BaseModel):
    """Partial update — only provided fields are changed."""
    name: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    location: Optional[str] = None
    notes: Optional[str] = None


class GrowOut(ORMBase):
    id: int
    name: str
    start_date: Optional[date]
    end_date: Optional[date]
    location: Optional[str]
    notes: Optional[str]
    created_at: datetime
    groups: List[GroupOut] = []


# ---------- Plant ----------

class PlantPhotoOut(ORMBase):
    id: int
    plant_id: int
    filename: str
    caption: Optional[str]
    uploaded_at: datetime


class PlantCreate(BaseModel):
    label: str
    seed_id: Optional[int] = None
    strain_id: Optional[int] = None
    grow_id: Optional[int] = None
    group_id: Optional[int] = None
    position: Optional[str] = None
    sex: PlantSex = PlantSex.unknown
    germination_date: Optional[date] = None
    transplant_date: Optional[date] = None
    flip_date: Optional[date] = None
    quantity_harvested: Optional[str] = None
    comments: Optional[str] = None
    issues: Optional[str] = None
    notes: Optional[str] = None


class PlantUpdate(BaseModel):
    """Partial update — only provided fields are changed."""
    label: Optional[str] = None
    seed_id: Optional[int] = None
    strain_id: Optional[int] = None
    grow_id: Optional[int] = None
    group_id: Optional[int] = None
    position: Optional[str] = None
    sex: Optional[PlantSex] = None
    germination_date: Optional[date] = None
    transplant_date: Optional[date] = None
    flip_date: Optional[date] = None
    quantity_harvested: Optional[str] = None
    comments: Optional[str] = None
    issues: Optional[str] = None
    notes: Optional[str] = None


class PlantOut(ORMBase):
    id: int
    label: str
    seed_id: Optional[int]
    strain_id: Optional[int]
    grow_id: Optional[int]
    group_id: Optional[int]
    position: Optional[str]
    sex: PlantSex
    germination_date: Optional[date]
    transplant_date: Optional[date]
    flip_date: Optional[date]
    quantity_harvested: Optional[str]
    comments: Optional[str]
    issues: Optional[str]
    notes: Optional[str]
    created_at: datetime
    strain_name: Optional[str] = None
    group_name: Optional[str] = None
    photos: List[PlantPhotoOut] = []


# ---------- CheckIn / Photo ----------

class PhotoOut(ORMBase):
    id: int
    checkin_id: int
    filename: str
    caption: Optional[str]
    uploaded_at: datetime


class CheckInCreate(BaseModel):
    date: Optional[date_type] = None
    plant_id: Optional[int] = None
    grow_id: Optional[int] = None
    height_inches: Optional[float] = None
    notes: str


class CheckInUpdate(BaseModel):
    """Partial update — only provided fields are changed."""
    date: Optional[date_type] = None
    plant_id: Optional[int] = None
    grow_id: Optional[int] = None
    height_inches: Optional[float] = None
    notes: Optional[str] = None


class CheckInOut(ORMBase):
    id: int
    date: date
    plant_id: Optional[int]
    grow_id: Optional[int]
    height_inches: Optional[float]
    notes: str
    created_at: datetime
    photos: List[PhotoOut] = []
    plant_label: Optional[str] = None


# ---------- Fertilizer ----------

class FertilizerEventCreate(BaseModel):
    date: Optional[date_type] = None
    grow_id: int
    group_id: Optional[int] = None
    product: str
    amount: Optional[str] = None
    stage: Optional[str] = None
    notes: Optional[str] = None


class FertilizerEventUpdate(BaseModel):
    """Partial update — only provided fields are changed."""
    date: Optional[date_type] = None
    group_id: Optional[int] = None
    product: Optional[str] = None
    amount: Optional[str] = None
    stage: Optional[str] = None
    notes: Optional[str] = None


class FertilizerEventOut(ORMBase):
    id: int
    date: date
    grow_id: int
    group_id: Optional[int]
    product: str
    amount: Optional[str]
    stage: Optional[str]
    notes: Optional[str]
    created_at: datetime


# ---------- Harvest ----------

class HarvestCreate(BaseModel):
    plant_id: int
    harvest_date: Optional[date] = None
    wet_weight_g: Optional[float] = None
    dry_weight_g: Optional[float] = None
    quality_notes: Optional[str] = None


class HarvestOut(ORMBase):
    id: int
    plant_id: int
    harvest_date: date
    wet_weight_g: Optional[float]
    dry_weight_g: Optional[float]
    quality_notes: Optional[str]
    created_at: datetime


# ---------- Pollen ----------

class PollenCreate(BaseModel):
    source_plant_id: int
    collected_date: Optional[date] = None
    amount: Optional[str] = None
    storage: Optional[str] = None
    notes: Optional[str] = None


class PollenUpdate(BaseModel):
    """Partial update — only provided fields are changed."""
    source_plant_id: Optional[int] = None
    collected_date: Optional[date] = None
    amount: Optional[str] = None
    storage: Optional[str] = None
    notes: Optional[str] = None


class PollenOut(ORMBase):
    id: int
    source_plant_id: int
    collected_date: date
    amount: Optional[str]
    storage: Optional[str]
    notes: Optional[str]
    created_at: datetime
    source_plant_label: Optional[str] = None
    source_plant_strain_name: Optional[str] = None


# ---------- Seed Production ----------

class SeedProductionCreate(BaseModel):
    date: Optional[date_type] = None
    parent_a_plant_id: int
    parent_b_plant_id: Optional[int] = None
    event_type: SeedProductionType
    seed_count: Optional[int] = None
    new_strain_name: Optional[str] = None
    notes: Optional[str] = None


class SeedProductionUpdate(BaseModel):
    """Partial update — only provided fields are changed.

    Edits the event record itself; does not retroactively create/alter the
    strain or seed batch that the original event may have spawned.
    """
    date: Optional[date_type] = None
    parent_a_plant_id: Optional[int] = None
    parent_b_plant_id: Optional[int] = None
    event_type: Optional[SeedProductionType] = None
    seed_count: Optional[int] = None
    new_strain_name: Optional[str] = None
    notes: Optional[str] = None


class SeedProductionOut(ORMBase):
    id: int
    date: date
    parent_a_plant_id: int
    parent_b_plant_id: Optional[int]
    event_type: SeedProductionType
    seed_count: Optional[int]
    new_strain_name: Optional[str]
    notes: Optional[str]
    created_at: datetime
    parent_a_label: Optional[str] = None
    parent_b_label: Optional[str] = None


# ---------- Lineage ----------

class LineageNode(BaseModel):
    """Recursive node for family-tree output."""
    id: int
    name: str
    breeder: Optional[str] = None
    parent_a: Optional["LineageNode"] = None
    parent_b: Optional["LineageNode"] = None


LineageNode.model_rebuild()
