import os
import uuid
import threading
from flask import Flask, request, redirect, url_for, jsonify, render_template, send_from_directory

# --- This is the crucial import from your own work ---
from engine import run_analysis_job

# Initialize the Flask application
app = Flask(__name__)

# This simple dictionary will act as our in-memory "database" for job statuses.
# In a real production app, you might use a database like Redis or a more robust queue.
jobs = {} 

@app.route("/")
def index():
    """
    Renders the main landing page.
    For now, we'll create a super simple placeholder HTML.
    """
    return render_template('index.html')

@app.route("/generate", methods=['POST'])
def generate():
    """
    This endpoint is called when the user submits the form.
    It starts the background job and redirects to the status page.
    """
    repo_url = request.form.get('url')
    if not repo_url:
        return "URL is required", 400

    job_id = str(uuid.uuid4())
    
    # --- This is where we start the background job ---
    # We pass the job_id and repo_url to our target function.
    thread = threading.Thread(target=run_analysis_job_wrapper, args=(job_id, repo_url))
    thread.start()
    
    # Immediately redirect the user so their browser doesn't wait and time out
    return redirect(url_for('status', job_id=job_id))

def run_analysis_job_wrapper(job_id, repo_url):
    """
    A wrapper function that runs our main job and updates the status.
    This is what the background thread will execute.
    """
    jobs[job_id] = {'status': 'PROCESSING', 'download_url': None}
    print(f"Starting job {job_id} for URL: {repo_url}")
    
    try:
        # --- This calls your tested engine code ---
        zip_file_path = run_analysis_job(repo_url, job_id)
        
        if zip_file_path:
            # Job succeeded
            jobs[job_id]['status'] = 'COMPLETE'
            # Create a URL the user can use to download the file
            jobs[job_id]['download_url'] = f"/download/{os.path.basename(zip_file_path)}"
            print(f"Job {job_id} completed successfully.")
        else:
            # Job failed gracefully (e.g., no files found)
            jobs[job_id]['status'] = 'FAILED'
            jobs[job_id]['error_message'] = 'No suitable files were found to analyze in the repository.'
            print(f"Job {job_id} failed: No files to analyze.")

    except Exception as e:
        # Job failed with an unexpected error
        print(f"Job {job_id} failed with an error: {e}")
        jobs[job_id]['status'] = 'FAILED'
        jobs[job_id]['error_message'] = str(e)


@app.route("/status/<job_id>")
def status(job_id):
    return render_template('status.html', job_id=job_id)

# --- This is the API endpoint that Person B's JavaScript will call ---
@app.route("/api/status/<job_id>")
def api_status(job_id):
    """Provides the status of a job in JSON format."""
    job = jobs.get(job_id)
    if not job:
        return jsonify({'status': 'NOT_FOUND'}), 404
    return jsonify(job)

@app.route("/download/<filename>")
def download(filename):
    """Serves the generated zip file for download."""
    print(f"Serving file: {filename}")
    # We need to provide the directory where the zip files are stored.
    # Since they are created in the root of our project, we use '.'
    return send_from_directory('.', filename, as_attachment=True)