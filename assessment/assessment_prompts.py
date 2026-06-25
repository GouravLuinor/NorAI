"""
assessment_prompts.py

Prompt(s) for the assessment engine.

Mirrors the convention in revision_prompts.py: a single prompt
constant (ASSESSMENT_PROMPT) that assessment_generator.py formats
with the chapter's id, title, and study-notes markdown, then sends
to Gemini requesting free-form JSON output matching the Question
schema in assessment_models.py, validated after the fact.

Design notes:

- The prompt explicitly frames this as assessing understanding, not
  generating trivia — per the "Prompt Philosophy" in the design doc,
  this is the single highest-leverage instruction in the whole prompt.
  Everything else (distribution guidance, type list, difficulty mix)
  is downstream of getting this framing right.

- The 8-10 questions/chapter figure and the example distribution are
  given as *guidance*, not a quota the model must hit exactly. The
  model is told to let chapter content determine the actual mix.
  assessment_models.py validates the *result* (sane bounds, no
  duplicate ids, options only where required) rather than the prompt
  enforcing an exact shape — see assessment_models.py docstring.

- Subject-specific question framing (Diagram Question for Biology,
  Chronology for History, Code Tracing for CS, etc.) is handled here
  as phrasing guidance layered on top of the generic QuestionType
  vocabulary, not as separate literal types in the schema. The model
  is told to pick whichever generic type fits and write the question
  in subject-appropriate language.

- generated_at and total_questions/total_chapters are NOT requested
  from the model — assessment_generator.py fills those in itself
  after collecting every chapter's questions, the same way it would
  for any other run-level metadata. Asking the model to self-report
  a timestamp or a total it can't actually verify (it only sees one
  chapter at a time) invites drift between metadata and reality.

- The model receives free-form generation instructions (this prompt
  asks explicitly for a pure JSON object, no fences, no commentary)
  rather than an API-level response_schema — response_schema was
  tested against this model and causes generate_content to hang, so
  generation is free-form and assessment_generator.py validates and
  normalizes the result after the fact, same pattern as
  notes_generator.py.

- The prompt explicitly forbids LaTeX / backslash math notation in
  any string field (e.g. "$O(N \\log N)$"). Root cause: the model
  would write LaTeX backslash commands (\\log, \\le, \\cdot, etc.)
  straight into a JSON string field, and a bare backslash followed by
  a letter isn't a valid JSON escape sequence — this produced
  "Invalid \\escape" JSON parse failures specifically on math-heavy
  (DSA/algorithms) chapters. Telling the model to write math in plain
  text (e.g. "O(N log N)") sidesteps the bug at the source rather
  than trying to repair broken JSON after the fact.

- The prompt now includes an explicit, field-by-field spec (exact
  field names, exact Literal values for "type" and "difficulty",
  which fields require options) instead of relying solely on prose
  ("vary the question types...", "vary difficulty too...") for the
  model to infer shape from. Root cause this addresses: without a
  concrete spec to copy from, the model would sometimes omit
  "difficulty" entirely, or send "type" values in the wrong case/
  format ("mcq", "fill_in_the_blank") — both are normalized as a
  safety net in assessment_generator.py's _normalize_type_value /
  _normalize_difficulty_value, but fixing the prompt to make the
  exact spec unambiguous should reduce how often that net needs to
  catch anything in the first place.
"""

