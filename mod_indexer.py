import os
import re
import pandas as pd

# --- CONFIGURATION ---
TARGET_TABS = ["common", "events", "localization"]

# Update with your actual Vanilla CK3 game folder path
VANILLA_PATH = r"C:\Program Files (x86)\Steam\steamapps\common\Crusader Kings III\game"

# Add the specific inline keys/variables you need to find in Vanilla here
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
    keys = set()
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
                            keys.add(potential_key)
                    continue
                    
                open_brackets = clean_line.count("{")
                close_brackets = clean_line.count("}")
                
                if bracket_count == 0 and "=" in clean_line:
                    potential_key = clean_line.split("=")[0].strip()
                    if re.match(r"^[a-zA-Z0-9_\-\:\.]+$", potential_key) and potential_key.lower() != "namespace":
                        keys.add(potential_key)
                        
                bracket_count += open_brackets
                bracket_count -= close_brackets
    except Exception:
        pass
    return keys

def build_vanilla_cache(vanilla_path):
    vanilla_cache = {tab: set() for tab in TARGET_TABS}
    if not os.path.exists(vanilla_path):
        return vanilla_cache
        
    print("Pre-scanning Vanilla files... (Optimized for English & Core tabs)")
    for tab_name in TARGET_TABS:
        tab_path = os.path.join(vanilla_path, tab_name)
        if not os.path.exists(tab_path): continue
        
        for root, _, files in os.walk(tab_path):
            if tab_name == "localization":
                relative_parts = os.path.relpath(root, tab_path).replace("\\", "/").split("/")
                if len(relative_parts) == 0 or relative_parts[0] == "." or relative_parts[0].lower() != "english":
                    continue
            for file in files:
                if file.endswith((".txt", ".yml")):
                    full_file_path = os.path.join(root, file)
                    vanilla_cache[tab_name].update(get_fast_vanilla_keys(full_file_path))
    return vanilla_cache

def parse_keys_and_lines(file_path):
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

def scan_specific_keys(file_path, tracked_keys):
    """Scans a file line-by-line for specific keys and maps them to their root block."""
    found_instances = []
    bracket_count = 0
    current_root_key = None
    
    try:
        with open(file_path, "r", encoding="utf-8-sig") as f:
            for line_no, line in enumerate(f, 1):
                clean_line = line.split("#")[0]
                stripped_line = clean_line.strip()
                if not stripped_line: continue
                
                # Identify Root Key Block
                open_brackets = stripped_line.count("{")
                close_brackets = stripped_line.count("}")
                
                if bracket_count == 0 and current_root_key is None:
                    if "=" in stripped_line:
                        potential_key = stripped_line.split("=")[0].strip()
                        if re.match(r"^[a-zA-Z0-9_\-\:\.]+$", potential_key) and potential_key.lower() != "namespace":
                            current_root_key = potential_key

                # Check for tracked targets using regex word boundaries
                for key in tracked_keys:
                    if re.search(r'\b' + re.escape(key) + r'\b', clean_line):
                        found_instances.append({
                            "Target Key": key,
                            "Root Code Key": current_root_key if current_root_key else "[Global/Unknown]",
                            "Line Number": line_no,
                            "Code Line": line.strip() 
                        })

                # Adjust brackets after scanning
                bracket_count += open_brackets
                bracket_count -= close_brackets
                if bracket_count == 0 and current_root_key is not None:
                    current_root_key = None
    except Exception:
        pass
    return found_instances

