import os
import shutil
import git
import fnmatch
import stat

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
        git.Repo.clone_from(url, dest_path, depth=1)
        print("Cloning complete.")
    except git.exc.GitCommandError as e:
        print(f"Error cloning repo: {e}")
        raise # Re-raise the exception to be handled by the caller

def get_code_files(repo_path):
    """
    Walks through a repository and returns a list of file paths to analyze.
    Filters out directories, large files, and specific file extensions.
    """
    code_files = []
    
    # Configuration for filtering
    ignored_dirs = [
        # Version Control
        '.git', '.svn', '.hg', '.bzr',
        # Dependencies
        'node_modules', 'venv', 'env', '.venv', '.env', 'virtualenv', 'venv.bak',
        # Python
        '__pycache__', '*.egg-info', '*.egg', 'dist', 'build', '.pytest_cache', '.mypy_cache',
        # IDE/Editor
        '.idea', '.vscode', '.vs', '.sublime', '.atom', '.eclipse', '.settings',
        # Build/Compile
        'target', 'out', 'build', 'dist', 'bin', 'obj', '.gradle', '.mvn',
        # Cache/Logs
        'logs', 'log', 'cache', '.cache', 'tmp', 'temp',
        # Documentation
        'docs', 'documentation', 'doc',
        # Test Coverage
        'coverage', '.coverage', 'htmlcov',
        # Misc
        '.DS_Store', 'Thumbs.db', 'node_modules', 'bower_components', 'jspm_packages'
    ]
    ignored_exts = [
        # Binary/Compiled Files
        '.exe', '.dll', '.so', '.dylib', '.o', '.obj', '.pyc', '.pyo', '.pyd',
        # Build/Dependency Files
        '.egg', '.whl', '.tar.gz', '.tar.bz2', '.tgz', '.tbz', '.tar.xz', '.txz',
        # Development/IDE Files
        '.swp', '.swo', '.bak', '.tmp',
        # Documentation/Media
        '.lock', '.log', '.svg', '.png', '.jpg', '.jpeg', '.ico', '.gif', '.pdf', '.zip',
        '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.mp3', '.mp4', '.avi', '.mov', '.wav',
        # Environment/Configuration
        '.env', '.ini', '.cfg', '.yml', '.yaml',
        # Database Files
        '.db', '.sqlite', '.sqlite3', '.mdb', '.accdb',
        # Cache/Log Files
        '.cache', '.temp',
        # Font Files
        '.ttf', '.otf', '.woff', '.woff2', '.eot',
        # ML/AI Files
        '.safetensors', '.pt', '.pth', '.h5', '.hdf5', '.onnx', '.pb', '.tflite', '.mlmodel'
    ]
    max_file_size_kb = 1000

    print("Scanning for code files to analyze...")
    
    def should_ignore_dir(dirname):
        """Check if a directory should be ignored using pattern matching."""
        # Check exact matches first
        if dirname in ignored_dirs:
            return True
        # Check pattern matches
        return any(fnmatch.fnmatch(dirname, pattern) for pattern in ignored_dirs if '*' in pattern)

    def is_text_file(filepath):
        """Check if a file is likely to be a text file."""
        try:
            with open(filepath, 'rb') as f:
                # Read first 1024 bytes
                chunk = f.read(1024)
                # Check if it contains null bytes
                if b'\x00' in chunk:
                    return False
                # Try to decode as text
                chunk.decode('utf-8')
                return True
        except (UnicodeDecodeError, IOError):
            return False

    for root, dirs, files in os.walk(repo_path, followlinks=False):
        # Filter out ignored directories using pattern matching
        dirs[:] = [d for d in dirs if not should_ignore_dir(d)]

        for file in files:
            # Skip hidden files unless explicitly allowed
            if file.startswith('.') and file not in ['.gitignore', '.env.example']:
                continue

            # Check for ignored extensions
            if any(file.endswith(ext) for ext in ignored_exts):
                continue
            
            file_path = os.path.join(root, file)

            # Skip if it's a symlink
            if os.path.islink(file_path):
                continue

            # Check file size
            try:
                if os.path.getsize(file_path) > max_file_size_kb * 1024:
                    print(f"Skipping large file: {file_path}")
                    continue
                
                # Skip binary files
                if not is_text_file(file_path):
                    print(f"Skipping binary file: {file_path}")
                    continue

            except OSError as e:
                print(f"Error accessing file {file_path}: {e}")
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

