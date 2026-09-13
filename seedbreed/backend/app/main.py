"""SeedBreed FastAPI app.

A single-file API on purpose — the surface area is small enough that
splitting into a dozen router files would obscure more than it clarifies.
"""
import os
import uuid
from datetime import date
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from PIL import Image, ExifTags

from .database import Base, engine, get_db, run_lightweight_migrations
from . import models, schemas, auth

PHOTOS_DIR = os.environ.get("SEEDBREED_PHOTOS_DIR", "/photos")
os.makedirs(PHOTOS_DIR, exist_ok=True)

# Create tables on startup, then patch in any newer columns.
Base.metadata.create_all(bind=engine)
run_lightweight_migrations()

app = FastAPI(title="SeedBreed", version="0.1.0")

# CORS — permissive because the app sits behind your Cloudflare Tunnel
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve uploaded photos directly
app.mount("/photos", StaticFiles(directory=PHOTOS_DIR), name="photos")


# ============ Auth ============
#
# Reading is open to everyone; changing anything requires a login. Rather than
# decorate every write route, a single middleware gates all unsafe HTTP methods
# under /api/. GETs (and the login route itself) pass straight through.

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


@app.middleware("http")
async def require_auth_for_writes(request: Request, call_next):
    path = request.url.path
    if (
        request.method in WRITE_METHODS
        and path.startswith("/api/")
        and path != "/api/auth/login"
    ):
        token = auth.bearer_from_header(request.headers.get("authorization"))
        if not auth.verify_token(token):
            return JSONResponse(
                status_code=401,
                content={"detail": "Log in to make changes."},
            )
    return await call_next(request)


@app.post("/api/auth/login")
def login(payload: schemas.LoginRequest):
    if not auth.check_credentials(payload.username, payload.password):
        raise HTTPException(401, "Invalid username or password")
    return {
        "token": auth.create_token(payload.username),
        "username": payload.username,
        "expires_in": auth.TOKEN_TTL,
    }


@app.get("/api/auth/me")
def whoami(authorization: Optional[str] = Header(None)):
    """Return the current user if the supplied token is valid, else 401."""
    username = auth.verify_token(auth.bearer_from_header(authorization))
    if not username:
        raise HTTPException(401, "Not authenticated")
    return {"username": username}


# ============ Strains ============

@app.get("/api/strains", response_model=List[schemas.StrainOut])
def list_strains(db: Session = Depends(get_db)):
    return db.query(models.Strain).order_by(models.Strain.name).all()


@app.post("/api/strains", response_model=schemas.StrainOut)
def create_strain(payload: schemas.StrainCreate, db: Session = Depends(get_db)):
    if db.query(models.Strain).filter_by(name=payload.name).first():
        raise HTTPException(400, f"Strain '{payload.name}' already exists")
    strain = models.Strain(**payload.model_dump())
    db.add(strain)
    db.commit()
    db.refresh(strain)
    return strain


@app.get("/api/strains/{strain_id}", response_model=schemas.StrainOut)
def get_strain(strain_id: int, db: Session = Depends(get_db)):
    strain = db.get(models.Strain, strain_id)
    if not strain:
        raise HTTPException(404, "Strain not found")
    return strain


@app.patch("/api/strains/{strain_id}", response_model=schemas.StrainOut)
def update_strain(strain_id: int, payload: schemas.StrainUpdate, db: Session = Depends(get_db)):
    """Edit an existing strain. Only the fields you send are changed."""
    strain = db.get(models.Strain, strain_id)
    if not strain:
        raise HTTPException(404, "Strain not found")
    updates = payload.model_dump(exclude_unset=True)
    new_name = updates.get("name")
    if new_name and new_name != strain.name:
        if db.query(models.Strain).filter_by(name=new_name).first():
            raise HTTPException(400, f"Strain '{new_name}' already exists")
    if strain_id in (updates.get("parent_a_id"), updates.get("parent_b_id")):
        raise HTTPException(400, "A strain can't be its own parent")
    for field, value in updates.items():
        setattr(strain, field, value)
    db.commit()
    db.refresh(strain)
    return strain


