import json
import sys
import asyncio
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client
# from mcp import types # Not immediately needed, will add if required

def load_mcp_config(config_path: str) -> dict:
    """
    Loads and parses a JSON configuration file.

    Args:
        config_path: The path to the JSON configuration file.

    Returns:
        A dictionary representing the parsed JSON content, 
        or an empty dictionary if an error occurs.
    """
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        return config
    except FileNotFoundError:
        print(f"Error: MCP config file not found at {config_path}", file=sys.stderr)
        return {}
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in MCP config file at {config_path}", file=sys.stderr)
        return {}
    except Exception as e:
        print(f"An unexpected error occurred while loading MCP config from {config_path}: {e}", file=sys.stderr)
        return {}

if __name__ == '__main__':
    # Example usage for testing
    # Create a dummy mcp_config.json for this test
    dummy_config_content = {
        "tools": {
            "get_weather": {
                "server_url": "http://localhost:8001/mcp",
                "mcp_tool_name": "fetch_weather_data",
                "transport": "streamable-http"
            }
        }
    }
    dummy_file_path = "mcp_config.json"
    with open(dummy_file_path, 'w') as f:
        json.dump(dummy_config_content, f, indent=2)

    print(f"Attempting to load '{dummy_file_path}'...")
    config_data = load_mcp_config(dummy_file_path)
    if config_data:
        print("MCP Config loaded successfully:")
        print(json.dumps(config_data, indent=2))
    else:
        print("Failed to load MCP config.")

    print("\nAttempting to load a non-existent file 'non_existent_config.json'...")
    config_data_non_existent = load_mcp_config("non_existent_config.json")
    if not config_data_non_existent:
        print("Failed to load non-existent MCP config as expected.")
    
    # Create a dummy invalid mcp_config.json for this test
    invalid_config_content = """
    {
        "tools": {
            "get_weather": {
                "server_url": "http://localhost:8001/mcp",
                "mcp_tool_name": "fetch_weather_data",
                "transport": "streamable-http"
            }
        } 
        // Missing closing brace, or extra comma, etc.
    """ # Invalid due to comment and potentially structure if not careful
    # Let's make it more clearly invalid
    invalid_config_content_definitely = '{"key": "value", error here}'

    dummy_invalid_file_path = "mcp_config_invalid.json"
    with open(dummy_invalid_file_path, 'w') as f:
        f.write(invalid_config_content_definitely)
    
    print(f"\nAttempting to load invalid '{dummy_invalid_file_path}'...")
    config_data_invalid = load_mcp_config(dummy_invalid_file_path)
    if not config_data_invalid:
        print("Failed to load invalid MCP config as expected.")
    
    # Clean up dummy files
    import os
    if os.path.exists(dummy_file_path):
        os.remove(dummy_file_path)
    if os.path.exists(dummy_invalid_file_path):
        os.remove(dummy_invalid_file_path)


