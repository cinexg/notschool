import os
from dotenv import load_dotenv

# Load variables from the .env file into the system environment
load_dotenv()

def validate_environment():
    """
    Validates that all necessary API keys are present.
    Run this when the application initializes.
    """
    missing_keys = []
    
    if not os.getenv("GEMINI_API_KEY"):
        missing_keys.append("GEMINI_API_KEY")
        
    if not os.getenv("YOUTUBE_API_KEY"):
        missing_keys.append("YOUTUBE_API_KEY")

    if missing_keys:
        raise ValueError(f"Missing critical environment variables: {', '.join(missing_keys)}. Please update your .env file.")

# Run validation immediately upon import
validate_environment()