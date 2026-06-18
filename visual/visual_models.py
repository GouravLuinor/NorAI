import os

from dotenv import load_dotenv
from google import genai


# Environment


load_dotenv()

API_KEY = os.getenv(
    "GEMINI_API_KEY"
)

if not API_KEY:
    raise ValueError(
        "GEMINI_API_KEY not found."
    )


# Client


client = genai.Client(
    api_key=API_KEY
)



# Image Analysis


def analyze_images(
    image_paths,
    prompt,
    model_name=
    "gemma-4-26b-a4b-it"
):
    """
    Analyze one or more images
    using Gemma 4.
    """

    uploaded_files = []

    for image_path in image_paths:

        print(
            f"Uploading: "
            f"{image_path}"
        )

        uploaded_file = (
            client.files.upload(
                file=image_path
            )
        )

        uploaded_files.append(
            uploaded_file
        )

    print(
        f"Sending "
        f"{len(uploaded_files)} "
        f"images to {model_name}"
    )

    response = (
        client.models.generate_content(
            model=model_name,

            contents=[
                *uploaded_files,
                prompt
            ]
        )
    )

    return response.text