@app.get("/api/strains/{strain_id}/lineage", response_model=schemas.LineageNode)
def get_lineage(strain_id: int, db: Session = Depends(get_db)):
    """Recursive family tree for a strain."""
    def build(s: models.Strain, depth: int = 0) -> schemas.LineageNode:
        if depth > 8 or s is None:
            return None
        return schemas.LineageNode(
            id=s.id,
            name=s.name,
            breeder=s.breeder,
            parent_a=build(s.parent_a, depth + 1) if s.parent_a_id else None,
            parent_b=build(s.parent_b, depth + 1) if s.parent_b_id else None,
        )

    strain = db.get(models.Strain, strain_id)
    if not strain:
        raise HTTPException(404, "Strain not found")
    return build(strain)


# ============ Seeds ============

def _seed_to_out(seed: models.Seed) -> schemas.SeedOut:
    data = schemas.SeedOut.model_validate(seed).model_dump()
    data["strain_name"] = seed.strain.name if seed.strain else None
    return schemas.SeedOut(**data)


@app.get("/api/seeds", response_model=List[schemas.SeedOut])
def list_seeds(db: Session = Depends(get_db)):
    seeds = db.query(models.Seed).order_by(models.Seed.id.desc()).all()
    return [_seed_to_out(s) for s in seeds]


@app.post("/api/seeds", response_model=schemas.SeedOut)
def create_seed(payload: schemas.SeedCreate, db: Session = Depends(get_db)):
    if not db.get(models.Strain, payload.strain_id):
        raise HTTPException(400, "Unknown strain_id")
    data = payload.model_dump()
    # A fresh batch starts with all of its seeds remaining unless told otherwise.
    if data.get("seeds_remaining") is None:
        data["seeds_remaining"] = data.get("quantity")
    seed = models.Seed(**data)
    db.add(seed)
    db.commit()
    db.refresh(seed)
    return _seed_to_out(seed)


@app.patch("/api/seeds/{seed_id}", response_model=schemas.SeedOut)
def update_seed(seed_id: int, payload: schemas.SeedUpdate, db: Session = Depends(get_db)):
    """Edit an existing seed batch. Only the fields you send are changed."""
    seed = db.get(models.Seed, seed_id)
    if not seed:
        raise HTTPException(404, "Seed not found")
    updates = payload.model_dump(exclude_unset=True)
    if "strain_id" in updates and not db.get(models.Strain, updates["strain_id"]):
        raise HTTPException(400, "Unknown strain_id")
    for field, value in updates.items():
        setattr(seed, field, value)
    db.commit()
    db.refresh(seed)
    return _seed_to_out(seed)


# ============ Grows ============

@app.get("/api/grows", response_model=List[schemas.GrowOut])
def list_grows(db: Session = Depends(get_db)):
    return db.query(models.Grow).order_by(models.Grow.start_date.desc()).all()


@app.post("/api/grows", response_model=schemas.GrowOut)
def create_grow(payload: schemas.GrowCreate, db: Session = Depends(get_db)):
    grow_data = payload.model_dump(exclude={"groups"})
    grow = models.Grow(**grow_data)
    db.add(grow)
    db.flush()
    if payload.groups:
        for g in payload.groups:
            db.add(models.Group(grow_id=grow.id, **g.model_dump()))
    db.commit()
    db.refresh(grow)
    return grow


@app.get("/api/grows/{grow_id}", response_model=schemas.GrowOut)
def get_grow(grow_id: int, db: Session = Depends(get_db)):
    grow = db.get(models.Grow, grow_id)
    if not grow:
        raise HTTPException(404, "Grow not found")
    return grow


