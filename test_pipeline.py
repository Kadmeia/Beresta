import sys
import os

# Ensure we can import from backend
sys.path.append(os.path.abspath('.'))

from backend.api import Api

def main():
    api = Api()
    print("Testing processing on Handwritten_2026-06-08_152924.pdf...")
    
    try:
        results = api.process_files(['/Volumes/CodeOS/Beresta/Handwritten_2026-06-08_152924.pdf'])
        for idx, res in enumerate(results):
            print(f"--- Document {idx + 1} ---")
            print(f"Pages: {res.get('start_page')} - {res.get('end_page')}")
            print(f"Short Name: {res.get('short_name')}")
            print(f"Full Name: {res.get('full_name')}")
            print(f"Parties: {res.get('parties')}")
            print(f"Date: {res.get('date')}")
            print(f"Confidence: {res.get('confidence')}")
            
            # Simulate frontend naming logic using backend fallback for simplicity
            # or just print the raw properties
    except Exception as e:
        print(f"Error during processing: {e}")

if __name__ == '__main__':
    main()
