# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Application

```bash
# Install dependencies (from project root)
uv sync

# Start the server (from project root)
./run.sh

# Or manually
cd backend && uv run uvicorn app:app --reload --port 8000
```

Requires a `.env` file in the project root with `ANTHROPIC_API_KEY=<key>`.

The app serves at `http://localhost:8000` (frontend + API). API docs at `http://localhost:8000/docs`.

## Architecture

This is a RAG (Retrieval-Augmented Generation) chatbot. The backend is in `backend/`, the frontend in `frontend/`, and course document sources in `docs/`.

### Request Flow

1. Frontend (`frontend/script.js`) POSTs `{ query, session_id }` to `POST /api/query`
2. `backend/app.py` routes to `RAGSystem.query()`
3. `RAGSystem` sends the query to Claude **with a tool definition** (`search_course_content`)
4. Claude decides to call the tool → `CourseSearchTool.execute()` runs a semantic search against ChromaDB
5. Search results are returned to Claude as `tool_result` messages
6. Claude generates the final answer using the retrieved content
7. Sources and answer are returned to the frontend

### Key Design Decisions

**Two-collection ChromaDB setup** (`backend/vector_store.py`):
- `course_catalog` — stores course-level metadata (title, instructor, link). Used for fuzzy course name resolution via semantic search.
- `course_content` — stores text chunks with `course_title` and `lesson_number` metadata. Used for actual content retrieval.

**Tool-based retrieval** — Claude controls when to search (not a fixed pre-retrieval step). The `search_course_content` tool accepts optional `course_name` and `lesson_number` filters. Claude is instructed to search at most once per query.

**Conversation history** is injected into the system prompt (not as message history), formatted as plain text. `SessionManager` keeps the last `MAX_HISTORY=2` exchanges (4 messages).

**Document format** (`backend/document_processor.py`): Course files in `docs/` must follow this structure:
```
Course Title: <title>
Course Link: <url>
Course Instructor: <name>

Lesson 0: <title>
Lesson Link: <url>
<lesson content...>

Lesson 1: <title>
...
```

### Configuration

All tunable parameters are in `backend/config.py`:
- `ANTHROPIC_MODEL` — Claude model used for generation
- `EMBEDDING_MODEL` — Sentence-Transformers model for embeddings (`all-MiniLM-L6-v2`)
- `CHUNK_SIZE` / `CHUNK_OVERLAP` — Text chunking parameters (800 / 100 chars)
- `MAX_RESULTS` — Number of chunks returned per vector search (5)
- `MAX_HISTORY` — Conversation turns retained per session (2)
- `CHROMA_PATH` — ChromaDB persistence path (`./chroma_db`, relative to `backend/`)

### Adding a New Tool

1. Create a class extending `Tool` (ABC) in `backend/search_tools.py`
2. Implement `get_tool_definition()` returning an Anthropic tool schema dict
3. Implement `execute(**kwargs)` returning a string result
4. Register it in `RAGSystem.__init__()` via `self.tool_manager.register_tool(...)`

### Adding Course Documents

Drop `.txt`, `.pdf`, or `.docx` files into `docs/`. They are loaded on startup by `app.py`'s `startup_event`. Already-loaded courses (matched by title) are skipped to avoid duplicates.