@app.patch("/api/grows/{grow_id}", response_model=schemas.GrowOut)
def update_grow(grow_id: int, payload: schemas.GrowUpdate, db: Session = Depends(get_db)):
    """Edit a grow's own fields. Only the fields you send are changed."""
    grow = db.get(models.Grow, grow_id)
    if not grow:
        raise HTTPException(404, "Grow not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(grow, field, value)
    db.commit()
    db.refresh(grow)
    return grow


@app.delete("/api/grows/{grow_id}")
def delete_grow(grow_id: int, db: Session = Depends(get_db)):
    """Delete a grow and everything that belongs to it: its groups, plants
    (and their photos), check-ins (and their photos), fertilizer events, and
    harvest records. Photo files on disk are removed too.

    Guarded: if any plant in this grow is recorded as a parent in a
    seed-production (breeding) event, the delete is blocked so we don't corrupt
    that lineage — remove the breeding record first.
    """
    grow = db.get(models.Grow, grow_id)
    if not grow:
        raise HTTPException(404, "Grow not found")

    plants = db.query(models.Plant).filter_by(grow_id=grow_id).all()
    plant_ids = [p.id for p in plants]

    if plant_ids:
        referenced = db.query(models.SeedProductionEvent).filter(
            (models.SeedProductionEvent.parent_a_plant_id.in_(plant_ids))
            | (models.SeedProductionEvent.parent_b_plant_id.in_(plant_ids))
        ).first()
        if referenced:
            raise HTTPException(
                400,
                "Can't delete this grow: one of its plants is recorded as a parent "
                "in a seed-production event. Remove that breeding record first.",
            )

    def _remove_file(filename: str):
        try:
            os.remove(os.path.join(PHOTOS_DIR, filename))
        except OSError:
            pass  # already gone — nothing to clean up

    # Check-ins tied to the grow itself or to any of its plants (+ their photos)
    checkins = db.query(models.CheckIn).filter_by(grow_id=grow_id).all()
    if plant_ids:
        checkins += db.query(models.CheckIn).filter(
            models.CheckIn.plant_id.in_(plant_ids)
        ).all()
    for c in checkins:
        for photo in c.photos:
            _remove_file(photo.filename)
        db.delete(c)  # photo rows cascade with the check-in

    # Plants: remove their photo files, harvests, then the plants themselves
    for p in plants:
        for photo in p.photos:
            _remove_file(photo.filename)
        for h in list(p.harvests):
            db.delete(h)
        db.delete(p)  # plant_photo rows cascade with the plant

    # Fertilizer events for this grow
    for e in db.query(models.FertilizerEvent).filter_by(grow_id=grow_id).all():
        db.delete(e)

    db.delete(grow)  # groups cascade with the grow
    db.commit()
    return {"ok": True, "id": grow_id}


@app.post("/api/grows/{grow_id}/groups", response_model=schemas.GroupOut)
def add_group(grow_id: int, payload: schemas.GroupCreate, db: Session = Depends(get_db)):
    if not db.get(models.Grow, grow_id):
        raise HTTPException(404, "Grow not found")
    g = models.Group(grow_id=grow_id, **payload.model_dump())
    db.add(g)
    db.commit()
    db.refresh(g)
    return g


# ============ Plants ============

MAX_PLANTS_PER_GROUP = 4


def _plant_strain_name(plant: models.Plant) -> Optional[str]:
    strain = plant.strain
    if strain is None and plant.seed and plant.seed.strain:
        strain = plant.seed.strain
    return strain.name if strain else None


def _plant_to_out(plant: models.Plant) -> schemas.PlantOut:
    data = schemas.PlantOut.model_validate(plant).model_dump()
    # Prefer a directly-linked strain; fall back to the seed's strain.
    data["strain_name"] = _plant_strain_name(plant)
    data["group_name"] = plant.group.name if plant.group else None
    return schemas.PlantOut(**data)


def _assert_group_has_room(db: Session, group_id: Optional[int], exclude_plant_id: Optional[int] = None):
    """Enforce the max-4-plants-per-group rule."""
    if group_id is None:
        return
    q = db.query(models.Plant).filter_by(group_id=group_id)
    if exclude_plant_id is not None:
        q = q.filter(models.Plant.id != exclude_plant_id)
    if q.count() >= MAX_PLANTS_PER_GROUP:
        raise HTTPException(400, f"A group can hold at most {MAX_PLANTS_PER_GROUP} plants.")


@app.get("/api/plants", response_model=List[schemas.PlantOut])
def list_plants(grow_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(models.Plant)
    if grow_id is not None:
        q = q.filter_by(grow_id=grow_id)
    return [_plant_to_out(p) for p in q.all()]


@app.post("/api/plants", response_model=schemas.PlantOut)
def create_plant(payload: schemas.PlantCreate, db: Session = Depends(get_db)):
    if payload.strain_id is not None and not db.get(models.Strain, payload.strain_id):
        raise HTTPException(400, "Unknown strain_id")
    _assert_group_has_room(db, payload.group_id)
    plant = models.Plant(**payload.model_dump())
    db.add(plant)
    db.commit()
    db.refresh(plant)
    return _plant_to_out(plant)


@app.get("/api/plants/{plant_id}", response_model=schemas.PlantOut)
def get_plant(plant_id: int, db: Session = Depends(get_db)):
    p = db.get(models.Plant, plant_id)
    if not p:
        raise HTTPException(404, "Plant not found")
    return _plant_to_out(p)


@app.patch("/api/plants/{plant_id}", response_model=schemas.PlantOut)
def update_plant(plant_id: int, payload: schemas.PlantUpdate, db: Session = Depends(get_db)):
    """Edit a plant. Only the fields you send are changed."""
    plant = db.get(models.Plant, plant_id)
    if not plant:
        raise HTTPException(404, "Plant not found")
    updates = payload.model_dump(exclude_unset=True)
    if "strain_id" in updates and updates["strain_id"] is not None:
        if not db.get(models.Strain, updates["strain_id"]):
            raise HTTPException(400, "Unknown strain_id")
    # If moving to a different group, make sure the destination has room.
    if "group_id" in updates and updates["group_id"] != plant.group_id:
        _assert_group_has_room(db, updates["group_id"], exclude_plant_id=plant_id)
    for field, value in updates.items():
        setattr(plant, field, value)
    db.commit()
    db.refresh(plant)
    return _plant_to_out(plant)


@app.delete("/api/plants/{plant_id}")
def delete_plant(plant_id: int, db: Session = Depends(get_db)):
    plant = db.get(models.Plant, plant_id)
    if not plant:
        raise HTTPException(404, "Plant not found")
    referenced = db.query(models.SeedProductionEvent).filter(
        (models.SeedProductionEvent.parent_a_plant_id == plant_id)
        | (models.SeedProductionEvent.parent_b_plant_id == plant_id)
    ).first()
    if referenced:
        raise HTTPException(
            400,
            "Can't delete this plant: it's recorded as a parent in a seed-production "
            "event. Remove that breeding record first.",
        )
    # Remove this plant's photo files from disk (rows cascade with the plant).
    for photo in plant.photos:
        try:
            os.remove(os.path.join(PHOTOS_DIR, photo.filename))
        except OSError:
            pass
    # Detach any check-ins that pointed at this plant so they aren't orphaned.
    for c in db.query(models.CheckIn).filter_by(plant_id=plant_id).all():
        c.plant_id = None
    for h in list(plant.harvests):
        db.delete(h)
    db.delete(plant)
    db.commit()
    return {"ok": True, "id": plant_id}


@app.post("/api/plants/{plant_id}/photos", response_model=schemas.PlantPhotoOut)
async def upload_plant_photo(
    plant_id: int,
    file: UploadFile = File(...),
    caption: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    plant = db.get(models.Plant, plant_id)
    if not plant:
        raise HTTPException(404, "Plant not found")
    fname = await _store_uploaded_image(file)
    photo = models.PlantPhoto(plant_id=plant_id, filename=fname, caption=caption)
    db.add(photo)
    db.commit()
    db.refresh(photo)
    return photo


@app.delete("/api/plant-photos/{photo_id}")
def delete_plant_photo(photo_id: int, db: Session = Depends(get_db)):
    ph = db.get(models.PlantPhoto, photo_id)
    if not ph:
        raise HTTPException(404, "Photo not found")
    try:
        os.remove(os.path.join(PHOTOS_DIR, ph.filename))
    except OSError:
        pass
    db.delete(ph)
    db.commit()
    return {"ok": True, "id": photo_id}


# ============ Check-ins & Photos ============

def _checkin_to_out(c: models.CheckIn) -> schemas.CheckInOut:
    data = schemas.CheckInOut.model_validate(c).model_dump()
    data["plant_label"] = c.plant.label if c.plant else None
    return schemas.CheckInOut(**data)


@app.get("/api/checkins", response_model=List[schemas.CheckInOut])
def list_checkins(
    plant_id: Optional[int] = None,
    grow_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    q = db.query(models.CheckIn)
    if plant_id is not None:
        q = q.filter_by(plant_id=plant_id)
    if grow_id is not None:
        q = q.filter_by(grow_id=grow_id)
    return [_checkin_to_out(c) for c in q.order_by(models.CheckIn.date.desc()).all()]


@app.post("/api/checkins", response_model=schemas.CheckInOut)
def create_checkin(payload: schemas.CheckInCreate, db: Session = Depends(get_db)):
    data = payload.model_dump()
    if data.get("date") is None:
        data["date"] = date.today()
    c = models.CheckIn(**data)
    db.add(c)
    db.commit()
    db.refresh(c)
    return _checkin_to_out(c)


@app.patch("/api/checkins/{checkin_id}", response_model=schemas.CheckInOut)
def update_checkin(checkin_id: int, payload: schemas.CheckInUpdate, db: Session = Depends(get_db)):
    """Edit an existing check-in. Only the fields you send are changed.

    Use this to fix notes/height/date later, or to retarget a check-in. Add or
    remove photos via the photo endpoints below.
    """
    c = db.get(models.CheckIn, checkin_id)
    if not c:
        raise HTTPException(404, "Check-in not found")
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(c, field, value)
    db.commit()
    db.refresh(c)
    return _checkin_to_out(c)


async def _store_uploaded_image(file: UploadFile) -> str:
    """Persist an uploaded image to PHOTOS_DIR, auto-rotating and downscaling.

    Returns the stored filename. Shared by check-in and plant photo uploads.
    """
    ext = os.path.splitext(file.filename or "")[1].lower() or ".jpg"
    if ext not in {".jpg", ".jpeg", ".png", ".webp", ".heic"}:
        raise HTTPException(400, f"Unsupported image type: {ext}")

    fname = f"{uuid.uuid4().hex}{ext}"
    fpath = os.path.join(PHOTOS_DIR, fname)
    raw = await file.read()
    with open(fpath, "wb") as f:
        f.write(raw)

    # Auto-rotate based on EXIF and downscale large phone photos
    try:
        img = Image.open(fpath)
        for tag, val in (img._getexif() or {}).items():
            if ExifTags.TAGS.get(tag) == "Orientation":
                if val == 3:
                    img = img.rotate(180, expand=True)
                elif val == 6:
                    img = img.rotate(270, expand=True)
                elif val == 8:
                    img = img.rotate(90, expand=True)
                break
        max_dim = 1800
        if img.width > max_dim or img.height > max_dim:
            img.thumbnail((max_dim, max_dim))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        save_ext = ".jpg" if ext in {".heic", ".webp"} else ext
        save_name = os.path.splitext(fname)[0] + save_ext
        save_path = os.path.join(PHOTOS_DIR, save_name)
        img.save(save_path, quality=88, optimize=True)
        if save_path != fpath:
            os.remove(fpath)
        fname = save_name
    except Exception:
        # If processing fails, keep the original upload
        pass

    return fname


@app.post("/api/checkins/{checkin_id}/photos", response_model=schemas.PhotoOut)
async def upload_photo(
    checkin_id: int,
    file: UploadFile = File(...),
    caption: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    checkin = db.get(models.CheckIn, checkin_id)
    if not checkin:
        raise HTTPException(404, "Check-in not found")

    fname = await _store_uploaded_image(file)
    photo = models.Photo(checkin_id=checkin_id, filename=fname, caption=caption)
    db.add(photo)
    db.commit()
    db.refresh(photo)
    return photo


@app.delete("/api/photos/{photo_id}")
def delete_photo(photo_id: int, db: Session = Depends(get_db)):
    ph = db.get(models.Photo, photo_id)
    if not ph:
        raise HTTPException(404, "Photo not found")
    try:
        os.remove(os.path.join(PHOTOS_DIR, ph.filename))
    except OSError:
        pass  # file already missing — nothing to clean up
    db.delete(ph)
    db.commit()
    return {"ok": True, "id": photo_id}


@app.delete("/api/checkins/{checkin_id}")
def delete_checkin(checkin_id: int, db: Session = Depends(get_db)):
    c = db.get(models.CheckIn, checkin_id)
    if not c:
        raise HTTPException(404, "Check-in not found")
    # Photo DB rows cascade-delete with the check-in, but the files on disk do
    # not — remove them here so we don't orphan images in PHOTOS_DIR.
    for photo in c.photos:
        try:
            os.remove(os.path.join(PHOTOS_DIR, photo.filename))
        except OSError:
            pass  # file already missing — nothing to clean up
    db.delete(c)
    db.commit()
    return {"ok": True, "id": checkin_id}


# ============ Fertilizer ============

@app.get("/api/fertilizer-events", response_model=List[schemas.FertilizerEventOut])
def list_fert(grow_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(models.FertilizerEvent)
    if grow_id is not None:
        q = q.filter_by(grow_id=grow_id)
    return q.order_by(models.FertilizerEvent.date.desc()).all()


@app.post("/api/fertilizer-events", response_model=schemas.FertilizerEventOut)
def create_fert(payload: schemas.FertilizerEventCreate, db: Session = Depends(get_db)):
    data = payload.model_dump()
    if data.get("date") is None:
        data["date"] = date.today()
    e = models.FertilizerEvent(**data)
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


@app.patch("/api/fertilizer-events/{event_id}", response_model=schemas.FertilizerEventOut)
def update_fert(event_id: int, payload: schemas.FertilizerEventUpdate, db: Session = Depends(get_db)):
    """Edit an existing fertilizer event. Only the fields you send are changed."""
    e = db.get(models.FertilizerEvent, event_id)
    if not e:
        raise HTTPException(404, "Fertilizer event not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(e, field, value)
    db.commit()
    db.refresh(e)
    return e


@app.delete("/api/fertilizer-events/{event_id}")
def delete_fert(event_id: int, db: Session = Depends(get_db)):
    e = db.get(models.FertilizerEvent, event_id)
    if not e:
        raise HTTPException(404, "Fertilizer event not found")
    db.delete(e)
    db.commit()
    return {"ok": True, "id": event_id}


# ============ Harvest ============

@app.get("/api/harvests", response_model=List[schemas.HarvestOut])
def list_harvests(plant_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(models.Harvest)
    if plant_id is not None:
        q = q.filter_by(plant_id=plant_id)
    return q.order_by(models.Harvest.harvest_date.desc()).all()


@app.post("/api/harvests", response_model=schemas.HarvestOut)
def create_harvest(payload: schemas.HarvestCreate, db: Session = Depends(get_db)):
    data = payload.model_dump()
    if data.get("harvest_date") is None:
        data["harvest_date"] = date.today()
    h = models.Harvest(**data)
    db.add(h)
    db.commit()
    db.refresh(h)
    return h


# ============ Pollen ============

POLLEN_SOURCE_SEXES = {models.PlantSex.male, models.PlantSex.hermaphrodite}


def _pollen_to_out(p: models.PollenCollection) -> schemas.PollenOut:
    data = schemas.PollenOut.model_validate(p).model_dump()
    data["source_plant_label"] = p.source_plant.label if p.source_plant else None
    data["source_plant_strain_name"] = _plant_strain_name(p.source_plant) if p.source_plant else None
    return schemas.PollenOut(**data)


def _assert_pollen_source(db: Session, plant_id: int) -> models.Plant:
    """Pollen can only come from a plant we've marked male or hermaphrodite."""
    plant = db.get(models.Plant, plant_id)
    if not plant:
        raise HTTPException(400, "source_plant_id not found")
    if plant.sex not in POLLEN_SOURCE_SEXES:
        raise HTTPException(
            400, "Pollen can only be collected from a plant marked male or hermaphrodite."
        )
    return plant


@app.get("/api/pollen", response_model=List[schemas.PollenOut])
def list_pollen(db: Session = Depends(get_db)):
    return [_pollen_to_out(p) for p in db.query(models.PollenCollection).order_by(
        models.PollenCollection.collected_date.desc(), models.PollenCollection.id.desc()).all()]


@app.post("/api/pollen", response_model=schemas.PollenOut)
def create_pollen(payload: schemas.PollenCreate, db: Session = Depends(get_db)):
    _assert_pollen_source(db, payload.source_plant_id)
    data = payload.model_dump()
    if data.get("collected_date") is None:
        data["collected_date"] = date.today()
    p = models.PollenCollection(**data)
    db.add(p)
    db.commit()
    db.refresh(p)
    return _pollen_to_out(p)


@app.patch("/api/pollen/{pollen_id}", response_model=schemas.PollenOut)
def update_pollen(pollen_id: int, payload: schemas.PollenUpdate, db: Session = Depends(get_db)):
    """Edit a pollen collection. Only the fields you send are changed."""
    p = db.get(models.PollenCollection, pollen_id)
    if not p:
        raise HTTPException(404, "Pollen collection not found")
    updates = payload.model_dump(exclude_unset=True)
    for required in ("source_plant_id", "collected_date"):
        if required in updates and updates[required] is None:
            raise HTTPException(400, f"{required} can't be null")
    if "source_plant_id" in updates and updates["source_plant_id"] != p.source_plant_id:
        _assert_pollen_source(db, updates["source_plant_id"])
        # Parent B on any cross that used this pollen is derived from the
        # source plant, so keep those events in sync.
        for ev in db.query(models.SeedProductionEvent).filter_by(pollen_collection_id=pollen_id).all():
            ev.parent_b_plant_id = updates["source_plant_id"]
    for field, value in updates.items():
        setattr(p, field, value)
    db.commit()
    db.refresh(p)
    return _pollen_to_out(p)


@app.delete("/api/pollen/{pollen_id}")
def delete_pollen(pollen_id: int, db: Session = Depends(get_db)):
    p = db.get(models.PollenCollection, pollen_id)
    if not p:
        raise HTTPException(404, "Pollen collection not found")
    referenced = db.query(models.SeedProductionEvent).filter_by(pollen_collection_id=pollen_id).first()
    if referenced:
        raise HTTPException(
            400,
            "Can't delete this pollen record: a seed-production event uses it. "
            "Edit that breeding record first.",
        )
    db.delete(p)
    db.commit()
    return {"ok": True, "id": pollen_id}


# ============ Seed Production (the breeding piece) ============

def _pollen_label(p: models.PollenCollection) -> str:
    label = p.source_plant.label if p.source_plant else f"Plant #{p.source_plant_id}"
    return f"{label} · {p.collected_date.isoformat()}"


def _sp_to_out(e: models.SeedProductionEvent) -> schemas.SeedProductionOut:
    data = schemas.SeedProductionOut.model_validate(e).model_dump()
    data["parent_a_label"] = e.parent_a.label if e.parent_a else None
    data["parent_b_label"] = e.parent_b.label if e.parent_b else None
    data["pollen_label"] = _pollen_label(e.pollen_collection) if e.pollen_collection else None
    return schemas.SeedProductionOut(**data)


def _get_pollen_or_400(db: Session, pollen_id: int) -> models.PollenCollection:
    p = db.get(models.PollenCollection, pollen_id)
    if not p:
        raise HTTPException(400, "pollen_collection_id not found")
    return p


@app.get("/api/seed-production", response_model=List[schemas.SeedProductionOut])
def list_seed_production(db: Session = Depends(get_db)):
    return [_sp_to_out(e) for e in db.query(models.SeedProductionEvent).order_by(
        models.SeedProductionEvent.date.desc()).all()]


@app.post("/api/seed-production", response_model=schemas.SeedProductionOut)
def create_seed_production(payload: schemas.SeedProductionCreate, db: Session = Depends(get_db)):
    """Log a seed-production event.

    Parent B (the pollen donor) is derived from the pollen collection, never
    set directly. Side effects: create a new Strain (if new_strain_name given
    and not existing), then create a Seed batch linked to that strain with
    origin='produced' and the parent event recorded — closing the lineage loop.
    """
    pa = db.get(models.Plant, payload.parent_a_plant_id)
    if not pa:
        raise HTTPException(400, "parent_a_plant_id not found")
    pollen = _get_pollen_or_400(db, payload.pollen_collection_id) if payload.pollen_collection_id else None
    pb = pollen.source_plant if pollen else None  # Full Plant (not just the id): the strain fallback below needs pb.strain / pb.seed.

    data = payload.model_dump()
    if data.get("date") is None:
        data["date"] = date.today()
    data["parent_b_plant_id"] = pb.id if pb else None
    event = models.SeedProductionEvent(**data)
    db.add(event)
    db.flush()

    # Figure out (or create) the resulting strain
    strain = None
    if payload.new_strain_name:
        strain = db.query(models.Strain).filter_by(name=payload.new_strain_name).first()
        if not strain:
            pa_strain = pa.strain or (pa.seed.strain if (pa.seed and pa.seed.strain) else None)
            pb_strain = (pb.strain or (pb.seed.strain if (pb.seed and pb.seed.strain) else None)) if pb else None
            strain = models.Strain(
                name=payload.new_strain_name,
                parent_a_id=pa_strain.id if pa_strain else None,
                parent_b_id=pb_strain.id if pb_strain else None,
                notes=f"Created from seed-production event on {data['date']}",
            )
            db.add(strain)
            db.flush()

    if strain:
        seed = models.Seed(
            strain_id=strain.id,
            origin=models.SeedOrigin.produced,
            source_label="self-produced",
            acquired_date=data["date"],
            quantity=payload.seed_count,
            produced_by_event_id=event.id,
            notes=payload.notes,
        )
        db.add(seed)

    db.commit()
    db.refresh(event)
    return _sp_to_out(event)


@app.patch("/api/seed-production/{event_id}", response_model=schemas.SeedProductionOut)
def update_seed_production(event_id: int, payload: schemas.SeedProductionUpdate, db: Session = Depends(get_db)):
    """Edit an existing seed-production event. Only the fields you send change.

    This edits the event record itself only — it doesn't retroactively create or
    rename the strain/seed batch the original event may have spawned. Sending
    pollen_collection_id re-derives parent B; sending null clears both.
    """
    event = db.get(models.SeedProductionEvent, event_id)
    if not event:
        raise HTTPException(404, "Seed-production event not found")
    updates = payload.model_dump(exclude_unset=True)
    if "parent_a_plant_id" in updates and not db.get(models.Plant, updates["parent_a_plant_id"]):
        raise HTTPException(400, "parent_a_plant_id not found")
    if "pollen_collection_id" in updates:
        if updates["pollen_collection_id"] is None:
            updates["parent_b_plant_id"] = None
        else:
            pollen = _get_pollen_or_400(db, updates["pollen_collection_id"])
            updates["parent_b_plant_id"] = pollen.source_plant_id
    for field, value in updates.items():
        setattr(event, field, value)
    db.commit()
    db.refresh(event)
    return _sp_to_out(event)


# ============ Dashboard summary ============

@app.get("/api/dashboard")
def dashboard(db: Session = Depends(get_db)):
    return {
        "strains": db.query(models.Strain).count(),
        "seeds": db.query(models.Seed).count(),
        "grows": db.query(models.Grow).count(),
        "plants": db.query(models.Plant).count(),
        "checkins": db.query(models.CheckIn).count(),
        "harvests": db.query(models.Harvest).count(),
        "crosses": db.query(models.SeedProductionEvent).count(),
    }


@app.get("/api/health")
def health():
    return {"status": "ok"}
