import warnings
import os
import json
import argparse
from pathlib import Path
from dotenv import load_dotenv
from litellm import completion
import re
import multiprocessing
from foxdot_runner import run_foxdot_code

# Disable Pydantic warning messages
warnings.filterwarnings("ignore", message="Valid config keys have changed in V2:*")
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic.*")

load_dotenv()

# Create threads directory if it doesn't exist
THREADS_DIR = Path("chat_threads")
THREADS_DIR.mkdir(exist_ok=True)

def extract_code_blocks(text):
    """Extract Python code blocks from markdown-formatted text."""
    pattern = r"```(?:python)?\n(.*?)\n```"
    return re.findall(pattern, text, re.DOTALL)

def execute_code_safely(code, code_queue):
    """Execute Python code in a safe manner and capture its output."""
    try:
        # Send code to FoxDot process
        code_queue.put(code)
        return "Code sent to FoxDot process"
    except Exception as e:
        return f"Error sending code to FoxDot process: {str(e)}"

def load_chat_thread(thread_name):
    """Load a chat thread from a JSON file."""
    file_path = THREADS_DIR / f"{thread_name}.json"
    if file_path.exists():
        with open(file_path, 'r') as f:
            return json.load(f)
    return []

def save_chat_thread(thread_name, messages):
    """Save a chat thread to a JSON file."""
    file_path = THREADS_DIR / f"{thread_name}.json"
    with open(file_path, 'w') as f:
        json.dump(messages, f, indent=2)

def create_system_prompt():
    return {
        "role": "system",
        "content": """
        You are a helpful assistant that can execute Python code and play music with FoxDot.
        All instrument names must be two letters long, like 'bd' or 'sd'.
        """
    }

def chat(thread_name=None):
    # Initialize or load conversation history
    messages = load_chat_thread(thread_name) if thread_name else []
    if not messages:
        messages.append(create_system_prompt())
    print(messages)
    
    # Set up multiprocessing queue and start FoxDot process
    code_queue = multiprocessing.Queue()
    foxdot_process = multiprocessing.Process(target=run_foxdot_code, args=(code_queue,))
    foxdot_process.start()
    
    print(f"Chat started{f' (Thread: {thread_name})' if thread_name else ''}. Type 'quit' to exit.")
    print("Special commands:")
    print("  'quit' - Exit the chat")
    print("  'run' - Execute the last detected Python code block")
    print("  'stop' - Stop all FoxDot sounds")
    
    last_code_blocks = []
    
    while True:
        # Get user input
        user_input = input("\nYou: ").strip()

        if user_input.lower() == 'stop':
            code_queue.put("Clock.stop()")
            print("Clock stopped")
            continue
        
        # Check for exit command
        if user_input.lower() == 'quit':
            # Send exit command to FoxDot process
            code_queue.put("EXIT")
            foxdot_process.join(timeout=5)
            break
            
        # Check for code execution command
        if user_input.lower() == 'run':
            if last_code_blocks:
                print("\nExecuting last code block:")
                for code in last_code_blocks:
                    print(code)
                    print("\n--- Code output ---")
                    output = execute_code_safely(code, code_queue)
                    print(output.strip())
                    print("--- End output ---")
                continue
            else:
                print("\nNo code blocks available to execute.")
                continue
        
        # Add user message to history
        messages.append({"role": "user", "content": user_input})
        
        try:
            # Get AI response with streaming
            response = completion(
                model="gpt-4o",
                messages=messages,
                api_base=os.getenv("OPENAPI_BASE_URL"),
                api_key=os.getenv("OPENAI_API_KEY"),
                stream=True
            )
            
            print("\nAssistant:", end=" ", flush=True)
            full_response = ""
            
            # Stream the response
            for chunk in response:
                if hasattr(chunk.choices[0], 'delta') and hasattr(chunk.choices[0].delta, 'content'):
                    content = chunk.choices[0].delta.content
                    if content:
                        print(content, end="", flush=True)
                        full_response += content
            
            print()  # New line after response
            
            # Check for code blocks in the response
            code_blocks = extract_code_blocks(full_response)
            if code_blocks:
                last_code_blocks = code_blocks
                print("\nPython code block detected! Type 'run' to execute it.")
            else:
                last_code_blocks = []
            
            # Add complete AI response to history
            messages.append({"role": "assistant", "content": full_response})
            
            # Save the updated thread if we're using a named thread
            if thread_name:
                save_chat_thread(thread_name, messages)
            
        except Exception as e:
            print(f"\nError: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description='Chat with AI using named threads')
    parser.add_argument('--thread', '-t', help='Name of the chat thread to use')
    args = parser.parse_args()
    
    chat(args.thread)

if __name__ == "__main__":
    main()