async def execute_mcp_tool(llm_tool_name: str, arguments_str: str, mcp_config: dict) -> str:
    """
    Executes a tool via MCP using the streamable-http transport.

    Args:
        llm_tool_name: The name of the tool as known by the LLM.
        arguments_str: A JSON string representing the arguments for the tool.
        mcp_config: The MCP configuration dictionary.

    Returns:
        A string which is either the JSON representation of the tool's result
        or an error message.
    """
    try:
        arguments_dict = json.loads(arguments_str)
    except json.JSONDecodeError as e:
        error_msg = f"Error: Invalid arguments JSON format for tool {llm_tool_name}. Details: {e}"
        print(error_msg, file=sys.stderr)
        return error_msg

    if not mcp_config or "tools" not in mcp_config:
        error_msg = f"Error: MCP configuration is missing or does not contain a 'tools' section."
        print(error_msg, file=sys.stderr)
        return error_msg
        
    tool_config = mcp_config["tools"].get(llm_tool_name)
    if not tool_config:
        error_msg = f"Error: Tool '{llm_tool_name}' not found in MCP configuration."
        print(error_msg, file=sys.stderr)
        return error_msg

    server_url = tool_config.get("server_url")
    actual_mcp_tool_name = tool_config.get("mcp_tool_name")
    transport = tool_config.get("transport", "streamable-http") # Default to streamable-http

    if not server_url or not actual_mcp_tool_name:
        error_msg = f"Error: Configuration for tool '{llm_tool_name}' is incomplete. Missing 'server_url' or 'mcp_tool_name'."
        print(error_msg, file=sys.stderr)
        return error_msg

    if transport != "streamable-http":
        error_msg = f"Error: Unsupported transport '{transport}' for tool '{llm_tool_name}'. Only 'streamable-http' is currently supported by this adapter."
        print(error_msg, file=sys.stderr)
        return error_msg

    try:
        # The MCP client components expect the server_url to be just scheme+host+port, 
        # and the path ('/mcp') is often implied or configured separately in some MCP server setups.
        # However, the mcp.client.streamable_http.streamablehttp_client takes the full URL including the path.
        # Let's assume server_url in config is like "http://localhost:8001" and path is "/mcp"
        # The example `streamablehttp_client(base_url + "/mcp")` suggests this.
        # If server_url in config is "http://localhost:8001/mcp", then it's fine.
        # We'll assume server_url in the config is the full base URL including the path.

        async with streamablehttp_client(server_url) as (read_stream, write_stream, _): # _ is auth_handler
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tool_result_obj = await session.call_tool(actual_mcp_tool_name, arguments=arguments_dict)
                
                if isinstance(tool_result_obj, (dict, list)):
                    return json.dumps(tool_result_obj)
                return str(tool_result_obj)
                
    except ConnectionRefusedError:
        error_msg = f"Error: Connection refused by MCP server at {server_url} for tool {llm_tool_name} (MCP name: {actual_mcp_tool_name})."
        print(error_msg, file=sys.stderr)
        return error_msg
    except json.JSONDecodeError as e: # Should be caught earlier, but if tool returns invalid JSON string
        error_msg = f"Error: Failed to serialize the result from tool {llm_tool_name} (MCP name: {actual_mcp_tool_name}) to JSON. Details: {e}"
        print(error_msg, file=sys.stderr)
        return error_msg
    except Exception as e:
        error_msg = f"Error executing tool {llm_tool_name} (MCP name: {actual_mcp_tool_name}) via MCP: {type(e).__name__} - {e}"
        print(error_msg, file=sys.stderr)
        return error_msg

