from pydantic import BaseModel


class ChapterGroup(BaseModel):

    chapter_id: int

    start_chunk: int

    end_chunk: int

    chunk_ids: list[int]

    topics: list[str]

    concepts: list[str]

    avg_similarity: float


class Chapter(BaseModel):

    chapter_id: int

    title: str

    start_chunk: int

    end_chunk: int

    chunk_ids: list[int]

    focus_concepts: list[str]

    topics: list[str]

    concepts: list[str]

    lecture_notes: list[str]

    visual_notes: list[str]

    important_information: list[str]

    inferred_knowledge: list[str]

    screenshots: list[str]