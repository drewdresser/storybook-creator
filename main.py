# main.py
import asyncio
import json
import logging
import os
from pathlib import Path
from dotenv import load_dotenv

from core.story_creator import StoryCreator, StoryConfig
from core.utils import setup_logging, ensure_dir_exists

# Setup logging as early as possible
logger = setup_logging()


def load_story_config(config_path: Path = Path("story_config.json")) -> StoryConfig:
    """Loads story configuration from JSON file."""
    if not config_path.exists():
        logger.error(f"Configuration file not found: {config_path}")
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    try:
        with open(config_path, "r") as f:
            config_data = json.load(f)
        # Validate using Pydantic
        config = StoryConfig(**config_data)
        logger.info(f"Loaded story configuration from {config_path}")
        return config
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from {config_path}: {e}")
        raise
    except Exception as e:  # Catch Pydantic validation errors etc.
        logger.error(f"Error loading or validating configuration: {e}")
        raise


async def run_creation():
    """Loads config, credentials and runs the story creation process."""
    # Load environment variables (API Keys)
    load_dotenv()
    credentials = {
        "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY"),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
    }

    # Basic check for keys
    if not credentials["GEMINI_API_KEY"] or not credentials["OPENAI_API_KEY"]:
        logger.error("API keys for Gemini or OpenAI not found in .env file.")
        print(
            "\nERROR: Missing API keys in .env file. Please ensure GEMINI_API_KEY and OPENAI_API_KEY are set."
        )
        return

    # Load Story Configuration
    try:
        story_config = load_story_config()
    except Exception:
        return  # Error already logged

    # Define output directory
    output_dir = Path("./output")
    ensure_dir_exists(output_dir)

    # Initialize Story Creator
    try:
        creator = StoryCreator(
            config=story_config, credentials=credentials, output_base_dir=output_dir
        )
    except Exception:
        logger.error(
            "Failed to initialize StoryCreator. Check API keys and configurations."
        )
        return  # Error already logged

    # Create the Book
    logger.info("Starting book creation process...")
    try:
        book = await creator.create_book()
        logger.info(f"Successfully created book: '{book.title}'")
        print(f"\nSuccess! Book '{book.title}' generated in folder: {book.output_dir}")
        print("Each page image and the full story text/manifest are saved there.")

    except Exception as e:
        logger.exception("An error occurred during book creation.")
        print(f"\nERROR: Book creation failed. Check logs for details. Error: {e}")


if __name__ == "__main__":
    # Use asyncio.run for the async main function
    try:
        asyncio.run(run_creation())
    except KeyboardInterrupt:
        logger.info("Process interrupted by user.")
        print("\nProcess stopped.")
