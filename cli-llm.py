import argparse 
import json
import sys
import requests
import os
from typing import Dict, Any, Optional

def send_to_openrouter(messages: list, model: str = "nousresearch/deephermes-3-mistral-24b-preview:free", api_key: Optional[str] = None) -> Optional[Dict[Any, Any]]:
    """
    Send messages to openrouter and return response.
    Args: 
    messages: list of messages to send
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
        "messages": messages
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

def interactive_mode(model, api_key, system_prompt_text=None):
    """Run the interactive chat mode."""
    print("OpenRouter Interactive Mode (Ctrl+C or type 'exit' to quit)")
    print(f"Using model: {model}")
    if system_prompt_text:
        print(f"System Prompt: {system_prompt_text}")
    print("-" * 50)
    
    if system_prompt_text:
        conversation_history = [{"role": "system", "content": system_prompt_text}]
    else:
        conversation_history = []
        
    try:
        while True:
            prompt = input("\nYou: ")
            if prompt.strip().lower() in ["exit", "quit"]:
                break
            
            conversation_history.append({"role": "user", "content": prompt})
                
            print("\nThinking...", end="\r")
            response_data = send_to_openrouter(conversation_history, model, api_key)
            if response_data:
                print(" " * 10, end="\r")  # Clear "Thinking..."
                
                try:
                    assistant_message_object = response_data["choices"][0]["message"]
                except (KeyError, IndexError, TypeError) as e:
                    print(f"\nError: Could not parse LLM response structure: {e}", file=sys.stderr)
                    print(f"Full response: {json.dumps(response_data, indent=2)}", file=sys.stderr)
                    continue # Skip to next iteration

                tool_calls = assistant_message_object.get("tool_calls")

                if tool_calls:
                    conversation_history.append(assistant_message_object) # Append message with tool_calls

                    for tool_call in tool_calls:
                        tool_call_id = tool_call.get("id")
                        function_call = tool_call.get("function", {})
                        tool_name = function_call.get("name")
                        tool_arguments = function_call.get("arguments") # Often a JSON string

                        print(f"\nLLM requests tool: {tool_name} with arguments: {tool_arguments} (ID: {tool_call_id})")
                        
                        tool_response_content = f"Simulated output for {tool_name}."
                        tool_response_message = {
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "name": tool_name, 
                            "content": tool_response_content
                        }
                        conversation_history.append(tool_response_message)

                    print("\nThinking...", end="\r")
                    final_response_data = send_to_openrouter(conversation_history, model, api_key)
                    print(" " * 10, end="\r") # Clear "Thinking..."

                    if final_response_data:
                        try:
                            final_assistant_message_object = final_response_data["choices"][0]["message"]
                            final_assistant_content = final_assistant_message_object.get("content", "")
                            print(f"\nLLM: {final_assistant_content}")
                            # Append the final assistant message content to history
                            conversation_history.append({"role": "assistant", "content": final_assistant_content})
                        except (KeyError, IndexError, TypeError) as e:
                            print(f"\nError: Could not parse final LLM response structure: {e}", file=sys.stderr)
                            print(f"Full response: {json.dumps(final_response_data, indent=2)}", file=sys.stderr)
                    else:
                        print("\nLLM: No further response after tool calls.")
                else:
                    # No tool_calls, proceed as normal
                    assistant_content = assistant_message_object.get("content", "")
                    print(f"\nLLM: {assistant_content}")
                    conversation_history.append(assistant_message_object) # Append original assistant message
            else:
                # Initial response failed
                print("\nLLM: Failed to get a response.")

    except KeyboardInterrupt:
        print("\nExiting interactive mode")

def main():
    parser = argparse.ArgumentParser(description="Send a prompt to OpenRouter and get a response")
    parser.add_argument("prompt", nargs="*", help="The prompt to send to the LLM")
    parser.add_argument("--model", "-m", default="nousresearch/deephermes-3-mistral-24b-preview:free", help="Model to use")
    parser.add_argument("--api-key", "-k", help="OpenRouter API key")
    parser.add_argument("--system-prompt", "-sp", help="An initial system prompt for the conversation")
    parser.add_argument("--interactive", "-i", action="store_true", help="Run in interactive mode")
    parser.add_argument("--chat", action="store_true", help="Shortcut for interactive mode")
    args = parser.parse_args()
    
    # Start interactive mode if explicitly requested with -i or --chat
    # or if no prompt was provided
    if args.interactive or args.chat or not args.prompt:
        interactive_mode(args.model, args.api_key, args.system_prompt)
    else:
        # Join all prompt arguments into a single string
        # System prompt is not used in non-interactive mode in this version
        prompt = " ".join(args.prompt)
        response = send_to_openrouter([{"role": "user", "content": prompt}], args.model, args.api_key)
        if response:
            print(format_response(response))

if __name__ == "__main__":
    main()