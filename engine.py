import os
import shutil
import git
import fnmatch
import stat

def create_file_tree_string(start_path):
    """Generates a string representation of a directory tree."""
    tree_string = ""
    for root, dirs, files in os.walk(start_path):
        # We don't want to show the full path, but the path relative to the start
        level = root.replace(start_path, '').count(os.sep)
        indent = ' ' * 4 * level
        tree_string += f"{indent}{os.path.basename(root)}/\n"
        sub_indent = ' ' * 4 * (level + 1)
        for f in files:
            tree_string += f"{sub_indent}{f}\n"
    return tree_string

def clone_repo(url, dest_path):
    """
    Clones a public GitHub repo to a specified destination path.
    Cleans up the destination path if it already exists.
    """
    if os.path.exists(dest_path):
        print(f"Cleaning up old directory: {dest_path}")
        shutil.rmtree(dest_path)
    
    print(f"Cloning {url} into {dest_path}...")
    try:
        repo = git.Repo.clone_from(url, dest_path, depth=1)
        print("Cloning complete.")
        return repo
    except git.exc.GitCommandError as e:
        print(f"Error cloning repo: {e}")
        raise # Re-raise the exception to be handled by the caller

def should_ignore_dir(dirname, ignored_dirs):
    if dirname in ignored_dirs:
        return True
    return any(fnmatch.fnmatch(dirname, pattern) for pattern in ignored_dirs if '*' in pattern)

def is_text_file(filepath):
    try:
        with open(filepath, 'rb') as f:
            chunk = f.read(1024)
            if b'\x00' in chunk:
                return False
            chunk.decode('utf-8')
            return True
    except (UnicodeDecodeError, IOError):
        return False

# --- Your new and improved get_code_files function ---
def get_code_files(repo_path):
    code_files = []
    
    ignored_dirs = [
        '.git', 'node_modules', 'venv', '__pycache__', 'dist', 'build', 
        '.idea', '.vscode', 'target', 'logs', 'docs', '*.egg-info' # Example with wildcard
    ]
    ignored_exts = [
        '.lock', '.log', '.svg', '.png', '.jpg', '.ico', '.gif', '.pdf', '.zip',
        '.exe', '.dll', '.so', '.pyc', '.env', '.db', '.safetensors', '.pt'
    ]
    ignored_filenames = [
        '__init__.py', 'setup.py', 'manage.py', 'config.py',
        'requirements.txt', 'package.json', 'Dockerfile', '.gitignore', 'LICENSE'
    ]
    max_file_size_kb = 100

    print("Scanning for code files to analyze...")
    for root, dirs, files in os.walk(repo_path, followlinks=False):
        dirs[:] = [d for d in dirs if not should_ignore_dir(d, ignored_dirs)]

        for file in files:
            if file in ignored_filenames or (file.startswith('.') and file not in ['.gitignore']):
                continue
            if file.startswith('test_') or file.endswith('_test.py'):
                continue
            if any(file.endswith(ext) for ext in ignored_exts):
                continue
            
            file_path = os.path.join(root, file)
            if os.path.islink(file_path):
                continue

            try:
                if os.path.getsize(file_path) > max_file_size_kb * 1024:
                    print(f"Skipping large file: {os.path.basename(file_path)}")
                    continue
                if not is_text_file(file_path):
                    print(f"Skipping binary file: {os.path.basename(file_path)}")
                    continue
            except OSError:
                continue

            code_files.append(file_path)
            
    print(f"Found {len(code_files)} files to analyze.")
    return code_files

from ai_content import generate_file_explanation, generate_project_overview

def on_rm_error(func, path, exc_info):
    """
    Error handler for shutil.rmtree.
    If the error is due to an access error (read only file)
    it attempts to add write permission and then retries.
    If the error is for another reason it re-raises the error.
    """
    # path contains the path of the file that couldn't be removed
    # func is the function that failed
    # exc_info is a tuple of the exception info
    if not os.access(path, os.W_OK):
        # Is the error an access error?
        os.chmod(path, stat.S_IWUSR)
        func(path)
    else:
        raise





def run_analysis_job(repo_url, job_id):
    """
    The main orchestrator function.
    Takes a repo URL and a job ID, performs the full analysis,
    and returns the path to the final zip file.
    """
    repo_path = f"./temp_repo_{job_id}"
    output_path = f"./output_repo_{job_id}"
    zip_filename = f"documentation_{job_id}"
    
    repo = None  # <-- NEW: Initialize repo variable to ensure it exists for the 'finally' block
    try:
        # Phase 1: Clone & Filter
        repo = clone_repo(repo_url, repo_path)  # <-- MODIFIED: Capture the repo object
        files_to_analyze = get_code_files(repo_path)
        
        # If no files found, exit gracefully
        if not files_to_analyze:
            print("No suitable files found to analyze.")
            return None

        # Phase 2: Process each file and generate explanations
        if os.path.exists(output_path):
            shutil.rmtree(output_path)

        individual_summaries = {}
        for file_path in files_to_analyze:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception as e:
                print(f"Could not read file {file_path}: {e}")
                continue
            
            explanation = generate_file_explanation(content, file_path)
            
            relative_path = os.path.relpath(file_path, repo_path)
            output_file_path = os.path.join(output_path, relative_path)
            os.makedirs(os.path.dirname(output_file_path), exist_ok=True)
            
            base, _ = os.path.splitext(output_file_path)
            with open(base + ".md", 'w', encoding='utf-8') as f:
                f.write(explanation)
            
            first_line = explanation.split('\n')[0]
            individual_summaries[relative_path] = first_line

        # Phase 3: Generate the final project overview
        print("Generating final project overview...")
        # Note: I moved this loop outside the main file processing loop. It should only run once.
        file_tree = create_file_tree_string(output_path)
        overview_content = generate_project_overview(file_tree, individual_summaries)
        with open(os.path.join(output_path, "_PROJECT_OVERVIEW.md"), 'w', encoding='utf-8') as f:
            f.write(overview_content)
            
        # Phase 4: Zip the final output folder
        print("Zipping the final documentation...")
        final_zip_path = shutil.make_archive(zip_filename, 'zip', output_path)
        print(f"Successfully created zip file: {final_zip_path}")

        return final_zip_path
        
    finally:
        # <-- NEW: This block now guarantees the repo lock is released
        # This is the crucial fix for the empty folder issue.
        if repo:
            repo.close()
            print(f"Git repo object for job {job_id} closed.")


# This block allows us to test the engine directly
if __name__ == "__main__":
    print("--- Running Engine Test ---")
    # A small, simple repo is best for testing
    test_repo_url = "https://github.com/pallets-eco/flask-sqlalchemy"
    test_job_id = "local_test"
    
    zip_file = run_analysis_job(test_repo_url, test_job_id)
    
    if zip_file:
        print(f"\n--- TEST COMPLETE ---")
        print(f"Final zip file is located at: {os.path.abspath(zip_file)}")
    else:
        print(f"\n--- TEST FAILED ---")