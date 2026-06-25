OUTLINE_PROMPT = """
You are an expert curriculum designer.

You are given a sequence of lecture chapters.

Your task is to create a clean lecture outline.

Goals:

1. Give each chapter a meaningful title.
2. Identify the primary concepts that chapter should focus on.
3. Ensure adjacent chapters have different purposes.
4. Avoid assigning the same concept as a primary focus
   for multiple chapters.
5. Think like a textbook author.

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