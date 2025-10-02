import os
import json
from flask import Flask, render_template, request, redirect, url_for
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- FLASK APP INITIALIZATION ---
# This part stays the same
app = Flask(__name__, static_folder='../static', template_folder='../templates')

# --- GOOGLE SHEETS AUTHENTICATION ---
# This function sets up the connection to Google Sheets
def get_sheets_client():
    try:
        # Vercel reads the env variable as a string, so we need to parse it as JSON
        creds_json = os.environ.get('GOOGLE_SHEETS_CREDENTIALS')
        creds_dict = json.loads(creds_json)
        
        # Define the scope
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        
        # Authorize the credentials
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        # This will print the error to your Vercel logs
        print(f"Error authenticating with Google Sheets: {e}")
        return None

# --- YOUR EXISTING ROUTE FOR DISPLAYING THE PAGE ---
# This route now also handles different item IDs
@app.route('/')
@app.route('/evaluate/<int:item_id>')
def evaluate_item(item_id=0):
    # --- IMPORTANT ---
    # Replace this with your actual logic to load data for item_id
    # For example, read from a pandas DataFrame or list
    
    # Dummy data for demonstration
    all_items = [
        {'eval_id': 'CC-AHIQ-Q1', 'web_path': 'your-image.jpg', 'class': 'A', 'metric': 'PSNR', 'case': '1'},
        {'eval_id': 'CC-AHIQ-Q2', 'web_path': 'your-image.jpg', 'class': 'B', 'metric': 'SSIM', 'case': '2'},
        # ... add all your other items here
    ]
    total_items = len(all_items)
    
    # Basic navigation logic
    current_item = all_items[item_id] if item_id < total_items else all_items[0]
    next_id = item_id + 1 if (item_id + 1) < total_items else None
    previous_id = item_id - 1 if item_id > 0 else None

    return render_template(
        'index.html',
        item=current_item,
        item_id=item_id,
        total_items=total_items,
        next_id=next_id,
        previous_id=previous_id
    )

# --- NEW ROUTE TO HANDLE FORM SUBMISSION ---
@app.route('/submit', methods=['POST'])
def submit_evaluation():
    try:
        # 1. Get all the data from the form
        form_data = request.form
        
        # 2. Connect to Google Sheets
        client = get_sheets_client()
        if not client:
            return "Could not connect to Google Sheets. Check server logs.", 500
            
        sheet = client.open("Image Evaluations").sheet1 # Opens the first sheet by name

        # 3. Prepare the new row in the correct order
        # Make sure this order EXACTLY matches your headers in the Google Sheet
        new_row = [
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            form_data.get('eval_id'),
            form_data.get('item_class'),
            form_data.get('item_metric'),
            form_data.get('item_case'),
            form_data.get('comparative_rating'),
            form_data.get('test_rating'),
            form_data.get('comparison_rating'),
            form_data.get('comments')
        ]
        
        # 4. Append the new row to the sheet
        sheet.append_row(new_row)
        
        # 5. Redirect the user to the next item, or a "finish" page
        next_id = form_data.get('next_item_id')
        if next_id:
            # Use url_for to generate the correct URL for the next item
            return redirect(url_for('evaluate_item', item_id=int(next_id)))
        else:
            # You can create a new 'thank_you.html' template for this
            return "<h1>Evaluation Complete! Thank you.</h1>"

    except Exception as e:
        print(f"Error submitting evaluation: {e}")
        return "An error occurred while saving your evaluation.", 500
