import argparse 
import json
import sys
import requests
import os
import asyncio # Added
from typing import Dict, Any, Optional
from mcp_adapter import execute_mcp_tool, load_mcp_config # Added

#deepseek/deepseek-r1-zero:free
#nousresearch/deephermes-3-mistral-24b-preview:free
#mistralai/devstral-small:free
#google/gemma-3n-e4b-it:free
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
    """Extract and format the message from the LLM response."""
    try:
        return response["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        print(f"Response parsing error: {e}", file=sys.stderr)
        print(f"Full response: {json.dumps(response, indent=2)}", file=sys.stderr)
        return "Error: Could not parse LLM response"

async def interactive_mode(model, api_key, system_prompt_text=None, mcp_config=None): # Changed to async def, added mcp_config
    """Run the interactive chat mode."""
    print("OpenRouter Interactive Mode (Ctrl+C or type 'exit' to quit)")
    print(f"Using model: {model}")
    if system_prompt_text:
        print(f"System Prompt: {system_prompt_text}")
    if mcp_config: # Added to print MCP config if present
        print(f"MCP Config loaded: {json.dumps(mcp_config, indent=2)}") # Example, can be more subtle
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
                        llm_tool_name = function_call.get("name") # Renamed for clarity
                        arguments_str = function_call.get("arguments") # Renamed for clarity
                        
                        actual_tool_response_content = ""
                        # Check if mcp_config is present and contains valid config for the tool_name
                        can_execute_mcp = False
                        if mcp_config and "tools" in mcp_config and llm_tool_name in mcp_config["tools"]:
                            tool_mcp_details = mcp_config["tools"][llm_tool_name]
                            if tool_mcp_details.get("server_url") and tool_mcp_details.get("mcp_tool_name"):
                                can_execute_mcp = True

                        if can_execute_mcp:
                            print(f"\nCalling MCP Tool '{llm_tool_name}' via mcp_adapter...")
                            sys.stdout.flush() # Ensure print statements appear before async operations that might block/log
                            print("\nCalling MCP Tool...", end="\r")
                            actual_tool_response_content = await execute_mcp_tool(llm_tool_name, arguments_str, mcp_config)
                            print(" " * 20, end="\r") # Clear "Calling MCP Tool..."
                            print(f"LLM Tool Call to '{llm_tool_name}' status/result:\n{actual_tool_response_content}")
                        else:
                            print(f"\nLLM requests tool: {llm_tool_name} with arguments: {arguments_str} (ID: {tool_call_id}). MCP config not loaded or tool '{llm_tool_name}' not found/incomplete in config. Simulating tool execution.")
                            actual_tool_response_content = f"Simulated output for {llm_tool_name} (MCP not configured or tool details missing)."

                        tool_response_message = {
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "name": llm_tool_name, 
                            "content": actual_tool_response_content # Use actual or simulated content
                        }
                        conversation_history.append(tool_response_message)

                    # After processing all tool calls (if any), send history back to LLM
                    print("\nThinking...", end="\r")
                    final_response_data = send_to_openrouter(conversation_history, model, api_key) # This is synchronous
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
    parser.add_argument("--mcp-config", help="Path to the MCP server configuration JSON file.") # Added
    parser.add_argument("--interactive", "-i", action="store_true", help="Run in interactive mode")
    parser.add_argument("--chat", action="store_true", help="Shortcut for interactive mode")
    args = parser.parse_args()

    mcp_config_data = None # Added
    if args.mcp_config:    # Added
        mcp_config_data = load_mcp_config(args.mcp_config) 
        if mcp_config_data:
            print(f"MCP Config loaded from {args.mcp_config}")
        else:
            print(f"Failed to load MCP Config from {args.mcp_config}")

    # Start interactive mode if explicitly requested with -i or --chat
    # or if no prompt was provided
    if args.interactive or args.chat or not args.prompt:
        asyncio.run(interactive_mode(args.model, args.api_key, args.system_prompt, mcp_config_data)) # Changed to asyncio.run and pass mcp_config_data
    else:
        # Join all prompt arguments into a single string
        # System prompt and MCP config are not used in non-interactive mode in this version
        prompt = " ".join(args.prompt)
        response = send_to_openrouter([{"role": "user", "content": prompt}], args.model, args.api_key)
        if response:
            print(format_response(response))

if __name__ == "__main__":
    main()