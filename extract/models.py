from pydantic import BaseModel


class KnowledgeObject(
    BaseModel
):

    chunk_id: int

    topic: str

    transcript: str

    lecture_notes: str

    key_points: list[str]

    concepts: list[str]

    inferred_knowledge: list[str]

    external_knowledge: dict[str, str]