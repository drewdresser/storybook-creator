# core/image_generator.py
import base64
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Dict, Any

import aiohttp
from openai import AsyncOpenAI  # Using AsyncOpenAI for better performance

logger = logging.getLogger(__name__)


class ImageGenerator(ABC):
    """Abstract base class for image generators."""

    @abstractmethod
    async def generate(
        self, prompt: str, output_path: Path, size: str = "1024x1024"
    ) -> Optional[Path]:
        """Generate an image from the prompt and save it to the output path."""
        pass


class OpenAIImageGenerator(ImageGenerator):
    """OpenAI DALL-E model implementation."""

    def __init__(self, api_key: str, config: Dict[str, Any]):
        self.api_key = api_key
        # Use the official openai async client
        self.client = AsyncOpenAI(api_key=self.api_key)
        self.config = config  # Store model, quality, style if needed
        self.model = config.get("model", "dall-e-3")  # Default to DALL-E 3
        logger.info(f"Initialized OpenAI Image Generator with model: {self.model}")

    async def generate(
        self, prompt: str, output_path: Path, size: str = "1024x1024"
    ) -> Optional[Path]:
        logger.info(f"Generating image for prompt (first 50 chars): {prompt[:50]}...")
        payload = {
            "model": self.model,
            "prompt": prompt,
            "n": 1,
            "size": size,
            "response_format": "b64_json",  # Request base64 encoded image
        }
        if "quality" in self.config:
            payload["quality"] = self.config["quality"]
        if "style" in self.config:
            payload["style"] = self.config["style"]

        try:
            response = await self.client.images.generate(**payload)

            b64_data = response.data[0].b64_json
            if not b64_data:
                logger.error(
                    f"OpenAI image generation failed: No image data in response."
                )
                return None

            image_data = base64.b64decode(b64_data)
            output_path.parent.mkdir(parents=True, exist_ok=True)  # Ensure dir exists
            with open(output_path, "wb") as f:
                f.write(image_data)
            logger.info(f"Image saved successfully to {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"OpenAI image generation failed: {e}")
            # Consider logging traceback for detailed debugging
            # import traceback
            # logger.error(traceback.format_exc())
            return None


class ImageGeneratorFactory:
    """Factory class for creating image generators."""

    @staticmethod
    def create(
        provider: str, credentials: Dict[str, str], config: Dict[str, Any]
    ) -> Optional[ImageGenerator]:
        """Create an image generator instance based on the provider."""
        provider_config = config.get("providers", {}).get(provider)
        if not provider_config:
            logger.warning(f"No configuration found for provider: {provider}")
            return None

        if provider == "openai" and credentials.get("OPENAI_API_KEY"):
            return OpenAIImageGenerator(
                api_key=credentials["OPENAI_API_KEY"], config=provider_config
            )
        # Add other providers like Replicate here if needed in the future
        # elif provider == "replicate" and credentials.get("REPLICATE_API_TOKEN"):
        #     # Import and return Replicate generator
        #     pass
        else:
            logger.warning(f"Unsupported provider '{provider}' or missing credentials.")
            return None
