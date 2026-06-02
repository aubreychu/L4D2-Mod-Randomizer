import asyncio
import aiohttp
import random
import traceback
from core.config import ALLOWED_TAGS, EXCLUDED_LOWER, EXCLUDED_TITLE_KEYWORDS, PAGES_TO_MINE, USER_CONFIG
from core.models import ModItem
from core.database import get_cached_ids, save_mods_to_pool, delete_mods
from core.network import fetch_page, fetch_details_chunk, fetch_vpk_bytes
from core.vpk_parser import extract_vpk_paths, map_extracted_files_to_slots
from core.logger import get_logger

log = get_logger(__name__)
PASSIVE_SCRAPE_FLAG = False

async def probe_and_map_mod(session, mod: ModItem, semaphore):
    try:
        binary_data = await fetch_vpk_bytes(session, mod.file_url, semaphore)
        if binary_data:
            internal_files = extract_vpk_paths(binary_data)
            map_extracted_files_to_slots(mod, internal_files)
    except Exception as e:
        pass
    return mod

async def hunter_scrape(session, tag, cached_ids, progress_callback):
    current_page = random.randint(1, 150)
    new_mods = []
    log.info(f"Hunter Scraper deployed for tag: [{tag}] starting at page {current_page}.")
    
    try:
        while True:
            mods = await fetch_page(session, tag, current_page, search_by="tag")
            if not mods: break 
                
            uncached = [m for m in mods if m["publishedfileid"] not in cached_ids]
            
            if len(uncached) < 10:
                current_page += 1
                if current_page > 300: break 
            else:
                new_mods.extend(uncached)
                if progress_callback: progress_callback(f"Mining new {tag} vein (Pg {current_page})...", 0.1)
                bonus_pages = await asyncio.gather(*[fetch_page(session, tag, p, search_by="tag") for p in range(current_page + 1, current_page + 1 + PAGES_TO_MINE)])
                for b_page in bonus_pages: 
                    new_mods.extend([m for m in b_page if m["publishedfileid"] not in cached_ids])
                break
    except Exception as e:
        log.error(f"Error during hunter_scrape for tag {tag}: {str(e)}\n{traceback.format_exc()}")
        
    return new_mods

async def build_mod_pool_async(progress_callback=None):
    if progress_callback: progress_callback("Hunter Scraper active...", 0.05)
    cached_ids = get_cached_ids()
    
    filters = USER_CONFIG.get("SCRAPER_FILTERS", {"MAX_SIZE_MB": 500, "MIN_SUBS": 10})
    max_bytes = filters["MAX_SIZE_MB"] * 1024 * 1024
    min_subs = filters["MIN_SUBS"]
    allow_packs = USER_CONFIG.get("ALLOW_PACKS", False)
    
    async with aiohttp.ClientSession() as session:
        results = await asyncio.gather(*[hunter_scrape(session, tag, cached_ids, progress_callback) for tag in ALLOWED_TAGS])
        
        raw_new_pool = {}
        for tag_data in results:
            for mod_data in tag_data:
                mod_title_lower = mod_data.get("title", "").lower()
                mod_tags = [t.get("tag", "").lower() for t in mod_data.get("tags", [])]
                
                if (not allow_packs and len(mod_tags) > 7) or any(k in mod_title_lower for k in EXCLUDED_TITLE_KEYWORDS) or any(e in mod_tags for e in EXCLUDED_LOWER): 
                    continue
                
                mod_id = mod_data["publishedfileid"]
                raw_new_pool[mod_id] = ModItem(id=mod_id, title=mod_data.get("title", "Unknown"), tags=mod_tags)

        if not raw_new_pool: return []
            
        if progress_callback: progress_callback(f"Fetching URLs for {len(raw_new_pool)} new mods...", 0.4)
        mod_ids = list(raw_new_pool.keys())
        detail_results = await asyncio.gather(*[fetch_details_chunk(session, mod_ids[i:i+100]) for i in range(0, len(mod_ids), 100)])
        
        # Apply Filters and extract Steam Engagement Metrics directly from the chunk payload
        for chunk in detail_results:
            for d in chunk:
                mod_id = d.get("publishedfileid")
                if mod_id in raw_new_pool: 
                    file_size = int(d.get("file_size") or 0)
                    subs = int(d.get("subscriptions") or 0)
                    
                    if (max_bytes > 0 and file_size > max_bytes) or (subs < min_subs):
                        del raw_new_pool[mod_id]
                        continue
                        
                    # Base variables
                    raw_new_pool[mod_id].file_url = d.get("file_url", "")
                    raw_new_pool[mod_id].preview_url = d.get("preview_url", "")
                    
                    # New Engine Metrics mapped for the sorting algorithms
                    raw_new_pool[mod_id].subscriptions = subs
                    raw_new_pool[mod_id].views = int(d.get("views") or 0)
                    raw_new_pool[mod_id].favorited = int(d.get("favorited") or 0)
                    raw_new_pool[mod_id].time_created = int(d.get("time_created") or 0)
                    raw_new_pool[mod_id].time_updated = int(d.get("time_updated") or 0)

        if progress_callback: progress_callback(f"X-Ray Probing {len(raw_new_pool)} VPKs...", 0.6)
        semaphore = asyncio.Semaphore(40) 
        await asyncio.gather(*[probe_and_map_mod(session, mod, semaphore) for mod in raw_new_pool.values()])
            
        new_safe_mods = [m for m in raw_new_pool.values() if m.eval.model_slots or m.eval.audio_slots]
        
        if progress_callback: progress_callback("Saving to Local Database...", 0.9)
        save_mods_to_pool(new_safe_mods)
        
        return new_safe_mods

