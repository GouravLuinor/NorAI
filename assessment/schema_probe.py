# Manual probe (NOT part of the offline test suite): makes a real Gemini
# generate_content call to check the assessment schema parses. Requires
# GEMINI_API_KEY; skipped by scripts/run-tests.sh because it isn't `test_*.py`.
import os
from google import genai
from google.genai import types
from config import MODEL_NAME
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
    model=MODEL_NAME,
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