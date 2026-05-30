import aiohttp
import requests
import json
from core.config import USER_CONFIG, APP_ID

async def fetch_page(session, target, page, search_by="tag"):
    url = "https://api.steampowered.com/IPublishedFileService/QueryFiles/v1/"
    params = {"key": USER_CONFIG["STEAM_API_KEY"], "appid": APP_ID, "page": page, "numperpage": 100, "return_tags": "true", "query_type": 1}
    
    if search_by == "tag": params["requiredtags[0]"] = target
    else: params["search_text"] = target
        
    async with session.get(url, params=params) as response:
        if response.status == 200:
            try:
                raw_bytes = await response.read()
                text_data = raw_bytes.decode('utf-8', errors='ignore')
                return json.loads(text_data).get("response", {}).get("publishedfiledetails", [])
            except Exception:
                pass
    return []

async def fetch_details_chunk(session, mod_ids):
    url = "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"
    data = {"itemcount": len(mod_ids)}
    for i, mod_id in enumerate(mod_ids): data[f"publishedfileids[{i}]"] = mod_id
    
    async with session.post(url, data=data) as response:
        if response.status == 200:
            try:
                raw_bytes = await response.read()
                text_data = raw_bytes.decode('utf-8', errors='ignore')
                return json.loads(text_data).get("response", {}).get("publishedfiledetails", [])
            except Exception:
                pass
    return []

async def fetch_vpk_bytes(session, url, semaphore):
    if not url: return None 
    async with semaphore:
        try:
            headers = {"Range": "bytes=0-1000000"} 
            async with session.get(url, headers=headers, timeout=5) as response:
                if response.status in (200, 206):
                    return await response.read()
        except: pass 
    return None

def get_collection_items(collection_id):
    url = "https://api.steampowered.com/ISteamRemoteStorage/GetCollectionDetails/v1/"
    try:
        response = requests.post(url, data={"collectioncount": 1, "publishedfileids[0]": collection_id})
        if response.status_code == 200:
            details = response.json().get("response", {}).get("collectiondetails", [])
            if details and "children" in details[0]: 
                return [child["publishedfileid"] for child in details[0]["children"]]
    except: pass
    return []

# NEW: High Performance Async Deploy
async def async_modify_collection(session, collection_id, mod_id, action="addchild"):
    url = f"https://steamcommunity.com/sharedfiles/{action}"
    cookies = {"sessionid": USER_CONFIG["SESSION_ID"], "steamLoginSecure": USER_CONFIG["STEAM_LOGIN_SECURE"]}
    data = {"sessionid": USER_CONFIG["SESSION_ID"], "id": collection_id, "childid": mod_id}
    try:
        async with session.post(url, data=data, cookies=cookies) as resp:
            return resp.status == 200
    except:
        return False