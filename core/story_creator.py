# core/story_creator.py
import asyncio
from datetime import datetime
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional

import google.generativeai as genai
from pydantic import BaseModel, Field

from .image_generator import ImageGeneratorFactory, ImageGenerator, GPTImageGenerator
from .utils import sanitize_filename, ensure_dir_exists

logger = logging.getLogger(__name__)


# --- Pydantic Models for Configuration ---
class Character(BaseModel):
    name: str
    description: str
    image_path: Optional[str] = None


class Location(BaseModel):
    setting: str
    details: List[str] = []


class StoryConfig(BaseModel):
    characters: List[Character]
    theme: str
    age_range: str
    location: Location
    story_length_pages: int = Field(
        default=8, ge=4, le=20
    )  # Sensible default and limits
    image_style: str


# --- Dataclasses for Story Output ---
@dataclass
class Page:
    page_number: int
    text: str
    image_path: Optional[Path] = None
    image_prompt: Optional[str] = None


@dataclass
class Book:
    title: str
    config: StoryConfig
    full_story: str
    output_dir: Path
    pages: List[Page] = field(default_factory=list)


# --- StoryCreator Class ---
class StoryCreator:
    def __init__(
        self,
        config: StoryConfig,
        credentials: Dict[str, str],
        output_base_dir: Path = Path("./output"),
    ):
        self.config = config
        self.credentials = credentials
        self.output_base_dir = output_base_dir
        self.gemini_model = None
        self.image_generator: Optional[ImageGenerator] = None
        self._setup_clients()

    def _setup_clients(self):
        """Initialize Gemini and Image Generator clients."""
        try:
            if self.credentials.get("GEMINI_API_KEY"):
                genai.configure(api_key=self.credentials["GEMINI_API_KEY"])
                # Use a model suitable for creative writing, like gemini-2.5-pro-preview-03-25
                self.gemini_model = genai.GenerativeModel(
                    "gemini-2.5-pro-preview-03-25"
                )
                logger.info("Gemini client configured.")
            else:
                logger.error("GEMINI_API_KEY not found in credentials.")
                raise ValueError("Missing GEMINI_API_KEY")

            # Setup Image Generator (defaulting to OpenAI for this project)
            # Allow specifying provider via config in future if needed
            img_gen_config = {
                "default_provider": "openai",
                "providers": {
                    "openai": {"model": "gpt-image-1"}  # Example, could be configurable
                },
            }
            self.image_generator = ImageGeneratorFactory.create(
                provider=img_gen_config["default_provider"],
                credentials=self.credentials,
                config=img_gen_config,  # Pass the whole config dict
            )
            if not self.image_generator:
                logger.error("Failed to initialize Image Generator.")
                raise ValueError("Could not create image generator instance.")

        except Exception as e:
            logger.exception(f"Error setting up AI clients: {e}")
            raise

    async def _generate_story_text(self) -> str:
        """Generates the full story text using Gemini."""
        if not self.gemini_model:
            raise RuntimeError("Gemini model not initialized.")

        char_desc = "\n".join(
            [f"- {c.name}: {c.description}" for c in self.config.characters]
        )
        loc_desc = f"{self.config.location.setting}, featuring {', '.join(self.config.location.details)}."

        prompt = (
            f"Write a children's story suitable for the age range {self.config.age_range}.\n"
            f"Theme: {self.config.theme}\n"
            f"Characters:\n{char_desc}\n"
            f"Location: {loc_desc}\n"
            f"The story should be engaging, positive, and approximately {self.config.story_length_pages} short paragraphs long (each paragraph will be a page).\n"
            f"Ensure the story has a clear beginning, middle, and a gentle resolution or end.\n"
            f"Use simple language appropriate for the age group.\n"
            f"Focus on the interactions between the characters and their environment."
            f"Do NOT include page numbers or explicit page breaks like '[Page X]' in the output. Just write the story text continuously."
        )
        logger.info("Generating story text...")
        try:
            response = await self.gemini_model.generate_content_async(prompt)
            story_text = response.text.strip()
            logger.info("Story text generated successfully.")
            # Basic validation
            if not story_text or len(story_text) < 50:
                raise ValueError("Generated story text is too short or empty.")
            return story_text
        except Exception as e:
            logger.exception(f"Error generating story text: {e}")
            raise

    def _split_story_into_pages(self, full_story: str) -> List[str]:
        """Splits the story into pages based on paragraphs."""
        # Simple split by double newline, filtering empty strings
        paragraphs = [p.strip() for p in full_story.split("\n\n") if p.strip()]

        # If too few paragraphs, split longer ones. If too many, merge short ones.
        # This is a basic approach; a more sophisticated method might use sentence boundaries
        # or even another LLM call to get ideal page breaks.

        target_pages = self.config.story_length_pages
        if len(paragraphs) < target_pages / 2:  # Heuristic: Too few paragraphs
            logger.warning(
                f"Only {len(paragraphs)} paragraphs found. Trying sentence splitting."
            )
            sentences = [
                s.strip() + "."
                for s in full_story.replace("\n", " ").split(".")
                if s.strip()
            ]
            # Rough estimate of sentences per page
            sents_per_page = max(1, len(sentences) // target_pages)
            pages = []
            for i in range(0, len(sentences), sents_per_page):
                pages.append(" ".join(sentences[i : i + sents_per_page]))
            paragraphs = pages[:target_pages]  # Take desired number of pages

        elif len(paragraphs) > target_pages * 1.5:  # Heuristic: Too many paragraphs
            logger.warning(
                f"Found {len(paragraphs)} paragraphs, more than expected. Merging shortest."
            )
            # Basic merging: combine shortest adjacent paragraphs until target length is approached
            # (A more robust implementation would be needed for complex cases)
            while len(paragraphs) > target_pages and len(paragraphs) > 1:
                shortest_idx = min(
                    range(len(paragraphs)), key=lambda i: len(paragraphs[i])
                )
                if shortest_idx > 0:  # Merge with previous if possible
                    paragraphs[shortest_idx - 1] += "\n" + paragraphs.pop(shortest_idx)
                elif len(paragraphs) > 1:  # Merge with next
                    paragraphs[0] += "\n" + paragraphs.pop(1)
                else:  # Cannot merge further
                    break
            paragraphs = paragraphs[:target_pages]  # Trim if still too long

        # Ensure we don't exceed the target page count significantly
        if len(paragraphs) > target_pages:
            paragraphs = paragraphs[:target_pages]

        logger.info(f"Split story into {len(paragraphs)} pages.")
        return paragraphs

    async def _generate_page_image(
        self,
        page_text: str,
        page_number: int,
        book_title: str,
        output_dir: Path,
        page_texts: List[str],
    ) -> Optional[Page]:
        """Generates or edits an image for a single page, using character images if available."""
        if not self.image_generator:
            logger.warning("Image generator not available.")
            # Still return Page object without image info
            return Page(page_number=page_number, text=page_text)

        # Find characters mentioned in the current page text and get their descriptions
        mentioned_chars = [
            c for c in self.config.characters if c.name.lower() in page_text.lower()
        ]
        character_details_str = (
            ", ".join([f"{c.name} ({c.description})" for c in mentioned_chars])
            if mentioned_chars
            else "None mentioned on this page."
        )
        logger.info(
            f"Page {page_number}: Characters mentioned: {character_details_str}"
        )

        character_image_paths = []
        if mentioned_chars:
            # logger.info(f"Page {page_number}: Characters mentioned: {[c.name for c in mentioned_chars]}") # Replaced by above log
            for char in mentioned_chars:
                if char.image_path:
                    img_path = Path(
                        char.image_path
                    )  # Assuming relative path from workspace root
                    if img_path.is_file():
                        character_image_paths.append(img_path)
                        logger.info(f"Found image for {char.name}: {img_path}")
                    else:
                        logger.warning(
                            f"Character image file not found for {char.name} at {img_path}, will generate without it."
                        )

        # Base prompt components - Enhanced with character descriptions
        base_prompt = (
            "You will generate a page for a children's book. I'll give you some metadata, the full text of the book, and the text for this specific page. \n"
            f"Style: {self.config.image_style}. \n    "
            f"Setting: {self.config.location.setting}. Theme: {self.config.theme}. \n"
            f"Age: {self.config.age_range}. Story context: {' '.join(page_texts)}. \n"  # Provide full story context
            f"This specific page shows: {page_text}. \n"
            # f"Characters present or interacting if mentioned: {', '.join(character_names)}. \n" # Use detailed info below
            f"Characters mentioned on this page (use descriptions): {character_details_str}. \n"
            f"Incorporate the page text '{page_text}' visually into the image using the Andika font from Google Fonts, perhaps on a sign, scroll, or subtly in the background."
            # Consider adding negative prompts if needed
        )

        filename = f"page_{page_number:02d}.png"  # Default to png, generator might change suffix
        image_path = output_dir / filename
        generated_path: Optional[Path] = None
        final_image_prompt: str = base_prompt

        # Check if we should use edit or generate
        # Currently only supporting edit for GPTImageGenerator
        if character_image_paths and isinstance(
            self.image_generator, GPTImageGenerator
        ):
            # We have character images and a compatible generator for editing
            # Enhance edit prompt with character descriptions
            edit_prompt = (
                f"{base_prompt} "
                f"Combine the character(s) from the input image(s) into the scene described above, maintaining the overall style. "
                f"Preserve the key characteristics of the characters (as described: {character_details_str}), but make them look like they are naturally part of the scene depicted in the page text."
            )
            final_image_prompt = edit_prompt  # Store the prompt used
            logger.info(
                f"Attempting image edit for page {page_number} using {len(character_image_paths)} character image(s)..."
            )
            generated_path = await self.image_generator.edit(
                prompt=edit_prompt,
                input_image_paths=character_image_paths,
                output_path=image_path,
            )
        else:
            # Generate from scratch (no char images, or generator doesn't support edit)
            # Use the base_prompt which already includes character descriptions
            if character_image_paths:
                logger.warning(
                    f"Character images found for page {page_number}, but image generator type does not support editing. Generating from scratch using descriptions."
                )
            else:
                logger.info(
                    f"Generating new image for page {page_number} from scratch using descriptions..."
                )

            generated_path = await self.image_generator.generate(
                prompt=base_prompt,  # Use the base prompt for generation
                output_path=image_path,
                size="1536x1024",  # Example size for generation
            )

        if generated_path:
            logger.info(
                f"Successfully processed image for page {page_number} at {generated_path}"
            )
            return Page(
                page_number=page_number,
                text=page_text,
                image_path=generated_path,
                image_prompt=final_image_prompt,  # Log the actual prompt used (edit or generate)
            )
        else:
            logger.error(f"Failed to generate or edit image for page {page_number}")
            return Page(
                page_number=page_number,
                text=page_text,
                image_path=None,
                image_prompt=final_image_prompt,  # Log the prompt even on failure
            )

    async def create_book(self) -> Book:
        """Orchestrates the book creation process."""
        # 1. Generate Story Text
        full_story = await self._generate_story_text()
        if not full_story:
            raise RuntimeError("Failed to generate story text.")

        # Attempt to extract a title (simple approach)
        first_sentence = full_story.split(".")[0]
        book_title = (
            sanitize_filename(first_sentence)[:30]
            or f"Story_{self.config.characters[0].name}"
        )
        logger.info(f"Using tentative title: {book_title}")

        # Create output directory for this specific book
        # Add timestamp to book title for uniqueness
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # book_title = f"{timestamp}_{book_title}"
        book_output_dir = self.output_base_dir / timestamp / book_title
        ensure_dir_exists(book_output_dir)

        # 2. Split into Pages
        page_texts = self._split_story_into_pages(full_story)

        # 3. Generate Images for Pages (Concurrently)
        image_tasks = []
        for i, text in enumerate(page_texts):
            page_number = i + 1
            task = self._generate_page_image(
                text, page_number, book_title, book_output_dir, page_texts
            )
            image_tasks.append(task)

        # Wait for all image generation tasks to complete
        generated_pages: List[Optional[Page]] = await asyncio.gather(*image_tasks)

        # Filter out None results (if image generation failed for a page)
        successful_pages = [page for page in generated_pages if page is not None]

        # 4. Assemble Book Object
        book = Book(
            title=book_title,
            config=self.config,
            full_story=full_story,
            pages=successful_pages,
            output_dir=book_output_dir,
        )

        # 5. Save story text and config to the book's directory
        self._save_book_metadata(book)

        logger.info(f"Book '{book.title}' created successfully in {book.output_dir}")
        return book

    def _save_book_metadata(self, book: Book):
        """Saves the story text and config to the book's output directory."""
        try:
            # Save full story text
            story_file = book.output_dir / "story.txt"
            with open(story_file, "w", encoding="utf-8") as f:
                f.write(f"Title: {book.title}\n\n")
                f.write("--- Story Config ---\n")
                f.write(book.config.model_dump_json(indent=2))
                f.write("\n\n--- Full Story Text ---\n")
                f.write(book.full_story)

            # Save page details (text and image prompts) as JSON
            page_data = [
                {
                    "page": p.page_number,
                    "text": p.text,
                    "image_prompt": p.image_prompt,
                    "image_filename": p.image_path.name if p.image_path else None,
                }
                for p in book.pages
            ]
            pages_file = book.output_dir / "pages_manifest.json"
            with open(pages_file, "w", encoding="utf-8") as f:
                json.dump(page_data, f, indent=2)

            logger.info(f"Saved story text and page manifest to {book.output_dir}")

        except Exception as e:
            logger.exception(f"Error saving book metadata: {e}")
