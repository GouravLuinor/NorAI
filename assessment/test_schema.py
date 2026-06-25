# Run this on YOUR machine (not here - google-genai isn't installed in this sandbox)
import os
from google import genai
from google.genai import types
from pydantic import BaseModel
from typing import Literal
from dotenv import load_dotenv
class TestQuestion(BaseModel):
    question_id: int
    type: Literal["MCQ", "True/False", "Short Answer"]
    difficulty: Literal["Easy", "Medium", "Hard"]
    question: str
    options: list[str] = []
    answer: str
    explanation: str = ""

class TestEnvelope(BaseModel):
    questions: list[TestQuestion]

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

response = client.models.generate_content(
    model="gemma-4-26b-a4b-it",
    contents=["Generate 3 short questions (mix of MCQ and Short Answer) "
              "about photosynthesis, matching the required schema exactly."],
    config=types.GenerateContentConfig(
        temperature=0.3,
        response_mime_type="application/json",
        response_schema=TestEnvelope,
    ),
)

print("RAW TEXT:")
print(response.text)
print()
print("PARSED:")
print(TestEnvelope.model_validate_json(response.text))