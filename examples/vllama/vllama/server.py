"""FastAPI server with both OpenAI and Ollama compatible endpoints."""

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Literal
import json
from datetime import datetime

from .config import settings
from .models import registry, ModelInfo
from .vllm_client import VLLMClient


app = FastAPI(
    title="vLLama",
    description="High-performance LLM server combining vLLM's speed with Ollama's UX",
    version="0.1.0"
)


# ============================================================================
# Pydantic Models for Request/Response
# ============================================================================

class Message(BaseModel):
    """Chat message."""
    role: Literal["system", "user", "assistant"]
    content: str


class OpenAIChatRequest(BaseModel):
    """OpenAI chat completion request."""
    model: str
    messages: List[Message]
    stream: bool = False
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None


class OllamaChatRequest(BaseModel):
    """Ollama chat request."""
    model: str
    messages: List[Message]
    stream: bool = False
    options: Optional[Dict[str, Any]] = None


class OllamaGenerateRequest(BaseModel):
    """Ollama generate request."""
    model: str
    prompt: str
    stream: bool = False
    options: Optional[Dict[str, Any]] = None


class OllamaTagsResponse(BaseModel):
    """Ollama tags (list models) response."""
    models: List[ModelInfo]


class OllamaShowRequest(BaseModel):
    """Ollama show model request."""
    name: str


