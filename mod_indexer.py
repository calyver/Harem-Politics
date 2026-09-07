import os
import re
import shutil
import pandas as pd

# --- CONFIGURATION ---
TARGET_TABS = ["common", "events", "gui", "localization"]
TARGET_TABS_INLINE = ["common", "events"] 
EXCLUDED_FOLDERS = ["culture/cultures", "religion/religion_types", "religion/rite_types"]

# 1. Your CK3 game folder
VANILLA_PATH = r"C:\Program Files (x86)\Steam\steamapps\common\Crusader Kings III\game"

# 2. Where the script should create the replicated vanilla folders and paste the files
VANILLA_OUTPUT_DIR = r"E:\Documents\Steve\Harem politics\Vanilla"

# 3. Specific keys you want to locate deep inside Vanilla files (Inline References)
SPECIFIC_TRACKED_KEYS = [
    "divorced_me_opinion",
    "spouse_made_secondary_opinion",
    "set_me_aside_opinion",
    "child_of_concubine_female",
    "child_of_concubine_male",
    "child_of_concubine",
    "doctrine_polygamy",
    "doctrine_concubines",
    "tradition_concubines",
    "tradition_polygamous",
    "tradition_tgp_court_machinations"
]

def get_grade(lines):
    if lines == "N/A": return "N/A"
    if lines <= 6: return 0
    elif lines <= 50: return 1
    elif lines <= 100: return 2
    elif lines <= 300: return 3
    else: return 4

def get_fast_vanilla_keys(file_path):
    """Returns a dict mapping root keys to their source file path."""
    keys = {}
    is_loc_file = file_path.endswith(".yml")
    bracket_count = 0
    
    try:
        with open(file_path, "r", encoding="utf-8-sig") as f:
            for line in f:
                clean_line = line.split("#")[0].strip()
                if not clean_line: continue
                
                if is_loc_file:
                    if bracket_count == 0 and ":" in clean_line:
                        potential_key = clean_line.split(":")[0].strip()
                        if re.match(r"^[a-zA-Z0-9_\-\:\.]+$", potential_key):
                            keys[potential_key] = file_path
                    continue
                    
                open_brackets = clean_line.count("{")
                close_brackets = clean_line.count("}")
                
                if bracket_count == 0 and "=" in clean_line:
                    potential_key = clean_line.split("=")[0].strip()
                    if re.match(r"^[a-zA-Z0-9_\-\:\.]+$", potential_key) and potential_key.lower() != "namespace":
                        keys[potential_key] = file_path
                        
                bracket_count += open_brackets
                bracket_count -= close_brackets
    except Exception:
        pass
    return keys

def build_vanilla_cache(vanilla_path):
    """Builds a memory map of Key -> Vanilla File Path."""
    cache = {tab: {} for tab in TARGET_TABS}
    if not os.path.exists(vanilla_path):
        print("⚠️ Vanilla path not found! Skipping mapping.")
        return cache
        
    print("Pre-scanning Vanilla files... (Optimized for Core tabs)")
    for tab_name in TARGET_TABS:
        tab_path = os.path.join(vanilla_path, tab_name)
        if not os.path.exists(tab_path): continue
        
        for root, _, files in os.walk(tab_path):
            if tab_name == "localization":
                rel = os.path.relpath(root, tab_path).replace("\\", "/").split("/")
                if len(rel) == 0 or rel[0] == "." or rel[0].lower() != "english":
                    continue
            for file in files:
                if file.endswith((".txt", ".yml", ".gui")):
                    full_file_path = os.path.join(root, file)
                    cache[tab_name].update(get_fast_vanilla_keys(full_file_path))
    return cache

