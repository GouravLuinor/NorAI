from pydantic import BaseModel


class KnowledgeObject(BaseModel):
    chunk_id: int
    start: float
    end: float
    topic: str
    transcript: str
    lecture_notes: str
    key_points: list[str]
    concepts: list[str]
    inferred_knowledge: list[str]


class ChunkKnowledgeModel(BaseModel):
    topic: str
    lecture_notes: str
    key_points: list[str]
    concepts: list[str]
    inferred_knowledge: list[str]