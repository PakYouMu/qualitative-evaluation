import os
import json
from flask import Flask, render_template, request, redirect, url_for
from datetime import datetime
import gspread
from urllib.parse import quote
from oauth2client.service_account import ServiceAccountCredentials

STATIC_IMAGE_FOLDER = 'static/evaluation_images'
CLASS_ABBREVIATIONS = {
    'Copra Cake': 'CC', 'Cracked Corn': 'CORN', 'Feed Wheats': 'FW',
    'Hard Pollard': 'HP', 'Jocky Oats': 'JO', 'Rice Bran': 'RB', 'US Soya': 'SOY'
}

EVALUATION_ITEMS = []

def load_evaluation_items():
    """
    Final version with URL quoting to handle any special characters in filenames.
    """
    print("--- Loading items by building public GitHub Raw URLs ---")
    
    GITHUB_USERNAME = "PakYouMu"
    IMAGE_REPO_NAME = "qualitative-evaluation-images"
    BRANCH_NAME = "main"

    image_folder_path = os.path.join(os.path.dirname(__file__), '..', STATIC_IMAGE_FOLDER)

    if not os.path.isdir(image_folder_path):
        print(f"CRITICAL ERROR: The directory '{STATIC_IMAGE_FOLDER}' was not found in the main repo.")
        return []
        
    image_data = []
    for filename in os.listdir(image_folder_path):
        if filename.lower().endswith(".png"):
            try:
                base_name = filename[:-4]
                class_part, metric_part, case_part = base_name.split('__')
                class_name = class_part.replace('_', ' ')
                
                # --- FINAL FIX: URL-safe quoting of the filename ---
                safe_filename = quote(filename)
                public_url = f"https://raw.githubusercontent.com/{GITHUB_USERNAME}/{IMAGE_REPO_NAME}/refs/heads/{BRANCH_NAME}/static/evaluation_images/{safe_filename}"
                
                image_data.append({
                    "metric": metric_part,
                    "class": class_name,
                    "case": case_part,
                    "web_path": public_url
                })
            except Exception as e:
                print(f"Warning: Could not parse filename '{filename}'. Skipping. Error: {e}")

    image_data.sort(key=lambda x: (x['class'], x['metric'], x['case']))
    
    for i, item in enumerate(image_data):
        class_abbr = CLASS_ABBREVIATIONS.get(item['class'], 'UNK')
        item['eval_id'] = f"{class_abbr}-{item['metric'].upper()}-{item['case']}"
        item['id'] = i

    print(f" -> Successfully built {len(image_data)} public GitHub image URLs.")
    return image_data

def get_sheets_client():
    try:
        creds_json = os.environ.get('GOOGLE_SHEETS_CREDENTIALS')
        if not creds_json:
            print("CRITICAL ERROR: GOOGLE_SHEETS_CREDENTIALS environment variable not found.")
            return None
        creds_dict = json.loads(creds_json)
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        print(f"Error authenticating with Google Sheets: {e}")
        return None

app = Flask(__name__, static_folder='../static', template_folder='../templates')
EVALUATION_ITEMS = load_evaluation_items()

@app.route('/')
@app.route('/evaluate/<int:item_id>')
def evaluate_item(item_id=0):
    if not EVALUATION_ITEMS:
        return "Error: No evaluation items were loaded. Please check the server logs.", 500
    if item_id < 0 or item_id >= len(EVALUATION_ITEMS):
        return redirect(url_for('complete'))
    item = EVALUATION_ITEMS[item_id]
    total_items = len(EVALUATION_ITEMS)
    previous_id = item_id - 1 if item_id > 0 else None
    next_id = item_id + 1 if item_id < total_items - 1 else None
    return render_template(
        'index.html', item=item, item_id=item_id, total_items=total_items,
        previous_id=previous_id, next_id=next_id
    )

@app.route('/submit', methods=['POST'])
def submit_evaluation():
    form_data = request.form
    next_item_id_str = form_data.get('next_item_id')

    try:
        client = get_sheets_client()
        if not client:
            print("Submit Error: Could not get Google Sheets client.")
            return "Could not connect to Google Sheets. Check server logs.", 500
        
        sheet = client.open("Image Evaluations").sheet1
        new_row = [
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            form_data.get('eval_id'), form_data.get('item_class'), 
            form_data.get('item_metric'), form_data.get('item_case'),
            form_data.get('comparative_rating'), form_data.get('test_rating'),
            form_data.get('comparison_rating'), form_data.get('comments', '').strip()
        ]
        
        # --- DEBUGGING STEP ---
        # We will capture the response and print it to the logs.
        response = sheet.append_row(new_row)
        print(f"DEBUG: gspread response type: {type(response)}")
        print(f"DEBUG: gspread response value: {response}")
        # --- END OF DEBUGGING STEP ---

        # The rest of the logic remains for now.
        if next_item_id_str:
            return redirect(url_for('evaluate_item', item_id=int(next_item_id_str)))
        else:
            return redirect(url_for('complete'))

    except Exception as e:
        # This will still catch the error, but our print statements will run first.
        print(f"A specific error occurred while saving to Google Sheets: {e}")
        return "An error occurred while saving your evaluation. Please check the server logs.", 500

@app.route('/complete')
def complete():
    return "<h1>Evaluation Complete!</h1><p>Thank you for your time. You can now close this window.</p>"