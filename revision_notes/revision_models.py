from pydantic import BaseModel


class RevisionMetadata(BaseModel):
    """
    Metadata describing the generated revision notes.
    """

    lecture_title: str

    total_chapters: int

    estimated_read_time: int  # minutes

    word_count: int

    generated_at: str


class RevisionChapter(BaseModel):
    """
    One revision chapter.
    """

    chapter_id: int

    title: str

    markdown: str


class RevisionNotes(BaseModel):
    """
    Complete revision notes.
    """

    metadata: RevisionMetadata

    chapters: list[RevisionChapter]