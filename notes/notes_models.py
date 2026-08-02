from pydantic import BaseModel, Field
from typing import List

class OutlineChapter(BaseModel):
    chapter_id: int
    title: str
    focus_concepts: List[str]
    chunk_ids: List[int]
    start_chunk: int
    end_chunk: int

class LectureOutlineModel(BaseModel):
    chapters: List[OutlineChapter]