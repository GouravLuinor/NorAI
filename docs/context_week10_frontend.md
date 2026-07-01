# NorAI Frontend — Phases 1–4 Context

## Overview

The frontend is a **React + TypeScript + Vite** application styled with **Tailwind CSS v4** using a custom NorAI dark theme inspired by NotebookLM, Claude Desktop, and Linear.

The application provides a three-panel educational workspace:

- Sidebar (navigation & threads)
- Document Viewer (Study Notes / Revision / Assessment)
- AI Assistant (Tutor / Quiz / Flashcards)

At the current stage the entire frontend is fully functional using realistic mock data.

The next milestone is connecting the UI to the real LangGraph tutor through a FastAPI backend.

---

# Tech Stack

- React 18
- TypeScript
- Vite
- Tailwind CSS v4
- Zustand
- Framer Motion
- react-markdown
- remark-gfm
- rehype-highlight
- lucide-react

---

# Frontend Architecture

The frontend follows a **feature-oriented architecture**.

```
Presentation Layer
        │
        ▼
 React Components
        │
        ▼
 Zustand Stores
        │
        ▼
 API Layer (Phase 5)
        │
        ▼
 FastAPI Backend
        │
        ▼
 LangGraph Tutor
```

Components never communicate directly with the backend.

All server communication will eventually go through a dedicated API layer (Phase 5), keeping UI components independent from networking logic.

Application state is separated into focused stores:

- Thread Store
- Chapter Store
- Quiz Store

This keeps rendering predictable while minimizing unnecessary component updates.

---

# Project Structure

```
src/

components/

    layout/
        Workspace.tsx
        Sidebar.tsx
        DocPanel.tsx
        AIPanel.tsx

    chat/
        ChatArea.tsx
        MessageBubble.tsx
        InputZone.tsx
        ReferencesPanel.tsx
        EvidenceCard.tsx
        ShimmerLoader.tsx

    quiz/
        QuizPanel.tsx

    flashcards/
        FlashcardsPanel.tsx

    doc/
        NotesView.tsx
        RevisionView.tsx
        AssessmentView.tsx

    ui/
        (reserved for future reusable primitives)

stores/

    useThreadStore.ts
    useChapterStore.ts
    useQuizStore.ts

mocks/

    chapters.ts
    messages.ts
    references.ts
    quizData.ts
    revisionData.ts
    notesData.ts
    assessmentData.ts

index.css

App.tsx

main.tsx
```

---

# Design Philosophy

NorAI is **not** designed as a chatbot.

The document is always the primary focus.

The AI exists to assist the learning experience—not replace the study material.

Visual inspiration comes from:

- NotebookLM
- Claude Desktop
- Linear
- Apple Human Interface Guidelines

The interface prioritizes:

- long-form reading
- minimal visual noise
- educational clarity
- smooth interactions
- premium desktop feel

The UI should disappear behind the learning experience.

---

# Phases Completed

## Phase 1 — Frontend Shell

Completed

- Vite project setup
- Tailwind CSS v4 theme
- Custom NorAI dark palette
- Three-panel workspace
- Sidebar
- Document panel
- AI panel
- Zustand stores
- Mock data architecture

---

## Phase 2 — Document Viewer

### Study Notes

- Markdown rendering
- Custom heading styles
- Code blocks
- Tables
- Lists
- Syntax highlighting

### Revision Notes

Educational card system

- Definition
- Algorithm
- Complexity
- Hint
- Common Mistake
- Observation
- Example

### Assessment

- MCQ cards
- True / False
- Free response
- Collapsible answer key
- Progress indicator

---

## Phase 3 — AI Assistant

### Tutor

- Mock streaming
- Markdown rendering
- References panel
- Evidence cards
- Screenshot previews
- Chat input
- Shimmer loading

### Quiz

Interactive quiz supporting

- MCQ
- True / False
- Free response
- Confidence selection
- Evaluation screen
- Score visualization

### Flashcards

- 3D flip animation
- Again / Hard / Good / Easy ratings
- Progress indicators
- Navigation
- Statistics footer

All modes are switchable inside the AI panel.

---

## Phase 4 — UX Polish

Completed

### Workspace

- Custom resizable panels
- Sidebar resize
- AI panel resize
- Collapse / Expand sidebar
- Smooth resizing
- Width persistence

### Interactions

- Ripple effects
- Framer Motion transitions
- Animated AI mode switching
- Keyboard shortcuts
- Responsive chat layout

### Keyboard

- Enter → Send
- Escape → Collapse Sidebar

### Visual Polish

- Custom scrollbar
- Streaming animation
- Loading shimmer
- Responsive layouts
- Hover interactions

---

# Workspace Behaviour

Resizable

- Sidebar
- Document Panel
- AI Panel

Persistent

- Sidebar width
- AI panel width
- Sidebar collapse state

Animated

- Sidebar collapse
- Tutor / Quiz / Flashcard switching
- Ripple interactions
- Streaming messages

Keyboard

- Enter → Send message
- Escape → Collapse sidebar

---

# Key Design Decisions

### No Component Library

All UI components are custom-built using Tailwind.

This keeps the interface lightweight and highly customizable.

---

### Mock-first Development

Every feature works with realistic mock data.

The UI can be developed independently from the backend.

---

### Zustand

Simple state management without unnecessary boilerplate.

---

### CSS Variables

Entire application uses a centralized NorAI theme through CSS variables.

---

### Grid Layout

The workspace uses CSS Grid with animated width variables.

---

### Custom Resize System

Instead of external resize libraries, the workspace uses a custom resize implementation for reliability and full control.

---

### Ripple Effects

Pure CSS implementation.

No JavaScript required.

---

### Motion

Framer Motion is only used where motion improves usability.

Animations remain subtle.

---

# Current Status

The frontend is feature complete.

Implemented

- Workspace
- Study Notes
- Revision Notes
- Assessment Viewer
- Tutor
- Quiz
- Flashcards
- Sidebar
- Resizable Panels
- Keyboard Shortcuts
- Animations
- Mock Data Architecture

Everything currently runs using local mock data.

---

# Not Yet Implemented

The UI is complete but still disconnected from the production backend.

Remaining work:

- Real tutor responses
- LangGraph integration
- FastAPI API layer
- Server-side streaming
- Real retrieval references
- Screenshot retrieval
- Real thread persistence
- Quiz backend integration
- Flashcard backend integration
- Dynamic chapter loading
- Loading generated Markdown
- Loading generated PDFs

---

# Planned UX Improvements

Post backend integration:

- AI ↔ Document synchronization
- Persistent workspace state
- Reading progress indicator
- Universal search (Ctrl + K)
- Image lightbox
- Keyboard-first flashcards
- Contextual quick actions
- Better empty states
- Better loading skeletons

---

# Next Phase

## Phase 5 — Backend Integration (FastAPI + LangGraph)

Goals

- Wrap the LangGraph tutor with FastAPI
- Connect Tutor Chat to the real backend
- Replace all mock data
- Enable streaming responses
- Serve generated study notes
- Serve revision notes
- Serve assessments
- Serve screenshots
- Support thread persistence

After Phase 5 the frontend will become fully functional using NorAI's real AI pipeline.

---

# How to Resume

Paste this entire document into a new chat.

This provides sufficient context to continue frontend development from **Phase 5** without requiring previous conversation history.