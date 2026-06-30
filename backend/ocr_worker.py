import sys
import os
import json

# Force 1 thread to prevent OpenMP deadlocks on macOS
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

# Set offline environment variables to prevent hanging on online registry checks
os.environ["PADDLEX_OFFLINE_MODE"] = "1"
os.environ["PADDLE_OCR_MODEL_DOWNLOAD"] = "0"
os.environ["PADDLE_DISABLE_TELEMETRY"] = "1"

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No image path provided"}))
        return
        
    img_path = sys.argv[1]
    if not os.path.exists(img_path):
        print(json.dumps({"error": f"Image path not found: {img_path}"}))
        return
        
    try:
        from PIL import Image
        import numpy as np
        from paddleocr import PaddleOCR
        import logging
        
        logging.getLogger('ppocr').setLevel(logging.ERROR)
        import warnings
        warnings.filterwarnings("ignore")
        
        ocr = PaddleOCR(use_textline_orientation=True, lang='ru')
        
        img = Image.open(img_path).convert('RGB')
        
        # Resize to max 1000 pixels to optimize performance and memory usage on CPU
        max_dim = 1000
        if max(img.size) > max_dim:
            ratio = max_dim / max(img.size)
            new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
            
        img_np = np.array(img)
        
        result = ocr.ocr(img_np)
        
        text_lines = []
        if result and isinstance(result, list):
            for page_res in result:
                if 'rec_texts' in page_res:
                    text_lines.extend(page_res['rec_texts'])
                    
        print(json.dumps({"text": "\n".join(text_lines)}))
    except Exception as e:
        print(json.dumps({"error": str(e)}))

if __name__ == "__main__":
    main()
