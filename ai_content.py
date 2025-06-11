import os
import google.generativeai as genai
from dotenv import load_dotenv

# --- Initialization ---
# Load environment variables from .env file
load_dotenv()

# Configure the Gemini API client
try:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in .env file.")
    genai.configure(api_key=api_key)
    
    # Create the model instance
    # We use 'gemini-1.5-flash' for its speed and large context window.
    model = genai.GenerativeModel('gemini-1.5-flash')
    print("Gemini AI Content Generator Initialized Successfully.")

except Exception as e:
    print(f"Error initializing Gemini AI: {e}")
    # If the AI fails to init, we create a dummy model that returns errors
    # This prevents the whole application from crashing if the API key is missing.
    class DummyModel:
        def generate_content(self, *args, **kwargs):
            return "ERROR: Gemini AI Client failed to initialize. Check your API key."
    model = DummyModel()


# --- Real AI Functions (will be populated next) ---

def generate_file_explanation(file_content, file_path):
    """
    Analyzes a single code file using the Gemini AI and returns a
    Markdown-formatted explanation.
    """
    filename = os.path.basename(file_path)
    print(f"REAL AI: Generating explanation for {filename}...")

    # This is the prompt. It's carefully structured to guide the AI.
    prompt = f"""
    You are an expert software developer and a skilled technical writer acting as an onboarding assistant for a new developer.
    Your task is to provide a clear, concise, and beginner-friendly explanation for a given code file.

    The file is located at the path: `{file_path}`
    The content of the file is:
    ```
    {file_content}
    ```

    Please generate documentation in Markdown format that includes the following sections:

    ### 1. File Overview
    Start with a one-paragraph summary of the file's primary purpose and its role within the larger project. What problem does this file solve?

    ### 2. Key Components
    Identify and describe the key functions, classes, or variables in this file. For each component, explain:
    - **What it is:** (e.g., A function named `calculate_total`, a class named `UserSession`).
    - **What it does:** (e.g., "This function takes a list of items and returns their total price.").
    - **How it might be used:** (e.g., "It's likely called by the main application logic when a user checks out.").
    Use bullet points for this section.

    ### 3. Dependencies and Interactions
    Based on the code (e.g., `import` statements or function calls), explain how this file interacts with other parts of the project or external libraries.
    - Mention any important imported modules (e.g., "This file depends on the `Flask` library for web server functionality.").
    - Speculate on which other files in the project might use this one (e.g., "The functions in this file are likely imported and used by `app.py` to handle user requests.").

    ### 4. Final Summary
    Conclude with a brief, high-level summary to reinforce the file's purpose.

    Keep the tone helpful and educational. Assume the reader is a competent developer but is completely new to this specific codebase.
    """

    try:
        # Make the actual API call
        response = model.generate_content(prompt)
        # Prepend a title to the AI's response
        return f"# Explanation for `{filename}`\n\n" + response.text
    except Exception as e:
        print(f"Error generating content for {filename}: {e}")
        # Return a helpful error message to be included in the documentation
        return f"# Error Analyzing `{filename}`\n\nAn error occurred while communicating with the AI model: {e}"


def generate_project_overview(file_tree_str, individual_summaries):
    """
    Analyzes the entire project structure and file summaries to generate a
    high-level overview.
    """
    print("REAL AI: Generating project overview...")

    # Convert the summaries dictionary into a more readable string format
    summaries_text = "\n".join(
        [f"- `{path}`: {summary.replace('# Explanation for', '').strip()}" for path, summary in individual_summaries.items()]
    )

    prompt = f"""
    You are a Principal Software Architect preparing an onboarding document for new developers.
    Your task is to provide a high-level architectural overview of a software project.

    You have been provided with two pieces of information:
    1. The complete file tree of the project.
    2. A one-line summary for each key file.

    **Project File Tree:**
    ```
    {file_tree_str}
    ```

    **Individual File Summaries:**
    ```
    {summaries_text}
    ```

    ---

    Please generate a comprehensive, high-level `README.md`-style overview in Markdown format. Your overview should include the following sections:

    ### 1. Project Purpose and High-Level Description
    Start with a paragraph explaining what this project likely does based on the file names and summaries. What is its main goal? (e.g., "This project appears to be a Flask web application that provides...").

    ### 2. Architectural Pattern
    Analyze the folder structure (e.g., `src`, `tests`, `docs`) and file names. Describe the likely architectural pattern. Is it a simple script, a web application, a library? Does it seem to follow a pattern like Model-View-Controller (MVC)?

    ### 3. Key Directories and Their Roles
    Using a bulleted list, explain the purpose of the most important directories. For example:
    - **`src/`**: Likely contains the main source code for the application.
    - **`tests/`**: Contains automated tests to ensure the code is working correctly.
    - **`docs/`**: Contains project documentation.

    ### 4. Suggested Onboarding Path
    For a new developer, where should they start looking? Suggest a logical order of files or folders to explore to understand the project. (e.g., "A good starting point would be to look at `setup.py` to understand the dependencies, then move to the main application file in the `src` directory.").

    ### 5. Final Conclusion
    A brief concluding paragraph to wrap up the summary.

    Your tone should be authoritative, clear, and helpful.
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Error generating project overview: {e}")
        return f"# Error Generating Project Overview\n\nAn error occurred while communicating with the AI model: {e}"