def build_mod_database(mod_path):
    output_file = os.path.join(mod_path, "mod_file_database_final.xlsx")
    writer = pd.ExcelWriter(output_file, engine="openpyxl")
    
    vanilla_cache = build_vanilla_cache(VANILLA_PATH)
    print("\nScanning mod files and generating main database...")
    
    for tab_name in TARGET_TABS:
        tab_path = os.path.join(mod_path, tab_name)
        if not os.path.exists(tab_path): continue
            
        data_rows = []
        for root, _, files in os.walk(tab_path):
            for file in files:
                if file.endswith((".txt", ".yml")):
                    full_file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(root, tab_path)
                    
                    if relative_path == ".": subfolders = []
                    else: subfolders = relative_path.replace("\\", "/").split("/")
                    
                    sub1 = subfolders[0] if len(subfolders) > 0 else "[No sub-folder found]"
                    sub2 = subfolders[1] if len(subfolders) > 1 else "[No sub-folder found]"
                    sub3 = subfolders[2] if len(subfolders) > 2 else "[No sub-folder found]"
                    
                    parsed_data = parse_keys_and_lines(full_file_path)
                    
                    if parsed_data:
                        for item in parsed_data:
                            is_vanilla = item["key"] in vanilla_cache[tab_name]
                            data_rows.append({
                                "Subfolder Level 1": sub1,
                                "Subfolder Level 2": sub2,
                                "Subfolder Level 3": sub3,
                                "File Name": file,
                                "Root Code Key": item["key"],
                                "Classification": "Vanilla" if is_vanilla else "Mod",
                                "Line Count": item["lines"],
                                "Grade (0-4)": item["grade"],
                                "Status": "" 
                            })
                    else:
                        data_rows.append({
                            "Subfolder Level 1": sub1,
                            "Subfolder Level 2": sub2,
                            "Subfolder Level 3": sub3,
                            "File Name": file,
                            "Root Code Key": "[No root keys found]",
                            "Classification": "",
                            "Line Count": "N/A",
                            "Grade (0-4)": "N/A",
                            "Status": "" 
                        })

        if data_rows:
            df = pd.DataFrame(data_rows)
            df.to_excel(writer, sheet_name=tab_name, index=False)
            print(f"Created tab '{tab_name}' with {len(df)} entries.")

    # --- NEW: SCAN VANILLA FOR INLINE REFERENCES ---
    print("\nScanning Vanilla for specific inline key occurrences...")
    specific_rows = []
    
    # Restrict the inline scan specifically to common and events per your request
    TARGET_TABS_INLINE = ["common", "events"] 
    EXCLUDED_FOLDERS = ["culture/cultures", "religion/religion_types", "religion/rite_types"]

    for tab_name in TARGET_TABS_INLINE:
        tab_path = os.path.join(VANILLA_PATH, tab_name)
        if not os.path.exists(tab_path): continue

        for root, _, files in os.walk(tab_path):
            relative_path = os.path.relpath(root, tab_path).replace("\\", "/")
            
            # Exclusion check: skip if we are in one of the forbidden folders
            if tab_name == "common":
                skip_folder = False
                for excl in EXCLUDED_FOLDERS:
                    if relative_path == excl or relative_path.startswith(excl + "/"):
                        skip_folder = True
                        break
                if skip_folder:
                    continue

            for file in files:
                if file.endswith(".txt"):
                    full_file_path = os.path.join(root, file)

                    if relative_path == "." or relative_path == "": 
                        subfolders = []
                    else: 
                        subfolders = relative_path.split("/")

                    sub1 = subfolders[0] if len(subfolders) > 0 else "[No sub-folder found]"
                    sub2 = subfolders[1] if len(subfolders) > 1 else "[No sub-folder found]"
                    sub3 = subfolders[2] if len(subfolders) > 2 else "[No sub-folder found]"

                    hits = scan_specific_keys(full_file_path, SPECIFIC_TRACKED_KEYS)
                    for hit in hits:
                        specific_rows.append({
                            "Target Key": hit["Target Key"],
                            "Root Tab": tab_name,
                            "Subfolder Level 1": sub1,
                            "Subfolder Level 2": sub2,
                            "Subfolder Level 3": sub3,
                            "File Name": file,
                            "Root Code Key": hit["Root Code Key"],
                            "Line Number": hit["Line Number"],
                            "Code Line": hit["Code Line"],
                            "Status": "",
                            "Notes": ""
                        })

    if specific_rows:
        df_specific = pd.DataFrame(specific_rows)
        df_specific.to_excel(writer, sheet_name="Inline References", index=False)
        print(f"Created tab 'Inline References' with {len(df_specific)} specific hits in Vanilla.")
    else:
        print("No specific inline keys found in Vanilla.")

    writer.close()
    print(f"\nDone! Final database saved to: {output_file}")


if __name__ == "__main__":
    current_directory = os.path.dirname(os.path.realpath(__file__))
    build_mod_database(current_directory)