import time
import os
import sys
import argparse
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.api import Api

def simulate_load(num_requests=5):
    api = Api()
    
    # We will use a dummy PDF path that doesn't exist, but since Api.process_files 
    # uses LLM, we should mock it for the stress test or test how it handles non-existent files.
    # In a real load test, we'd provide a large PDF.
    dummy_pdf = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "test_data", "dummy.pdf"))
    
    # Create a dummy PDF if it doesn't exist
    os.makedirs(os.path.dirname(dummy_pdf), exist_ok=True)
    if not os.path.exists(dummy_pdf):
        with open(dummy_pdf, 'w') as f:
            f.write("Dummy PDF content")

    def run_task(task_id):
        print(f"Task {task_id} started")
        start = time.time()
        try:
            # This will fail since dummy.pdf is not a real PDF and fitz will complain, 
            # but it tests the API concurrency bounds and memory.
            api.process_files([dummy_pdf])
        except Exception as e:
            pass # Expected if dummy.pdf is invalid
        end = time.time()
        print(f"Task {task_id} finished in {end-start:.2f} seconds")

    print(f"Starting {num_requests} concurrent document processing requests...")
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(run_task, i) for i in range(num_requests)]
        for f in futures:
            f.result()
            
    print(f"Load test completed in {time.time() - start_time:.2f} seconds.")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Stress Test for Beresta API")
    parser.add_argument('--requests', type=int, default=5, help="Number of concurrent requests")
    args = parser.parse_args()
    simulate_load(args.requests)
