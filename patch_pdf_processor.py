import re

with open('backend/pdf_processor.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Remove import pytesseract
content = re.sub(r'import pytesseract\n', '', content)

# Remove tesseract comments in __init__
content = re.sub(r'        # Update tesseract cmd path if needed for Windows packaging\n        # pytesseract.pytesseract.tesseract_cmd = r\'C:\\Program Files\\Tesseract-OCR\\tesseract.exe\'\n', '', content)

# Remove tesseract fallback from paddleocr
content = content.replace('''                if status_callback:
                    status_callback("Ошибка PaddleOCR, переключаемся на Tesseract...")
                # Fallback to Tesseract
                return pytesseract.image_to_string(img, lang='rus+eng')''', 
'''                if status_callback:
                    status_callback("Ошибка PaddleOCR.")
                return ""''')

# Remove tesseract fallback from applevision
content = content.replace('''            if sys.platform != 'darwin':
                return pytesseract.image_to_string(img, lang='rus+eng')''', 
'''            if sys.platform != 'darwin':
                return ""''')

content = content.replace('''                if status_callback:
                    status_callback("Ошибка Apple Vision, переключаемся на Tesseract...")
                return pytesseract.image_to_string(img, lang='rus+eng')''',
'''                if status_callback:
                    status_callback("Ошибка Apple Vision.")
                return ""''')

# Remove final else
content = content.replace('''        else:
            return pytesseract.image_to_string(img, lang='rus+eng')''',
'''        else:
            return ""''')

with open('backend/pdf_processor.py', 'w', encoding='utf-8') as f:
    f.write(content)
