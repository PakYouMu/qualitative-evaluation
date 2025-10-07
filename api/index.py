from flask import Flask, render_template, request, jsonify, redirect, url_for
import os
from supabase import create_client, Client
from urllib.parse import quote
import traceback

# --- App Initialization ---
# When using this single-file structure, Flask needs to know where to find the templates/static folders.
# The paths are relative to this 'api' directory.
app = Flask(__name__, template_folder='../templates', static_folder='../static')

# --- Supabase Initialization ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("--- Supabase client initialized successfully. ---")
    except Exception as e:
        print(f"--- FATAL: Error initializing Supabase client: {e} ---")
else:
    print("--- FATAL: Supabase environment variables not found. ---")


# --- Image Data Loading ---
STATIC_IMAGE_FOLDER = 'static/evaluation_images'
CLASS_ABBREVIATIONS = {
    'Copra Cake': 'CC', 'Cracked Corn': 'CORN', 'Feed Wheats': 'FW',
    'Hard Pollard': 'HP', 'Jocky Oats': 'JO', 'Rice Bran': 'RB', 'US Soya': 'SOY'
}
EVALUATION_ITEMS = []

def load_evaluation_items():
    print("--- Loading evaluation items... ---")
    GITHUB_USERNAME = "PakYouMu"
    IMAGE_REPO_NAME = "qualitative-evaluation-images"
    BRANCH_NAME = "main"
    
    # Path is relative to the project root, so we go up one level from 'api'
    project_root = os.path.dirname(os.path.dirname(__file__))
    image_folder_path = os.path.join(project_root, STATIC_IMAGE_FOLDER)
    
    image_data = []
    if os.path.isdir(image_folder_path):
        for filename in sorted(os.listdir(image_folder_path)):
            if filename.lower().endswith(".png"):
                try:
                    base_name, _ = os.path.splitext(filename)
                    class_part, metric_part, case_part = base_name.split('__')
                    class_name = class_part.replace('_', ' ')
                    safe_filename = quote(filename)
                    public_url = f"https://raw.githubusercontent.com/{GITHUB_USERNAME}/{IMAGE_REPO_NAME}/{BRANCH_NAME}/{STATIC_IMAGE_FOLDER}/{safe_filename}"
                    image_data.append({"metric": metric_part, "class": class_name, "case": case_part, "web_path": public_url})
                except Exception as e:
                    print(f"Warning: Could not parse filename '{filename}'. Skipping. Error: {e}")
    else:
        print(f"CRITICAL WARNING: Local image directory not found at '{image_folder_path}'. URL generation may be incomplete.")

    for i, item in enumerate(image_data):
        class_abbr = CLASS_ABBREVIATIONS.get(item['class'], 'UNK')
        item['eval_id'] = f"{class_abbr}-{item['metric'].upper()}-{item['case']}"
        item['id'] = i

    print(f" -> Successfully built {len(image_data)} image URLs.")
    return image_data

EVALUATION_ITEMS = load_evaluation_items()
TOTAL_ITEMS = len(EVALUATION_ITEMS)

# --- Route Definitions ---

# This will now handle all routes, including API calls
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    # This is a simple router inside Flask
    
    # --- API Routes ---
    if path == "api/get_new_user_id":
        if not supabase:
            return jsonify({'error': 'Supabase client not initialized'}), 500
        try:
            response = supabase.rpc('get_next_user_id', {}).execute()
            if response.data:
                return jsonify({'user_id': response.data})
            else:
                raise Exception(getattr(response, 'error', 'Unknown RPC error'))
        except Exception as e:
            print(f"Error calling Supabase RPC: {e}")
            return jsonify({'error': 'Could not generate user ID'}), 500

    # --- Page Routes ---
    elif path == "" or path == "evaluate/0":
        item_id = 0
        if not 0 <= item_id < TOTAL_ITEMS: return "No items found", 404
        item = EVALUATION_ITEMS[item_id]
        next_id = item_id + 1 if (item_id + 1) < TOTAL_ITEMS else None
        return render_template('index.html', item=item, item_id=item_id, total_items=TOTAL_ITEMS, previous_id=None, next_id=next_id)

    elif path.startswith('evaluate/'):
        try:
            item_id = int(path.split('/')[-1])
            if not 0 <= item_id < TOTAL_ITEMS: return redirect(url_for('catch_all', path=''))
            item = EVALUATION_ITEMS[item_id]
            previous_id = item_id - 1 if item_id > 0 else None
            next_id = item_id + 1 if item_id < TOTAL_ITEMS - 1 else None
            return render_template('index.html', item=item, item_id=item_id, total_items=TOTAL_ITEMS, previous_id=previous_id, next_id=next_id)
        except (ValueError, IndexError):
            return "Invalid item ID.", 404
            
    elif path == "complete":
        return render_template('complete.html')
        
    # If no route matches, return a 404
    return "Not Found", 404

@app.route('/api/submit', methods=['POST'])
def submit():
    if not supabase:
        return "Error: Supabase client not initialized.", 500
    try:
        form_data = request.form.to_dict()
        data_to_insert = {
            'session_identifier': int(form_data.get('session_identifier')),
            'eval_id': form_data.get('eval_id'), 'item_class': form_data.get('item_class'),
            'item_metric': form_data.get('item_metric'), 'item_case': form_data.get('item_case'),
            'comparative_rating': form_data.get('comparative_rating'),
            'test_rating': int(form_data.get('test_rating')),
            'comparison_rating': int(form_data.get('comparison_rating')),
            'comments': form_data.get('comments', '').strip()
        }
        response = supabase.table('evaluations').insert(data_to_insert).execute()
        if len(response.data) == 0 and response.error:
             raise Exception(response.error.message)
        print("Successfully inserted a row into Supabase.")
    except Exception as e:
        print(f"A REAL error occurred while saving to Supabase: {e}")
        traceback.print_exc()
        return "An error occurred while saving your evaluation.", 500

    next_id_str = form_data.get('next_item_id')
    if next_id_str and next_id_str != 'None':
        # Use url_for with the 'catch_all' function name and the correct path
        return redirect(url_for('catch_all', path=f'evaluate/{next_id_str}'))
    else:
        return redirect(url_for('catch_all', path='complete'))