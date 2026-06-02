# Project Context: L4D2 Mod Director Engine
**Repository:** `aubreychu/l4d2-mod-randomizer`

## 1. Executive Summary
The L4D2 Mod Director Engine is an intelligent, high-performance desktop mod manager and automated loadout curator designed for Left 4 Dead 2. It performs binary structural scanning on `.vpk` (Valve Pack) files to map out internal asset pathways (e.g., `.mdl`, `.vmt`, `.wav`). Using this map, it identifies precise in-game slots a mod replaces and executes a mathematical conflict-resolution system to generate completely conflict-free, randomized, or themed mod loadouts. It then interfaces directly with the Steam API to inject the loadout into a Steam Workshop Collection in seconds.

## 2. Technical Stack Matrix
*   **Runtime:** Python 3.11+
*   **GUI Framework:** PySide6 (Qt for Python) with custom diagnostic overlay structures.
*   **Database:** Local SQLite managed through asynchronous SQLAlchemy ORM (`vpk_mod_pool.db`).
*   **Networking:** Asynchronous I/O via `aiohttp` (for non-blocking concurrent Steam Workshop syncs/scraping) and `requests` (for synchronous baseline fetches).
*   **Compilation:** PyInstaller configured for single-file, self-contained distributions (`--onefile`).

## 3. Core File Architecture
*   `main.py`: The main entry point. Bootstraps the PySide6 controller window and event loops.
*   `vpk_dictionary.json`: Core classification token registry. Maps directory strings to L4D2's physical slot architecture.
*   `settings.json`: Core parameters (API Keys, Session Cookies, QOL arrays). **STRICTLY IGNORED IN GIT.**
*   `core/config.py`: Global state management and configuration parser.
*   `core/database.py`: SQLAlchemy ORM instantiator. Manages `zlib` compression/decompression for local SQLite cache.
*   `core/models.py`: Declarative dataclasses mapping mod metadata, Steam metrics, and asset tracking fingerprints.
*   `core/director.py`: The algorithmic core. Runs conflict-resolution, top-tier metric slicing, and loadout generation.
*   `core/vpk_parser.py`: Low-level stream worker that reads inner `.vpk` byte allocations and logs absolute internal file structures.
*   `core/scraper.py`: Async background miner that interrogates Steam Workshop, bypasses tag limits (if packs are allowed), and extracts Steam engagement metrics.
*   `core/network.py`: Connection manager executing Steam API calls and cookie-authenticated web scraping for private collections.
*   `.github/workflows/build.yml`: CI/CD pipeline automating Windows PyInstaller compilation.

---

## 4. CRUCIAL ARCHITECTURAL INVARIANTS (RULES FOR AGENTS)
When modifying this codebase, you MUST strictly adhere to the following rules:

### I. Absolute Local Security Isolation
The tool interacts directly with the user's Steam identity. All core authorization items (`STEAM_API_KEY`, `COLLECTION_ID`, `sessionid`, `steamLoginSecure`) are pulled exclusively from `settings.json`. Credentials MUST NEVER pass through third-party remote endpoints. Both `settings.json` and `vpk_mod_pool.db` are explicitly blocked via `.gitignore`. Do not attempt to track them.

### II. Explicit Substring Token Matching (No Greediness)
When modifying `vpk_dictionary.json` or `core/vpk_parser.py`, avoid standard string containment validations (e.g., `if token in file_path`) that can trigger false positives. (e.g., The token `models/infected/hulk` must not accidentally trigger a match in the Common Infected group).

### III. Explicit File Extensions & Structural Bounds
When isolating items that share a root path (e.g., `rifle` vs `rifle_ak47`), utilize trailing dot properties (e.g., `models/v_models/v_rifle.`). Bind matches strictly to file extensions (`.mdl`, `.vtf`, `.wav`) to precisely track structural bounds.

### IV. Complete Decoupling of Cosmetic GUIs from Weapon Slots
`materials/vgui/hud/...` strings MUST NEVER be included in physical firearm, melee, or item arrays in `vpk_dictionary.json`. Including them causes UI-only mods to spoof physical 3D slots, completely breaking the Director's conflict resolution. Keep HUD elements strictly in dedicated UI slots.

### V. PyInstaller Flat One-File Workspace Context
The CI/CD pipeline uses PyInstaller's `--onefile` flag. The environment has a flat workspace layout. Any commands copying assets, loading JSON dictionaries, or writing logs must read directly from the executable's current working directory context, rather than searching for non-existent `_internal` folder trees.

---

## 5. Recent System Upgrades (Context for Agents)
*   **Database Compression:** To prevent SQLite bloat, `core/database.py` uses `zlib` and `base64` to silently compress/decompress the massive arrays of raw `.vpk` file paths on the fly. Do not write raw lists directly to the `raw_paths` column.
*   **Steam Metadata Filters:** The engine tracks Steam metrics (`subscriptions`, `views`, `favorited`, `time_created`, `time_updated`) within the SQLite schema. `core/database.py` executes advanced native SQL sorting (`ORDER BY`) to filter these. 
*   **Top-Tier Slicing:** To maintain RNG while filtering (e.g., "Most Subscribed"), `core/director.py` slices the top 800 mods from the active filter and shuffles *only* that elite group.
*   **Private Collection Bypasses:** `core/network.py` uses cookie-authenticated HTTP requests (via `sessionid` and `steamLoginSecure`) to scrape the target Steam Collection, bypassing the API's restriction on Private/Unlisted collections.
*   **Multi-Item Pack Support:** `core/scraper.py` respects the `ALLOW_PACKS` user setting, bypassing the standard `>7` tag limit to allow massive, multi-slot mod packs into the engine.
