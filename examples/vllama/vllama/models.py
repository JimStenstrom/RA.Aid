"""Model management and registry for vLLama."""

from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel


class ModelInfo(BaseModel):
    """Information about a model."""

    name: str
    model: str  # Actual model path for vLLM
    modified_at: datetime = datetime.now()
    size: int = 0
    digest: str = ""
    details: Dict = {}


class ModelRegistry:
    """
    Simple in-memory model registry.

    Maps Ollama-style model names to vLLM model paths.
    """

    def __init__(self):
        self._models: Dict[str, ModelInfo] = {}
        self._initialize_default_models()

    def _initialize_default_models(self):
        """Initialize with common model mappings."""
        default_models = [
            ModelInfo(
                name="llama3:8b",
                model="meta-llama/Llama-3-8B",
                size=8_000_000_000,
                digest="sha256:llama3-8b",
                details={
                    "parameter_size": "8B",
                    "quantization_level": "fp16"
                }
            ),
            ModelInfo(
                name="llama3:70b",
                model="meta-llama/Llama-3-70B",
                size=70_000_000_000,
                digest="sha256:llama3-70b",
                details={
                    "parameter_size": "70B",
                    "quantization_level": "fp16"
                }
            ),
            ModelInfo(
                name="mistral:7b",
                model="mistralai/Mistral-7B-v0.1",
                size=7_000_000_000,
                digest="sha256:mistral-7b",
                details={
                    "parameter_size": "7B",
                    "quantization_level": "fp16"
                }
            ),
        ]

        for model in default_models:
            self._models[model.name] = model

    def get_model(self, name: str) -> Optional[ModelInfo]:
        """Get model info by name."""
        return self._models.get(name)

    def get_vllm_model_name(self, ollama_name: str) -> str:
        """
        Convert Ollama model name to vLLM model path.

        If not found in registry, return as-is (assume it's already a vLLM path).
        """
        model_info = self.get_model(ollama_name)
        if model_info:
            return model_info.model
        return ollama_name

    def list_models(self) -> List[ModelInfo]:
        """List all registered models."""
        return list(self._models.values())

    def add_model(self, model_info: ModelInfo):
        """Add or update a model in the registry."""
        self._models[model_info.name] = model_info

    def remove_model(self, name: str) -> bool:
        """Remove a model from the registry."""
        if name in self._models:
            del self._models[name]
            return True
        return False


# Global registry instance
registry = ModelRegistry()
