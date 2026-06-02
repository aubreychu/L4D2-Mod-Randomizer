import json
import zlib
import base64
from typing import List, Set, Optional
from enum import Enum
from sqlalchemy import create_engine, Column, String, Text, Integer, text
from sqlalchemy.orm import declarative_base, sessionmaker
from core.config import DB_POOL
from core.models import ModItem, ModEvaluation

Base = declarative_base()

class FilterType(str, Enum):
    NONE = "none"
    TRENDING = "trending"
    MOST_SUBSCRIBED = "most_subscribed"
    RECENTLY_UPDATED = "recently_updated"
    RECENTLY_UPLOADED = "recently_uploaded"

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
    
    # New columns for filtering metrics
    subscriptions = Column(Integer, default=0)
    views = Column(Integer, default=0)
    favorited = Column(Integer, default=0)
    time_created = Column(Integer, default=0)
    time_updated = Column(Integer, default=0)

engine = create_engine(f"sqlite:///{DB_POOL}")
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

from sqlalchemy import event

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA cache_size=-2000")
    cursor.close()


def compress_paths(path_list: List[str]) -> str:
    if not path_list: return "[]"
    json_str = json.dumps(path_list)
    compressed = zlib.compress(json_str.encode('utf-8'))
    return base64.b64encode(compressed).decode('utf-8')

def decompress_paths(data_str: str) -> List[str]:
    if not data_str or data_str == "[]": return []
    # Legacy fallback: If it's old, uncompressed JSON, read it normally
    if data_str.startswith('['): 
        try: return json.loads(data_str)
        except: return []
    # Modern approach: Decompress Zlib/Base64 strings
    try:
        decoded = base64.b64decode(data_str)
        decompressed = zlib.decompress(decoded).decode('utf-8')
        return json.loads(decompressed)
    except Exception:
        return []

def init_pool_db():
    # Structural Schema Migrations
    with engine.connect() as conn:
        columns_to_add = [
            ("preview_url", "TEXT DEFAULT ''"),
            ("theme_tag", "TEXT DEFAULT 'None'"),
            ("raw_paths", "TEXT DEFAULT '[]'"),
            ("subscriptions", "INTEGER DEFAULT 0"),
            ("views", "INTEGER DEFAULT 0"),
            ("favorited", "INTEGER DEFAULT 0"),
            ("time_created", "INTEGER DEFAULT 0"),
            ("time_updated", "INTEGER DEFAULT 0")
        ]
        for col_name, col_type in columns_to_add:
            try:
                conn.execute(text(f"ALTER TABLE workshop_pool ADD COLUMN {col_name} {col_type}"))
            except Exception:
                pass  # Column already exists
        conn.commit()
        
    Base.metadata.create_all(bind=engine)
    
    # Run legacy data compression sweep if necessary
    needs_vacuum = False
    with engine.connect() as conn:
        res = conn.execute(text("SELECT mod_id, raw_paths FROM workshop_pool WHERE raw_paths LIKE '[%' AND raw_paths != '[]'")).fetchall()
        if res:
            with conn.begin():
                for r in res:
                    mod_id, raw = r[0], r[1]
                    try:
                        comp = compress_paths(json.loads(raw))
                        conn.execute(text("UPDATE workshop_pool SET raw_paths = :c WHERE mod_id = :id"), {"c": comp, "id": mod_id})
                    except Exception: pass
            needs_vacuum = True
            
    if needs_vacuum:
        with engine.execution_options(isolation_level="AUTOCOMMIT").connect() as conn:
            conn.execute(text("VACUUM"))

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
            raw_paths=decompress_paths(db_mod.raw_paths)
        ),
        subscriptions=db_mod.subscriptions or 0,
        views=db_mod.views or 0,
        favorited=db_mod.favorited or 0,
        time_created=db_mod.time_created or 0,
        time_updated=db_mod.time_updated or 0
    )

# --- RESTORED STANDARD CRUD FUNCTIONS ---

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

def get_db_size() -> int:
    with SessionLocal() as db:
        return db.query(DBMod).count()

def update_mod_theme(mod_id: str, theme: str):
    with SessionLocal() as db:
        db.query(DBMod).filter(DBMod.mod_id == mod_id).update({"theme_tag": theme})
        db.commit()

def delete_mods(mod_ids: List[str]):
    if not mod_ids: return
    with SessionLocal() as db:
        db.query(DBMod).filter(DBMod.mod_id.in_(mod_ids)).delete(synchronize_session=False)
        db.commit()

# --- ADVANCED FILTERING FUNCTIONS ---

def get_filtered_mods(filter_type: FilterType, limit: Optional[int] = None) -> List[ModItem]:
    """Retrieves pool mods utilizing accelerated SQLite sorting filters."""
    with SessionLocal() as db:
        query = db.query(DBMod)
        
        if filter_type == FilterType.MOST_SUBSCRIBED:
            query = query.order_by(DBMod.subscriptions.desc())
        elif filter_type == FilterType.RECENTLY_UPDATED:
            query = query.order_by(DBMod.time_updated.desc())
        elif filter_type == FilterType.RECENTLY_UPLOADED:
            query = query.order_by(DBMod.time_created.desc())
        elif filter_type == FilterType.TRENDING:
            # Trending calculation: Total interactions balanced against account lifespan.
            current_time_stub = 1780000000  # Fallback calculation baseline
            query = query.order_by(
                (DBMod.favorited + (DBMod.subscriptions * 0.2)) / 
                ((current_time_stub - DBMod.time_created) / 86400 + 1)
                .desc()
            )
            
        if limit:
            query = query.limit(limit)
            
        return [_db_to_dataclass(m) for m in query.all()]

def save_mods_to_pool(mods_list: List[ModItem]):
    if not mods_list: return
    with SessionLocal() as db:
        # Fetch existing IDs to decide insert vs update
        incoming_ids = [m.id for m in mods_list]
        existing_mods = {m.mod_id: m for m in db.query(DBMod).filter(DBMod.mod_id.in_(incoming_ids)).all()}

        new_db_mods = []
        for mod in mods_list:
            db_mod = existing_mods.get(mod.id)
            if not db_mod:
                db_mod = DBMod(mod_id=mod.id)
                new_db_mods.append(db_mod)
                
            db_mod.title = mod.title
            db_mod.tags = json.dumps(mod.tags)
            db_mod.model_slots = ",".join(mod.eval.model_slots)
            db_mod.audio_slots = ",".join(mod.eval.audio_slots)
            db_mod.preview_url = mod.preview_url
            db_mod.theme_tag = mod.theme_tag
            db_mod.raw_paths = compress_paths(mod.eval.raw_paths)
            
            db_mod.subscriptions = mod.subscriptions
            db_mod.views = mod.views
            db_mod.favorited = mod.favorited
            db_mod.time_created = mod.time_created
            db_mod.time_updated = mod.time_updated
            
        if new_db_mods:
            db.add_all(new_db_mods)

        db.commit()