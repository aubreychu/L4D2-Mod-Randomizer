import aiohttp
import requests
import json
import re
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

async def fetch_vpk_stream(session, url, semaphore):
    if not url:
        yield b''
        return
    async with semaphore:
        try:
            headers = {"Range": "bytes=0-1000000"}
            async with session.get(url, headers=headers, timeout=5) as response:
                if response.status in (200, 206):
                    async for chunk in response.content.iter_chunked(8192):
                        yield chunk
        except Exception:
            pass


def get_collection_items(collection_id):
    # NEW: Overhauled retrieval to bypass private collection blocks using cookies
    url = f"https://steamcommunity.com/sharedfiles/filedetails/?id={collection_id}"
    cookies = {
        "sessionid": USER_CONFIG.get("SESSION_ID", ""), 
        "steamLoginSecure": USER_CONFIG.get("STEAM_LOGIN_SECURE", "")
    }
    
    try:
        response = requests.get(url, cookies=cookies, timeout=10)
        if response.status_code == 200:
            # Steam collections list items in HTML like: <div class="collectionItem" id="sharedfile_3161277824">
            matches = re.findall(r'id="sharedfile_(\d+)"', response.text)
            if matches:
                return list(set(matches))
    except Exception:
        pass

    # Fallback to WebAPI
    api_url = "https://api.steampowered.com/ISteamRemoteStorage/GetCollectionDetails/v1/"
    try:
        data = {"collectioncount": 1, "publishedfileids[0]": collection_id}
        if USER_CONFIG.get("STEAM_API_KEY"):
            data["key"] = USER_CONFIG.get("STEAM_API_KEY")
            
        response = requests.post(api_url, data=data, timeout=10)
        if response.status_code == 200:
            details = response.json().get("response", {}).get("collectiondetails", [])
            if details and "children" in details[0]: 
                return [child["publishedfileid"] for child in details[0]["children"]]
    except Exception:
        pass
        
    return []

# High Performance Async Deploy
async def async_modify_collection(session, collection_id, mod_id, action="addchild"):
    url = f"https://steamcommunity.com/sharedfiles/{action}"
    cookies = {"sessionid": USER_CONFIG["SESSION_ID"], "steamLoginSecure": USER_CONFIG["STEAM_LOGIN_SECURE"]}
    data = {"sessionid": USER_CONFIG["SESSION_ID"], "id": collection_id, "childid": mod_id}
    try:
        async with session.post(url, data=data, cookies=cookies) as resp:
            return resp.status == 200
    except:
        return False

async def resolve_dependencies_recursive(session, api_key, mod_ids, visited=None):
    if visited is None:
        visited = set()

    if not mod_ids:
        return set()

    to_check = [mid for mid in mod_ids if mid not in visited]
    if not to_check:
        return set()

    for mid in to_check:
        visited.add(mid)

    # We can query up to 100 items per request
    deps = set()
    url = "https://api.steampowered.com/IPublishedFileService/GetDetails/v1/"

    for i in range(0, len(to_check), 100):
        chunk = to_check[i:i+100]
        params = {
            "key": api_key,
            "include_children": "true"
        }
        for j, mid in enumerate(chunk):
            params[f"publishedfileids[{j}]"] = mid

        try:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    details = data.get("response", {}).get("publishedfiledetails", [])

                    new_children = []
                    for item in details:
                        children = item.get("children", [])
                        for child in children:
                            child_id = child.get("publishedfileid")
                            if child_id and child_id not in visited:
                                new_children.append(child_id)
                                deps.add(child_id)

                    if new_children:
                        sub_deps = await resolve_dependencies_recursive(session, api_key, new_children, visited)
                        deps.update(sub_deps)
        except Exception as e:
            pass

    return deps
