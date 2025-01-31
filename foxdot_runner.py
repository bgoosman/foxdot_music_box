from FoxDot import *
import multiprocessing
import queue
import time

def run_foxdot_code(code_queue):
    """
    Process that runs FoxDot code received through a queue
    """
    while True:
        try:
            # Get code from queue with timeout
            code = code_queue.get(timeout=1)
            
            # Special command to exit the process
            if code == "EXIT":
                Clock.stop()
                break
                
            # Execute the code
            try:
                exec(code, globals(), locals())
            except Exception as e:
                if str(e) != "cannot set daemon status of active thread":
                    print(f"Error executing FoxDot code: {str(e)}")
                
        except queue.Empty:
            # No code received, continue waiting
            continue
        except Exception as e:
            print(f"Error in FoxDot runner: {str(e)}")
            break
    
    print("FoxDot runner stopping...") 