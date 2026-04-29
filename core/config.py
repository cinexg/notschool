import os
from dotenv import load_dotenv

# Load variables from the .env file into the system environment
load_dotenv()

def validate_environment():
    """
    Validates that all necessary API keys are present.
    Run this when the application initializes.
    """
    if not os.getenv("GEMINI_API_KEY"):
        raise ValueError("Missing critical environment variable: GEMINI_API_KEY. Please update your .env file.")

    if not os.getenv("YOUTUBE_API_KEY"):
        # Non-fatal: librarian will still run, just without curated videos.
        print("Warning: YOUTUBE_API_KEY not set — video lookups will be skipped.")