import pandas as pd
import math
import pickle
from pathlib import Path

# Get the directory where this Python script is located
BASE_DIR = Path(__file__).resolve().parent

def generate_and_pickle_blocks():
    # Absolute paths relative to this script
    DIRECTORY_FILE = BASE_DIR / "pincodes_data.csv"
    CASES_FILE = BASE_DIR / "lead_data.csv"
    OUTPUT_PKL = BASE_DIR / "generated_blocks.pkl"

    print("📂 Reading datasets from local project folder...")
    print("Script folder:", BASE_DIR)
    print("Looking for:", CASES_FILE)
    print("Looking for:", DIRECTORY_FILE)

    # Check that the files exist before reading them
    if not CASES_FILE.exists():
        raise FileNotFoundError(f"Missing file: {CASES_FILE}")

    if not DIRECTORY_FILE.exists():
        raise FileNotFoundError(f"Missing file: {DIRECTORY_FILE}")

    df_cases = pd.read_csv(CASES_FILE)
    df_dir = pd.read_csv(DIRECTORY_FILE)

    print("✅ Loaded datasets successfully")

    # 4. Standardize Pincodes to clean 6-digit strings
    case_pin_col = 'Pincode' if 'Pincode' in df_cases.columns else 'pincode'
    df_cases[case_pin_col] = df_cases[case_pin_col].astype(str).str.strip().str.split('.').str[0].str.zfill(6)

    dir_pin_col = 'pincode' if 'pincode' in df_dir.columns else 'Pincode'
    df_dir[dir_pin_col] = df_dir[dir_pin_col].astype(str).str.strip().str.split('.').str[0].str.zfill(6)

    # 5. Normalize Directory Schemas to match Indian Pincode Data column layout
    df_dir = df_dir.rename(columns={
        'state': 'State', 
        'subdistrict': 'Branch', 
        'district': 'Region', 
        dir_pin_col: 'Pincode'
    })

    for col in ['State', 'Region', 'Branch']:
        if col in df_dir.columns:
            df_dir[col] = df_dir[col].astype(str).str.upper().str.strip()

    df_dir = df_dir.drop_duplicates(subset=['Pincode'])

    # 6. Merge Active Cases with Master Pincode Reference
    cols_to_check_and_add = ['State', 'Region', 'Branch']

    for col in cols_to_check_and_add:
        if col not in df_dir.columns:
            found_alt = False
            if col == 'State' and 'state' in df_dir.columns:
                df_dir = df_dir.rename(columns={'state': 'State'})
                found_alt = True
            elif col == 'Region' and 'district' in df_dir.columns: 
                df_dir = df_dir.rename(columns={'district': 'Region'})
                found_alt = True
            elif col == 'Branch' and 'subdistrict' in df_dir.columns: 
                df_dir = df_dir.rename(columns={'subdistrict': 'Branch'})
                found_alt = True
            if not found_alt and col not in df_dir.columns:
                df_dir[col] = pd.NA

    df_master_cases = pd.merge(df_cases[['LAN', case_pin_col]], df_dir[['Pincode', 'State', 'Region', 'Branch']], left_on=case_pin_col, right_on='Pincode', how='left')

    # Fill missing lookups so code doesn't break
    df_master_cases['Branch'] = df_master_cases['Branch'].fillna('UNKNOWN BRANCH')
    df_master_cases['State'] = df_master_cases['State'].fillna('UNKNOWN STATE')
    df_master_cases['Region'] = df_master_cases['Region'].fillna('UNKNOWN REGION')

    # ==========================================
    # # 7. Create Territory Distribution Blocks
    # ==========================================
    print("📦 Building localized case allocation blocks with flexible floor (150-300)...")
    block_counter = 1
    block_metadata = {}

    # Strict boundaries for processing
    HARD_MIN = 150     # Absolute minimum floor allowed for awkward splits
    TARGET_MIN = 200   # Preferred baseline target per block
    MAX_BOUND = 300    # Maximum workload ceiling per block
    TARGET_SIZE = 250  # Optimal midpoint for chunk division

    branch_groups = df_master_cases.groupby(['State', 'Region', 'Branch'])

    for (state, region, branch), b_group in branch_groups:
        # Sort pincodes numerically so geographically adjacent areas clump together sequentially
        pincode_counts = b_group['Pincode'].value_counts().sort_index()

        current_merge_bucket = []
        current_bucket_cases = []

        pincodes_list = list(pincode_counts.items())
        for idx, (pincode, count) in enumerate(pincodes_list):
            if pd.isna(pincode):
                continue
            pincode_cases = b_group[b_group['Pincode'] == pincode]['LAN'].tolist()

            # Accumulate the current pincode data into the active bucket
            current_merge_bucket.append(str(pincode))
            current_bucket_cases.extend(pincode_cases)

            is_last_pincode = (idx == len(pincodes_list) - 1)

            # Keep processing blocks while the accumulated bucket meets the preferred target threshold
            while len(current_bucket_cases) >= TARGET_MIN:
                total_working_count = len(current_bucket_cases)

                # Scenario A: The volume perfectly falls into our optimal 200-300 sweet spot
                if total_working_count <= MAX_BOUND:
                    block_name = f"Block {block_counter}"
                    block_metadata[block_name] = {
                        "State": state, "Region": region, "Branch": branch,
                        "Pincode": ", ".join(sorted(list(set(current_merge_bucket)))),
                        "Cases Count": total_working_count, "Cases": current_bucket_cases
                    }
                    block_counter += 1
                    current_merge_bucket, current_bucket_cases = [], []
                    break

                # Scenario B: High volume bucket. Calculate the ideal breakdown of balanced blocks
                num_blocks = max(1, math.floor(total_working_count / TARGET_SIZE))
                chunk_size = math.ceil(total_working_count / num_blocks)

                # Check what residual balance would be left behind if we cut this chunk size out
                residual_count = len(current_bucket_cases[chunk_size:])

                # Lookahead check: Prevent creating a chunk that leaves behind an unresolvable remainder
                if 0 < residual_count < HARD_MIN:
                    if is_last_pincode:
                        # No more incoming pincodes to save it; perfectly bisect the remaining volume instead
                        chunk_size = total_working_count // 2
                    else:
                        # Let the loop break and hold off on generating a block until the next pincode feeds the pool
                        break

                chunk = current_bucket_cases[:chunk_size]

                # Final verification of safety constraints before saving block
                if len(chunk) >= HARD_MIN:
                    block_name = f"Block {block_counter}"
                    block_metadata[block_name] = {
                        "State": state, "Region": region, "Branch": branch,
                        "Pincode": ", ".join(sorted(list(set(current_merge_bucket)))),
                        "Cases Count": len(chunk), "Cases": chunk
                    }
                    block_counter += 1
                    current_bucket_cases = current_bucket_cases[chunk_size:]
                else:
                    break

        # --- Branch-End Cleanup Guardrail ---
        # Handle remaining case fractions leftover at the absolute outer edge of the branch group
        if current_bucket_cases:
            # Fallback A: If the volume is completely functional on its own (>= 150), commit it as its own block
            if len(current_bucket_cases) >= HARD_MIN:
                block_name = f"Block {block_counter}"
                block_metadata[block_name] = {
                    "State": state, "Region": region, "Branch": branch,
                    "Pincode": ", ".join(sorted(list(set(current_merge_bucket)))),
                    "Cases Count": len(current_bucket_cases), "Cases": current_bucket_cases
                    }
                block_counter += 1
            # Fallback B: If it's too tiny (< 150), look backwards and merge it back into the preceding block if space allows
            elif block_counter > 1:
                last_block_id = f"Block {block_counter - 1}"
                if len(block_metadata[last_block_id]["Cases"]) + len(current_bucket_cases) <= MAX_BOUND:
                    block_metadata[last_block_id]["Cases"].extend(current_bucket_cases)
                    block_metadata[last_block_id]["Cases Count"] = len(block_metadata[last_block_id]["Cases"])

                    # Update block names safely to reflect the absorption
                    old_pins = block_metadata[last_block_id]["Pincode"].split(", ")
                    new_pins = list(set(old_pins + current_merge_bucket))
                    block_metadata[last_block_id]["Pincode"] = ", ".join(sorted(new_pins))
                else:
                    # Ultimate fallback protection to ensure 0 dropped leads
                    block_name = f"Block {block_counter}"
                    block_metadata[block_name] = {
                        "State": state, "Region": region, "Branch": branch,
                        "Pincode": ", ".join(sorted(list(set(current_merge_bucket)))),
                        "Cases Count": len(current_bucket_cases), "Cases": current_bucket_cases
                    }
                    block_counter += 1

    # Save data structure directly out to pickle object format
    print(f"💾 Saving block structures into {OUTPUT_PKL} file...")
    with open(OUTPUT_PKL, 'wb') as f:
        pickle.dump(block_metadata, f)
        
    print(f"✔️ Success! Generated {len(block_metadata)} structural matching blocks for visualization layout parsing optimization.")

if __name__ == "__main__":
    generate_and_pickle_blocks()