# ============================================================================
# Health and Info Endpoints
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "vLLama",
        "version": "0.1.0",
        "description": "vLLM + Ollama compatibility layer",
        "endpoints": {
            "openai": ["/v1/chat/completions", "/v1/completions"],
            "ollama": ["/api/chat", "/api/generate", "/api/tags", "/api/show"]
        }
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    async with VLLMClient() as client:
        vllm_healthy = await client.health_check()

    return {
        "status": "healthy" if vllm_healthy else "degraded",
        "vllm_backend": "healthy" if vllm_healthy else "unhealthy",
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# OpenAI-Compatible Endpoints (Proxy to vLLM)
# ============================================================================

@app.post("/v1/chat/completions")
async def openai_chat_completions(request: OpenAIChatRequest):
    """
    OpenAI chat completions endpoint.

    Proxies directly to vLLM backend.
    """
    async with VLLMClient() as client:
        try:
            # Convert pydantic models to dicts for vLLM
            messages = [msg.model_dump() for msg in request.messages]

            # Build kwargs
            kwargs = {}
            if request.temperature is not None:
                kwargs["temperature"] = request.temperature
            if request.max_tokens is not None:
                kwargs["max_tokens"] = request.max_tokens
            if request.top_p is not None:
                kwargs["top_p"] = request.top_p

            if request.stream:
                # Streaming response
                async def generate():
                    async for chunk in await client.chat_completion(
                        messages=messages,
                        model=request.model,
                        stream=True,
                        **kwargs
                    ):
                        yield f"data: {json.dumps(chunk)}\n\n"
                    yield "data: [DONE]\n\n"

                return StreamingResponse(generate(), media_type="text/event-stream")
            else:
                # Non-streaming response
                result = await client.chat_completion(
                    messages=messages,
                    model=request.model,
                    stream=False,
                    **kwargs
                )
                return result

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/completions")
async def openai_completions(
    model: str,
    prompt: str,
    stream: bool = False,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None
):
    """
    OpenAI completions endpoint.

    Proxies directly to vLLM backend.
    """
    async with VLLMClient() as client:
        try:
            kwargs = {}
            if temperature is not None:
                kwargs["temperature"] = temperature
            if max_tokens is not None:
                kwargs["max_tokens"] = max_tokens

            if stream:
                async def generate():
                    async for chunk in await client.completion(
                        prompt=prompt,
                        model=model,
                        stream=True,
                        **kwargs
                    ):
                        yield f"data: {json.dumps(chunk)}\n\n"
                    yield "data: [DONE]\n\n"

                return StreamingResponse(generate(), media_type="text/event-stream")
            else:
                result = await client.completion(
                    prompt=prompt,
                    model=model,
                    stream=False,
                    **kwargs
                )
                return result

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Ollama-Compatible Endpoints (Format Conversion)
# ============================================================================

@app.post("/api/chat")
async def ollama_chat(request: OllamaChatRequest):
    """
    Ollama chat endpoint.

    Converts Ollama format to OpenAI format and calls vLLM.
    """
    # Convert Ollama model name to vLLM model name
    vllm_model = registry.get_vllm_model_name(request.model)

    async with VLLMClient() as client:
        try:
            # Convert messages
            messages = [msg.model_dump() for msg in request.messages]

            # Extract options
            kwargs = {}
            if request.options:
                if "temperature" in request.options:
                    kwargs["temperature"] = request.options["temperature"]
                if "num_predict" in request.options:
                    kwargs["max_tokens"] = request.options["num_predict"]
                if "top_p" in request.options:
                    kwargs["top_p"] = request.options["top_p"]

            if request.stream:
                # Streaming: convert OpenAI format to Ollama format
                async def generate():
                    async for chunk in await client.chat_completion(
                        messages=messages,
                        model=vllm_model,
                        stream=True,
                        **kwargs
                    ):
                        # Convert OpenAI chunk to Ollama format
                        ollama_chunk = {
                            "model": request.model,
                            "created_at": datetime.now().isoformat(),
                            "message": {
                                "role": "assistant",
                                "content": chunk.get("choices", [{}])[0]
                                .get("delta", {})
                                .get("content", "")
                            },
                            "done": False
                        }
                        yield json.dumps(ollama_chunk) + "\n"

                    # Final chunk
                    yield json.dumps({"done": True}) + "\n"

                return StreamingResponse(generate(), media_type="application/x-ndjson")
            else:
                # Non-streaming
                result = await client.chat_completion(
                    messages=messages,
                    model=vllm_model,
                    stream=False,
                    **kwargs
                )

                # Convert OpenAI response to Ollama format
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                return {
                    "model": request.model,
                    "created_at": datetime.now().isoformat(),
                    "message": {
                        "role": "assistant",
                        "content": content
                    },
                    "done": True,
                    "total_duration": 0,
                    "load_duration": 0,
                    "prompt_eval_count": result.get("usage", {}).get("prompt_tokens", 0),
                    "eval_count": result.get("usage", {}).get("completion_tokens", 0)
                }

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/generate")
async def ollama_generate(request: OllamaGenerateRequest):
    """
    Ollama generate endpoint.

    Converts to OpenAI completion format and calls vLLM.
    """
    vllm_model = registry.get_vllm_model_name(request.model)

    async with VLLMClient() as client:
        try:
            kwargs = {}
            if request.options:
                if "temperature" in request.options:
                    kwargs["temperature"] = request.options["temperature"]
                if "num_predict" in request.options:
                    kwargs["max_tokens"] = request.options["num_predict"]

            if request.stream:
                async def generate():
                    async for chunk in await client.completion(
                        prompt=request.prompt,
                        model=vllm_model,
                        stream=True,
                        **kwargs
                    ):
                        ollama_chunk = {
                            "model": request.model,
                            "created_at": datetime.now().isoformat(),
                            "response": chunk.get("choices", [{}])[0].get("text", ""),
                            "done": False
                        }
                        yield json.dumps(ollama_chunk) + "\n"

                    yield json.dumps({"done": True}) + "\n"

                return StreamingResponse(generate(), media_type="application/x-ndjson")
            else:
                result = await client.completion(
                    prompt=request.prompt,
                    model=vllm_model,
                    stream=False,
                    **kwargs
                )

                return {
                    "model": request.model,
                    "created_at": datetime.now().isoformat(),
                    "response": result.get("choices", [{}])[0].get("text", ""),
                    "done": True,
                    "total_duration": 0,
                    "load_duration": 0,
                    "prompt_eval_count": result.get("usage", {}).get("prompt_tokens", 0),
                    "eval_count": result.get("usage", {}).get("completion_tokens", 0)
                }

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tags")
async def ollama_tags():
    """
    Ollama tags endpoint - lists available models.
    """
    models = registry.list_models()
    return {"models": [model.model_dump() for model in models]}


@app.post("/api/show")
async def ollama_show(request: OllamaShowRequest):
    """
    Ollama show endpoint - show model details.
    """
    model = registry.get_model(request.name)
    if not model:
        raise HTTPException(status_code=404, detail=f"Model {request.name} not found")

    return {
        "modelfile": f"# Modelfile for {model.name}",
        "parameters": model.details,
        "template": "{{ .System }}\n{{ .Prompt }}",
        "details": {
            "format": "gguf",
            "family": model.name.split(":")[0],
            "parameter_size": model.details.get("parameter_size", "unknown"),
            "quantization_level": model.details.get("quantization_level", "unknown")
        }
    }