ASSESSMENT_PROMPT = """\
You are building an assessment for a student who just studied a chapter \
of lecture notes. Your goal is NOT to generate questions. Your goal is to \
assess whether the student truly understood this chapter — the questions \
are just the instrument.

Before writing anything, ask yourself: "If a student could answer every \
question I write without having understood the underlying idea — by \
pattern-matching a sentence from the notes, or guessing from surface \
wording — then I have failed." Write questions that require actual \
understanding of the concept, not recall of a sentence.

# Chapter

Chapter ID: {chapter_id}
Chapter Title: {chapter_title}

# Study Notes (source material — base every question on this content only)

{chapter_markdown}

# What to produce

Generate a list of questions based on the chapter.
Ensure you strictly follow the JSON schema provided by the system.
Your output must be a pure JSON object containing a "questions" array.
No markdown fences, no commentary before or after.

Every question object MUST have exactly these fields, with no field \
omitted and no field renamed:

- "question_id": integer, unique within this chapter, starting at 1.
- "type": exactly one of these strings, copied character-for-character \
including capitalization: "MCQ", "True/False", "Fill in the Blank", \
"Short Answer", "Long Answer", "Conceptual", "Application", \
"Code Tracing", "Complexity", "Scenario".
- "difficulty": exactly one of these strings, copied \
character-for-character including capitalization: "Easy", "Medium", \
"Hard". This field is REQUIRED on every single question — never omit it.
- "concepts": a list of short strings naming the specific idea(s) this \
question probes.
- "question": the question text.
- "options": a list of strings. Required (at least 2 entries) for "MCQ" \
and "True/False" questions only. For every other type, this MUST be an \
empty list — do not include it, or include it as [], for non-MCQ/True-False \
questions.
- "answer": the correct answer, as a string. For "MCQ" and "True/False", \
this must exactly match one of the strings in "options".
- "explanation": a short string explaining why the answer is correct.

Write all math and algorithmic notation in plain text, not LaTeX. \
Every question, option, answer, and explanation is a JSON string, and \
LaTeX commands use backslashes (e.g. \\log, \\le, \\cdot, \\sqrt, \\frac) \
that are NOT valid inside a JSON string and will break parsing. Write \
"O(N log N)" instead of "$O(N \\log N)$", "i <= j" instead of "$i \\le \
j$", "n^2" or "n squared" instead of "$n^2$", and so on — plain \
characters only, no backslashes, no dollar signs.

# How many questions, and what mix

There is no fixed number. Let the chapter's actual content decide:

- A short, narrow chapter might only support 5-6 good questions.
- A dense chapter covering several distinct ideas might support 12+.
- As a general anchor, aim for roughly 8-10 questions for a typical \
chapter — but do not pad to hit this number with filler questions, and \
do not cut a chapter short of it if the content genuinely supports more.

Vary the question types based on what the content actually calls for, \
not a fixed template. A chapter that's mostly definitions might lean on \
MCQ, True/False, and Conceptual questions. A chapter built around a \
process or algorithm should include Application or Scenario questions \
that ask the student to use the idea, not just recognize it. A chapter \
with a complexity/proof angle (common in CS/DSA content) should include \
at least one Complexity question. A chapter built around code should \
include at least one Code Tracing question. As a loose illustration of \
the kind of mix to aim for in an 8-question chapter: a few MCQs, one \
True/False, one Fill in the Blank, a couple of Short Answer questions, \
and one Application or Conceptual question that goes a level deeper than \
the rest. Treat this only as a feel for proportion, not a checklist.

Vary difficulty too. Don't make every question Medium. Include some Easy \
questions that confirm baseline recall of a definition or fact, and at \
least one Hard question per chapter that requires connecting two or more \
ideas from the chapter, or applying a concept somewhere the notes didn't \
explicitly spell out.

# Subject-appropriate framing

The question types above are intentionally generic so this works across \
subjects. Within them, phrase questions the way this specific subject \
calls for:

- For a CS / data structures / algorithms chapter: lean on Code Tracing \
(trace through an algorithm step-by-step) and Complexity questions \
(reason about time/space complexity), framed as "Application" or \
"Scenario" type questions where the schema needs a type name.
- For a Biology / life-sciences chapter: frame "Scenario" questions as \
case studies (e.g. "A patient presents with X — what does this suggest \
about Y process?"), and "Conceptual" questions around diagram-style \
reasoning (e.g. "If you were to label the stages of X, what happens at \
each step and why?") even though there's no literal image.
- For a History / social-science chapter: frame "Conceptual" questions \
as cause-and-effect or compare/contrast questions, and "Application" \
questions as chronology or "what would have happened if X hadn't \
occurred" reasoning.
- For any other subject, use your judgment to find the equivalent: the \
schema's type names are buckets, the phrasing inside them should always \
sound native to the subject.

# Hard constraints

- Base every question ONLY on the study notes provided above. Do not \
introduce facts, examples, or framings that aren't supported by this \
chapter's content.
- Every "concepts" tag should name something specific enough to be \
useful for tracking — "Partial Overlap" is useful, "Segment Trees" (the \
whole chapter topic) is not.
- Never write a question whose correct answer is "all of the above" / \
"none of the above" — these test test-taking strategy, not understanding.
- Never write a question that can be answered correctly from general \
knowledge without having read this chapter at all.
- question_id must be unique within this chapter's questions and should \
start at 1.
- No LaTeX, no backslash commands, no "$...$" math delimiters anywhere \
in any string field. Plain text only, even for formulas and complexity \
notation.
- Every question object must include a "difficulty" field with one of \
"Easy", "Medium", or "Hard". Double-check this before finishing — a \
question missing "difficulty" will be rejected entirely.
"""