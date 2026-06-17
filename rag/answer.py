import os
from google import genai
from dotenv import load_dotenv

from retrieval.retrieve import (
    retrieve_chunks,
    get_retrieval_confidence
)

from rag.prompts import (
    SYSTEM_PROMPT,
    FALLBACK_PROMPT,
    build_user_prompt
)

load_dotenv()


RETRIEVAL_DISTANCE_THRESHOLD = 0.8


def format_time(seconds):
    """
    Convert seconds into MM:SS format.
    """

    minutes = int(seconds // 60)
    seconds = int(seconds % 60)

    return f"{minutes}:{seconds:02d}"


# LLM Setup


def load_llm():
    """
    Load Gemini model.
    """

    api_key = os.getenv(
        "GEMINI_API_KEY"
    )

    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY not found."
        )

    client = genai.Client(
        api_key=api_key
    )

    return client


# Context Builder


def build_context(
    retrieved_chunks
):
    """
    Convert chunks into context.
    """

    return "\n\n".join(
        chunk["text"]
        for chunk in retrieved_chunks
    )



# Citation Builder



def build_sources(
    retrieved_chunks
):
    """
    Create source metadata
    with evidence snippets.
    """

    sources = []

    for chunk in retrieved_chunks:

        sources.append(
            {
                "chunk_id":
                    chunk["chunk_id"],

                "start":
                    chunk["start"],

                "end":
                    chunk["end"],

                "text":
                    chunk["text"][:250]
            }
        )

    return sources


# Answer Generation


def generate_answer(
    question,
    n_results=3
):
    """
    Full RAG pipeline.
    """

    retrieved_chunks = (
        retrieve_chunks(
            query=question,
            n_results=n_results
        )
    )

    confidence = (
        get_retrieval_confidence(
            retrieved_chunks
        )
    )

    print(
        f"Retrieval distance: "
        f"{confidence:.4f}"
    )


    context = build_context(
        retrieved_chunks
    )

    prompt = build_user_prompt(
        question,
        context
    )
    print(
        f"Prompt length: {len(prompt)} chars"
    )
    client = load_llm()

    if (
        confidence
        < RETRIEVAL_DISTANCE_THRESHOLD
    ):

        response = (
            client.models.generate_content(
                model=
                "gemma-4-26b-a4b-it",

                contents=
                f"{SYSTEM_PROMPT}\n\n{prompt}"
            )
        )

        lecture_found = True

    else:

        response = (
            client.models.generate_content(
                model=
                "gemma-4-26b-a4b-it",

                contents=
                f"""
    {FALLBACK_PROMPT}

    Question:
    {question}
    """
            )
        )

        lecture_found = False


    return {
        "question":
            question,

        "answer":
            response.text,

        "sources":
            build_sources(
                retrieved_chunks
            ),

        "lecture_found":
            lecture_found,

        "confidence":
            confidence
    }


# Example Usage


if __name__ == "__main__":

    result = generate_answer(
        "is segment tree better than binary indexed tree?"
    )

    if result["lecture_found"]:

        print(
            "✓ Answer found in lecture\n"
        )

    else:

        print(
            "⚠ Not directly covered "
            "in the lecture\n"
        )

    print(
        result["answer"]
    )

    print()

print("\nSources:\n")

for source in result["sources"]:

    print(
        f"[Chunk {source['chunk_id']} | "
        f"{format_time(source['start'])}"
        f" - "
        f"{format_time(source['end'])}]"
    )

    print(
        f'"{source["text"]}"'
    )

    print()