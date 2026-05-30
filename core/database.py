import json
from typing import List, Set
from sqlalchemy import create_engine, Column, String, Text, text
from sqlalchemy.orm import declarative_base, sessionmaker
from core.config import DB_POOL
from core.models import ModItem, ModEvaluation

Base = declarative_base()

class DBMod(Base):
    __tablename__ = 'workshop_pool'
    mod_id = Column(String, primary_key=True)
    title = Column(String)
    tags = Column(Text)
    model_slots = Column(Text)
    audio_slots = Column(Text)
    preview_url = Column(String)
    theme_tag = Column(String, default="None")
    raw_paths = Column(Text, default="[]")

engine = create_engine(f"sqlite:///{DB_POOL}")
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_pool_db():
    # Safe SQLite schema migrations for older versions of the DB
    with engine.connect() as conn:
        try: conn.execute(text("ALTER TABLE workshop_pool ADD COLUMN preview_url TEXT DEFAULT ''"))
        except: pass
        try: conn.execute(text("ALTER TABLE workshop_pool ADD COLUMN theme_tag TEXT DEFAULT 'None'"))
        except: pass
        try: conn.execute(text("ALTER TABLE workshop_pool ADD COLUMN raw_paths TEXT DEFAULT '[]'"))
        except: pass
        conn.commit()
        
    Base.metadata.create_all(bind=engine)

def _db_to_dataclass(db_mod: DBMod) -> ModItem:
    return ModItem(
        id=db_mod.mod_id,
        title=db_mod.title,
        tags=json.loads(db_mod.tags) if db_mod.tags else [],
        preview_url=db_mod.preview_url or "",
        theme_tag=db_mod.theme_tag or "None",
        eval=ModEvaluation(
            model_slots=db_mod.model_slots.split(",") if db_mod.model_slots else [],
            audio_slots=db_mod.audio_slots.split(",") if db_mod.audio_slots else [],
            raw_paths=json.loads(db_mod.raw_paths) if db_mod.raw_paths else []
        )
    )

def get_cached_ids() -> Set[str]:
    with SessionLocal() as db:
        return set(row[0] for row in db.query(DBMod.mod_id).all())

def get_all_cached_mods() -> List[ModItem]:
    with SessionLocal() as db:
        return [_db_to_dataclass(m) for m in db.query(DBMod).all()]
        
def get_mods_by_ids(mod_ids: List[str]) -> List[ModItem]:
    with SessionLocal() as db:
        mods = db.query(DBMod).filter(DBMod.mod_id.in_(mod_ids)).all()
        return [_db_to_dataclass(m) for m in mods]

def get_mod_by_id(mod_id: str) -> ModItem:
    with SessionLocal() as db:
        mod = db.query(DBMod).filter(DBMod.mod_id == mod_id).first()
        return _db_to_dataclass(mod) if mod else None

def save_mods_to_pool(mods_list: List[ModItem]):
    with SessionLocal() as db:
        for mod in mods_list:
            db_mod = db.query(DBMod).filter(DBMod.mod_id == mod.id).first()
            if not db_mod:
                db_mod = DBMod(mod_id=mod.id)
                db.add(db_mod)
                
            db_mod.title = mod.title
            db_mod.tags = json.dumps(mod.tags)
            db_mod.model_slots = ",".join(mod.eval.model_slots)
            db_mod.audio_slots = ",".join(mod.eval.audio_slots)
            db_mod.preview_url = mod.preview_url
            db_mod.theme_tag = mod.theme_tag
            db_mod.raw_paths = json.dumps(mod.eval.raw_paths)
            
        db.commit()

def update_mod_theme(mod_id: str, theme: str):
    with SessionLocal() as db:
        db.query(DBMod).filter(DBMod.mod_id == mod_id).update({"theme_tag": theme})
        db.commit()

def get_db_size() -> int:
    with SessionLocal() as db:
        return db.query(DBMod).count()

def delete_mods(mod_ids: List[str]):
    if not mod_ids: return
    with SessionLocal() as db:
        db.query(DBMod).filter(DBMod.mod_id.in_(mod_ids)).delete(synchronize_session=False)
        db.commit()