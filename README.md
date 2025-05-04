# Story Book Creator

An AI-powered tool that creates personalized children's storybooks with text and illustrations.

## Overview

Story Book Creator uses generative AI to craft engaging children's stories with matching illustrations. By providing simple configuration details, you can generate complete storybooks featuring custom characters, themes, and settings.

Features:
- Create original stories using AI, tailored to specific age ranges
- Generate matching illustrations for each page
- Include your own characters with custom images
- Configure story themes, settings, and length
- Automatic book organization with pages and metadata

## Installation

### Prerequisites
- Python 3.12 or higher
- OpenAI API key
- Google Gemini API key

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/story-book-creator.git
   cd story-book-creator
   ```

2. Install dependencies:
   ```bash
   uv sync
   ```

3. Create a `.env` file in the project root with your API keys:
    ```bash
    cp .env.example .env
    ```
    ```bash
    OPENAI_API_KEY=your_openai_key_here
    GEMINI_API_KEY=your_gemini_key_here
    ```

## Usage

1. Create your story configuration by copying the example:
   ```bash
   cp story_config.example.json input/story_config.json
   ```

2. Edit `input/story_config.json` to customize your story:
   ```json
   {
     "characters": [
       {
         "name": "Ella",
         "description": "A baby human with a big smile",
         "image_path": "input/images/ella.jpeg"
       },
       {
         "name": "Rory",
         "description": "A black and white tibetan terrier puppy"
       }
     ],
     "theme": "Friendship and overcoming fears",
     "age_range": "1-2 years",
     "location": {
       "setting": "A sunny meadow next to a sparkling blue river",
       "details": ["Tall swaying grass", "Colorful wildflowers", "Busy buzzing bees"]
     },
     "story_length_pages": 5,
     "image_style": "Colorful cartoon illustration, simple and friendly, watercolor texture"
   }
   ```

3. Run the story creator:
   ```bash
   uv run main.py
   ```

4. Find your generated storybook in the `output` directory. Each story is saved in its own timestamped folder.

## Configuration Options

### Characters
- `name`: The character's name (required)
- `description`: Physical and personality details (required)
- `image_path`: Optional path to a character image to incorporate into illustrations

### Story Settings
- `theme`: Main story theme or message
- `age_range`: Target audience age
- `location`: Setting details including specific features
- `story_length_pages`: Number of pages (4-20)
- `image_style`: Description of the desired illustration style

## Including Character Images

To incorporate your own characters into the illustrations:

1. Add character images to the `input/images/` directory
2. Reference these images in your configuration with the `image_path` property
3. The system will intelligently incorporate the characters into each story page where they appear

## Output

Each generated story includes:

- A full story text file
- Individual illustrated page images
- A JSON manifest with page details
- The original configuration used to generate the story

## Notes

- Story generation can take several minutes depending on length
- Higher quality illustrations require more processing time
- Both API keys must be valid for the system to work

## License

[MIT License](LICENSE)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.