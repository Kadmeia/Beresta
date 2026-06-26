import os
import re
import json
import urllib.request
import base64
import tempfile
import fitz  # PyMuPDF
from smolagents import Model, CodeAgent, Tool
from smolagents.models import ChatMessage, MessageRole

class OllamaModel(Model):
    def __init__(self, model_id="saiga:4b", base_url="http://localhost:11434", **kwargs):
        super().__init__(**kwargs)
        self.model_id = model_id
        self.base_url = base_url

    def generate(self, messages, stop_sequences=None, response_format=None, tools_to_call_from=None, **kwargs):
        formatted_messages = []
        for m in messages:
            content = m.content
            if isinstance(content, list):
                text_parts = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text_parts.append(part.get("text", ""))
                    elif isinstance(part, str):
                        text_parts.append(part)
                content = "".join(text_parts)
            
            role = m.role.value if hasattr(m.role, "value") else str(m.role)
            formatted_messages.append({
                "role": role,
                "content": content
            })

        options = {"temperature": 0.0}
        if stop_sequences:
            options["stop"] = stop_sequences

        payload = {
            "model": self.model_id,
            "messages": formatted_messages,
            "stream": False,
            "options": options
        }

        url = f"{self.base_url.rstrip('/')}/api/chat"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                assistant_message = res_data.get("message", {})
                content = assistant_message.get("content", "")
                return ChatMessage(role=MessageRole.ASSISTANT, content=content)
        except Exception as e:
            print(f"Error querying Ollama: {e}")
            raise RuntimeError(f"Error querying Ollama: {e}")

class GetPageTextTool(Tool):
    name = "get_page_text"
    description = "Retrieves the OCR text for a single page."
    inputs = {
        "page_number": {
            "type": "integer",
            "description": "The 1-based page number of the PDF."
        }
    }
    output_type = "string"

    def __init__(self, workflow):
        super().__init__()
        self.workflow = workflow

    def forward(self, page_number: int) -> str:
        for p in self.workflow.pages_text:
            if p['page_num'] == page_number:
                return p['text']
        return ""

class GetDocumentPagesTextTool(Tool):
    name = "get_document_pages_text"
    description = "Retrieves combined OCR text for a range of pages."
    inputs = {
        "start_page": {
            "type": "integer",
            "description": "The 1-based start page number (inclusive)."
        },
        "end_page": {
            "type": "integer",
            "description": "The 1-based end page number (inclusive)."
        }
    }
    output_type = "string"

    def __init__(self, workflow):
        super().__init__()
        self.workflow = workflow

    def forward(self, start_page: int, end_page: int) -> str:
        texts = []
        for p in self.workflow.pages_text:
            if start_page <= p['page_num'] <= end_page:
                texts.append(p['text'])
        return "\n\n".join(texts)

class DetectSplitPointsTool(Tool):
    name = "detect_split_points"
    description = "Detects potential 1-based page numbers where new documents start in the PDF."
    inputs = {}
    output_type = "any"

    def __init__(self, workflow):
        super().__init__()
        self.workflow = workflow

    def forward(self) -> list:
        self.workflow.log("Поиск точек разделения документов...")
        if self.workflow.mode == "rename":
            return [1]
            
        points = [1]
        for p in self.workflow.pages_text:
            page_num = p['page_num']
            if page_num == 1:
                continue
            if self.workflow.mode == "extract" and not self.workflow.extract_settings.get('split', True):
                continue
                
            text = p['text'][:3000]
            if self.workflow.check_is_new_document(text, page_num):
                points.append(page_num)
        return sorted(list(set(points)))

