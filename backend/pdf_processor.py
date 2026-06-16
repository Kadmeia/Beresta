import os
import fitz  # PyMuPDF
from pypdf import PdfReader, PdfWriter
import pytesseract
from PIL import Image, ImageEnhance, ImageStat
import io
import re
import numpy as np

class PDFProcessor:
    def __init__(self):
        # Update tesseract cmd path if needed for Windows packaging
        # pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        self.ocr_engine = 'paddleocr'
        self.paddle_ocr = None
        self.model_storage_dir = os.path.join(os.getenv('LOCALAPPDATA', os.path.expanduser('~')), 'BerestaAI', 'paddleocr')

    def check_encryption(self, file_path):
        try:
            reader = PdfReader(file_path)
            return reader.is_encrypted
        except Exception:
            return True # Treat as encrypted or broken

    def _vision_ocr(self, img):
        import tempfile
        import Vision
        import objc
        from Foundation import NSURL
        
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
            img.save(tf, format="PNG")
            temp_path = tf.name
            
        url = NSURL.fileURLWithPath_(temp_path)
        handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(url, None)
        
        request = Vision.VNRecognizeTextRequest.alloc().init()
        request.setRecognitionLanguages_(["ru-RU", "en-US"])
        # Accurate is slower but much better
        request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
        
        success, error = handler.performRequests_error_([request], None)
        
        text = ""
        if success:
            for observation in request.results():
                text += observation.topCandidates_(1)[0].string() + "\n"
                
        os.remove(temp_path)
        return text.strip()

    def _perform_ocr(self, img, status_callback=None):
        if self.ocr_engine == 'paddleocr':
            try:
                if self.paddle_ocr is None:
                    if status_callback:
                        status_callback("Инициализация PaddleOCR (скачивание моделей может занять время)...")
                    from paddleocr import PaddleOCR
                    import logging
                    # Suppress paddle verbose logging
                    logging.getLogger('ppocr').setLevel(logging.ERROR)
                    os.makedirs(self.model_storage_dir, exist_ok=True)
                    self.paddle_ocr = PaddleOCR(use_angle_cls=True, lang='ru', det_model_dir=os.path.join(self.model_storage_dir, 'det'), rec_model_dir=os.path.join(self.model_storage_dir, 'rec'), cls_model_dir=os.path.join(self.model_storage_dir, 'cls'), show_log=False)
                
                # PaddleOCR expects numpy array (BGR or RGB)
                img_np = np.array(img.convert('RGB'))
                if status_callback:
                    status_callback("Распознавание текста через PaddleOCR...")
                
                result = self.paddle_ocr.ocr(img_np, cls=True)
                
                text_lines = []
                if result and result[0]:
                    for line in result[0]:
                        text_lines.append(line[1][0])
                return "\n".join(text_lines)
            except Exception as e:
                print(f"PaddleOCR Error: {e}")
                if status_callback:
                    status_callback("Ошибка PaddleOCR, переключаемся на Tesseract...")
                # Fallback to Tesseract
                return pytesseract.image_to_string(img, lang='rus+eng')
        elif self.ocr_engine == 'applevision':
            import sys
            if sys.platform != 'darwin':
                return pytesseract.image_to_string(img, lang='rus+eng')
            try:
                if status_callback:
                    status_callback("Распознавание текста через Apple Vision...")
                return self._vision_ocr(img)
            except Exception as e:
                print(f"Apple Vision Error: {e}")
                if status_callback:
                    status_callback("Ошибка Apple Vision, переключаемся на Tesseract...")
                return pytesseract.image_to_string(img, lang='rus+eng')
        else:
            return pytesseract.image_to_string(img, lang='rus+eng')

    def extract_text(self, file_path, status_callback=None):
        if self.check_encryption(file_path):
            raise ValueError(f"Файл {os.path.basename(file_path)} зашифрован. Обработка невозможна.")
            
        doc = fitz.open(file_path)
        pages_text = []
        
        for i in range(len(doc)):
            if status_callback:
                status_callback(f"Чтение бересты (страница {i+1}/{len(doc)})...")
                
            page = doc[i]
            text = page.get_text()
            
            # Heuristic: if text has < 10 "normal" words, treat as image
            words = [w for w in text.split() if len(w) > 3]
            
            if len(words) < 10:
                # OCR fallback
                zoom_matrix = fitz.Matrix(3.0, 3.0)
                pix = page.get_pixmap(matrix=zoom_matrix)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                
                img = img.convert('L')
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(2.0)
                
                text = self._perform_ocr(img, status_callback)

            # Ignore empty pages or noise
            # Count actual letters to determine if there's real text
            letters = re.findall(r'[А-Яа-яA-Za-z]', text)
            if len(letters) > 15:
                pages_text.append({"page_num": i+1, "text": text})
            else:
                if status_callback:
                    status_callback(f"Очистка от чистой бересты (страница {i+1} пропущена)")

        return pages_text

    def force_ocr_page(self, file_path, page_num, status_callback=None):
        """Forces OCR extraction on a specific page, ignoring text layer."""
        doc = fitz.open(file_path)
        page = doc[page_num - 1]
        
        zoom_matrix = fitz.Matrix(3.0, 3.0)
        pix = page.get_pixmap(matrix=zoom_matrix)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        
        img = img.convert('L')
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2.0)
        
        return self._perform_ocr(img, status_callback)

    def _is_page_blank(self, fitz_doc, page_index):
        try:
            page = fitz_doc[page_index]
            # Быстрый рендер с низким разрешением
            pix = page.get_pixmap(matrix=fitz.Matrix(0.5, 0.5))
            img = Image.open(io.BytesIO(pix.tobytes('png'))).convert('L')
            stat = ImageStat.Stat(img)
            
            # Полностью пустая страница обычно имеет stddev около 0 и среднее около 255
            if stat.stddev[0] < 5.0 and stat.mean[0] > 240:
                return True
                
            text = page.get_text().strip()
            # Если текста нет, а страница имеет очень мало шума, тоже считаем пустой
            if not text and stat.stddev[0] < 12.0:
                return True
                
            return False
        except Exception:
            return False

    def split_and_save(self, original_path, start_page, end_page, new_name, output_dir):
        """
        Splits the PDF and saves with a new name. Adds (1), (2) if file exists.
        start_page and end_page are 1-indexed.
        Removes blank pages.
        """
        reader = PdfReader(original_path)
        writer = PdfWriter()
        
        # Открываем через fitz для проверки на пустые страницы
        fitz_doc = None
        try:
            fitz_doc = fitz.open(original_path)
        except Exception:
            pass
        
        # 1-indexed to 0-indexed
        for i in range(start_page - 1, min(end_page, len(reader.pages))):
            if fitz_doc and self._is_page_blank(fitz_doc, i):
                print(f"Skipping blank page {i+1} in {original_path}")
                continue
                
            writer.add_page(reader.pages[i])
            
        if fitz_doc:
            fitz_doc.close()
            
        # Если все страницы оказались пустыми, сохраняем хотя бы первую, чтобы не вылетала ошибка
        if len(writer.pages) == 0:
            writer.add_page(reader.pages[start_page - 1])
            
        base_path = os.path.join(output_dir, new_name + ".pdf")
        final_path = base_path
        
        counter = 1
        while os.path.exists(final_path):
            final_path = os.path.join(output_dir, f"{new_name} ({counter}).pdf")
            counter += 1
            
        with open(final_path, "wb") as f:
            writer.write(f)
            
        return final_path
