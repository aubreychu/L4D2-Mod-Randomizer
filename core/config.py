import os
import json

CONFIG_FILE = "settings.json"
DICT_FILE = "vpk_dictionary.json"
DB_POOL = "vpk_mod_pool.db"

def load_user_config():
    if not os.path.exists(CONFIG_FILE):
        default_config = {
            "STEAM_API_KEY": "",
            "COLLECTION_ID": "",
            "SESSION_ID": "",
            "STEAM_LOGIN_SECURE": "",
            "QOL_MODS": ["3161277824"],
            "ALLOW_PACKS": False,
            "SCRAPER_FILTERS": {
                "MAX_SIZE_MB": 500,
                "MIN_SUBS": 10
            }
        }
        with open(CONFIG_FILE, 'w') as f:
            json.dump(default_config, f, indent=4)
        return default_config
        
    with open(CONFIG_FILE, 'r') as f:
        cfg = json.load(f)
        needs_save = False
        if "SCRAPER_FILTERS" not in cfg:
            cfg["SCRAPER_FILTERS"] = {"MAX_SIZE_MB": 500, "MIN_SUBS": 10}
            needs_save = True
        if "ALLOW_PACKS" not in cfg:
            cfg["ALLOW_PACKS"] = False
            needs_save = True
            
        if needs_save:
            save_user_config(cfg)
        return cfg

def save_user_config(config_data):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config_data, f, indent=4)

USER_CONFIG = load_user_config()

APP_ID = 550
PAGES_TO_MINE = 3

ALLOWED_TAGS = ["Weapons", "Infected", "Survivors", "Items", "UI", "Sounds", "Miscellaneous", "Grenade Launcher", "M60", "Melee", "Pistol", "Rifle", "Shotgun", "SMG", "Sniper", "Throwable", "Adrenaline", "Defibrillator", "Medkit", "Pills"]
EXCLUDED_TAGS = ["Campaigns", "Mutations", "Scripts", "Gamemodes", "Addon Campaign", "General Mature Content", "Some Nudity or Sexual Content", "Frequent Nudity or Sexual Content", "Adult Only Sexual Content", "NSFW"]
EXCLUDED_LOWER = [tag.lower() for tag in EXCLUDED_TAGS]

# Removed "pack" and "collection" so multi-slot mods can be parsed
EXCLUDED_TITLE_KEYWORDS = ["nsfw", "nsfl", "r18", "r-18", "18+", "18禁", "uncensored", "hentai", "nude", "lewd"]

if not os.path.exists(DICT_FILE):
    VPK_DICT = {}
else:
    with open(DICT_FILE, 'r', encoding='utf-8') as f:
        VPK_DICT = json.load(f).get("vpk_path_dictionary", {})

    INFECTED_SLOTS = ["Tank", "Boomer", "Smoker", "Hunter", "Jockey", "Charger", "Spitter", "Witch"]
    for slot, paths in VPK_DICT.items():
        if slot in INFECTED_SLOTS:
            VPK_DICT[slot] = [p for p in paths if "zombieteamimage_" not in p.lower()]