def parse_mod_keys(file_path):
    root_keys = []
    is_loc_file = file_path.endswith(".yml")
    bracket_count = 0
    current_key = None
    current_lines = 0
    
    try:
        with open(file_path, "r", encoding="utf-8-sig") as f:
            for line in f:
                clean_line = line.split("#")[0].strip()
                
                if is_loc_file:
                    if not clean_line: continue
                    if bracket_count == 0 and ":" in clean_line:
                        potential_key = clean_line.split(":")[0].strip()
                        if re.match(r"^[a-zA-Z0-9_\-\:\.]+$", potential_key):
                            root_keys.append({"key": potential_key, "lines": "N/A", "grade": "N/A"})
                    continue
                    
                if not clean_line:
                    if current_key: current_lines += 1
                    continue
                    
                open_brackets = clean_line.count("{")
                close_brackets = clean_line.count("}")
                
                if bracket_count == 0 and current_key is None:
                    if "=" in clean_line:
                        potential_key = clean_line.split("=")[0].strip()
                        if re.match(r"^[a-zA-Z0-9_\-\:\.]+$", potential_key) and potential_key.lower() != "namespace":
                            current_key = potential_key
                            current_lines = 1
                                
                elif current_key is not None:
                    current_lines += 1
                    
                bracket_count += open_brackets
                bracket_count -= close_brackets
                
                if bracket_count == 0 and current_key is not None:
                    root_keys.append({"key": current_key, "lines": current_lines, "grade": get_grade(current_lines)})
                    current_key = None
                    current_lines = 0
    except Exception:
        pass
    return root_keys

def get_subfolders(relative_path):
    """Pads directory paths up to 4 levels."""
    if relative_path == "." or relative_path == "":
        dirs = []
    else:
        dirs = relative_path.replace("\\", "/").split("/")
    
    s1 = dirs[0] if len(dirs) > 0 else "[No sub-folder found]"
    s2 = dirs[1] if len(dirs) > 1 else "[No sub-folder found]"
    s3 = dirs[2] if len(dirs) > 2 else "[No sub-folder found]"
    s4 = dirs[3] if len(dirs) > 3 else "[No sub-folder found]"
    return s1, s2, s3, s4

