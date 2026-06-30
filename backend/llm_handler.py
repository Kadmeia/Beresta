import os
import json
import re
import subprocess
import time
import urllib.request
import platform
import socket

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None

METADATA_GRAMMAR = r"""root      ::= "<metadata>\n" parties typ num date conf "</metadata>"
parties   ::= "<parties>" line "</parties>\n"
typ       ::= "<doc_type>" line "</doc_type>\n"
num       ::= "<doc_number>" line "</doc_number>\n"
date      ::= "<doc_date>" line "</doc_date>\n"
conf      ::= "<confidence>" [0-9]+ "</confidence>\n"
line      ::= [^<\n]*
"""

def format_parties(text):
    if not text or text == "-": return ""
    
    # Сокращение организационно-правовых форм
    text = re.sub(r'(?i)общество\s+с\s+ограниченной\s+ответственностью', 'ООО', text)
    text = re.sub(r'(?i)публичное\s+акционерное\s+общество', 'ПАО', text)
    text = re.sub(r'(?i)акционерное\s+общество', 'АО', text)
    text = re.sub(r'(?i)индивидуальный\s+предприниматель', 'ИП', text)
    
    # Удаление ИНН/ОГРН и цифр
    text = re.sub(r'(?i)ОГРНИП\s*\d*', '', text)
    text = re.sub(r'(?i)ОГРН\s*\d*', '', text)
    text = re.sub(r'(?i)ОГРИП\s*\d*', '', text)
    text = re.sub(r'(?i)ИНН\s*\d*', '', text)
    text = re.sub(r'\d{10,}', '', text)
    
    # Очистка от ролей и лишних фраз (нежадная замена)
    text = re.sub(r'(?i)\b(именуем[а-я]+\s+в\s+дальнейшем|именуем[а-я]+)\b', '', text)
    text = re.sub(r'(?i)\b(заказчик[а-я]*|исполнитель[а-я]*|покупатель[а-я]*|поставщик[а-я]*|подрядчик[а-я]*|арендатор[а-я]*|арендодатель[а-я]*|сторона[а-я]*|сторон[а-я]*)\b', '', text)
    text = re.sub(r'(?i)\b(генеральный\s+директор[а-я]*|директор[а-я]*|в\s+лице|действующ[а-я]+\s+на\s+основании)\b', '', text)
    
    # Очистка мусорных символов и скобок
    text = re.sub(r'\(\s*\)', '', text)
    text = re.sub(r'[;]', ',', text)
    text = re.sub(r',\s*,', ',', text)
    
    # Разделяем по запятым и союзу "и"
    raw_parts = []
    for part in text.split(','):
        sub_parts = re.split(r'\s+и\s+', part)
        raw_parts.extend(sub_parts)
        
    clean_parts = []
    seen = set()
    for p in raw_parts:
        p = p.strip()
        p = re.sub(r'^["\'«“` ]+|["\'»”` ]+$', '', p)
        p = p.strip()
        
        p_lower = p.lower()
        if (len(p) > 2 and len(p) < 80 
            and not p_lower.startswith('с одной стороны') 
            and not p_lower.startswith('с другой стороны')
            and p_lower not in ['физическое лицо', 'юридическое лицо', 'гражданин', 'гражданка', 'ооо', 'ип', 'пао', 'ао']):
            
            if p not in seen:
                seen.add(p)
                clean_parts.append(p)
                
    result = "_".join(clean_parts)
    return result if result else "-"

def clean_doc_type(doc_type):
    if not doc_type:
        return "Документ"
    cleaned = re.sub(r'[^\w\s\-№""«»\.\,]', '', doc_type).strip()
    cleaned = re.sub(r'\s+', ' ', cleaned)
    if cleaned:
        cleaned = cleaned[0].upper() + cleaned[1:]
    else:
        cleaned = "Документ"
    cleaned = cleaned.replace('N&', '№').replace('Ng', '№').replace('N@', '№')
    return cleaned

