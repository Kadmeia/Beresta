import os
import fitz  # PyMuPDF
from pypdf import PdfReader, PdfWriter
from PIL import Image, ImageEnhance, ImageStat
import io
import re

class PDFProcessor:
    def __init__(self):
        self.ocr_engine = 'docling'
        self.paddle_ocr = None
        self.model_storage_dir = os.path.join(os.getenv('LOCALAPPDATA', os.path.expanduser('~')), 'BerestaAI', 'paddleocr')

    def check_encryption(self, file_path):
        try:
            reader = PdfReader(file_path)
            return reader.is_encrypted
        except Exception:
            return True # Treat as encrypted or broken

    def _perform_ocr(self, img, status_callback=None):
        import tempfile
        import subprocess
        import sys
        import json
        
        # Save PIL image to a temp PNG
        fd, temp_path = tempfile.mkstemp(suffix='.png')
        try:
            os.close(fd)
            img.save(temp_path)
            
            if status_callback:
                status_callback("Распознавание текста через PaddleOCR (процесс)...")
                
            current_dir = os.path.dirname(os.path.abspath(__file__))
            worker_path = os.path.join(current_dir, 'ocr_worker.py')
            python_bin = sys.executable
            
            res = subprocess.run(
                [python_bin, worker_path, temp_path],
                capture_output=True,
                text=True
            )
            if res.returncode != 0:
                print(f"OCR subprocess failed: {res.stderr}")
                return ""
                
            try:
                data = json.loads(res.stdout.strip())
                if 'error' in data:
                    print(f"OCR subprocess error: {data['error']}")
                    return ""
                return data.get('text', '')
            except Exception as parse_err:
                print(f"Failed to parse OCR subprocess output: {res.stdout}. Error: {parse_err}")
                return ""
        except Exception as e:
            print(f"PaddleOCR Subprocess Error: {e}")
            return ""
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

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

    def check_paddleocr_exists(self):
        default_dir1 = os.path.expanduser('~/.paddleocr')
        default_dir2 = os.path.expanduser('~/.paddlex')
        
        # Если хотя бы одна из этих папок существует и не пустая, значит модели скачаны
        if os.path.exists(default_dir1) and len(os.listdir(default_dir1)) > 0:
            return True
        if os.path.exists(default_dir2) and len(os.listdir(default_dir2)) > 0:
            return True
        
        return False

    def download_paddleocr(self, progress_callback=None):
        if self.check_paddleocr_exists():
            if progress_callback: progress_callback("PaddleOCR уже установлен.")
            return True
            
        if progress_callback:
            progress_callback("Скачивание моделей OCR (PaddleOCR)... Это займет некоторое время.")
            
        try:
            import sys
            import re
            
            class ProgressCatcher:
                def __init__(self, orig, cb):
                    self.orig = orig
                    self.cb = cb
                    self.last_pct = ""
                    
                def write(self, data):
                    self.orig.write(data)
                    match = re.search(r'(\d+)%', data)
                    if match:
                        pct = match.group(1)
                        if pct != self.last_pct:
                            self.last_pct = pct
                            if self.cb:
                                self.cb(f"Скачивание моделей: {pct}%")
                    elif "Downloading [" in data:
                        match_file = re.search(r'Downloading \[(.*?)\]', data)
                        if match_file and self.cb:
                            self.cb(f"Загрузка файла: {match_file.group(1)}...")
                            
                def flush(self):
                    self.orig.flush()

            orig_stderr = sys.stderr
            sys.stderr = ProgressCatcher(orig_stderr, progress_callback)

            from paddleocr import PaddleOCR
            import logging
            logging.getLogger('ppocr').setLevel(logging.ERROR)
            self.paddle_ocr = PaddleOCR(use_angle_cls=True, lang='ru')
            
            sys.stderr = orig_stderr
            
            if progress_callback:
                progress_callback("Скачивание OCR завершено. Модель готова.")
            return True
        except Exception as e:
            if 'orig_stderr' in locals():
                import sys
                sys.stderr = orig_stderr
            if progress_callback:
                progress_callback(f"Ошибка скачивания OCR: {str(e)}")
            return False

    def check_tesseract_exists(self):
        import sys
        import subprocess
        import os
        import shutil
        
        if sys.platform != 'win32':
            # 1. Проверяем в стандартном PATH
            tess_path = shutil.which('tesseract')
            
            # 2. Проверяем в стандартных директориях Homebrew
            if not tess_path:
                for path in ['/opt/homebrew/bin/tesseract', '/usr/local/bin/tesseract']:
                    if os.path.exists(path):
                        tess_path = path
                        break
                        
            if tess_path:
                try:
                    subprocess.run([tess_path, '-v'], capture_output=True, check=True)
                    # Если нашли через brew, нужно указать путь для pytesseract
                    import pytesseract
                    pytesseract.pytesseract.tesseract_cmd = tess_path
                    return True
                except:
                    return False
            return False
            
        # On Windows:
        tess_path = shutil.which('tesseract')
        if tess_path:
            try:
                import pytesseract
                pytesseract.pytesseract.tesseract_cmd = tess_path
                return True
            except:
                pass
                
        standard_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        if os.path.exists(standard_path):
            try:
                import pytesseract
                pytesseract.pytesseract.tesseract_cmd = standard_path
                return True
            except:
                pass

        tess_dir = os.path.join(os.getenv('LOCALAPPDATA', os.path.expanduser('~')), 'BerestaAI', 'tesseract')
        exe_path = os.path.join(tess_dir, 'tesseract.exe')
        if os.path.exists(exe_path):
            try:
                import pytesseract
                pytesseract.pytesseract.tesseract_cmd = exe_path
                return True
            except:
                pass
        return False

    def download_tesseract(self, progress_callback=None):
        import sys
        import time
        if self.check_tesseract_exists():
            if progress_callback: progress_callback("Tesseract уже установлен.")
            return True
            
        if sys.platform != 'win32':
            import subprocess
            import shutil
            
            brew_path = shutil.which('brew')
            if not brew_path:
                if os.path.exists('/opt/homebrew/bin/brew'):
                    brew_path = '/opt/homebrew/bin/brew'
                elif os.path.exists('/usr/local/bin/brew'):
                    brew_path = '/usr/local/bin/brew'
                else:
                    if progress_callback:
                        progress_callback("На Mac не установлен Homebrew. Установите его вручную с brew.sh")
                    return False
            
            if progress_callback:
                progress_callback("Установка Tesseract через Homebrew (это может занять время)...")
            
            try:
                # На Маке ставим tesseract и русский язык к нему
                process = subprocess.Popen([brew_path, 'install', 'tesseract', 'tesseract-lang'], 
                                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                for line in process.stdout:
                    if progress_callback:
                        msg = line.strip()
                        if msg and not msg.startswith('==>'):
                            # Выводим аккуратно, чтобы не заспамить интерфейс
                            progress_callback(f"Установка: {msg[:60]}...")
                
                process.wait()
                if process.returncode == 0:
                    if progress_callback:
                        progress_callback("Скачивание Tesseract завершено. Движок готов к работе.")
                    return True
                else:
                    if progress_callback:
                        progress_callback(f"Ошибка установки Homebrew (Код: {process.returncode})")
                    return False
            except Exception as e:
                if progress_callback:
                    progress_callback(f"Ошибка: {str(e)}")
                return False
            
        if progress_callback:
            progress_callback("Скачивание Tesseract OCR (~40 МБ)...")
            
        try:
            import urllib.request
            import zipfile
            import shutil
            
            tess_dir = os.path.join(os.getenv('LOCALAPPDATA', os.path.expanduser('~')), 'BerestaAI', 'tesseract')
            
            # Ссылка на ваш скачанный и загруженный куда-либо tesseract-portable.zip
            # TODO: После загрузки архива на сервер, вставьте прямую ссылку сюда
            download_url = "ВАША_ССЫЛКА_НА_TESSERACT_PORTABLE.ZIP" 
            
            zip_path = os.path.join(os.getenv('LOCALAPPDATA', os.path.expanduser('~')), 'BerestaAI', 'tess_temp.zip')
            
            # Если архив уже лежит в папке с проектом (для тестов)
            local_zip = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tesseract-portable.zip")
            if os.path.exists(local_zip):
                if progress_callback:
                    progress_callback("Найден локальный архив. Распаковка...")
                zip_path = local_zip
            else:
                if progress_callback:
                    progress_callback("Скачивание архива Tesseract (около 45 МБ)...")
                # TODO: Раскомментировать когда будет реальная ссылка
                # urllib.request.urlretrieve(download_url, zip_path)
                pass # Пока нет ссылки, код просто пойдет дальше и упадет, если локального архива тоже нет

            if progress_callback:
                progress_callback("Распаковка файлов Tesseract...")
                
            os.makedirs(tess_dir, exist_ok=True)
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(tess_dir)
                
            # Если мы скачивали во временный файл, удаляем его
            if zip_path != local_zip and os.path.exists(zip_path):
                os.remove(zip_path)
                
            # Прописываем путь
            exe_path = os.path.join(tess_dir, 'tesseract.exe')
            if os.path.exists(exe_path):
                import pytesseract
                pytesseract.pytesseract.tesseract_cmd = exe_path

            if progress_callback:
                progress_callback("Скачивание Tesseract завершено. Движок готов к работе.")
            return True
            
        except Exception as e:
            if progress_callback:
                progress_callback(f"Ошибка установки OCR: {str(e)}")
            return False

    def unload_ocr(self):
        self.paddle_ocr = None
        import gc
        gc.collect()

