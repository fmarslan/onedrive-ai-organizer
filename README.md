# OneDrive AI Organizer

This project exports the **full OneDrive folder + file tree** and creates helper reports you can review later. It works on any machine or inside Google Colab.

- Runtime: local Python or Google Colab  
- Auth: Microsoft Graph device-code flow  
- Output: CSV inventory + two text summaries (current structure + suggested structure) + JSON state file

---

## 1. Prerequisites (one-time Azure setup)

1. Go to <https://portal.azure.com>.
2. Azure Active Directory → App registrations → New registration.
3. Give it any name, e.g., `onedrive-ai-organizer-app`.
4. Supported account types: choose what you need (for most users `Accounts in this organizational directory only` or `common`).
5. After creation, copy the **Application (client) ID**.
6. Under Authentication → Add a platform → Mobile and desktop applications → redirect URI `https://login.microsoftonline.com/common/oauth2/nativeclient`. Enable “Allow public client flows” if available.
7. Under API permissions add Microsoft Graph → Delegated → `Files.Read.All`, then grant admin consent if required.

You will use the client ID (and optionally tenant) when running the script. No other Azure work is needed.

---

## 2. Project structure

```
onedrive-ai-organizer/
├─ README.md
├─ requirements.txt
├─ main.py
└─ src/onedrive_ai_organizer/
   ├─ __init__.py
   ├─ config.py
   └─ onedrive_tree.py
```

`main.py` bootstraps Python, asks for config, runs the Graph scan, and writes all outputs.

---

## 3. How to run (local machine)

```bash
python -m venv .venv
. .venv/bin/activate          # Windows: .venv\Scripts\activate
# Optional: choose a persistent folder for results
export OUTPUT_DIR="/absolute/path/onedrive-exports"
pip install -r requirements.txt
python main.py
```

During the run:

1. The CLI asks which classification flow you want (option 1 = full scan + automatic recommendation, option 2 = coming soon).
2. It prompts for `MS_CLIENT_ID`, `MS_TENANT`, and (if empty) an **output directory** for all artifacts (you can skip the prompt by exporting `OUTPUT_DIR` beforehand).
3. Follow the printed device-code instructions to log in with your Microsoft account.
4. The script shows a progress bar while it walks the tree, then saves:
   - `onedrive_tree.csv` (raw inventory),
   - `original_structure.txt` (human-readable snapshot),
   - `recommended_structure.txt` (simple grouped suggestion),
   - `scan_state.json` (metadata that updates about once per minute so you can monitor progress).
5. If the Microsoft Graph token expires mid-scan, the CLI first tries to refresh it silently; if that fails, it asks you to approve a fresh device-code login and then resumes exactly where it stopped.

---

## 4. Running inside Google Colab

1. Open a new Colab notebook and mount Google Drive (`from google.colab import drive; drive.mount('/content/drive')`).  
2. Clone this repo: `!git clone https://github.com/fmarslan/onedrive-ai-organizer.git` and `cd onedrive-ai-organizer`.  
3. Install requirements with `!pip install -r requirements.txt`.  
4. Set an output folder that lives on Drive (`import os; os.environ["OUTPUT_DIR"] = "/content/drive/MyDrive/onedrive-ai-organizer"`).  
5. Run `!python main.py` and follow the same prompts as above.

---

## 5. What happens behind the scenes

1. The script collects config (client ID + tenant).  
2. It starts the MSAL device-code flow and waits for you to approve access.  
3. Once the token is ready, it calls `me/drive/root` and recursively loads every folder and file (with `id`, `path`, `size`, timestamps, etc.). The scanner handles rate limits (429/503) and silently refreshes tokens whenever possible.  
4. It exports the raw data to CSV and produces the two text summaries so you can quickly review the current vs. suggested structure.
5. It keeps writing `scan_state.json` during the scan (roughly once per minute) so you can see partial progress, then replaces it with the final summary when the run completes.

Use the CSV and text files to plan your cleanup or feed them into other tooling. If you extend the repo later (classification pipelines, re-organization scripts, etc.), keep this README as the entry point for running the baseline export.
