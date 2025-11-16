# Implementation Plan: vLLama (vLLM + Ollama Features)

**Project:** High-performance LLM server combining vLLM's speed with Ollama's UX
**Architecture Pattern:** Following RA.Aid's three-stage methodology

---

## Research Summary (Stage 1 - Completed)

### Findings:
1. **vLLM** provides OpenAI-compatible API with superior performance (V1: 1.7x faster)
2. **Ollama** provides user-friendly model management and API
3. **Gap:** No tool combining vLLM performance with Ollama simplicity
4. **Opportunity:** Build compatibility layer

### Key Technical Details:
- vLLM runs on `http://localhost:8000/v1/*` (OpenAI format)
- Ollama runs on `http://localhost:11434/api/*` (Ollama format)
- Both support chat, completions, embeddings
- vLLM V1 has zero-overhead prefix caching, chunked prefill

---

## Implementation Plan (Stage 2)

### Project Structure:
```
vllama/
├── __init__.py
├── __main__.py          # CLI entry point
├── server.py            # FastAPI server with dual API support
├── models.py            # Model management (Ollama-style)
├── vllm_client.py       # vLLM backend client
├── config.py            # Configuration
├── README.md
├── pyproject.toml
└── tests/
    └── test_server.py
```

### Components to Build:

#### 1. FastAPI Server (`server.py`)
**Purpose:** Dual API support - OpenAI + Ollama endpoints

**Endpoints to implement:**
- `/v1/chat/completions` (OpenAI) → proxy to vLLM
- `/v1/completions` (OpenAI) → proxy to vLLM
- `/api/chat` (Ollama) → convert to vLLM format
- `/api/generate` (Ollama) → convert to vLLM format
- `/api/tags` (Ollama) → list available models
- `/api/show` (Ollama) → show model details

**Dependencies:** FastAPI, uvicorn, httpx (for vLLM client)

#### 2. Model Management (`models.py`)
**Purpose:** Track available models, convert Ollama model names to vLLM format

**Features:**
- Model registry (in-memory for v1, could add SQLite later)
- Name mapping (e.g., "llama3:8b" → "meta-llama/Llama-3-8B")
- Model info metadata

#### 3. vLLM Client (`vllm_client.py`)
**Purpose:** Async client for vLLM backend

**Features:**
- HTTP client to vLLM server (localhost:8000)
- Request/response handling
- Streaming support
- Error handling

#### 4. Request Converters
**Purpose:** Convert between Ollama and OpenAI formats

**Conversions needed:**
```python
# Ollama /api/chat format
{
  "model": "llama3",
  "messages": [...],
  "stream": true
}

# OpenAI /v1/chat/completions format
{
  "model": "meta-llama/Llama-3-8B",
  "messages": [...],
  "stream": true
}
```

#### 5. CLI (`__main__.py`)
**Purpose:** Easy server startup

```bash
vllama serve --port 11434 --vllm-url http://localhost:8000
vllama models list
vllama models pull <model>  # Future: auto-download from HF
```

---

## Implementation Steps (Stage 3 Preview)

### Step 1: Project Setup
- Create directory structure
- Set up pyproject.toml
- Initialize git repository

### Step 2: Core Server
- Implement FastAPI app
- Add health check endpoint
- Add basic OpenAI proxy

### Step 3: Ollama API Compatibility
- Implement `/api/chat` endpoint
- Implement `/api/generate` endpoint
- Add request format conversion

### Step 4: Model Management
- Implement model registry
- Add `/api/tags` endpoint
- Add name mapping logic

### Step 5: Testing & Documentation
- Write unit tests
- Create README with examples
- Add docker-compose for easy setup

---

## Technical Decisions

### Why FastAPI?
- Async/await support for high performance
- Built-in OpenAPI docs
- Easy to test

### Why Proxy Pattern?
- Let vLLM handle inference (it's optimized for this)
- Focus on API translation and UX
- Simpler than reimplementing inference

### Why In-Memory Model Registry First?
- Faster to implement
- Good enough for v1
- Can add persistence later

---

## Success Criteria

1. ✅ Server starts and responds to health checks
2. ✅ OpenAI API endpoints work (proxy to vLLM)
3. ✅ Ollama `/api/chat` works with format conversion
4. ✅ Model listing returns available models
5. ✅ Streaming works for both API formats
6. ✅ README has clear setup instructions

---

## Out of Scope (Future Work)

- Automatic model downloads from HuggingFace
- Modelfile parsing and custom model creation
- GPU resource management
- Multi-model serving
- Authentication/API keys
- Metrics and monitoring

---

## Estimated Effort

- **Core Server:** 2-3 hours
- **API Compatibility:** 2-3 hours
- **Model Management:** 1-2 hours
- **Testing & Docs:** 1-2 hours
- **Total:** ~6-10 hours for MVP

---

## Next Step

Proceed to **Stage 3: Implementation** - Build the components in order.
