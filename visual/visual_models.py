from pydantic import BaseModel, Field
from typing import List, Optional

class VisualConcept(BaseModel):
    title: str
    description: str
    diagram_type: Optional[str] = None
    key_labels: Optional[List[str]] = Field(default_factory=list)
    screenshots: Optional[List[str]] = Field(default_factory=list)

class VisualChunkKnowledgeModel(BaseModel):
    visual_concepts: List[VisualConcept]