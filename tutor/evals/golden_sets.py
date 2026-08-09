"""
golden_sets.py — Hand-authored golden-QA sets for the P3.1 eval suite.

Schema:
    GOLDEN_SETS: dict[lecture_id, {
        "title": str,
        "questions": [
            {
                "q": str,                      # the student's question
                "gold": [str, ...],            # short heading fragments that a
                                               # correct retrieval MUST surface.
            },
        ],
    }]

Gold fragments are matched as case-insensitive substrings against each chunk's
heading_path / heading (see evals/metrics.py chunk_matches). Keep fragments
short and distinctive ("AI as a Sounding Board") so they survive full heading
paths like "Chapter 10: ... > Practical Applications > 1. AI as a Sounding Board".
"""

from __future__ import annotations

GOLDEN_SETS: dict[str, dict] = {
    # 15-chapter "Generative AI" course used for P1/P2 DoD validation.
    "6ddb64c1-e42d-40c4-b99e-22b469d76f07": {
        "title": "Generative AI (15 chapters)",
        "questions": [
            {
                "q": "What is generative AI and how does it differ from traditional computing?",
                "gold": ["Foundations of Generative AI > Overview", "Foundations of Generative AI > The Paradigm Shift"],
            },
            {
                "q": "What are the key concepts behind machine learning and generative AI?",
                "gold": ["Foundations of Generative AI > Key Concepts"],
            },
            {
                "q": "What mental models help humans interact with AI?",
                "gold": ["Mental Models and Human-AI Interaction > Key Metaphors"],
            },
            {
                "q": "What role does prompt engineering play in large language models?",
                "gold": ["The Role of Prompt Engineering"],
            },
            {
                "q": "How does the Transformer architecture process language?",
                "gold": ["Core Architecture: The Transformer"],
            },
            {
                "q": "How do LLMs generate text through next-word prediction?",
                "gold": ["Core Mechanism: Next-Word Prediction"],
            },
            {
                "q": "How are models aligned with human feedback?",
                "gold": ["Model Alignment and Human Feedback > Core Training Mechanism"],
            },
            {
                "q": "What is the two-stage training process for LLMs?",
                "gold": ["The Two-Stage Training Process"],
            },
            {
                "q": "What are the key deployment models for generative AI systems?",
                "gold": ["Key Deployment Models"],
            },
            {
                "q": "What emergent capabilities do large language models show?",
                "gold": ["Emergent Capabilities in AI > Overview", "Emergent Capabilities"],
            },
            {
                "q": "How can AI serve as a sounding board?",
                "gold": ["AI as a Sounding Board"],
            },
            {
                "q": "What are the different training paradigms for LLMs?",
                "gold": ["Training Paradigms"],
            },
            {
                "q": "How do autonomous AI agents work?",
                "gold": ["Autonomous AI Agents"],
            },
            {
                "q": "What are the three mindsets people take toward AI?",
                "gold": ["The Three Mindsets Toward AI"],
            },
            {
                "q": "What are the key themes in AI governance and oversight?",
                "gold": ["Governance, Reliability, and Oversight > Key Themes", "Governance, Reliability, and Oversight"],
            },
        ],
    },
}


def get_golden_set(lecture_id: str) -> dict | None:
    """Return the golden set for a lecture id, or None if un-authored."""
    return GOLDEN_SETS.get(lecture_id)