async def passive_scrape_loop(active_targets, log_callback):
    global PASSIVE_SCRAPE_FLAG
    cached_ids = get_cached_ids()
    semaphore = asyncio.Semaphore(20) 
    
    filters = USER_CONFIG.get("SCRAPER_FILTERS", {"MAX_SIZE_MB": 500, "MIN_SUBS": 10})
    max_bytes = filters["MAX_SIZE_MB"] * 1024 * 1024
    min_subs = filters["MIN_SUBS"]
    allow_packs = USER_CONFIG.get("ALLOW_PACKS", False)

    async with aiohttp.ClientSession() as session:
        while PASSIVE_SCRAPE_FLAG:
            try:
                search_by, target_val = random.choice(active_targets)
                max_page = 150 if search_by == "tag" else 25
                page = random.randint(1, max_page)
                
                log_callback(f"Scraping [{target_val}] ({search_by}) on Page {page}...")
                mods = await fetch_page(session, target_val, page, search_by=search_by)
                
                if not mods: 
                    await asyncio.sleep(1)
                    continue

                raw_new_pool = {}
                for mod_data in mods:
                    mod_id = mod_data["publishedfileid"]
                    if mod_id in cached_ids: continue
                    
                    mod_title_lower = mod_data.get("title", "").lower()
                    mod_tags = [t.get("tag", "").lower() for t in mod_data.get("tags", [])]
                    
                    if (not allow_packs and len(mod_tags) > 7) or any(k in mod_title_lower for k in EXCLUDED_TITLE_KEYWORDS) or any(e in mod_tags for e in EXCLUDED_LOWER): 
                        continue
                    
                    raw_new_pool[mod_id] = ModItem(id=mod_id, title=mod_data.get("title", "Unknown"), tags=mod_tags)

                if not raw_new_pool:
                    await asyncio.sleep(1)
                    continue

                log_callback(f"  -> Found {len(raw_new_pool)} unmapped mods. Evaluating filters...")
                
                mod_ids = list(raw_new_pool.keys())
                for i in range(0, len(mod_ids), 100):
                    chunk = await fetch_details_chunk(session, mod_ids[i:i+100])
                    for d in chunk:
                        mod_id = d.get("publishedfileid")
                        if mod_id in raw_new_pool:
                            file_size = int(d.get("file_size") or 0)
                            subs = int(d.get("subscriptions") or 0)
                            
                            if (max_bytes > 0 and file_size > max_bytes) or (subs < min_subs):
                                del raw_new_pool[mod_id]
                                continue
                                
                            # Base variables
                            raw_new_pool[mod_id].file_url = d.get("file_url", "")
                            raw_new_pool[mod_id].preview_url = d.get("preview_url", "")
                            
                            # New Engine Metrics mapped for the sorting algorithms
                            raw_new_pool[mod_id].subscriptions = subs
                            raw_new_pool[mod_id].views = int(d.get("views") or 0)
                            raw_new_pool[mod_id].favorited = int(d.get("favorited") or 0)
                            raw_new_pool[mod_id].time_created = int(d.get("time_created") or 0)
                            raw_new_pool[mod_id].time_updated = int(d.get("time_updated") or 0)

                if not raw_new_pool:
                    log_callback("  -> All mods rejected by quality filters.")
                    await asyncio.sleep(1)
                    continue
                    
                log_callback(f"  -> {len(raw_new_pool)} passed filters. X-Raying...")
                await asyncio.gather(*[probe_and_map_mod(session, mod, semaphore) for mod in raw_new_pool.values()])
                
                new_safe_mods = [m for m in raw_new_pool.values() if m.eval.model_slots or m.eval.audio_slots]
                if new_safe_mods:
                    save_mods_to_pool(new_safe_mods)
                    for m in new_safe_mods: cached_ids.add(m.id)
                    log_callback(f"  -> Successfully mapped and saved {len(new_safe_mods)} mods to Database!")
                else:
                    log_callback(f"  -> No targeted files found in this batch. Discarding.")
                
                await asyncio.sleep(3) 
                
            except Exception as e:
                log_callback(f"[ERROR] {str(e)}")
                await asyncio.sleep(5)

async def prune_database_async(progress_callback=None):
    cached_ids = list(get_cached_ids())
    if not cached_ids: return 0
    
    dead_ids = []
    try:
        async with aiohttp.ClientSession() as session:
            for i in range(0, len(cached_ids), 100):
                chunk = cached_ids[i:i+100]
                if progress_callback: progress_callback(f"Pruning: Checking {i} to {i+len(chunk)}...", i/len(cached_ids))
                
                chunk_results = await fetch_details_chunk(session, chunk)
                returned_ids = {str(d.get("publishedfileid")) for d in chunk_results if d.get("result") == 1}
                
                for mod_id in chunk:
                    if mod_id not in returned_ids: dead_ids.append(mod_id)

        if dead_ids: delete_mods(dead_ids)
        if progress_callback: progress_callback(f"Prune Complete. Removed {len(dead_ids)} dead links.", 1.0)
        return len(dead_ids)
    except Exception as e:
        if progress_callback: progress_callback(f"Prune Error: {str(e)}", 1.0)
        return 0