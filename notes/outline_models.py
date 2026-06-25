from pydantic import BaseModel


class OutlineChapter(BaseModel):

    chapter_id: int

    title: str

    focus_concepts: list[str]

    summary: str


class LectureOutline(BaseModel):

    lecture_title: str

    chapters: list[OutlineChapter]