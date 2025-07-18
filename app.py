import os
import uuid
import threading
from flask import Flask, request, redirect, url_for, jsonify, render_template, send_from_directory
from flask import after_this_request
import shutil
import platform
import subprocess
from google.cloud import datastore

# --- This is the crucial import from your own work ---
from engine import run_analysis_job

# Initialize the Flask application
app = Flask(__name__)

# Initialize the Google Cloud Datastore client
# This will use the project defined in your GOOGLE_CLOUD_PROJECT environment variable
datastore_client = datastore.Client()


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

    # --- Create a record in Datastore to track the job ---
    kind = 'Job'
    key = datastore_client.key(kind, job_id)
    job_entity = datastore.Entity(key=key)
    job_entity.update({
        'status': 'PENDING',
        'download_url': None,
        'error_message': None
    })
    datastore_client.put(job_entity)

    # --- This is where we start the background job ---
    # We pass the job_id and repo_url to our target function.
    thread = threading.Thread(target=run_analysis_job_wrapper, args=(job_id, repo_url))
    thread.start()

    # Immediately redirect the user so their browser doesn't wait and time out
    return redirect(url_for('status', job_id=job_id))


def cleanup_job_files(job_id):
    """
    Safely removes all temporary files and the final zip for a given job.
    Uses platform-specific commands for robustness on Windows.
    """
    print(f"Cleaning up files for completed job: {job_id}")

    # Use absolute paths to prevent ambiguity
    current_directory = os.path.abspath('.')
    repo_path = os.path.join(current_directory, f"temp_repo_{job_id}")
    output_path = os.path.join(current_directory, f"output_repo_{job_id}")
    zip_filename = os.path.join(current_directory, f"documentation_{job_id}.zip")

    # --- Robust directory removal ---
    if os.path.exists(repo_path):
        print(f"Attempting to remove temp repo: {repo_path}")
        try:
            if platform.system() == "Windows":
                # On Windows, shutil.rmtree can struggle with .git directories.
                # The native 'rmdir' command is more reliable.
                # /s is for recursive, /q is for quiet mode.
                subprocess.run(f'rmdir /s /q "{repo_path}"', shell=True, check=True)
                print(f"Successfully removed temp repo: {repo_path}")
            else:
                # For other OSes, shutil.rmtree is generally fine.
                shutil.rmtree(repo_path)
                print(f"Successfully removed temp repo: {repo_path}")
        except (subprocess.CalledProcessError, OSError) as e:
            # If even the native commands fail, log the error.
            print(f"ERROR: Failed to remove directory {repo_path}. Error: {e}")
            # As a last resort, try the less reliable method which might clean some files.
            shutil.rmtree(repo_path, ignore_errors=True)

    # Clean up other generated files, which are less likely to have lock issues.
    if os.path.exists(output_path):
        shutil.rmtree(output_path, ignore_errors=True)
        print(f"Removed output repo: {output_path}")

    if os.path.exists(zip_filename):
        try:
            os.remove(zip_filename)
            print(f"Removed zip file: {zip_filename}")
        except OSError as e:
            print(f"Warning: Could not remove zip file {zip_filename}: {e}")


def run_analysis_job_wrapper(job_id, repo_url):
    """
    A wrapper function that runs our main job and updates the status.
    This is what the background thread will execute.
    """
    # --- Update status in Datastore ---
    key = datastore_client.key('Job', job_id)
    job_entity = datastore_client.get(key)
    job_entity['status'] = 'PROCESSING'
    datastore_client.put(job_entity)
    
    print(f"Starting job {job_id} for URL: {repo_url}")
    
    try:
        # --- This calls your tested engine code ---
        # NOTE: We need to adjust the engine to work in a read-only filesystem on App Engine
        zip_file_path = run_analysis_job(repo_url, job_id)
        
        if zip_file_path:
            # Job succeeded
            job_entity['status'] = 'COMPLETE'
            # Create a URL the user can use to download the file
            job_entity['download_url'] = f"/download/{os.path.basename(zip_file_path)}"
            print(f"Job {job_id} completed successfully.")
        else:
            # Job failed gracefully (e.g., no files found)
            job_entity['status'] = 'FAILED'
            job_entity['error_message'] = 'No suitable files were found to analyze in the repository.'
            print(f"Job {job_id} failed: No files to analyze.")

    except Exception as e:
        # Job failed with an unexpected error
        print(f"Job {job_id} failed with an error: {e}")
        job_entity['status'] = 'FAILED'
        job_entity['error_message'] = str(e)
    
    # --- Final update to Datastore ---
    datastore_client.put(job_entity)


@app.route("/status/<job_id>")
def status(job_id):
    return render_template('status.html', job_id=job_id)

# --- This is the API endpoint that Person B's JavaScript will call ---
@app.route("/api/status/<job_id>")
def api_status(job_id):
    """Provides the status of a job in JSON format from Datastore."""
    key = datastore_client.key('Job', job_id)
    job_entity = datastore_client.get(key)
    
    if not job_entity:
        return jsonify({'status': 'NOT_FOUND'}), 404
    
    # The entity itself is a dict-like object, perfect for jsonify
    return jsonify(job_entity)


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