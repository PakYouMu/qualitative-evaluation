import os
print("--- Vercel Environment Debug ---")
print("SUPABASE_URL is set:", "SUPABASE_URL" in os.environ)
print("SUPABASE_SERVICE_ROLE_KEY is set:", "SUPABASE_SERVICE_ROLE_KEY" in os.environ)
print("------------------------------")
import json
from flask import Flask, render_template, request, redirect, url_for, jsonify
import traceback 
from urllib.parse import quote
from supabase import create_client, Client
import threading

# --- Supabase Initialization ---
# These environment variables are set automatically by Vercel when you link Supabase
SUPABASE_URL = os.environ.get("SUPABASE_URL")
# IMPORTANT: Use the SERVICE_ROLE_KEY for server-to-server communication
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") 

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    print(f"Error initializing Supabase client: {e}. Environment variables might be missing.")
    supabase = None

# --- Configuration & Initialization ---
STATIC_IMAGE_FOLDER = 'static/evaluation_images'
CLASS_ABBREVIATIONS = {
    'Copra Cake': 'CC', 'Cracked Corn': 'CORN', 'Feed Wheats': 'FW',
    'Hard Pollard': 'HP', 'Jocky Oats': 'JO', 'Rice Bran': 'RB', 'US Soya': 'SOY'
}
EVALUATION_ITEMS = []
app = Flask(__name__, static_folder='../static', template_folder='../templates')

# --- Image Loading Logic (Unchanged) ---
def load_evaluation_items():
    """
    Builds a list of evaluation items by constructing public GitHub Raw URLs.
    This logic remains from your original script.
    """
    print("--- Loading items by building public GitHub Raw URLs ---")
    
    # NOTE: It's better practice to get these from environment variables
    # but we will keep your original hardcoded values for now.
    GITHUB_USERNAME = "PakYouMu"
    IMAGE_REPO_NAME = "qualitative-evaluation-images" # Corrected repo name
    BRANCH_NAME = "main"

    # This path is for local discovery, but the URL is what's used in the app
    image_folder_path = os.path.join(os.path.dirname(__file__), '..', STATIC_IMAGE_FOLDER)

    if not os.path.isdir(image_folder_path):
        print(f"CRITICAL ERROR: The directory '{image_folder_path}' was not found.")
        return []
        
    image_data = []
    # Assumes filenames are like 'ClassName__MetricName__CaseName.png'
    for filename in sorted(os.listdir(image_folder_path)): # Added sorted() for consistent order
        if filename.lower().endswith(".png"):
            try:
                base_name = filename[:-4]
                class_part, metric_part, case_part = base_name.split('__')
                class_name = class_part.replace('_', ' ')
                
                safe_filename = quote(filename)
                # Corrected the GitHub Raw URL structure
                public_url = f"https://raw.githubusercontent.com/{GITHUB_USERNAME}/{IMAGE_REPO_NAME}/refs/heads/{BRANCH_NAME}/{STATIC_IMAGE_FOLDER}/{safe_filename}"
                
                # # --- FINAL FIX: URL-safe quoting of the filename ---
                # safe_filename = quote(filename)
                # public_url = f"https://raw.githubusercontent.com/{GITHUB_USERNAME}/{IMAGE_REPO_NAME}/refs/heads/{BRANCH_NAME}/static/evaluation_images/{safe_filename}"

                image_data.append({
                    "metric": metric_part,
                    "class": class_name,
                    "case": case_part,
                    "web_path": public_url
                })
            except Exception as e:
                print(f"Warning: Could not parse filename '{filename}'. Skipping. Error: {e}")

    # This sorting might be redundant if listdir is sorted, but it's safe to keep
    image_data.sort(key=lambda x: (x['class'], x['metric'], x['case']))
    
    for i, item in enumerate(image_data):
        class_abbr = CLASS_ABBREVIATIONS.get(item['class'], 'UNK')
        item['eval_id'] = f"{class_abbr}-{item['metric'].upper()}-{item['case']}"
        item['id'] = i

    print(f" -> Successfully built {len(image_data)} public GitHub image URLs.")
    return image_data

# Load the items when the application starts
EVALUATION_ITEMS = load_evaluation_items()


# --- HTML Page Serving Routes (Unchanged) ---
@app.route('/')
@app.route('/evaluate/<int:item_id>')
def evaluate_item(item_id=0):
    if not EVALUATION_ITEMS:
        return "Error: No evaluation items were loaded. Please check the server logs.", 500
    if not 0 <= item_id < len(EVALUATION_ITEMS):
        return redirect(url_for('home')) # Redirect home if ID is invalid
        
    item = EVALUATION_ITEMS[item_id]
    total_items = len(EVALUATION_ITEMS)
    previous_id = item_id - 1 if item_id > 0 else None
    next_id = item_id + 1 if item_id < total_items - 1 else None
    return render_template(
        'index.html', item=item, item_id=item_id, total_items=total_items,
        previous_id=previous_id, next_id=next_id
    )

@app.route('/complete')
def complete():
    """Renders the completion page."""
    return render_template('complete.html')


# --- NEW AND MODIFIED API ROUTES ---

@app.route('/api/get_new_user_id', methods=['GET'])
def get_new_user_id():
    """Calls the Supabase RPC to get a new, unique, sequential user ID."""
    if not supabase:
        return jsonify({'error': 'Supabase client not initialized'}), 500
    try:
        # Call the 'get_next_user_id' function you created in the Supabase SQL Editor
        response = supabase.rpc('get_next_user_id', {}).execute()
        if response.data:
            return jsonify({'user_id': response.data})
        else:
            raise Exception(getattr(response, 'error', 'Unknown RPC error'))
    except Exception as e:
        print(f"Error calling Supabase RPC: {e}")
        return jsonify({'error': 'Could not generate user ID'}), 500

@app.route('/api/submit', methods=['POST'])
def submit_evaluation():
    """Receives form data and inserts it into the Supabase 'evaluations' table."""
    if not supabase:
        return "Error: Supabase client not initialized.", 500
        
    try:
        form_data = request.form.to_dict()
        
        # Prepare the data for insertion, matching the Supabase table schema
        data_to_insert = {
            'session_identifier': int(form_data.get('session_identifier')),
            'eval_id': form_data.get('eval_id'),
            'item_class': form_data.get('item_class'),
            'item_metric': form_data.get('item_metric'),
            'item_case': form_data.get('item_case'),
            'comparative_rating': form_data.get('comparative_rating'),
            'test_rating': int(form_data.get('test_rating')),
            'comparison_rating': int(form_data.get('comparison_rating')),
            'comments': form_data.get('comments', '').strip()
        }
        
        # Insert the data into the Supabase 'evaluations' table
        response = supabase.table('evaluations').insert(data_to_insert).execute()

        # Check for errors during insertion
        if len(response.data) == 0 and response.error:
             raise Exception(response.error.message)
        
        print("Successfully inserted a row into Supabase.")

    except Exception as e:
        print(f"A REAL error occurred while saving to Supabase: {e}")
        traceback.print_exc()
        return "An error occurred while saving your evaluation. Please check the server logs.", 500

    # Redirect logic is now safely outside the try/except block for data insertion
    next_item_id_str = form_data.get('next_item_id')
    if next_item_id_str and next_item_id_str != 'None':
        return redirect(url_for('evaluate_item', item_id=int(next_item_id_str)))
    else:
        return redirect(url_for('complete'))

# This block is for local development if you run 'python api/index.py'
if __name__ == '__main__':
    app.run(debug=True)