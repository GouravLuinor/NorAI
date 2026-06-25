from pydantic import BaseModel


class Chapter(BaseModel):

    chapter_title: str

    chunk_ids: list[int]

    concepts: list[str]

    lecture_notes: str

    visual_notes: str

    important_information: list[str]

    screenshots: list[str]


class LectureNotes(BaseModel):

    lecture_title: str

    generated_from: int

    chapters: list[Chapter]