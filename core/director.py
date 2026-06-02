import random
import asyncio
import aiohttp
import base64
import zlib
import json
from core.config import USER_CONFIG, VPK_DICT
from core.database import get_all_cached_mods, get_filtered_mods, FilterType
from core.scraper import build_mod_pool_async
from core.network import get_collection_items, async_modify_collection, resolve_dependencies_recursive
from core.logger import get_logger

log = get_logger(__name__)

def generate_share_code(assignments: dict) -> str:
    try:
        minified = {slot: data["id"] for slot, data in assignments.items() if data}
        json_str = json.dumps(minified)
        compressed = zlib.compress(json_str.encode('utf-8'))
        return base64.urlsafe_b64encode(compressed).decode('utf-8')
    except Exception as e:
        log.error(f"Failed to generate share code: {e}")
        return ""

def decode_share_code(code: str) -> dict:
    try:
        decoded = base64.urlsafe_b64decode(code.encode('utf-8'))
        decompressed = zlib.decompress(decoded).decode('utf-8')
        return json.loads(decompressed) 
    except Exception as e:
        log.error(f"Failed to decode share code: {e}")
        return None

def prep_mixed_pool(progress_callback=None, cache_ratio=-1.0, target_theme="Any Theme", filter_mode="none"):
    try:
        if cache_ratio == 1.0:
            new_mods = []
            if progress_callback: progress_callback("Skipping Network Scrape (Using Local Cache)...", 0.5)
        else:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            new_mods = loop.run_until_complete(build_mod_pool_async(progress_callback))
    except Exception as e:
        log.error(f"Async Error: {e}")
        return [], {}

    # Map the UI string to our Database Enum safely
    try:
        f_mode_clean = str(filter_mode).lower().replace(" ", "_")
        f_type = FilterType(f_mode_clean)
    except ValueError:
        f_type = FilterType.NONE

    # Implement Top-Tier Slicing for active filters
    if f_type != FilterType.NONE:
        # Grabs the top 800 highest ranking mods so we randomize from the elite pool
        cached_mods = get_filtered_mods(f_type, limit=800)
        log.info(f"Filter [{f_type.value}] active. Isolated the top {len(cached_mods)} elite mods.")
    else:
        cached_mods = get_all_cached_mods()
    
    if target_theme != "Any Theme":
        cached_mods = [m for m in cached_mods if m.theme_tag == target_theme]
        new_mods = [] 

    total_pool_size = len(cached_mods) + len(new_mods)
    
    stats = {
        "cached_count": len(cached_mods),
        "new_count": len(new_mods),
        "total": total_pool_size,
        "cached_pct": int((len(cached_mods) / total_pool_size) * 100) if total_pool_size > 0 else 0,
        "new_pct": int((len(new_mods) / total_pool_size) * 100) if total_pool_size > 0 else 0
    }
    
    if total_pool_size == 0: return [], stats
        
    random.shuffle(cached_mods)
    random.shuffle(new_mods)
    
    actual_ratio = random.uniform(0.3, 0.7) if cache_ratio == -1.0 else cache_ratio
    
    if actual_ratio == 1.0: mixed_pool = cached_mods
    elif actual_ratio == 0.0: mixed_pool = new_mods
    else:
        cache_take = min(int(total_pool_size * actual_ratio), len(cached_mods))
        new_take = min(int(total_pool_size * (1.0 - actual_ratio)), len(new_mods))
        mixed_pool = cached_mods[:cache_take] + new_mods[:new_take]
        
    random.shuffle(mixed_pool)
    return mixed_pool, stats

def allocate_loadout(mixed_pool):
    assignments = {f"{s} [{t}]": None for s in VPK_DICT.keys() for t in ["Model", "Sound"]}
    selected_mods = set(USER_CONFIG.get("QOL_MODS", []))
    
    for slot_name in VPK_DICT.keys():
        for slot_type in ["Model", "Sound"]:
            target_key = f"{slot_name} [{slot_type}]"
            
            if assignments[target_key] is None:
                for mod in mixed_pool:
                    if mod.id in selected_mods: continue
                    
                    fits = False
                    if slot_type == "Model" and slot_name in mod.eval.model_slots: fits = True
                    elif slot_type == "Sound" and slot_name in mod.eval.audio_slots: fits = True
                        
                    if fits:
                        conflict = False
                        for ms in mod.eval.model_slots:
                            if assignments.get(f"{ms} [Model]") is not None: conflict = True
                        for ast in mod.eval.audio_slots:
                            if assignments.get(f"{ast} [Sound]") is not None: conflict = True
                                
                        if not conflict:
                            mod_data = {"id": mod.id, "title": mod.title, "preview_url": mod.preview_url, "theme_tag": mod.theme_tag}
                            selected_mods.add(mod.id)
                            
                            for ms in mod.eval.model_slots:
                                assignments[f"{ms} [Model]"] = mod_data
                            for ast in mod.eval.audio_slots:
                                assignments[f"{ast} [Sound]"] = mod_data
                            break 
                            
    return assignments, list(selected_mods)