def clean_doc_date(doc_date, document_text=None):
    if not doc_date:
        doc_date = "-"
    doc_date = doc_date.strip()
    
    # 1. Попытка найти ДД.ММ.ГГГГ
    date_match = re.search(r'(\d{1,2})\.(\d{1,2})\.(\d{4})', doc_date)
    if date_match:
        day = date_match.group(1).zfill(2)
        month = date_match.group(2).zfill(2)
        year = date_match.group(3)
        return f"{day}.{month}.{year}"
        
    # 2. Попытка распарсить текстовую дату вроде "12 апреля 2025"
    months_map = {
        "янв": "01", "фев": "02", "мар": "03", "апр": "04", "май": "05", "мая": "05",
        "июн": "06", "июл": "07", "авг": "08", "сен": "09", "окт": "10", "ноя": "11", "дек": "12"
    }
    
    text_date_match = re.search(r'(\d{1,2})\s+([а-яёА-ЯЁ]+)\s+(\d{4})', doc_date)
    if text_date_match:
        day = text_date_match.group(1).zfill(2)
        month_str = text_date_match.group(2).lower()[:3]
        year = text_date_match.group(3)
        if month_str in months_map:
            return f"{day}.{months_map[month_str]}.{year}"
            
    return "-"

class GeminiHandler:
    def __init__(self, api_key, model_name):
        self.api_key = api_key
        self.model_name = model_name
        if not genai:
            raise RuntimeError("google-genai не установлен. Пожалуйста, выполните: pip install google-genai")
        self.client = genai.Client(api_key=self.api_key)

    def analyze_documents_bulk(self, docs_text_list):
        prompt = """Ты — строгий робот-анализатор. Твоя задача — извлечь реквизиты документов из переданных текстов (полученных через OCR).
Исправь опечатки OCR в именах и названиях. Выведи результат СТРОГО в формате JSON.
Не пиши никаких рассуждений.

ПРАВИЛА ИЗВЛЕЧЕНИЯ ДЛЯ КАЖДОГО ДОКУМЕНТА:
1. Стороны (parties) — извлеки краткие названия организаций и ФИО граждан. Обязательно исключи ИНН, ОГРН, адреса, должности, слова "именуемый в дальнейшем". Если сторон нет, верни "-".
2. Тип (doc_type) — ПОЛНОЕ ДОСЛОВНОЕ наименование (заголовок) документа как в тексте. Обязательно включай все относящиеся к заголовку приписки (например: "к Приложению №1...", "к Договору...", "на объект недвижимости"). НЕ сокращай заголовок до одного слова! (например: "Акт сдачи-приемки оказанных услуг к Приложению №15", "Выписка из ЕГРН об основных характеристиках"). По умолчанию "Документ".
3. Номер (number) — только короткий номер самого документа (после знака № или слова "номер"). Игнорируй ИНН/ОГРН. Если нет, верни "-".
4. Дата (date) — дата подписания документа. Переведи её в числовой формат ДД.ММ.ГГГГ. Если нет, верни "-".
5. Учитывай только реквизиты текущего документа, игнорируй реквизиты договоров-оснований, упоминаемых в тексте.
6. Поле doc_id должно в точности соответствовать переданному DOCUMENT ID (это строка-идентификатор).

Формат вывода (JSON):
{
  "results": [
    {
      "doc_id": <string>,
      "parties": <string>,
      "doc_type": <string>,
      "number": <string>,
      "date": <string>
    }
  ]
}

Входные документы:
"""
        for doc in docs_text_list:
            prompt += f"\n--- DOCUMENT ID {doc['doc_id']} ---\n{doc['text'][:3000]}\n"

        import time
        max_retries = 5
        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.0
                    )
                )
                data = json.loads(response.text)
                return data.get("results", [])
            except Exception as e:
                err_str = str(e)
                if ("503" in err_str or "429" in err_str) and attempt < max_retries - 1:
                    print(f"Gemini API rate limit / 503 error (attempt {attempt+1}/{max_retries}). Retrying in 8 seconds...")
                    time.sleep(8)
                    continue
                import traceback
                error_details = traceback.format_exc()
                print(f"Gemini API Error details:\n{error_details}")
                raise RuntimeError(f"{e}")