def safe_remove_dir(path: str) -> None:
    """
    Safely remove a directory, handling Windows permission errors for .git directories.
    """
    if not os.path.exists(path):
        return

    try:
        # First try normal removal
        shutil.rmtree(path)
    except PermissionError as e:
        if '.git' in path:
            print(f"Attempting to force remove .git directory: {path}")
            try:
                # On Windows, we need to remove read-only attributes first
                for root, dirs, files in os.walk(path):
                    for dir in dirs:
                        os.chmod(os.path.join(root, dir), 0o777)
                    for file in files:
                        os.chmod(os.path.join(root, file), 0o777)
                # Try removal again
                shutil.rmtree(path, ignore_errors=True)
            except Exception as e:
                print(f"Warning: Could not fully remove {path}: {e}")
                # Continue execution even if cleanup fails
        else:
            print(f"Warning: Could not remove {path}: {e}")
            # Continue execution even if cleanup fails

def cleanup_old_jobs():
    """
    Clean up any leftover files from previous jobs.
    Removes old zip files, output directories, and temp repositories.
    """
    print("Cleaning up old job files...")
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Clean up old zip files
    for file in os.listdir(current_dir):
        if file.startswith("documentation_") and file.endswith(".zip"):
            try:
                os.remove(os.path.join(current_dir, file))
                print(f"Removed old zip file: {file}")
            except Exception as e:
                print(f"Warning: Could not remove old zip file {file}: {e}")
    
    # Clean up old output and temp directories
    for item in os.listdir(current_dir):
        if (item.startswith("output_repo_") or item.startswith("temp_repo_")) and os.path.isdir(os.path.join(current_dir, item)):
            try:
                safe_remove_dir(os.path.join(current_dir, item))
                print(f"Removed old directory: {item}")
            except Exception as e:
                print(f"Warning: Could not remove old directory {item}: {e}")

def run_analysis_job(repo_url, job_id):
    """
    The main orchestrator function.
    Takes a repo URL and a job ID, performs the full analysis,
    and returns the path to the final zip file.
    """
    # Clean up any old job files before starting
    cleanup_old_jobs()
    
    repo_path = f"./temp_repo_{job_id}"
    output_path = f"./output_repo_{job_id}"
    zip_filename = f"documentation_{job_id}"
    
    try:
        # Phase 1: Clone & Filter
        clone_repo(repo_url, repo_path)
        files_to_analyze = get_code_files(repo_path)
        
        # If no files found, exit gracefully
        if not files_to_analyze:
            print("No suitable files found to analyze.")
            return None

        # Phase 2: Process each file and generate explanations
        if os.path.exists(output_path):
            shutil.rmtree(output_path) # Clean up previous output

        individual_summaries = {}
        for file_path in files_to_analyze:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception as e:
                print(f"Could not read file {file_path}: {e}")
                continue
            
            # --- This is where we call Person C's function ---
            explanation = generate_file_explanation(content, file_path)
            
            # Create the mirrored directory structure in the output folder
            relative_path = os.path.relpath(file_path, repo_path)
            output_file_path = os.path.join(output_path, relative_path)
            os.makedirs(os.path.dirname(output_file_path), exist_ok=True)
            
            # Save the explanation as a Markdown file (e.g., helpers.py -> helpers.md)
            base, _ = os.path.splitext(output_file_path)
            with open(base + ".md", 'w', encoding='utf-8') as f:
                f.write(explanation)
            
            # Store the first line of the explanation for the final summary
            first_line = explanation.split('\n')[0]
            individual_summaries[relative_path] = first_line

        # Phase 3: Generate the final project overview
        # --- This is the second call to Person C's functions ---
        overview_content = generate_project_overview("DUMMY_TREE", individual_summaries)
        with open(os.path.join(output_path, "_PROJECT_OVERVIEW.md"), 'w', encoding='utf-8') as f:
            f.write(overview_content)
            
        # Phase 4: Zip the final output folder
        print("Zipping the final documentation...")
        final_zip_path = shutil.make_archive(zip_filename, 'zip', output_path)
        print(f"Successfully created zip file: {final_zip_path}")

        return final_zip_path

    finally:
        # Phase 5: Cleanup - VERY IMPORTANT
        print("Cleaning up temporary files...")
        try:
            safe_remove_dir(repo_path)
            safe_remove_dir(output_path)
        except Exception as e:
            print(f"Warning: Error during cleanup: {e}")
            # Continue execution even if cleanup fails
        print("Cleanup complete.")

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