OUTLINE_PROMPT = """
You are an expert curriculum designer.

You are given a sequence of raw lecture chunks.

Your task is to organize and cluster these chunks into a clean, high-level lecture outline with substantial, well-balanced chapters.

CRITICAL CLUSTERING RULES:
1. Do NOT create a separate chapter for every input chunk. Group related consecutive chunks together into major thematic chapters.
2. For typical lectures (15-30 minutes), create strictly 3 to 6 major chapters total. Each chapter must cover a substantial portion of the lecture.
3. Give each chapter a clear, professional textbook-style title.
4. Identify the primary concepts that each chapter should focus on.
5. Ensure adjacent chapters represent meaningful transitions in topic or depth.
6. Think like a textbook author creating major chapter divisions.

Return ONLY valid JSON.

Schema:

{
    "lecture_title": "",
    "chapters": [
        {
            "chapter_id": 1,
            "title": "",
            "focus_concepts": [],
            "summary": ""
        }
    ]
}
"""