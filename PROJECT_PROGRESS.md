# NorAI - Project Progress

## Project Vision

NorAI is an AI-powered Lecture Revision Assistant that transforms long educational videos into an intelligent study companion.

Pipeline:

Video
→ Audio Extraction
→ Transcription
→ Chunking
→ Embeddings
→ Vector Database
→ Retrieval
→ Question Answering

---

# Current Architecture

Video
↓
Ingestion
↓
Audio Extraction
↓
Transcription
↓
Chunking
↓
Embeddings
↓
ChromaDB
↓
Retrieval

---

# Week 1 - Ingestion Pipeline ✅

Completed:

* Local video ingestion
* YouTube video ingestion
* Google Drive video ingestion
* Audio extraction using ffmpeg
* Metadata generation
* Duration tracking
* Error handling
* File validation

Output:

* video.mp4
* audio.mp3
* metadata.json

---

# Week 2 - Transcription Pipeline ✅

Completed:

* Faster-Whisper integration
* Timestamped transcripts
* TXT transcript export
* JSON transcript export
* Metadata integration
* Language detection
* Long lecture validation

Output Schema:

{
"source": {...},
"segments": [...]
}

Notes:

* No chunking performed during transcription.
* Raw Whisper segments preserved.

---

# Week 3 - Chunking Pipeline ✅

Completed:

* Transcript loading
* Segment-based chunking
* Timestamp preservation
* Chunk metadata schema
* Segment tracking
* Duration tracking
* JSON chunk export

Chunk Schema:

{
"chunk_id": 0,
"start": 0.0,
"end": 57.4,
"duration": 57.4,
"segment_start": 0,
"segment_end": 14,
"segment_ids": [...],
"text": "..."
}

Validation:

* 518 transcript segments
* 35 generated chunks

---

# Week 4 - Embeddings & Retrieval ✅

Completed:

* Sentence Transformers integration
* all-MiniLM-L6-v2 embeddings
* Embedding generation
* ChromaDB integration
* Metadata storage
* Semantic retrieval
* Retrieval validation

Validation Queries:

* What is a segment tree?
* Why do we use segment trees?
* Range query problem
* Full binary tree
* O(log n)

Results:

* Relevant chunks retrieved successfully
* Non-existent concepts (e.g. lazy propagation) correctly produced low-confidence matches

Current Status:

Question
↓
Embedding
↓
Chroma Search
↓
Top-K Chunks

Working successfully.

---

# Upcoming Work

## Week 5 - Question Answering

Goal:

Question
↓
Retrieval
↓
Context Construction
↓
LLM
↓
Grounded Answer

Features:

* Context assembly
* Prompt engineering
* Citation support
* Answer generation

---

# Future Roadmap

Planned Features:

* Semantic chunking
* Quiz generation
* Notes generation
* Revision mode
* Multi-video retrieval
* Lecture comparison
* Web UI
* User authentication
* Personal knowledge base

---

# Lessons Learned

* Preserve timestamps as early as possible.
* Keep modules single-responsibility.
* Chunking and transcription should remain separate concerns.
* Retrieval quality should be measured before introducing more complexity.
* Metadata preservation is critical for citations.

---

Last Updated:

Week 4 Complete
