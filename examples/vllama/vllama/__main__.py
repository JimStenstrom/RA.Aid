"""CLI entry point for vLLama."""

import argparse
import uvicorn
from .config import settings
from .models import registry


def serve_command(args):
    """Start the vLLama server."""
    print(f"🦙 Starting vLLama server on {args.host}:{args.port}")
    print(f"📡 vLLM backend: {args.vllm_url}")
    print()
    print("Available endpoints:")
    print("  OpenAI-compatible:")
    print(f"    http://{args.host}:{args.port}/v1/chat/completions")
    print(f"    http://{args.host}:{args.port}/v1/completions")
    print("  Ollama-compatible:")
    print(f"    http://{args.host}:{args.port}/api/chat")
    print(f"    http://{args.host}:{args.port}/api/generate")
    print(f"    http://{args.host}:{args.port}/api/tags")
    print()

    # Update settings
    settings.host = args.host
    settings.port = args.port
    settings.vllm_url = args.vllm_url

    # Start server
    uvicorn.run(
        "vllama.server:app",
        host=args.host,
        port=args.port,
        log_level="info"
    )


def models_list_command(args):
    """List available models."""
    models = registry.list_models()
    if not models:
        print("No models registered.")
        return

    print("Available models:")
    print()
    for model in models:
        size_gb = model.size / 1_000_000_000
        print(f"  {model.name}")
        print(f"    vLLM model: {model.model}")
        print(f"    Size: {size_gb:.1f}GB")
        print(f"    Modified: {model.modified_at}")
        print()


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="vLLama: vLLM with Ollama-compatible API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start server
  vllama serve

  # Start server on custom port
  vllama serve --port 8080

  # List available models
  vllama models list

For more information, visit: https://github.com/yourusername/vllama
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Serve command
    serve_parser = subparsers.add_parser("serve", help="Start the vLLama server")
    serve_parser.add_argument(
        "--host",
        default=settings.host,
        help=f"Host to bind to (default: {settings.host})"
    )
    serve_parser.add_argument(
        "--port",
        type=int,
        default=settings.port,
        help=f"Port to bind to (default: {settings.port})"
    )
    serve_parser.add_argument(
        "--vllm-url",
        default=settings.vllm_url,
        help=f"vLLM backend URL (default: {settings.vllm_url})"
    )
    serve_parser.set_defaults(func=serve_command)

    # Models command
    models_parser = subparsers.add_parser("models", help="Model management")
    models_subparsers = models_parser.add_subparsers(dest="models_command")

    list_parser = models_subparsers.add_parser("list", help="List available models")
    list_parser.set_defaults(func=models_list_command)

    # Parse and execute
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
