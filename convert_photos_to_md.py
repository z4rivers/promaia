#!/usr/bin/env python3
"""
Convert photos from dated directories into markdown documents with AI-generated transcripts.
Includes inline descriptions of drawings, symbols, and non-text elements.
"""

import os
import glob
import uuid
from datetime import datetime
from pathlib import Path
from PIL import Image
from PIL.ExifTags import TAGS
import anthropic
from dotenv import load_dotenv
from promaia.utils.image_processing import encode_image_from_path

# Load environment variables from .env file
load_dotenv()

# Configuration
DATED_DIR = "2025-12-23-2059-31"
OUTPUT_DIR = "data/md/notion/koii/journal"
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

if not ANTHROPIC_API_KEY:
    raise ValueError("ANTHROPIC_API_KEY not found in environment. Please check your .env file.")

def get_photo_capture_time(image_path):
    """Extract capture time from EXIF data, fallback to file mtime."""
    try:
        img = Image.open(image_path)
        exif = img.getexif()
        if exif:
            # Try DateTimeOriginal first (tag 36867), then DateTime (tag 306)
            for tag_id in [36867, 306]:
                if tag_id in exif:
                    date_str = exif[tag_id]
                    return datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S')
    except Exception as e:
        print(f"  Warning: Could not extract EXIF from {image_path}: {e}")

    # Fallback to file modification time
    return datetime.fromtimestamp(os.path.getmtime(image_path))

def get_camera_model(image_path):
    """Extract camera model from EXIF data."""
    try:
        img = Image.open(image_path)
        exif = img.getexif()
        if exif:
            # Tag 272 is Make, 273 is Model
            make = exif.get(271, "")
            model = exif.get(272, "")
            if make and model:
                return f"{make} {model}".strip()
            elif model:
                return model
    except:
        pass
    return "Unknown"

def generate_ai_transcript(image_path):
    """Generate AI transcript with inline descriptions of drawings and non-text elements."""
    print(f"  Generating AI transcript for {os.path.basename(image_path)}...")

    # Initialize Anthropic client
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    # Encode image
    image_result = encode_image_from_path(image_path)
    image_data = image_result['data']

    # Create prompt for transcript generation
    prompt = """Please analyze this notebook page with pen sketches and provide a transcript-style output.

Instructions:
1. Do your best to transcribe any handwritten text, even cursive. If text is unclear, transcribe what you can and use [Unclear: possible interpretation] for ambiguous words
2. For drawings, insert inline descriptions like: [Drawing: detailed description of the sketch]
3. For symbols, use: [Symbol: description of the symbol]
4. For diagrams, use: [Diagram: description of the diagram layout and elements]
5. For abstract art, use: [Abstract art: description of shapes, patterns, style]
6. For anything completely illegible, use: [Illegible handwriting]
7. Preserve the layout and flow of the page (top to bottom, left to right)
8. Include page numbers if visible
9. Be detailed but concise in descriptions

Focus on describing WHAT is drawn and transcribing WHAT is written. These are pen/pencil sketches and handwritten notes in a notebook. Try your best with cursive handwriting."""

    # Call Claude Sonnet 4.5 with vision
    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=2000,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": image_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ],
            }
        ],
    )

    # Extract transcript from response
    transcript = response.content[0].text
    return transcript

def create_markdown_file(image_path, index, total, capture_time, transcript):
    """Create a markdown file with frontmatter and AI-generated transcript."""
    # Generate UUID for page ID
    page_id = str(uuid.uuid4())

    # Format dates
    created_time_iso = capture_time.strftime('%Y-%m-%dT%H:%M:%S.000Z')
    date_formatted = capture_time.strftime('%B %d, %Y %I:%M %p')
    date_simple = capture_time.strftime('%Y-%m-%d')

    # Get camera model
    camera = get_camera_model(image_path)

    # Create filename
    filename = f"{date_simple} Sketch-{index:03d} {page_id}.md"
    output_path = os.path.join(OUTPUT_DIR, filename)

    # Get relative path to image
    image_rel_path = os.path.relpath(image_path, OUTPUT_DIR)

    # Create markdown content
    markdown_content = f"""Created time: {created_time_iso}
Date: {date_formatted}
Name: Sketch {index} - {date_simple}
Blog Status: Don't sync
Newsletter Status: Don't send

# Notebook Sketch {index}

{transcript}

---

![Sketch {index}]({image_rel_path})

**Metadata:**
- Camera: {camera}
- Capture Time: {capture_time.strftime('%Y-%m-%d %H:%M:%S')}
- Source: {os.path.basename(image_path)}
"""

    # Ensure output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Write markdown file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(markdown_content)

    print(f"  ✓ Created: {filename}")
    return output_path

def main():
    """Main processing function."""
    print(f"\n{'='*60}")
    print("Photo to Markdown Converter")
    print(f"{'='*60}\n")

    # Find all JPG files in the dated directory
    photo_pattern = os.path.join(DATED_DIR, "*.JPG")
    photo_files = glob.glob(photo_pattern)

    if not photo_files:
        print(f"Error: No JPG files found in {DATED_DIR}")
        return

    print(f"Found {len(photo_files)} photos in {DATED_DIR}")

    # Extract capture times and sort chronologically
    print("\nExtracting capture times and sorting...")
    photos_with_times = []
    for photo_path in photo_files:
        capture_time = get_photo_capture_time(photo_path)
        photos_with_times.append((photo_path, capture_time))

    # Sort by capture time
    photos_with_times.sort(key=lambda x: x[1])

    print(f"Photos sorted chronologically from {photos_with_times[0][1]} to {photos_with_times[-1][1]}")

    # Process each photo
    print(f"\n{'='*60}")
    print("Processing photos with Claude Sonnet 4.5...")
    print(f"{'='*60}\n")

    total = len(photos_with_times)
    created_files = []

    for index, (photo_path, capture_time) in enumerate(photos_with_times, start=1):
        print(f"\n[{index}/{total}] Processing: {os.path.basename(photo_path)}")
        print(f"  Capture time: {capture_time}")

        try:
            # Generate AI transcript
            transcript = generate_ai_transcript(photo_path)

            # Create markdown file
            output_path = create_markdown_file(photo_path, index, total, capture_time, transcript)
            created_files.append(output_path)

        except Exception as e:
            print(f"  ✗ Error processing {photo_path}: {e}")
            continue

    # Summary
    print(f"\n{'='*60}")
    print("Conversion Complete!")
    print(f"{'='*60}")
    print(f"Total photos processed: {len(created_files)}/{total}")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