def build_mod_database(mod_path):
    output_file = os.path.join(mod_path, "mod_update_tracker.xlsx")
    writer = pd.ExcelWriter(output_file, engine="openpyxl")
    
    vanilla_cache = build_vanilla_cache(VANILLA_PATH)
    copied_files = set() 
    
    print("\nScanning your mod files and processing overlaps...")
    
    for tab_name in TARGET_TABS:
        tab_path = os.path.join(mod_path, tab_name)
        if not os.path.exists(tab_path): continue
            
        data_rows = []
        for root, _, files in os.walk(tab_path):
            for file in files:
                if file.endswith((".txt", ".yml", ".gui")):
                    full_file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(root, tab_path)
                    s1, s2, s3, s4 = get_subfolders(relative_path)
                    
                    parsed_data = parse_mod_keys(full_file_path)
                    if parsed_data:
                        for item in parsed_data:
                            v_path = vanilla_cache[tab_name].get(item["key"])
                            is_vanilla = v_path is not None
                            
                            if is_vanilla and v_path not in copied_files:
                                rel_v_path = os.path.relpath(v_path, VANILLA_PATH)
                                target_dest = os.path.join(VANILLA_OUTPUT_DIR, rel_v_path)
                                os.makedirs(os.path.dirname(target_dest), exist_ok=True)
                                shutil.copy2(v_path, target_dest)
                                copied_files.add(v_path)
                            
                            data_rows.append({
                                "Subfolder Level 1": s1, "Subfolder Level 2": s2,
                                "Subfolder Level 3": s3, "Subfolder Level 4": s4,
                                "File Name": file,
                                "Root Code Key": item["key"],
                                "Classification": "Vanilla" if is_vanilla else "Mod Exclusive",
                                "Vanilla Conflict": "Conflict / Match" if is_vanilla else "", 
                                "Line Count": item["lines"],
                                "Difficulty Grade": item["grade"],
                                "Status": "", "Notes/Observations": "" 
                            })
                    else:
                        data_rows.append({
                            "Subfolder Level 1": s1, "Subfolder Level 2": s2,
                            "Subfolder Level 3": s3, "Subfolder Level 4": s4,
                            "File Name": file, "Root Code Key": "[No root keys found]",
                            "Classification": "", "Vanilla Conflict": "",
                            "Line Count": "N/A", "Difficulty Grade": "N/A",
                            "Status": "", "Notes/Observations": "" 
                        })

        if data_rows:
            df = pd.DataFrame(data_rows)
            df.to_excel(writer, sheet_name=tab_name, index=False)
            print(f"Created tab '{tab_name}' with {len(df)} entries.")

    # --- INLINE VANILLA SCANNER (Now with File Copying) ---
    print("\nScanning Vanilla for specific inline references...")
    inline_rows = []

    for tab_name in TARGET_TABS_INLINE:
        tab_path = os.path.join(VANILLA_PATH, tab_name)
        if not os.path.exists(tab_path): continue

        for root, _, files in os.walk(tab_path):
            relative_path = os.path.relpath(root, tab_path).replace("\\", "/")
            
            if tab_name == "common":
                skip_folder = False
                for excl in EXCLUDED_FOLDERS:
                    if relative_path == excl or relative_path.startswith(excl + "/"):
                        skip_folder = True
                        break
                if skip_folder:
                    continue
                    
            for file in files:
                if file.endswith((".txt", ".yml", ".gui")):
                    full_file_path = os.path.join(root, file)
                    s1, s2, s3, s4 = get_subfolders(relative_path)

                    bracket_count = 0
                    current_root_key = None
                    
                    try:
                        with open(full_file_path, "r", encoding="utf-8-sig") as f:
                            for line_no, line in enumerate(f, 1):
                                clean_line = line.split("#")[0]
                                stripped = clean_line.strip()
                                if not stripped: continue
                                
                                open_b = stripped.count("{")
                                close_b = stripped.count("}")
                                
                                if bracket_count == 0 and current_root_key is None and "=" in stripped:
                                    potential = stripped.split("=")[0].strip()
                                    if re.match(r"^[a-zA-Z0-9_\-\:\.]+$", potential) and potential.lower() != "namespace":
                                        current_root_key = potential

                                for key in SPECIFIC_TRACKED_KEYS:
                                    if re.search(r'\b' + re.escape(key) + r'\b', clean_line):
                                        
                                        # File auto-copy logic for inline hits
                                        if full_file_path not in copied_files:
                                            rel_v_path = os.path.relpath(full_file_path, VANILLA_PATH)
                                            target_dest = os.path.join(VANILLA_OUTPUT_DIR, rel_v_path)
                                            os.makedirs(os.path.dirname(target_dest), exist_ok=True)
                                            shutil.copy2(full_file_path, target_dest)
                                            copied_files.add(full_file_path)

                                        inline_rows.append({
                                            "Target Key": key, "Root Tab": tab_name,
                                            "Subfolder Level 1": s1, "Subfolder Level 2": s2,
                                            "Subfolder Level 3": s3, "Subfolder Level 4": s4,
                                            "File Name": file,
                                            "Root Key": current_root_key if current_root_key else "[Global]",
                                            "Line Number": line_no, "Code Line": line.strip(),
                                            "Status": "", "Notes/Comments/Observation": ""
                                        })

                                bracket_count += open_b
                                bracket_count -= close_b
                                if bracket_count == 0: current_root_key = None
                    except Exception:
                        pass

    if inline_rows:
        df_inline = pd.DataFrame(inline_rows)
        df_inline.to_excel(writer, sheet_name="Inline References", index=False)
        print(f"Created tab 'Inline References' with {len(df_inline)} hits.")

    writer.close()
    print(f"\nDone! Database saved. Unique vanilla files copied to: {VANILLA_OUTPUT_DIR}")


if __name__ == "__main__":
    current_directory = os.path.dirname(os.path.realpath(__file__))
    build_mod_database(current_directory)