# Example for testing execute_mcp_tool - requires a running MCP server
async def main_test_execute():
    # This is a conceptual test. A real test requires a running MCP server
    # configured to serve a tool like 'test_tool_mcp_name'.
    print("Starting execute_mcp_tool test (requires a running MCP server)...")
    
    dummy_mcp_config = {
        "tools": {
            "llm_tool_name_weather": {
                "server_url": "http://localhost:8001/mcp", # Replace with your actual MCP server URL
                "mcp_tool_name": "get_weather_data",       # Replace with a tool name your MCP server offers
                "transport": "streamable-http"
            },
            "llm_tool_name_echo": {
                "server_url": "http://localhost:8001/mcp", 
                "mcp_tool_name": "echo_tool",       
                "transport": "streamable-http"
            }
        }
    }

    # Test case 1: Successful tool call (conceptual)
    # Replace arguments with what your 'echo_tool' expects
    print("\n--- Test Case: Successful Call (Conceptual) ---")
    args_str_success = '{"message": "hello from cli-llm"}'
    print(f"Calling 'llm_tool_name_echo' with args: {args_str_success}")
    try:
        result_success = await execute_mcp_tool("llm_tool_name_echo", args_str_success, dummy_mcp_config)
        print(f"Result: {result_success}")
    except Exception as e:
        print(f"Test execution failed: {e}")


    # Test case 2: Tool not configured
    print("\n--- Test Case: Tool Not Configured ---")
    args_str_not_config = '{}'
    result_not_config = await execute_mcp_tool("non_existent_llm_tool", args_str_not_config, dummy_mcp_config)
    print(f"Result for non_existent_llm_tool: {result_not_config}")
    expected_error_not_config = "Error: Tool 'non_existent_llm_tool' not found in MCP configuration."
    assert result_not_config == expected_error_not_config

    # Test case 3: Invalid arguments JSON
    print("\n--- Test Case: Invalid Arguments JSON ---")
    args_str_invalid_json = '{"message": "missing_quote}'
    result_invalid_json = await execute_mcp_tool("llm_tool_name_echo", args_str_invalid_json, dummy_mcp_config)
    print(f"Result for invalid JSON: {result_invalid_json}")
    # Expected result will contain "Error: Invalid arguments JSON format..."
    assert "Error: Invalid arguments JSON format" in result_invalid_json

    # Test case 4: Connection refused (conceptual - will only work if server is NOT running)
    print("\n--- Test Case: Connection Refused (Conceptual) ---")
    config_conn_refused = {
        "tools": {
            "tool_conn_refused": {
                "server_url": "http://localhost:9999/mcp", # Non-existent server
                "mcp_tool_name": "some_tool",
                "transport": "streamable-http"
            }
        }
    }
    args_str_conn_refused = '{}'
    result_conn_refused = await execute_mcp_tool("tool_conn_refused", args_str_conn_refused, config_conn_refused)
    print(f"Result for connection refused: {result_conn_refused}")
    assert "Error: Connection refused by MCP server" in result_conn_refused
    
    print("\nexecute_mcp_tool tests finished.")

if __name__ == '__main__':
    # Existing test for load_mcp_config
    # ... (keeping existing __main__ content for load_mcp_config) ...
    # Create a dummy mcp_config.json for this test
    dummy_config_content = {
        "tools": {
            "get_weather": {
                "server_url": "http://localhost:8001/mcp",
                "mcp_tool_name": "fetch_weather_data",
                "transport": "streamable-http"
            }
        }
    }
    dummy_file_path = "mcp_config.json" # Defined again, ensure consistent naming
    with open(dummy_file_path, 'w') as f:
        json.dump(dummy_config_content, f, indent=2)

    print(f"Attempting to load '{dummy_file_path}'...")
    config_data = load_mcp_config(dummy_file_path)
    if config_data:
        print("MCP Config loaded successfully:")
        print(json.dumps(config_data, indent=2))
    else:
        print("Failed to load MCP config.")
    # ... (rest of the load_mcp_config tests) ...
    print("\nAttempting to load a non-existent file 'non_existent_config.json'...")
    config_data_non_existent = load_mcp_config("non_existent_config.json")
    if not config_data_non_existent:
        print("Failed to load non-existent MCP config as expected.")
    
    invalid_config_content_definitely = '{"key": "value", error here}'
    dummy_invalid_file_path = "mcp_config_invalid.json" # Defined again
    with open(dummy_invalid_file_path, 'w') as f:
        f.write(invalid_config_content_definitely)
    
    print(f"\nAttempting to load invalid '{dummy_invalid_file_path}'...")
    config_data_invalid = load_mcp_config(dummy_invalid_file_path)
    if not config_data_invalid:
        print("Failed to load invalid MCP config as expected.")
    
    # Clean up dummy files
    import os
    if os.path.exists(dummy_file_path): # Check before removing
        os.remove(dummy_file_path)
    if os.path.exists(dummy_invalid_file_path): # Check before removing
        os.remove(dummy_invalid_file_path)

    # Running the async test for execute_mcp_tool
    # Note: This will try to connect to http://localhost:8001/mcp for the "successful" case.
    # If no server is running, this specific test will likely fail with ConnectionRefusedError.
    # Other tests (tool not configured, invalid JSON, connection refused to port 9999) should pass.
    print("\n--- Running execute_mcp_tool tests ---")
    asyncio.run(main_test_execute())
