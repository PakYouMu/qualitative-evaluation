# /api/index.py

from flask import Flask, render_template, request, jsonify, redirect, url_for
import os
from supabase import create_client, Client
from urllib.parse import quote
import traceback
import sys

# --- App Initialization ---
app = Flask(__name__, template_folder='../templates', static_folder='../static')

# --- Supabase Initialization ---
def initialize_supabase():
    """Initialize Supabase client with detailed error reporting"""
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    
    print("--- Attempting Supabase initialization ---", file=sys.stderr)
    print(f"SUPABASE_URL present: {bool(SUPABASE_URL)}", file=sys.stderr)
    print(f"SUPABASE_KEY present: {bool(SUPABASE_KEY)}", file=sys.stderr)
    
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("ERROR: Supabase environment variables are missing.", file=sys.stderr)
        return None
    
    try:
        client = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("--- Supabase client initialized successfully ---", file=sys.stderr)
        return client
    except Exception as e:
        print(f"--- FATAL: Error initializing Supabase client: {e} ---", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return None

supabase = initialize_supabase()

# --- Image Data Loading ---
STATIC_IMAGE_FOLDER = 'static/evaluation_images'
CLASS_ABBREVIATIONS = {
    'Copra Cake': 'CC', 'Cracked Corn': 'CORN', 'Feed Wheats': 'FW',
    'Hard Pollard': 'HP', 'Jocky Oats': 'JO', 'Rice Bran': 'RB', 'US Soya': 'SOY'
}
EVALUATION_ITEMS = []

def load_evaluation_items():
    print("--- Loading evaluation items... ---", file=sys.stderr)
    GITHUB_USERNAME = "PakYouMu"
    IMAGE_REPO_NAME = "qualitative-evaluation-images"
    BRANCH_NAME = "main"
    
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
                    public_url = f"https://raw.githubusercontent.com/{GITHUB_USERNAME}/{IMAGE_REPO_NAME}/refs/heads/{BRANCH_NAME}/{STATIC_IMAGE_FOLDER}/{safe_filename}"
                    image_data.append({"metric": metric_part, "class": class_name, "case": case_part, "web_path": public_url})
                except Exception as e:
                    print(f"Warning: Could not parse filename '{filename}'. Skipping. Error: {e}", file=sys.stderr)
    else:
        print(f"CRITICAL WARNING: Local image directory not found at '{image_folder_path}'.", file=sys.stderr)

    for i, item in enumerate(image_data):
        class_abbr = CLASS_ABBREVIATIONS.get(item['class'], 'UNK')
        item['eval_id'] = f"{class_abbr}-{item['metric'].upper()}-{item['case']}"
        item['id'] = i
    print(f" -> Successfully built {len(image_data)} image URLs.", file=sys.stderr)
    return image_data

EVALUATION_ITEMS = load_evaluation_items()
TOTAL_ITEMS = len(EVALUATION_ITEMS)


# --- ROUTE DEFINITIONS ---

@app.route('/')
def home():
    return redirect(url_for('evaluate_item', item_id=0))

@app.route('/evaluate/<int:item_id>')
def evaluate_item(item_id):
    if not 0 <= item_id < TOTAL_ITEMS:
        return redirect(url_for('home'))
    item = EVALUATION_ITEMS[item_id]
    previous_id = item_id - 1 if item_id > 0 else None
    next_id = item_id + 1 if item_id < TOTAL_ITEMS - 1 else None
    return render_template('index.html', item=item, item_id=item_id, total_items=TOTAL_ITEMS, previous_id=previous_id, next_id=next_id)

@app.route('/complete')
def complete():
    return render_template('complete.html')

@app.route('/api/get_new_user_id', methods=['GET'])
def get_new_user_id():
    if not supabase:
        error_msg = 'Supabase client not initialized. Check environment variables.'
        print(f"ERROR in get_new_user_id: {error_msg}", file=sys.stderr)
        return jsonify({'error': error_msg}), 500
    try:
        response = supabase.rpc('get_next_user_id', {}).execute()
        if response.data:
            return jsonify({'user_id': response.data})
        else:
            raise Exception(getattr(response, 'error', 'Unknown RPC error'))
    except Exception as e:
        print(f"Error calling Supabase RPC: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return jsonify({'error': f'Could not generate user ID: {str(e)}'}), 500

# --- MODIFIED SUBMIT FUNCTION ---
@app.route('/api/submit', methods=['POST'])
def submit():
    if not supabase:
        error_msg = "Supabase client not initialized. Please check your environment variables in Vercel."
        print(f"ERROR in submit: {error_msg}", file=sys.stderr)
        return jsonify({'error': error_msg}), 500
    
    try:
        form_data = request.form.to_dict()
        print(f"Received form data: {form_data}", file=sys.stderr)
        
        # Prepare the data dictionary for the upsert operation.
        data_to_upsert = {
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
        
        # --- THIS IS THE KEY CHANGE ---
        # Use .upsert() instead of .insert().
        # 'on_conflict' tells Supabase which columns form the unique key.
        # If a row with this combination exists, it will be updated.
        # If not, a new row will be inserted.
        print(f"Attempting to upsert: {data_to_upsert}", file=sys.stderr)
        response = supabase.table('evaluations').upsert(
            data_to_upsert,
            on_conflict='session_identifier, eval_id'
        ).execute()
        
        # Check for errors from the upsert operation.
        if hasattr(response, 'error') and response.error:
            raise Exception(f"Supabase upsert failed: {response.error.message}")
        
        print("Successfully upserted a row into Supabase.", file=sys.stderr)
        
        # Redirection logic remains the same.
        next_id_str = form_data.get('next_item_id')
        if next_id_str and next_id_str != 'None':
            return redirect(url_for('evaluate_item', item_id=int(next_id_str)))
        else:
            return redirect(url_for('complete'))
            
    except Exception as e:
        error_message = f"Error occurred while saving to Supabase: {str(e)}"
        print(error_message, file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return jsonify({'error': error_message}), 500


# Health check endpoint for debugging
@app.route('/api/health')
def health():
    return jsonify({
        'status': 'ok',
        'supabase_initialized': supabase is not None,
        'has_supabase_url': bool(os.environ.get("SUPABASE_URL")),
        'has_supabase_key': bool(os.environ.get("SUPABASE_SERVICE_ROLE_KEY")),
        'total_items': TOTAL_ITEMS
    })