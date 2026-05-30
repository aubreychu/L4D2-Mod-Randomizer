# L4D2 Mod Director Engine

An automated, intelligent mod manager and loadout generator for Left 4 Dead 2. 

The Director Engine acts as an automated curator for your Steam Workshop. It uses a custom VPK X-Ray parser to scan the internal file structures of mods, categorize them by exact slot (e.g., AK-47 Model vs. AK-47 Sound), and generate mathematically conflict-free loadouts. Once generated, it uses asynchronous networking to deploy the loadout directly to a target Steam Collection in seconds.

**Security Note:** Your Steam API key and session cookies are stored *strictly locally* on your machine in `settings.json`. This application communicates directly with the Steam API and never routes your credentials or data through any third-party servers.

## Table of Contents
- [Installation](#installation)
- [Initial Setup & Steam Credentials](#initial-setup--steam-credentials)
- [Tutorial of Usage](#tutorial-of-usage)
- [Best Practices](#best-practices)
- [Advanced Features](#advanced-features)

---

## Installation

### Method 1: Standalone Executable (Recommended)
1. Download the latest `L4D2_Director_Engine.zip` from the **Releases** tab.
2. Extract the folder to your desktop.
3. Rename `settings.example.json` to `settings.json`.
4. Run `L4D2_Director_Engine.exe`.

### Method 2: Running from Source
1. Clone this repository.
2. Install Python 3.11+.
3. Install dependencies: `pip install -r requirements.txt`.
4. Rename `settings.example.json` to `settings.json`.
5. Run `python main.py`.

---

## Initial Setup & Steam Credentials

To automatically sync loadouts to your Steam account, the engine requires three credentials. Open the **Settings & Maintenance** tab in the app and input the following:

1. **Steam API Key:** - Get this from: `https://steamcommunity.com/dev/apikey`
2. **Collection ID:** - Create a blank "Left 4 Dead 2" Workshop Collection. Look at the URL. The ID is the string of numbers at the end (e.g., `?id=3731863890`). Do not publish this collection.
3. **Session Cookies (`sessionid` and `steamLoginSecure`):**
   - Log into Steam on your web browser.
   - Press `F12` to open Developer Tools.
   - Go to the **Application** tab (Chrome/Edge) or **Storage** tab (Firefox).
   - Under **Cookies** -> `https://steamcommunity.com`, find `sessionid` and `steamLoginSecure`.
   - Copy their respective values into the engine's Settings tab.

Click **Save Configuration**. Your credentials are now encrypted locally.

---

## Tutorial of Usage

1. **Build your Database (Optional for first run):** If you didn't download a pre-built `vpk_mod_pool.db`, go to the **Passive Scraper** tab, select your target tags (e.g., "Weapons", "Survivors"), and click **Start Mining**. The engine will find, download, parse, and categorize mods in the background.
2. **Generate a Loadout:**
   Go to **The Director** tab. Use the slider to mix between your cached mods and entirely new mods from the Workshop. Click **1. Generate Loadout**.
3. **Review Assignments:**
   The engine will assign a mod to every available slot in the game. It guarantees no two mods will overlap or conflict.
4. **Deploy:**
   Once you are happy with the loadout, click **2. Deploy to Steam**. The engine and inject the new mod list concurrently in 1–3 seconds.
5. **Play:**
   Launch Left 4 Dead 2. Let the add-on menu load your newly subscribed items, and play.
6  **Reroll:**
   Remember to remove all previous mods in the collection before rerolling (Optional: Remove all installed addons in your game files as well to avoid bloat)
---

## Best Practices

* **Always Check the Advanced View:** Toggle the review board to "Advanced" to see exactly which models and sounds are filling the minor slots (like consumables and melee weapons).
* **Tag Your Mods:** Right-click any mod in the Assignment Review board to tag it with a Theme (e.g., "Anime", "Realistic", "Horror"). Future generations can be forced to exclusively pull from these themes using the Dropdown menu.
* **Keep QOL Mods Permanent:** In the Settings tab, paste the Workshop IDs of mods you *always* want active (like custom campaigns, UI fixes, or mutation mods). The Director will always bypass these and include them in the final sync.
* **Prune Regularly:** Workshop items get deleted or hidden by authors. Hit the **Prune Dead Links** button in Settings once a month to clear out dead mods from your local database.

---

## Advanced Features

### Deep-Scan Asset Inspector
Not sure if a mod is actually an AK-47 replacement or just a VGUI icon? Right-click any assigned mod and select **Inspect Raw Assets**. The engine will open a diagnostic window listing the exact internal `.mdl`, `.vmt`, and `.wav` paths the mod replaces inside the game engine.

### Loadout Share Codes
Want to run the exact same modlist with your friends in Co-Op? 
- Click **Code** at the bottom of the Director tab to compress your current loadout into a base64 string. 
- Your friends can click **Import**, paste the string, and the engine will instantly reconstruct the loadout from the database and prep it for Steam deployment.

### The Passive Miner
The built-in scraper evaluates mod file sizes and subscription counts before X-Raying them. Adjust the "Quality Filters" in the Scraper tab to ignore bloated 2GB files or dead 0-subscriber mods to keep your database fast and clean.