def reroll_single_slot(full_slot_name, mixed_pool, current_assignments, current_selected):
    base_slot, slot_type = full_slot_name.rsplit(" [", 1)
    slot_type = slot_type.strip("]") 
    random.shuffle(mixed_pool) 
    
    old_mod = current_assignments.get(full_slot_name)
    old_id = old_mod["id"] if old_mod else None
    
    for mod in mixed_pool:
        if mod.id in current_selected: continue
        
        fits = False
        if slot_type == "Model" and base_slot in mod.eval.model_slots: fits = True
        elif slot_type == "Sound" and base_slot in mod.eval.audio_slots: fits = True
            
        if fits:
            conflict = False
            for ms in mod.eval.model_slots:
                existing = current_assignments.get(f"{ms} [Model]")
                if existing and existing["id"] != old_id: conflict = True
            for ast in mod.eval.audio_slots:
                existing = current_assignments.get(f"{ast} [Sound]")
                if existing and existing["id"] != old_id: conflict = True
                    
            if not conflict:
                if old_id:
                    current_selected.remove(old_id)
                    for k, v in list(current_assignments.items()):
                        if v and v["id"] == old_id:
                            current_assignments[k] = None
                            
                mod_data = {"id": mod.id, "title": mod.title, "preview_url": mod.preview_url, "theme_tag": mod.theme_tag}
                current_selected.append(mod.id)
                for ms in mod.eval.model_slots:
                    current_assignments[f"{ms} [Model]"] = mod_data
                for ast in mod.eval.audio_slots:
                    current_assignments[f"{ast} [Sound]"] = mod_data
                return True 
                
    return False

async def _async_sync_pipeline(collection_id, selected_ids, progress_callback):
    qol_mods = USER_CONFIG.get("QOL_MODS", [])
    
    if progress_callback: progress_callback("Reading current collection...", 0.1)
    current_mods = get_collection_items(collection_id)
    
    if not current_mods:
        log.warning("Collection appears empty. (If it's not, verify your Session ID cookies).")
    else:
        log.info(f"Targeting {len(current_mods)} items currently in the collection for wipe processing.")
    
    semaphore = asyncio.Semaphore(5) 
    
    async def safe_modify(session, cid, mid, action):
        async with semaphore:
            await asyncio.sleep(random.uniform(0.01, 0.05))
            result = await async_modify_collection(session, cid, mid, action)
            if not result:
                log.warning(f"Steam API rejected {action} for Mod ID {mid}. (Possible rate limit or dead link)")
            return result

    async with aiohttp.ClientSession() as session:
        mods_to_add = set(qol_mods) | set(selected_ids)

        # Resolve dependencies
        api_key = USER_CONFIG.get("STEAM_API_KEY", "")
        if api_key:
            if progress_callback: progress_callback("Resolving mod dependencies...", 0.2)
            try:
                deps = await resolve_dependencies_recursive(session, api_key, list(mods_to_add))
                if deps:
                    log.info(f"Found {len(deps)} required dependencies.")
                    mods_to_add.update(deps)
            except Exception as e:
                log.error(f"Failed to resolve dependencies: {e}")
        else:
            log.warning("STEAM_API_KEY missing. Cannot automatically resolve dependencies.")

        mods_to_remove = [m for m in current_mods if m not in mods_to_add]
        if progress_callback: progress_callback(f"Clearing {len(mods_to_remove)} old mods...", 0.4)
        
        if mods_to_remove:
            remove_tasks = [safe_modify(session, collection_id, m, "removechild") for m in mods_to_remove]
            await asyncio.gather(*remove_tasks)
        
        if progress_callback: progress_callback(f"Injecting {len(mods_to_add)} mods...", 0.7)
        
        if mods_to_add:
            add_tasks = [safe_modify(session, collection_id, m, "addchild") for m in mods_to_add]
            await asyncio.gather(*add_tasks)
            
    if progress_callback: progress_callback("Sync Complete!", 1.0)

def sync_collection_loadout(collection_id, selected_ids, progress_callback=None):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(_async_sync_pipeline(collection_id, selected_ids, progress_callback))