import os
import shutil
import docx

class DocxProcessor:
    def __init__(self):
        pass

    def extract_text(self, file_path, status_callback=None):
        if status_callback:
            status_callback("Чтение DOCX документа...")
            
        try:
            doc = docx.Document(file_path)
            full_text = []
            
            # Extract paragraphs
            for para in doc.paragraphs:
                if para.text.strip():
                    full_text.append(para.text.strip())
                    
            # Extract tables
            for table in doc.tables:
                for row in table.rows:
                    row_text = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                    if row_text:
                        full_text.append(" ".join(row_text))
                        
            text = "\n".join(full_text)
            
            # Docx documents are always treated as a single page/document
            if len(text.strip()) > 10:
                return [{"page_num": 1, "text": text}]
            else:
                return []
        except Exception as e:
            print(f"Error reading docx: {e}")
            raise ValueError(f"Не удалось прочитать файл {os.path.basename(file_path)}: {str(e)}")

    def copy_and_save(self, original_path, new_name, output_dir):
        """
        Copies the original docx file to the output directory with a new name.
        """
        base_path = os.path.join(output_dir, new_name + ".docx")
        final_path = base_path
        
        counter = 1
        while os.path.exists(final_path):
            final_path = os.path.join(output_dir, f"{new_name} ({counter}).docx")
            counter += 1
            
        shutil.copy2(original_path, final_path)
            
        return final_path
