from pydantic import BaseModel


class ExternalKnowledgeItem(BaseModel):
    key: str
    value: str


class KnowledgeObject(BaseModel):
    chunk_id: int
    topic: str
    transcript: str
    lecture_notes: str
    key_points: list[str]
    concepts: list[str]
    inferred_knowledge: list[str]
    external_knowledge: list[ExternalKnowledgeItem]


class ChunkKnowledgeModel(BaseModel):
    topic: str
    lecture_notes: str
    key_points: list[str]
    concepts: list[str]
    inferred_knowledge: list[str]
    external_knowledge: list[ExternalKnowledgeItem]