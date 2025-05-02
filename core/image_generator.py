# core/image_generator.py
import base64
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Dict, Any

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


class DallEImageGenerator(ImageGenerator):
    """OpenAI DALL-E model implementation (dall-e-2, dall-e-3)."""

    def __init__(self, api_key: str, config: Dict[str, Any]):
        self.api_key = api_key
        # Use the official openai async client
        self.client = AsyncOpenAI(api_key=self.api_key)
        self.config = config  # Store model, quality, style if needed
        self.model = config.get("model", "dall-e-3")  # Ensure a DALL-E model is set
        logger.info(f"Initialized DALL-E Image Generator with model: {self.model}")
        if not self.model.startswith("dall-e"):
            logger.warning(
                f"DallEImageGenerator initialized with non-DALL-E model: {self.model}"
            )

    async def generate(
        self, prompt: str, output_path: Path, size: str = "1024x1024"
    ) -> Optional[Path]:
        logger.info(
            f"Generating DALL-E image for prompt (first 50 chars): {prompt[:50]}..."
        )
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
                    "DALL-E image generation failed: No image data in response."
                )
                return None

            image_data = base64.b64decode(b64_data)
            output_path.parent.mkdir(parents=True, exist_ok=True)  # Ensure dir exists
            with open(output_path, "wb") as f:
                f.write(image_data)
            logger.info(f"Image saved successfully to {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"DALL-E image generation failed: {e}")
            # Consider logging traceback for detailed debugging
            # import traceback
            # logger.error(traceback.format_exc())
            return None


class GPTImageGenerator(ImageGenerator):
    """OpenAI GPT Image model implementation (e.g., gpt-image-1)."""

    # According to https://cookbook.openai.com/examples/generate_images_with_gpt_image
    # Valid sizes: "1024x1024", "1536x1024", "1024x1536" or "auto"
    # Valid quality: "low", "medium", "high", or "auto"
    # Valid output_format: "jpeg", "png", "webp" (default "jpeg")

    def __init__(self, api_key: str, config: Dict[str, Any]):
        self.api_key = api_key
        self.client = AsyncOpenAI(api_key=self.api_key)
        self.config = config
        self.model = config.get(
            "model", "gpt-image-1"
        )  # Ensure a GPT Image model is set
        logger.info(f"Initialized GPT Image Generator with model: {self.model}")
        if not self.model.startswith("gpt-image"):
            logger.warning(
                f"GPTImageGenerator initialized with non-GPT-Image model: {self.model}"
            )

    async def generate(
        self, prompt: str, output_path: Path, size: str = "1536x1024"
    ) -> Optional[Path]:
        logger.info(
            f"Generating GPT Image for prompt (first 50 chars): {prompt[:50]}..."
        )

        # Build payload, respecting config overrides
        payload: Dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "size": size,
        }
        if "quality" in self.config:
            payload["quality"] = self.config["quality"]
        if "output_format" in self.config:
            # Ensure output_path suffix matches format if specified
            output_format = self.config["output_format"].lower()
            payload["output_format"] = output_format
            if output_path.suffix.lower() != f".{output_format}":
                output_path = output_path.with_suffix(f".{output_format}")
                logger.info(f"Adjusted output path to match format: {output_path}")
        if "output_compression" in self.config:
            # API expects 0-100, useful for jpeg/webp
            payload["output_compression"] = self.config["output_compression"]
        # Note: 'style' is not listed as a param for gpt-image-1 in the cookbook

        try:
            logger.info(f"Payload: {payload}")
            response = await self.client.images.generate(**payload)

            b64_data = response.data[0].b64_json
            if not b64_data:
                logger.error(f"GPT Image generation failed: No image data in response.")
                return None

            image_data = base64.b64decode(b64_data)
            output_path.parent.mkdir(parents=True, exist_ok=True)  # Ensure dir exists
            with open(output_path, "wb") as f:
                f.write(image_data)
            logger.info(f"Image saved successfully to {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"GPT Image generation failed: {e}")
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

        model_name = provider_config.get("model", "").lower()

        if provider == "openai" and credentials.get("OPENAI_API_KEY"):
            api_key = credentials["OPENAI_API_KEY"]
            if model_name.startswith("gpt-image"):
                logger.info(f"Creating GPTImageGenerator for model: {model_name}")
                return GPTImageGenerator(api_key=api_key, config=provider_config)
            elif model_name.startswith("dall-e"):
                logger.info(f"Creating DallEImageGenerator for model: {model_name}")
                return DallEImageGenerator(api_key=api_key, config=provider_config)
            else:
                logger.warning(
                    f"Unknown OpenAI model specified: '{model_name}'. Cannot create generator."
                )
                return None

        # Add other providers like Replicate here if needed in the future
        # elif provider == "replicate" and credentials.get("REPLICATE_API_TOKEN"):
        else:
            logger.warning(f"Unsupported provider '{provider}' or missing credentials.")
            return None
