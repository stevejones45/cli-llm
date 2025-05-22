import argparse 
import json
import sys
import requests
import os
from typing import Dict, Any, Optional

def send_to_openrouter(prompt: str, model: str = "nousresearch/deephermes-3-mistral-24b-preview:free", api_key: Optional[str] = None) -> Optional[Dict[Any, Any]]:
    """
    Send prompt to openrouter and return response.
    Args: 
    prompt: user message to send
    model: the model to use
    api_key: openrouter API key
    """
    
    if not api_key:
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            print("Error: No API key provided. Set OPENROUTER_API_KEY environment variable or use --api-key", file=sys.stderr)
            return None
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://localhost", # OpenRouter requires this
        "X-Title": "Terminal LLM Client" # Optional title 
    }
    
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }
    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions",
                                 headers=headers,
                                 json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error: Failed to communicate with OpenRouter: {e}", file=sys.stderr)
        return None

def format_response(response: Dict[Any, Any]) -> str:
    """Extract amd format the message from the LLM response."""
    try:
        return response["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        print(f"Response parsing error: {e}", file=sys.stderr)
        print(f"Full response: {json.dumps(response, indent=2)}", file=sys.stderr)
        return "Error: Could not parse LLM response"

def interactive_mode(model, api_key):
    """Run the interactive chat mode."""
    print("OpenRouter Interactive Mode (Ctrl+C or type 'exit' to quit)")
    print(f"Using model: {model}")
    print("-" * 50)
    try:
        while True:
            prompt = input("\nYou: ")
            if prompt.strip().lower() in ["exit", "quit"]:
                break
                
            print("\nThinking...", end="\r")
            response = send_to_openrouter(prompt, model, api_key)
            if response:
                print(" " * 10, end="\r")  # Clear "Thinking..."
                print("\nLLM:", format_response(response))
    except KeyboardInterrupt:
        print("\nExiting interactive mode")

def main():
    parser = argparse.ArgumentParser(description="Send a prompt to OpenRouter and get a response")
    parser.add_argument("prompt", nargs="*", help="The prompt to send to the LLM")
    parser.add_argument("--model", "-m", default="nousresearch/deephermes-3-mistral-24b-preview:free", help="Model to use")
    parser.add_argument("--api-key", "-k", help="OpenRouter API key")
    parser.add_argument("--interactive", "-i", action="store_true", help="Run in interactive mode")
    parser.add_argument("--chat", action="store_true", help="Shortcut for interactive mode")
    args = parser.parse_args()
    
    # Start interactive mode if explicitly requested with -i or --chat
    # or if no prompt was provided
    if args.interactive or args.chat or not args.prompt:
        interactive_mode(args.model, args.api_key)
    else:
        # Join all prompt arguments into a single string
        prompt = " ".join(args.prompt)
        response = send_to_openrouter(prompt, args.model, args.api_key)
        if response:
            print(format_response(response))

if __name__ == "__main__":
    main()