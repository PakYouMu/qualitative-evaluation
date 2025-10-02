import os
import shutil
from pathlib import Path

# --- CONFIGURATION ---
# IMPORTANT: Point this to the root folder of your DEEP image structure on your local machine.
# This should be the same path as in your 'prepare_images.py' script.
SOURCE_FOLDER = Path(r"B:\[1] Main Drive Supposedly\Datasets\Thesis\[5] Qualitative Evaluation")

# This is the destination folder for the EMPTY placeholder files.
DESTINATION_FOLDER = Path("static/evaluation_images")
# --- END OF CONFIGURATION ---

def create_placeholder_files():
    """
    Scans the deep source folder, generates the correct flattened filenames,
    and creates empty (0 KB) placeholder files in the destination folder.
    """
    print("--- Starting Placeholder File Creation Script ---")
    
    if not SOURCE_FOLDER.is_dir():
        print(f"!!! ERROR: The source folder was not found at: {SOURCE_FOLDER}")
        return

    # Clear out the old destination folder for a fresh start
    if DESTINATION_FOLDER.exists():
        print(f"-> Removing existing placeholder folder: {DESTINATION_FOLDER}")
        shutil.rmtree(DESTINATION_FOLDER)
    
    # Create the new, empty destination folder
    DESTINATION_FOLDER.mkdir(parents=True)
    print(f"-> Created new empty placeholder folder: {DESTINATION_FOLDER}")

    file_count = 0
    # Use rglob to find all matching files recursively
    for source_path in SOURCE_FOLDER.rglob("*_stacked.png"):
        try:
            # This logic is IDENTICAL to prepare_images.py
            class_name = source_path.parent.name
            metric_name = source_path.parent.parent.name
            case_name = source_path.name.replace('_stacked.png', '')

            new_filename = f"{class_name.replace(' ', '_')}__{metric_name}__{case_name}.png"
            destination_path = DESTINATION_FOLDER / new_filename
            
            # --- THE KEY CHANGE ---
            # Instead of copying the file, we just create an empty file with the same name.
            destination_path.touch()
            file_count += 1

        except Exception as e:
            print(f"-> WARNING: Could not process file: {source_path}. Error: {e}")
            
    print("\n--- Placeholder Creation Complete! ---")
    print(f"Successfully created {file_count} empty placeholder files in '{DESTINATION_FOLDER}'.")
    print("You are now ready to commit and push this folder to your main application repository.")

if __name__ == '__main__':
    create_placeholder_files()