class LLMHandler:
    def __init__(self, model_path):
        self.model_path = model_path
        self.model_dir = os.path.dirname(model_path)
        self.server_path = os.path.join(self.model_dir, 'bin', 'llama-server')
        self.process = None
        self.port = None

    def _find_free_port(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('', 0))
        port = s.getsockname()[1]
        s.close()
        return port

    def load_model(self):
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Модель не найдена по пути: {self.model_path}")
            
        if not os.path.exists(self.server_path):
            raise FileNotFoundError(f"Движок llama-server не найден по пути: {self.server_path}. Пожалуйста, скачайте компоненты.")
            
        self.port = self._find_free_port()
        
        machine = platform.machine().lower()
        # На Apple Silicon (arm64) переносим все слои в GPU (Metal)
        # На Intel (x86_64) используем CPU (ngl 0)
        ngl = "99" if ("arm" in machine or "aarch64" in machine) else "0"
        
        cmd = [
            self.server_path,
            "-m", self.model_path,
            "-c", "4096",
            "--port", str(self.port),
            "-ngl", ngl,
            "--threads", "4",
            "--log-disable"
        ]
        
        print(f"Starting llama-server: {' '.join(cmd)}")
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Ждем запуска сервера, опрашивая endpoint /health
        health_url = f"http://127.0.0.1:{self.port}/health"
        retries = 40
        connected = False
        for _ in range(retries):
            if self.process.poll() is not None:
                stderr_output = self.process.stderr.read()
                print(f"llama-server завершился с кодом {self.process.returncode}. Stderr: {stderr_output}")
                raise RuntimeError(f"Не удалось запустить движок ИИ: {stderr_output}")
                
            try:
                req = urllib.request.Request(health_url)
                with urllib.request.urlopen(req, timeout=1) as response:
                    if response.status == 200:
                        data = json.loads(response.read().decode('utf-8'))
                        if data.get('status') == 'ok':
                            connected = True
                            break
            except Exception:
                pass
            time.sleep(0.5)
            
        if not connected:
            self.unload_model()
            raise RuntimeError("Превышено время ожидания запуска ИИ движка.")
            
        print(f"llama-server успешно запущен на порту {self.port}")

    def unload_model(self):
        if self.process:
            print("Stopping llama-server process...")
            try:
                self.process.terminate()
                self.process.wait(timeout=3)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None
            self.port = None

    def __del__(self):
        self.unload_model()

    def _query_server(self, prompt, max_tokens=300, temperature=0.0, repeat_penalty=1.0, stop=None, grammar=None, progress_callback=None):
        if stop is None:
            stop = []
        if not self.process:
            self.load_model()
            
        print(f"\n[INFO] Начат запрос к локальной LLM (размер промпта: {len(prompt)} символов)")
        url = f"http://127.0.0.1:{self.port}/completion"
        data = {
            "prompt": prompt,
            "n_predict": max_tokens,
            "temperature": temperature,
            "repeat_penalty": repeat_penalty,
            "stop": stop,
            "stream": bool(progress_callback)
        }
        if grammar:
            data["grammar"] = grammar
        
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        
        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                import sys
                if progress_callback:
                    full_text = ""
                    tokens_count = 0
                    print("\n[LLM] ", end="", flush=True)
                    for line in response:
                        line_str = line.decode('utf-8').strip()
                        if line_str.startswith("data: "):
                            try:
                                chunk = json.loads(line_str[6:])
                                content = chunk.get("content", "")
                                if content:
                                    sys.stdout.write(content)
                                    sys.stdout.flush()
                                full_text += content
                                tokens_count += 1
                                if tokens_count % 15 == 0:
                                    progress_callback(tokens_count)
                            except json.JSONDecodeError:
                                pass
                    print()
                    return full_text
                else:
                    res_data = json.loads(response.read().decode('utf-8'))
                    return res_data.get('content', '')
        except Exception as e:
            print(f"Error querying llama-server: {e}")
            raise RuntimeError(f"Ошибка обращения к ИИ-серверу: {e}")

    def analyze_text(self, text, page_num, retry=0, progress_callback=None):
        prompt = f"""<|im_start|>system
Ты — строгий робот-анализатор юридических документов (гражданские, уголовные, административные дела). Твоя задача — извлечь реквизиты документа из его текста (полученного через OCR).
Исправь опечатки OCR в именах и названиях. Выведи результат СТРОГО в формате XML-тегов.
Не пиши никаких рассуждений, пояснений или вступлений. Пиши только XML-структуру.

ВАЖНО:
1. Стороны (<parties>) — краткие названия организаций (ООО "Ромашка", ИП Иванов) и ФИО граждан.
   - Для процессуальных актов: обвиняемый, истец, судья, следователь и т.д.
   - Для свидетельств: граждане, в отношении которых выдан документ.
   - Если сторон нет, пиши "-". Обязательно исключи ИНН, ОГРН, адреса, должности.
2. Тип (<doc_type>) — ПОЛНОЕ наименование (заголовок) документа.
   - Обязательно включай все относящиеся к заголовку приписки (например: "к Договору...", "на объект недвижимости", "по делу об административном правонарушении").
   - ЕСЛИ это Приложение, Дополнительное соглашение или Спецификация к договору, ОБЯЗАТЕЛЬНО пиши полный заголовок (например: "Приложение к Договору аренды").
   - НЕ сокращай заголовок до одного слова! 
3. Номер (<doc_number>) — только короткий номер САМОГО документа (после знака № или слова "номер"). 
   - ЕСЛИ это "Приложение № 1", то номер приложения это "1". Если номера у самого документа нет, пиши "-".
   - Игнорируй номера договоров-оснований, ИНН, банковские счета.
4. Дата (<doc_date>) — дата подписания/выдачи документа (ДД.ММ.ГГГГ). Если даты нет, пиши "-".
5. Учитывай только реквизиты самого документа. Игнорируй реквизиты договоров-оснований (кроме как в составе doc_type для Приложений).

Пример 1:
<|im_end|>
<|im_start|>user
Текст документа:
Приложение № 1
к Договору оказания услуг № 12/А от 01.01.2025
г. Пермь
Индивидуальный предприниматель Петров П.П. и ООО "Ромашка"...
<|im_end|>
<|im_start|>assistant
<metadata>
<parties>ИП Петров П.П., ООО "Ромашка"</parties>
<doc_type>Приложение к Договору оказания услуг № 12/А от 01.01.2025</doc_type>
<doc_number>1</doc_number>
<doc_date>-</doc_date>
<confidence>100</confidence>
</metadata>
<|im_end|>
<|im_start|>user
Текст документа:
СУДЕБНЫЙ УЧАСТОК № 234
ПОСТАНОВЛЕНИЕ
по делу об административном правонарушении № 5-234/2026
г. Москва, 15 мая 2026 года
Мировой судья судебного участка № 234 района Арбат г. Москвы, рассмотрев материалы дела в отношении гражданина Иванова И.И....
<|im_end|>
<|im_start|>assistant
<metadata>
<parties>Мировой судья судебного участка № 234, Иванов И.И.</parties>
<doc_type>Постановление по делу об административном правонарушении</doc_type>
<doc_number>5-234/2026</doc_number>
<doc_date>15.05.2026</doc_date>
<confidence>100</confidence>
</metadata>
<|im_end|>
<|im_start|>user
Текст документа:
СВИДЕТЕЛЬСТВО О РАСТОРЖЕНИИ БРАКА
Гражданин Петров Петр Петрович и гражданка Петрова Анна Сергеевна, брак между которыми прекращен 10 января 2026 года...
Дата выдачи: 15 января 2026 года. Номер записи акта № 12345
<|im_end|>
<|im_start|>assistant
<metadata>
<parties>Петров Петр Петрович, Петрова Анна Сергеевна</parties>
<doc_type>Свидетельство о расторжении брака</doc_type>
<doc_number>12345</doc_number>
<doc_date>15.01.2026</doc_date>
<confidence>95</confidence>
</metadata>
<|im_end|>
<|im_start|>user
Текст документа:
{text[:4000]}
<|im_end|>
<|im_start|>assistant
"""

        try:
            generated_text = self._query_server(
                prompt,
                max_tokens=300,
                temperature=0.0,
                stop=["<|im_end|>"],
                grammar=METADATA_GRAMMAR,
                progress_callback=progress_callback
            )
            
            response_text = generated_text.strip()
            if not response_text.endswith("</metadata>"):
                response_text += "\n</metadata>"
            
            response_text = re.sub(r'<think>.*?</think>', '', response_text, flags=re.DOTALL)
            
            print(f"DEBUG LLM RAW:\n{response_text}")
            
            # Чтение полей
            def get_xml_tag(tag, default="-"):
                m = re.search(fr"<{tag}>(.*?)</{tag}>", response_text, flags=re.DOTALL | re.IGNORECASE)
                val = m.group(1).strip() if m else default
                val_clean = val.strip()
                if val_clean.lower() in ["", "-", "—", "нет", "none", "null", "б/н", "б/д"]:
                    return default
                return val_clean
                
            parties_raw = get_xml_tag("parties")
            doc_type = get_xml_tag("doc_type", "Документ")
            doc_number = get_xml_tag("doc_number")
            doc_date = get_xml_tag("doc_date")
            confidence_str = get_xml_tag("confidence", "0")
            
            nums = re.findall(r'\d+', confidence_str)
            confidence_score = int(nums[0]) if nums else 0
            
            parties = format_parties(parties_raw)
            raw_type = clean_doc_type(doc_type)
            clean_date = clean_doc_date(doc_date, text)
            
            clean_num = ""
            if doc_number and doc_number != "-":
                clean_num = doc_number.replace("№", "").replace("номер", "").replace("No", "").strip()

            full_parts = []
            
            # Умная сборка названия, чтобы не дублировать номера и правильно склеивать приложения
            if clean_num and (f"№{clean_num}" in raw_type.replace(" ", "") or clean_num in raw_type):
                full_parts.append(raw_type)
            else:
                is_appendix = bool(re.search(r'(?i)^(приложение|дополнительное\s+соглашение|доп\.\s*соглашение|спецификация)', raw_type))
                if is_appendix and clean_num:
                    raw_type = re.sub(
                        r'(?i)^(приложение|дополнительное\s+соглашение|доп\.\s*соглашение|спецификация)', 
                        lambda m: m.group(1) + ' № ' + clean_num, 
                        raw_type
                    )
                    full_parts.append(raw_type)
                else:
                    full_parts.append(raw_type)
                    if clean_num:
                        full_parts.append(f"№ {clean_num}")
                        
            if clean_date and clean_date != "-":
                if clean_date not in raw_type:
                    full_parts.append(f"от {clean_date}")
                    
            full_name = " ".join(full_parts)
            full_name = re.sub(r'\s+', ' ', full_name).strip()
            
            return {
                "parties": parties,
                "short_name": raw_type,
                "full_name": full_name,
                "date": clean_date,
                "confidence_score": confidence_score
            }
            
        except Exception as e:
            print(f"LLM Error: {e}")
            return {
                "parties": "",
                "short_name": "Документ",
                "full_name": "Неизвестный документ",
                "date": "",
                "confidence_score": 0
            }

    def is_new_document(self, text, page_num, progress_callback=None):
        """Проверяет, начинается ли новый документ на текущей странице."""
        clean_text = text[:2000]
        clean_text = re.sub(r'#+\s*', '', clean_text)
        clean_text = re.sub(r'\|', ' ', clean_text)
        clean_text = re.sub(r'[-:]{3,}', ' ', clean_text)
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
            
        print(f"[DEBUG] is_new_document: Формирование промпта (длина чистого текста: {len(clean_text)})")
        prompt = f"""<|im_start|>system
Ты — эксперт по анализу структуры юридических документов. Твоя задача — определить, начинается ли на данной странице НОВЫЙ документ (например, Акт, Договор, Соглашение, Справка, Накладная).
Выведи ответ СТРОГО в формате XML-тегов:
<split>
<is_new>true или false</is_new>
</split>
Не пиши никаких рассуждений, пояснений или другого текста. Пиши только XML.

ПРАВИЛА:
1. Если на странице есть полноценный заголовок нового документа (например, "АКТ ВЫПОЛНЕННЫХ РАБОТ", "ДОГОВОР", "СОГЛАШЕНИЕ") в первых строках, а также дата и место составления — это ВСЕГДА новый документ (is_new = true).
2. Если страница начинается с продолжения текста предыдущего документа (например, с середины предложения, пунктов вроде "п. 4.2", "5. Права сторон", таблицы услуг или подписей) без нового заголовка в самом начале — это продолжение документа (is_new = false).
3. Если страница начинается с указания места (например, "г. Москва") и даты (например, "31 июля 2025г."), после чего идет название организации — это ВСЕГДА новый документ (is_new = true), даже если заголовок был пропущен при распознавании (OCR).
4. Если на странице есть заголовок нового документа (например, "АКТ ВЫПОЛНЕННЫХ РАБОТ", "ДОГОВОР") и либо место составления (например, "г. Москва"), либо дата составления (например, "30 ноября 2023 г."), после чего идет название организации — это ВСЕГДА новый документ (is_new = true).
5. Если на странице в самом начале есть заголовок нового документа (например, "АКТ ВЫПОЛНЕННЫХ РАБОТ"), дата, место и стороны, то это новый документ (is_new = true), даже если на этой же странице есть подписи или таблицы (одностраничный документ).

Примеры:
Ввод: АКТ ВЫПОЛНЕННЫХ РАБОТ № 4. г. Пермь, 12 апреля 2025 года. ООО "Ромашка" и ИП Петров...
Вывод: <split><is_new>true</is_new></split>

Ввод: г. Москва. 31 марта 2025г. Общество с ограниченной ответственностью "ТехноПром" и ИП Лаврентьев...
Вывод: <split><is_new>true</is_new></split>

Ввод: Акт Nº от 30 ноября 2023 г. ИП Лаврентьев Александр Владимирович, ИНН 590299825983...
Вывод: <split><is_new>true</is_new></split>

Ввод: Настоящий акт составлен в двух экземплярах, по одному для каждой стороны. Подписи сторон: Заказчик...
Вывод: <split><is_new>false</is_new></split>
<|im_end|>
<|im_start|>user
Текст страницы:
{clean_text[:1500]}
<|im_end|>
<|im_start|>assistant
"""
        try:
            print("[DEBUG] is_new_document: Запрос к _query_server...")
            raw_response = self._query_server(
                prompt,
                max_tokens=100,
                temperature=0.0,
                stop=["<|im_end|>", "</split>"],
                progress_callback=progress_callback
            )
            print(f"[DEBUG] is_new_document: Получен ответ от сервера: {repr(raw_response)}")
            if not raw_response.endswith("</split>") and "</split>" not in raw_response:
                raw_response += "</split>"
            response_clean = re.sub(r'<think>.*?</think>', '', raw_response, flags=re.DOTALL).strip().lower()
            return "true" in response_clean
        except Exception as e:
            print(f"Error in is_new_document LLM call: {e}")
            return False

    def proofread_text(self, raw_text, progress_callback=None):
        """Исправляет ошибки OCR."""
        prompt = f"""<|im_start|>system
Ты — профессиональный корректор. Твоя задача исправить опечатки распознавания текста (OCR), убрать лишние переносы строк внутри абзацев и исправить лишние пробелы.
Не меняй смысл текста, факты, ФИО, цифры и суммы. Выведи ТОЛЬКО исправленный текст без вступительных или заключительных слов.<|im_end|>
<|im_start|>user
Текст для исправления:
{raw_text}<|im_end|>
<|im_start|>assistant
"""
        try:
            response_text = self._query_server(
                prompt,
                max_tokens=2048,
                temperature=0.1,
                repeat_penalty=1.0,
                stop=["<|im_end|>", "user"],
                progress_callback=progress_callback
            )
            response_text = re.sub(r'<think>.*?</think>', '', response_text, flags=re.DOTALL).strip()
            
            if not response_text:
                return raw_text
                
            return response_text
        except Exception as e:
            print(f"LLM Proofread Error: {e}")
            return raw_text
