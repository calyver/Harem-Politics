import os
import re
import pandas as pd

# --- CONFIGURATION ---
TARGET_TABS = ["common", "events", "localization"]

# 1. Update your Vanilla path
VANILLA_PATH = r"C:\Program Files (x86)\Steam\steamapps\common\Crusader Kings III\game"

# 2. Update the Love Marriage Family mod folder path
LMF_PATH = r"C:\Program Files (x86)\Steam\steamapps\workshop\content\1158310\3037969445"

# 3. Specific inline keys/strings you want to track anywhere in the LMF code
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


def get_fast_keys(file_path):
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
    cache = {tab: set() for tab in TARGET_TABS}
    if not os.path.exists(vanilla_path):
        print("⚠️ Vanilla path not found! Skipping mapping.")
        return cache
        
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
                    cache[tab_name].update(get_fast_keys(full_file_path))
    return cache


def build_lmf_cache(lmf_path):
    cache = set()
    if not os.path.exists(lmf_path):
        print("⚠️ LMF path not found! Skipping mapping.")
        return cache
        
    print("Pre-scanning Love Marriage Family files... (Scanning ENTIRE mod folder)")
    for root, _, files in os.walk(lmf_path):
        for file in files:
            if file.endswith((".txt", ".yml")):
                full_file_path = os.path.join(root, file)
                cache.update(get_fast_keys(full_file_path))
    return cache


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
                    
    except Exception as e:
        print(f"Skipping {file_path} due to error: {e}")
        pass
        
    return root_keys


def scan_specific_keys(file_path, tab_name, tracked_keys, user_mod_keys):
    """Scans for specific inline keys, but intelligently ignores them if they are inside a known shared root."""
    found_instances = []
    is_loc_file = file_path.endswith(".yml")
    bracket_count = 0
    current_root_key = None
    
    try:
        with open(file_path, "r", encoding="utf-8-sig") as f:
            for line_no, line in enumerate(f, 1):
                clean_line = line.split("#")[0]
                stripped_line = clean_line.strip()
                if not stripped_line:
                    continue
                
                # Figure out what Root Key block we are currently reading inside LMF
                if is_loc_file:
                    if bracket_count == 0 and ":" in stripped_line:
                        potential_key = stripped_line.split(":")[0].strip()
                        if re.match(r"^[a-zA-Z0-9_\-\:\.]+$", potential_key):
                            current_root_key = potential_key
                else:
                    open_brackets = stripped_line.count("{")
                    close_brackets = stripped_line.count("}")
                    
                    if bracket_count == 0 and current_root_key is None:
                        if "=" in stripped_line:
                            potential_key = stripped_line.split("=")[0].strip()
                            if re.match(r"^[a-zA-Z0-9_\-\:\.]+$", potential_key) and potential_key.lower() != "namespace":
                                current_root_key = potential_key

                # Scan the line for our specific tracked keywords
                for key in tracked_keys:
                    if re.search(r'\b' + re.escape(key) + r'\b', clean_line):
                        
                        # THE MAGIC CHECK: Is this block already tracked in our main Excel tabs?
                        if current_root_key and current_root_key in user_mod_keys:
                            continue # Ignore it, you already know about this block!
                        
                        found_instances.append({
                            "Target Key": key,
                            "Line Number": line_no,
                            "Line Snippet": line.strip(),
                            "LMF Root Key": current_root_key if current_root_key else "[Global/Unknown]"
                        })

                # Adjust brackets *after* scanning the line to catch the closing bracket properly
                if not is_loc_file:
                    bracket_count += open_brackets
                    bracket_count -= close_brackets
                    if bracket_count == 0 and current_root_key is not None:
                        current_root_key = None
                        
    except Exception:
        pass
        
    return found_instances


def build_mod_database(mod_path):
    output_file = os.path.join(mod_path, "mod_compatch_database.xlsx")
    writer = pd.ExcelWriter(output_file, engine="openpyxl")
    
    vanilla_cache = build_vanilla_cache(VANILLA_PATH)
    lmf_cache = build_lmf_cache(LMF_PATH)
    
    # We will build a memory bank of ALL root keys present in your mod files 
    user_mod_keys = set()
    
    print("\nScanning your mod files and identifying overlaps...")
    
    for tab_name in TARGET_TABS:
        tab_path = os.path.join(mod_path, tab_name)
        if not os.path.exists(tab_path):
            continue
            
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
                            # Save your root key into the global memory bank for the inline scanner to use later
                            user_mod_keys.add(item["key"])
                            
                            is_vanilla = item["key"] in vanilla_cache[tab_name]
                            is_lmf = item["key"] in lmf_cache
                            
                            data_rows.append({
                                "Subfolder Level 1": sub1,
                                "Subfolder Level 2": sub2,
                                "Subfolder Level 3": sub3,
                                "File Name": file,
                                "Root Code Key": item["key"],
                                "Classification": "Vanilla" if is_vanilla else "Mod",
                                "LMF Coincidence": "Conflict / Match" if is_lmf else "", 
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
                            "LMF Coincidence": "",
                            "Line Count": "N/A",
                            "Grade (0-4)": "N/A",
                            "Status": "" 
                        })

        if data_rows:
            df = pd.DataFrame(data_rows)
            df.to_excel(writer, sheet_name=tab_name, index=False)
            print(f"Created tab '{tab_name}' with {len(df)} entries.")

    # --- SCAN FOR SPECIFIC INLINE KEYS IN LMF ---
    print("\nScanning Love Marriage Family (LMF) for specific inline key occurrences...")
    specific_rows = []

    for tab_name in TARGET_TABS:
        tab_path = os.path.join(LMF_PATH, tab_name)
        if not os.path.exists(tab_path):
            continue

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

                    # Pass the 'user_mod_keys' into the scanner so it knows what to skip!
                    hits = scan_specific_keys(full_file_path, tab_name, SPECIFIC_TRACKED_KEYS, user_mod_keys)
                    
                    for hit in hits:
                        specific_rows.append({
                            "Target Key": hit["Target Key"],
                            "Root Tab": tab_name,
                            "Subfolder Level 1": sub1,
                            "Subfolder Level 2": sub2,
                            "Subfolder Level 3": sub3,
                            "File Name": file,
                            "LMF Root Key": hit["LMF Root Key"],
                            "Line Number": hit["Line Number"],
                            "Code Line": hit["Line Snippet"],
                            "Status": ""
                        })

    if specific_rows:
        df_specific = pd.DataFrame(specific_rows)
        df_specific.to_excel(writer, sheet_name="Inline References", index=False)
        print(f"Created tab 'Inline References' with {len(df_specific)} specific isolated hits in LMF.")
    else:
        print("No isolated inline keys found in LMF (all hits were inside already tracked roots).")

    writer.close()
    print(f"\nDone! Compatch database saved to: {output_file}")


if __name__ == "__main__":
    current_directory = os.path.dirname(os.path.realpath(__file__))
    build_mod_database(current_directory)