class ExtractDocumentMetadataTool(Tool):
    name = "extract_document_metadata"
    description = "Extracts document metadata (doc_type, number, date, parties) from OCR text."
    inputs = {
        "text": {
            "type": "string",
            "description": "The OCR text of the document."
        }
    }
    output_type = "any"

    def __init__(self, workflow):
        super().__init__()
        self.workflow = workflow

    def forward(self, text: str) -> dict:
        self.workflow.log("Извлечение реквизитов документа...")
        prompt = f"""Ты — строгий робот-анализатор. Твоя задача — извлечь реквизиты документа из его текста (полученного через OCR).
Исправь опечатки OCR в именах и названиях. Выведи результат СТРОГО в формате JSON.
Не пиши никаких рассуждений, пояснений, вступлений или заключений. Пиши только JSON.

ВАЖНО:
1. parties (Стороны) — извлеки краткие названия организаций и ФИО граждан. Исключи ИНН, ОГРН, адреса, должности.
2. doc_type (Тип) — ПОЛНОЕ ДОСЛОВНОЕ наименование (заголовок) документа как в тексте. Обязательно включай все относящиеся к заголовку приписки (например: "к Приложению №1...", "к Договору...", "на объект недвижимости"). НЕ сокращай заголовок до одного слова! (например: "Акт сдачи-приемки оказанных услуг к Приложению №15").
3. number (Номер) — только короткий номер самого документа. Если нет, верни "-".
4. date (Дата) — дата подписания в формате ДД.ММ.ГГГГ. Если нет, верни "-".

Формат вывода (JSON):
{{
  "parties": "ООО Ромашка, ИП Петров",
  "doc_type": "Договор",
  "number": "12",
  "date": "12.04.2025"
}}

Текст документа:
{text[:3000]}
"""
        resp = self.workflow.query_ollama(prompt)
        resp_clean = re.sub(r'<think>.*?</think>', '', resp, flags=re.DOTALL).strip()
        json_match = re.search(r'\{.*\}', resp_clean, flags=re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except:
                pass
        return {"doc_type": "Документ", "number": "-", "date": "-", "parties": "-"}

class CompileFinalFilenameTool(Tool):
    name = "compile_final_filename"
    description = "Compiles a clean, standardized and safe filename from metadata."
    inputs = {
        "metadata": {
            "type": "any",
            "description": "A dictionary containing 'doc_type', 'number', 'date', 'parties'."
        }
    }
    output_type = "string"

    def __init__(self, workflow):
        super().__init__()
        self.workflow = workflow

    def forward(self, metadata: dict) -> str:
        raw_type = self.workflow.clean_doc_type(metadata.get("doc_type", "Документ"))
        doc_number = metadata.get("number", "-")
        clean_date = self.workflow.clean_doc_date(metadata.get("date", "-"))
        parties = self.workflow.format_parties(metadata.get("parties", "-"))
        
        full_parts = []
        full_type = raw_type
        # Удалено жесткое приведение типов, чтобы сохранить полное наименование
            
        full_parts.append(full_type)
        if doc_number and doc_number != "-":
            clean_num = doc_number.replace("№", "").replace("номер", "").replace("No", "").strip()
            if clean_num:
                full_parts.append(f"№{clean_num}")
        if clean_date and clean_date != "-":
            full_parts.append(f"от {clean_date}")
        if parties and parties != "-":
            full_parts.append(parties)
        full_name = " ".join(full_parts)
        full_name = re.sub(r'[\\/*?:"<>|]', "", full_name).strip()
        return full_name

class SplitPdfAtPagesTool(Tool):
    name = "split_pdf_at_pages"
    description = "Physically splits the main PDF into multiple PDFs based on start pages and returns paths."
    inputs = {
        "file_path": {
            "type": "string",
            "description": "The absolute path of the input PDF file to split."
        },
        "split_points": {
            "type": "any",
            "description": "A sorted list of 1-based start page numbers where each new document begins."
        }
    }
    output_type = "any"

    def __init__(self, workflow):
        super().__init__()
        self.workflow = workflow

    def forward(self, file_path: str, split_points: list) -> list:
        self.workflow.log(f"Физическое разделение PDF на сегменты: {split_points}...")
        self.workflow.split_points = split_points
        
        try:
            doc = fitz.open(file_path)
            total_pages = len(doc)
            sp = sorted(list(set([1] + split_points)))
            
            temp_paths = []
            for i in range(len(sp)):
                start = sp[i]
                end = sp[i+1] - 1 if i+1 < len(sp) else total_pages
                
                new_doc = fitz.create_pdf()
                new_doc.insert_pdf(doc, from_page=start-1, to_page=end-1)
                
                temp_file = os.path.join(tempfile.gettempdir(), f"temp_split_{start}_{end}.pdf")
                new_doc.save(temp_file)
                new_doc.close()
                
                temp_paths.append(temp_file)
                self.workflow.temp_files.append(temp_file)
                
            doc.close()
            return temp_paths
        except Exception as e:
            self.workflow.log(f"Ошибка при разделении PDF: {e}")
            return []

class RenameDocumentTool(Tool):
    name = "rename_document"
    description = "Renames a split document file and records its details in the system."
    inputs = {
        "old_path": {
            "type": "string",
            "description": "The current path of the split PDF file."
        },
        "new_name": {
            "type": "string",
            "description": "The target clean name of the document (without extension)."
        },
        "metadata": {
            "type": "any",
            "description": "Optional dictionary containing 'doc_type', 'number', 'date', 'parties'.",
            "nullable": True
        }
    }
    output_type = "string"

    def __init__(self, workflow):
        super().__init__()
        self.workflow = workflow

    def forward(self, old_path: str, new_name: str, metadata: dict = None) -> str:
        self.workflow.log(f"Именование документа: '{new_name}'")
        filename = os.path.basename(old_path)
        match = re.search(r'temp_split_(\d+)_(\d+)', filename)
        
        start_page = 1
        end_page = 1
        if match:
            start_page = int(match.group(1))
            end_page = int(match.group(2))
            
        segment_texts = [p['text'] for p in self.workflow.pages_text if start_page <= p['page_num'] <= end_page]
        combined_text = "\n\n".join(segment_texts)
        
        # Generate preview image
        b64_image = ""
        try:
            tmp_doc = fitz.open(self.workflow.file_path)
            tmp_page = tmp_doc[start_page - 1]
            pix = tmp_page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
            img_data = pix.tobytes("jpeg", 80)
            b64_image = base64.b64encode(img_data).decode("utf-8")
            tmp_doc.close()
        except Exception as e:
            print(f"Error in preview image: {e}")
            
        meta = metadata or {}
        raw_type = self.workflow.clean_doc_type(meta.get("doc_type", "Документ"))
        clean_date = self.workflow.clean_doc_date(meta.get("date", "-"))
        parties = self.workflow.format_parties(meta.get("parties", "-"))
        
        # Build full_name
        full_parts = []
        full_type = raw_type
        # Удалено жесткое приведение типов, чтобы сохранить полное наименование
        
        full_parts.append(full_type)
        doc_number = meta.get("number", "-")
        if doc_number and doc_number != "-":
            clean_num = doc_number.replace("№", "").replace("номер", "").replace("No", "").strip()
            if clean_num:
                full_parts.append(f"№{clean_num}")
        if clean_date and clean_date != "-":
            full_parts.append(f"от {clean_date}")
        full_name = " ".join(full_parts)
        
        # Add to results
        doc_item = {
            "original_file": self.workflow.file_path,
            "start_page": start_page,
            "end_page": end_page,
            "actual_page_count": end_page - start_page + 1,
            "is_docx": False,
            "parties": parties,
            "short_name": raw_type,
            "full_name": full_name,
            "date": clean_date,
            "confidence": True,
            "isMerged": False,
            "isActive": True,
            "isManualEdit": False,
            "new_name": new_name,
            "text": combined_text,
            "image_b64": b64_image
        }
        self.workflow.documents.append(doc_item)
        return old_path

class LogMessageTool(Tool):
    name = "log_message"
    description = "Logs a progress or debug message to the application console."
    inputs = {
        "message": {
            "type": "string",
            "description": "The log message to display."
        }
    }
    output_type = "any"

    def __init__(self, workflow):
        super().__init__()
        self.workflow = workflow

    def forward(self, message: str) -> None:
        self.workflow.log(message)

class SmolAgentsWorkflow:
    def __init__(self, file_path, pages_text, mode, extract_settings, ollama_config, status_callback=None):
        self.file_path = file_path
        self.pages_text = pages_text
        self.mode = mode
        self.extract_settings = extract_settings
        self.ollama_config = ollama_config
        self.status_callback = status_callback
        
        # State variables to gather results
        self.split_points = []
        self.documents = []  # List of finalized document dicts
        self.temp_files = [] # Track temp files for cleanup
        
        # Import clean helpers
        from backend.llm_handler import format_parties, clean_doc_type, clean_doc_date
        self.format_parties = format_parties
        self.clean_doc_type = clean_doc_type
        self.clean_doc_date = clean_doc_date

    def log(self, message):
        print(f"[SmolAgents Workflow] {message}")
        if self.status_callback:
            self.status_callback(message)

    def query_ollama(self, prompt, system_prompt=None):
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.ollama_config.get("model", "saiga:4b"),
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.0}
        }
        
        url = f"{self.ollama_config.get('base_url', 'http://localhost:11434').rstrip('/')}/api/chat"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                return res_data.get("message", {}).get("content", "")
        except Exception as e:
            print(f"Error querying Ollama API direct: {e}")
            return ""

    def check_is_new_document(self, text, page_num):
        from backend.api import is_new_document_start
        if not is_new_document_start(text):
            return False
            
        clean_text = text[:2000]
        clean_text = re.sub(r'#+\s*', '', clean_text)
        clean_text = re.sub(r'\|', ' ', clean_text)
        clean_text = re.sub(r'[-:]{3,}', ' ', clean_text)
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        
        system_prompt = "Ты — эксперт по анализу структуры юридических документов. Твоя задача — определить, начинается ли на данной странице НОВЫЙ документ (например, Акт, Договор, Соглашение, Справка, Накладная). Выведи ответ СТРОГО в формате XML-тегов: <split><is_new>true или false</is_new></split>. Не пиши никаких рассуждений, пояснений или другого текста. Пиши только XML."
        prompt = f"Текст страницы:\n{clean_text[:1500]}"
        
        resp = self.query_ollama(prompt, system_prompt)
        resp_clean = re.sub(r'<think>.*?</think>', '', resp, flags=re.DOTALL).strip().lower()
        return "true" in resp_clean

    def run(self):
        self.log("Инициализация SmolAgents...")
        
        # Instantiate Tool classes passing workflow reference
        get_page_text = GetPageTextTool(self)
        get_document_pages_text = GetDocumentPagesTextTool(self)
        detect_split_points = DetectSplitPointsTool(self)
        extract_document_metadata = ExtractDocumentMetadataTool(self)
        compile_final_filename = CompileFinalFilenameTool(self)
        split_pdf_at_pages = SplitPdfAtPagesTool(self)
        rename_document = RenameDocumentTool(self)
        log_message = LogMessageTool(self)

        # Run agent
        try:
            model = OllamaModel(
                model_id=self.ollama_config.get("model", "saiga:4b"),
                base_url=self.ollama_config.get("base_url", "http://localhost:11434")
            )
            
            agent = CodeAgent(
                tools=[
                    get_page_text,
                    get_document_pages_text,
                    detect_split_points,
                    extract_document_metadata,
                    compile_final_filename,
                    split_pdf_at_pages,
                    rename_document,
                    log_message
                ],
                model=model,
                max_steps=15
            )
            
            total_pages = len(self.pages_text)
            first_10_pages_sample = ""
            for p in self.pages_text[:10]:
                first_10_pages_sample += f"\n--- Page {p['page_num']} ---\n{p['text'][:400]}\n"
                
            task_prompt = f"""You are an autonomous document processing agent. Your goal is to split a large multi-document PDF into individual PDF files and rename them accurately based on their content. Think step-by-step and output only valid Python code to achieve your goal.

YOUR TASK EXECUTION STEPS:
1. Detect potential split points using detect_split_points().
2. Pass the list of split points to split_pdf_at_pages(file_path, split_points) to physically split the PDF.
3. For each split document segment:
   - Extract the OCR text of its page range using get_document_pages_text(start, end).
   - Use extract_document_metadata(text) to get its type, number, date, and parties.
   - Use compile_final_filename(metadata) to get the clean filename.
   - Use rename_document(old_path, new_name, metadata) to rename and register the document.
4. When done, print("TASK_COMPLETE").

CURRENT CONTEXT:
- file_path: "{self.file_path}"
- Total pages: {total_pages}
- Sample text from first pages: {repr(first_10_pages_sample[:1000])}
"""
            self.log("Запуск CodeAgent...")
            agent.run(task_prompt)
            self.log("Агент успешно завершил работу.")
        except Exception as e:
            self.log(f"Ошибка выполнения агента: {e}. Применение резервной логики...")

        # Fallback if no documents were processed by agent
        if not self.documents:
            self.log("Резервный разбор документов...")
            try:
                # Detect split points manually using our check_is_new_document helper
                split_points = [1]
                if self.mode != "rename":
                    for p in self.pages_text:
                        page_num = p['page_num']
                        if page_num == 1:
                            continue
                        if self.mode == "extract" and not self.extract_settings.get('split', True):
                            continue
                        text = p['text'][:3000]
                        if self.check_is_new_document(text, page_num):
                            split_points.append(page_num)
                
                # Split and compile names manually
                total_pages = len(self.pages_text)
                sp = sorted(list(set(split_points)))
                
                for i in range(len(sp)):
                    start = sp[i]
                    end = sp[i+1] - 1 if i+1 < len(sp) else total_pages
                    
                    segment_texts = [p['text'] for p in self.pages_text if start <= p['page_num'] <= end]
                    combined_text = "\n\n".join(segment_texts)
                    
                    # Extract metadata
                    meta_prompt = f"""Ты — строгий робот-анализатор. Твоя задача — извлечь реквизиты документа из его текста (полученного через OCR).
Выведи результат СТРОГО в формате JSON. Не пиши никаких рассуждений.

ВАЖНО:
1. parties (Стороны) — краткие названия организаций и ФИО граждан. Исключи ИНН, ОГРН, адреса.
2. doc_type (Тип) — ПОЛНОЕ ДОСЛОВНОЕ наименование (заголовок) документа как в тексте (без сокращений, со всеми приписками).
3. number (Номер) — только короткий номер. Если нет, верни "-".
4. date (Дата) — в формате ДД.ММ.ГГГГ. Если нет, верни "-".

Формат:
{{
  "parties": "Стороны",
  "doc_type": "Тип",
  "number": "Номер",
  "date": "Дата"
}}

Текст:
{combined_text[:3000]}
"""
                    resp = self.query_ollama(meta_prompt)
                    resp_clean = re.sub(r'<think>.*?</think>', '', resp, flags=re.DOTALL).strip()
                    json_match = re.search(r'\{.*\}', resp_clean, flags=re.DOTALL)
                    meta = {}
                    if json_match:
                        try:
                            meta = json.loads(json_match.group(0))
                        except:
                            pass
                            
                    raw_type = self.clean_doc_type(meta.get("doc_type", "Документ"))
                    doc_number = meta.get("number", "-")
                    clean_date = self.clean_doc_date(meta.get("date", "-"))
                    parties = self.format_parties(meta.get("parties", "-"))
                    
                    # Build full name
                    full_parts = []
                    full_type = raw_type
                    # Удалено жесткое приведение типов, чтобы сохранить полное наименование
                    
                    full_parts.append(full_type)
                    if doc_number and doc_number != "-":
                        clean_num = doc_number.replace("№", "").replace("номер", "").replace("No", "").strip()
                        if clean_num:
                            full_parts.append(f"№{clean_num}")
                    if clean_date and clean_date != "-":
                        full_parts.append(f"от {clean_date}")
                    full_name = " ".join(full_parts)
                    
                    # Preview Image
                    b64_image = ""
                    try:
                        tmp_doc = fitz.open(self.file_path)
                        tmp_page = tmp_doc[start - 1]
                        pix = tmp_page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
                        img_data = pix.tobytes("jpeg", 80)
                        b64_image = base64.b64encode(img_data).decode("utf-8")
                        tmp_doc.close()
                    except Exception as e:
                        print(f"Error in preview image: {e}")
                        
                    doc_item = {
                        "original_file": self.file_path,
                        "start_page": start,
                        "end_page": end,
                        "actual_page_count": end - start + 1,
                        "is_docx": False,
                        "parties": parties,
                        "short_name": raw_type,
                        "full_name": full_name,
                        "date": clean_date,
                        "confidence": True,
                        "isMerged": False,
                        "isActive": True,
                        "isManualEdit": False,
                        "new_name": full_name,
                        "text": combined_text,
                        "image_b64": b64_image
                    }
                    self.documents.append(doc_item)
            except Exception as e:
                self.log(f"Сбой резервного разбора: {e}")

        # Cleanup temp files
        for f in self.temp_files:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except:
                pass
                
        # Sort documents by start_page to ensure UI receives them ordered
        self.documents.sort(key=lambda x: x.get("start_page", 1))
        return self.documents
