import os
import uuid
import threading
from flask import Flask, request, redirect, url_for, jsonify, render_template, send_from_directory
from flask import after_this_request 
import shutil

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

def cleanup_job_files(job_id):
    """Safely removes all temporary files and the final zip for a given job."""
    print(f"Cleaning up files for completed job: {job_id}")
    try:
        # Define all paths associated with this specific job
        repo_path = f"./temp_repo_{job_id}"
        output_path = f"./output_repo_{job_id}"
        zip_filename = f"documentation_{job_id}.zip"

        # shutil.rmtree with ignore_errors is robust enough to handle the
        # lingering .git file lock issue without crashing the app.
        if os.path.exists(repo_path):
            shutil.rmtree(repo_path, ignore_errors=True)
            print(f"Removed temp repo: {repo_path}")
        
        if os.path.exists(output_path):
            shutil.rmtree(output_path, ignore_errors=True)
            print(f"Removed output repo: {output_path}")

        # Finally, delete the zip file itself
        if os.path.exists(zip_filename):
            os.remove(zip_filename)
            print(f"Removed zip file: {zip_filename}")
            
    except Exception as e:
        # Log any errors but don't crash the server
        print(f"Warning: A non-critical error occurred during cleanup for job {job_id}: {e}")

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
    """Serves the generated zip file and then triggers cleanup."""
    # We must extract the job_id from the filename to know what to clean up.
    # Assumes filename format is 'documentation_some-uuid-string.zip'
    try:
        job_id = filename.split('_')[1].replace('.zip', '')
        
        # This is a special Flask decorator that schedules a function
        # to run AFTER the current request has been fully sent to the user.
        @after_this_request
        def trigger_cleanup(response):
            # The background thread will run this function after the download is complete
            cleanup_thread = threading.Thread(target=cleanup_job_files, args=(job_id,))
            cleanup_thread.start()
            return response

    except IndexError:
        print(f"Warning: Could not parse job_id from filename {filename} for cleanup.")
        pass

    print(f"Serving file: {filename}")
    # Use the absolute path for robustness
    directory = os.path.abspath('.')
    return send_from_directory(directory, filename, as_attachment=True)