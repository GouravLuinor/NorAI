# NorAI — Week 9 Context (Interactive AI Tutor)

## Overview

Week 9 transforms NorAI from a static educational content generator into an **interactive AI learning platform**.

Instead of retrieving study notes directly, the system now provides an intelligent tutor capable of answering questions, maintaining conversations, conducting quizzes, generating flashcards, and guiding students through lecture material.

The tutor is built using **LangGraph**, allowing modular orchestration, persistent memory, retrieval, and tool execution.

---

# Overall Tutor Pipeline

```
User Question

↓

Load Memory

↓

Chapter Detection

↓

Command Detection

↓

Query Rewrite

↓

Parallel Retrieval
(Text + Screenshots)

↓

Confidence Analysis

↓

Tool Calling (if required)

↓

Tutor Response

↓

Save Memory
```

The tutor now supports both traditional conversational RAG and interactive educational workflows.

---

# Architecture

The tutor is implemented as a **LangGraph State Graph**.

Unlike a linear RAG pipeline, each node performs a single responsibility.

```
START

↓

Load Memory

↓

Detect Chapter

↓

Quiz Active?

↓

Command?

↓

Query Rewrite

↓

Retrieve Notes

↓

Retrieve Images

↓

Generate Answer

↓

Save Memory

↓

END
```

This architecture makes every stage independently replaceable and easier to debug.

---

# Memory System

## Goal

Create natural educational conversations that persist across sessions.

Implemented:

- Persistent SQLite checkpointing
- Multi-thread conversations
- Conversation history
- Windowed context
- Conversation summarization

Features:

- Multiple independent conversations
- Resume previous learning sessions
- Long-term conversational continuity
- Automatic history compression

Output:

```
outputs/tutor/

checkpoints.sqlite
```

---

# Query Understanding

## Chapter Routing

The tutor detects references such as:

- Chapter 2
- Ch 5
- Chapter Five

without requiring an LLM call.

Retrieval is automatically scoped to the requested chapter.

---

## Query Rewriting

Every educational question is rewritten into an optimized retrieval query.

Purpose:

- remove conversational ambiguity
- improve semantic retrieval
- preserve user intent
- avoid unnecessary query expansion

This significantly improves retrieval quality.

---

# Retrieval System

The tutor performs **parallel retrieval**.

Two retrieval pipelines execute simultaneously.

## Study Notes Retrieval

Knowledge source:

```
outputs/notes/

chapter_*.md
```

Returns:

- relevant educational sections
- markdown chunks
- citations

---

## Screenshot Retrieval

Knowledge source:

```
outputs/screenshots/selected/
```

Returns:

- lecture screenshots
- captions
- timestamps

The tutor can directly reference lecture diagrams and handwritten explanations.

---

# Confidence Awareness

The tutor evaluates retrieval confidence.

If retrieved chunks exceed a cosine-distance threshold:

- distinguishes lecture material from general knowledge
- expresses uncertainty
- avoids hallucinating unsupported lecture content

This makes educational answers more trustworthy.

---

# Prompt Design

The tutor prompt was redesigned for educational conversations.

Characteristics:

- conversational tone
- progressive disclosure
- educational explanations
- screenshot awareness
- citation support
- markdown formatting

Instead of saying:

"According to the notes..."

the tutor naturally incorporates lecture knowledge into its explanations.

---

# Tool Calling

The tutor uses LangGraph's tool-calling workflow.

Hard-coded routing was replaced with an LLM agent capable of selecting the correct educational tool.

Current tools:

- Start Quiz
- Show Chapter Summary
- Show Flashcards

Normal questions bypass the tool agent and continue through retrieval.

This architecture allows future educational tools to be added without modifying the graph.

---

# Interactive Quiz

Quiz mode operates as a dedicated conversational workflow.

Question types:

- MCQ
- True / False
- Fill in the Blank
- Short Answer
- Conceptual
- Scenario-Based

Workflow:

```
Start Quiz

↓

Ask Question

↓

Store Answer

↓

Next Question

↓

Evaluation

↓

Feedback
```

The tutor automatically grades objective questions and uses an LLM for qualitative evaluation.

---

# Flashcards

Flashcards reuse the assessment knowledge base.

Each card contains:

- question
- answer
- explanation

The tutor presents cards conversationally, allowing students to self-test without leaving the chat.

---

# Chapter Summaries

The tutor can instantly return concise chapter summaries.

Source:

```
outputs/revision/

revision_chapter_*.md
```

No LLM generation is required.

The pre-generated revision notes are served directly.

---

# Conversation Summarization

Long conversations are automatically compressed.

After sufficient history:

```
Conversation

↓

Summary Generation

↓

Context Window
```

The tutor preserves long-term memory while maintaining a manageable prompt size.

---

# Package Structure

```
tutor/

    state.py
    graph.py
    prompts.py

    nodes.py
    nodes_retrieval.py

    retriever.py
    embedding.py
    chunker.py

    tools.py

    quiz_nodes.py

    memory.py

    retrieval_config.py

    build_index.py
    build_screenshot_index.py

    cli.py
```

---

# Educational Design Principles

## Retrieval over Structured Resources

The tutor retrieves from:

- Study Notes
- Revision Notes
- Screenshots

rather than raw transcripts.

---

## Graph-Based Orchestration

Each node performs a single responsibility.

Benefits:

- modularity
- easier debugging
- easier experimentation
- scalable workflows

---

## Tool-Based Architecture

Educational capabilities are implemented as tools instead of hard-coded logic.

Future additions require minimal graph changes.

---

## Screenshot-Grounded Learning

Visual lecture content is treated as educational evidence.

Whenever useful, the tutor references diagrams, handwritten explanations, and lecture slides.

---

## Persistent Learning

Students can continue conversations across multiple sessions without losing context.

---

# Output Produced After Week 9

```
tutor/

├── graph.py
├── state.py
├── prompts.py
├── nodes.py
├── nodes_retrieval.py
├── retriever.py
├── tools.py
├── quiz_nodes.py
├── memory.py
├── embedding.py
├── chunker.py
├── build_index.py
├── build_screenshot_index.py
├── cli.py
└── checkpoints.sqlite
```

---

# Current Status (End of Week 9)

Completed

✅ LangGraph Tutor

✅ Persistent Multi-Thread Memory

✅ Query Rewriting

✅ Chapter Routing

✅ Parallel Retrieval

✅ Screenshot Retrieval

✅ Confidence-Aware Responses

✅ Conversation Summarization

✅ Interactive Quiz

✅ Flashcards

✅ Chapter Summaries

✅ Tool Calling Architecture

The interactive AI tutor is complete.

The next stage begins the **Interactive Web Platform**, where the tutor and educational pipeline are integrated into a production-ready frontend and backend application.