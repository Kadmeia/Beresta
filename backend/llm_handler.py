import os
import json
import re
from llama_cpp import Llama

class LLMHandler:
    def __init__(self, model_path):
        self.model_path = model_path
        self.llm = None

    def load_model(self):
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Model not found at {self.model_path}")
            
        self.llm = Llama(
            model_path=self.model_path,
            n_ctx=4096,
            n_gpu_layers=0,
            verbose=False # Отключаем спам в логи
        )

    def unload_model(self):
        if self.llm:
            self.llm = None

    def analyze_text(self, text, page_num, retry=0):
        if not self.llm:
            self.load_model()
            
        # Prefilled XML-based prompt template for Stage 1 Metadata Extraction
        prompt = f"""<|im_start|>system
Ты — строгий робот-анализатор. Твоя задача — извлечь реквизиты документа из его текста (полученного через OCR).
Исправь опечатки OCR в именах и названиях. Выведи результат СТРОГО в формате XML-тегов.
Не пиши никаких рассуждений, пояснений, вступлений или заключений. Пиши только XML-структуру.

ВАЖНО:
1. Стороны (<parties>) — извлеки краткие названия организаций и ФИО граждан. Обязательно исключи ИНН, ОГРН, адреса, должности, слова "именуемый в дальнейшем".
2. Тип (<doc_type>) — одно слово классифицирующее документ (например: Договор, Акт, Соглашение, Приложение, Справка, Накладная).
3. Номер (<doc_number>) — только короткий номер самого документа (после знака № или слова "номер" в заголовке). Игнорируй банковские счета, ИНН, ОГРН, ОГРНИП. Если номера нет, пиши "-".
4. Дата (<doc_date>) — дата подписания документа. Переведи её в числовой формат ДД.ММ.ГГГГ. Если даты нет, пиши "-".
5. Игнорируй номера и даты договоров-оснований, упоминаемых в тексте документа. Нужны только реквизиты самого документа.

Пример 1:
<|im_end|>
<|im_start|>user
Текст документа:
АКТ ВЫПОЛНЕННЫХ РАБОТ № 4
г. Пермь
12 апреля 2025 года
Индивидуальный предприниматель Петров П.П. и ООО "Ромашка"...
Основание: Договор № 12/А от 01.01.2025
<|im_end|>
<|im_start|>assistant
<metadata>
<parties>ИП Петров П.П., ООО "Ромашка"</parties>
<doc_type>Акт</doc_type>
<doc_number>4</doc_number>
<doc_date>12.04.2025</doc_date>
<confidence>100</confidence>
</metadata>
<|im_end|>
<|im_start|>user
Текст документа:
Договор аренды помещения без номера.
г. Пермь
Стороны: гражданин Иванов Иван Иванович и ООО "Глобус"...
<|im_end|>
<|im_start|>assistant
<metadata>
<parties>Иванов Иван Иванович, ООО "Глобус"</parties>
<doc_type>Договор</doc_type>
<doc_number>-</doc_number>
<doc_date>-</doc_date>
<confidence>95</confidence>
</metadata>
<|im_end|>
<|im_start|>user
Текст документа:
{text[:4000]}
<|im_end|>
<|im_start|>assistant
<metadata>
<parties>"""

        try:
            output = self.llm(
                prompt,
                max_tokens=300,
                temperature=0.0, # strict temperature
                stop=["<|im_end|>", "</metadata>"]
            )
            
            # Reconstruct and clean
            response_text = "<metadata>\n<parties>" + output['choices'][0]['text'].strip()
            if not response_text.endswith("</metadata>"):
                response_text += "\n</metadata>"
            
            # Remove any <think> tags if model thought
            response_text = re.sub(r'<think>.*?</think>', '', response_text, flags=re.DOTALL)
            
            print(f"DEBUG LLM RAW:\n{response_text}")
            
            # Stage 1: parse XML fields
            def get_xml_tag(tag, default="-"):
                m = re.search(fr"<{tag}>(.*?)</{tag}>", response_text, flags=re.DOTALL | re.IGNORECASE)
                val = m.group(1).strip() if m else default
                val_clean = val.strip()
                # Игнорируем различные плейсхолдеры и мусорные значения, которые может вернуть ИИ
                if val_clean.lower() in ["", "-", "—", "нет", "none", "null", "б/н", "б/д"]:
                    return default
                return val_clean
                
            parties_raw = get_xml_tag("parties")
            doc_type = get_xml_tag("doc_type", "Документ")
            doc_number = get_xml_tag("doc_number")
            doc_date = get_xml_tag("doc_date")
            confidence_str = get_xml_tag("confidence", "0")
            
            # Parse confidence
            nums = re.findall(r'\d+', confidence_str)
            confidence_score = int(nums[0]) if nums else 0
            
            # Format parties
            def format_parties(text):
                if not text or text == "-": return ""
                text = re.sub(r'(?i)общество\s+с\s+ограниченной\s+ответственностью', 'ООО', text)
                text = re.sub(r'(?i)публичное\s+акционерное\s+общество', 'ПАО', text)
                text = re.sub(r'(?i)акционерное\s+общество', 'АО', text)
                text = re.sub(r'(?i)индивидуальный\s+предприниматель', 'ИП', text)
                
                # Clean LLM artifacts and extra keywords
                text = re.sub(r'(?i)\(?[^,;()]*\b(именуемое в дальнейшем|именуемый в дальнейшем|именуемое|именуемый|именуемая)\b[^,;()]*\)?', '', text)
                text = re.sub(r'(?i)\(?[^,;()]*\b(заказчик|исполнитель|покупатель|поставщик|подрядчик|арендатор|арендодатель|сторона)\b[^,;()]*\)?', '', text)
                text = re.sub(r'(?i)\(?[^,;()]*\b(генеральный\s+директор|директор|в лице|действующего на основании)\b[^,;()]*\)?', '', text)
                text = re.sub(r'(?i)ОГРНИП\s*\d*', '', text)
                text = re.sub(r'(?i)ОГРН\s*\d*', '', text)
                text = re.sub(r'(?i)ОГРИП\s*\d*', '', text)
                text = re.sub(r'(?i)ИНН\s*\d*', '', text)
                text = re.sub(r'(?i)\(ИНН[^)]*\)', '', text)
                text = re.sub(r'(?i)\(ОГРНИП[^)]*\)', '', text)
                
                text = re.sub(r'\d{10,}', '', text)
                text = re.sub(r'\(\s*\)', '', text)
                text = re.sub(r'[;]', ',', text)
                text = re.sub(r',\s*,', ',', text)
                text = re.sub(r'^\s*,\s*|\s*,\s*$', '', text)
                
                if not text.strip(): return "-"
                
                parts = [p.strip() for p in text.split(',') if p.strip()]
                clean_parts = []
                seen = set()
                for p in parts:
                    if p.lower().startswith('и '):
                        p = p[2:].strip()
                    # Clean trailing artifacts
                    p = re.sub(r'(?i)\s+ОГРИП\s*$', '', p)
                    p = re.sub(r'(?i)\s+ОГРНИП\s*$', '', p)
                    p = re.sub(r'(?i)\s+ОГРН\s*$', '', p)
                    
                    # Normalize known entity variations (removed hardcoded examples)

                        
                    if len(p) > 2 and len(p) < 80 and not p.lower().startswith('с одной стороны') and not p.lower().startswith('с другой стороны'):
                        if p not in seen:
                            seen.add(p)
                            clean_parts.append(p)
                
                result = "_".join(clean_parts)
                return result if result else "-"

            parties = format_parties(parties_raw)
            
            # Format and sanitize doc_type
            first_word_match = re.search(r'^([А-Яа-яЁёA-Za-z]+)', doc_type)
            if first_word_match:
                raw_type = first_word_match.group(1).capitalize()
            else:
                raw_type = "Документ"
            raw_type = raw_type.replace('N&', '№').replace('Ng', '№').replace('N@', '№')
            
            # Parse date strictly (ensure DD.MM.YYYY)
            date_match = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', doc_date)
            clean_date = f"{date_match.group(1)}.{date_match.group(2)}.{date_match.group(3)}" if date_match else "-"
            
            if clean_date == "-":
                # Fallback: try to extract from raw text using regex, picking the earliest match
                matches = []
                
                # 1. Look for DD.MM.YYYY or DD.MM.YY
                for m in re.finditer(r'\b(\d{1,2})\.(\d{2})\.(\d{2,4})\b', text):
                    day = int(m.group(1))
                    month = m.group(2)
                    year = m.group(3)
                    if len(year) == 2:
                        year = "20" + year
                    matches.append((m.start(), f"{day:02d}.{month}.{year}"))
                    
                # 2. Look for DD MonthName YYYY/YY
                months_ru = {
                    "января": "01", "февраля": "02", "марта": "03", "апреля": "04",
                    "мая": "05", "июня": "06", "июля": "07", "августа": "08",
                    "сентября": "09", "октября": "10", "ноября": "11", "декабря": "12"
                }
                months_pattern = "|".join(months_ru.keys())
                for m in re.finditer(fr'\b(\d{{1,2}})\s+({months_pattern})\s+(\d{{2,4}})\b', text, re.IGNORECASE):
                    day = int(m.group(1))
                    month = months_ru[m.group(2).lower()]
                    year = m.group(3)
                    if len(year) == 2:
                        year = "20" + year
                    matches.append((m.start(), f"{day:02d}.{month}.{year}"))
                
                if matches:
                    # Sort matches by start position in text
                    matches.sort(key=lambda x: x[0])
                    clean_date = matches[0][1]
            
            # Stage 2: Compile name in Python to avoid hallucinations
            full_parts = []
            full_type = raw_type
            if raw_type.lower() == "акт":
                full_type = "Акт выполненных работ"
            elif raw_type.lower() == "договор":
                full_type = "Договор"
            elif raw_type.lower() == "соглашение":
                full_type = "Дополнительное соглашение"
            elif raw_type.lower() == "накладная":
                full_type = "Товарная накладная"
                
            full_parts.append(full_type)
            if doc_number and doc_number != "-":
                clean_num = doc_number.replace("№", "").replace("номер", "").replace("No", "").strip()
                if clean_num:
                    full_parts.append(f"№{clean_num}")
            if clean_date and clean_date != "-":
                full_parts.append(f"от {clean_date}")
            full_name = " ".join(full_parts)
            
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

    def is_new_document(self, text, page_num):
        """Verifies if the page starts a new document using the LLM."""
        if not self.llm:
            self.load_model()
            
        # Clean text for split decision to match examples and simplify for small LLM
        clean_text = text[:2000]
        # Remove markdown headers
        clean_text = re.sub(r'#+\s*', '', clean_text)
        # Remove markdown table lines
        clean_text = re.sub(r'\|', ' ', clean_text)
        clean_text = re.sub(r'[-:]{3,}', ' ', clean_text)
        # Normalize spaces and newlines
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
            
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
            output = self.llm(
                prompt,
                max_tokens=300,
                temperature=0.0,
                stop=["<|im_end|>", "</split>"]
            )
            raw_response = output['choices'][0]['text']
            if not raw_response.endswith("</split>") and "</split>" not in raw_response:
                raw_response += "</split>"
            response_clean = re.sub(r'<think>.*?</think>', '', raw_response, flags=re.DOTALL).strip().lower()
            return "true" in response_clean
        except Exception as e:
            print(f"Error in is_new_document LLM call: {e}")
            return False

    def proofread_text(self, raw_text):
        if not self.llm:
            self.load_model()
            
        prompt = f"""<|im_start|>system
Ты — профессиональный корректор. Твоя задача исправить опечатки распознавания текста (OCR), убрать лишние переносы строк внутри абзацев и исправить лишние пробелы.
Не меняй смысл текста, факты, ФИО, цифры и суммы. Выведи ТОЛЬКО исправленный текст без вступительных или заключительных слов.<|im_end|>
<|im_start|>user
Текст для исправления:
{raw_text}<|im_end|>
<|im_start|>assistant
"""
        try:
            output = self.llm(
                prompt,
                max_tokens=4000,
                temperature=0.1,
                repeat_penalty=1.15,
                stop=["<|im_end|>", "user"]
            )
            response_text = output['choices'][0]['text'].strip()
            
            # Убираем теги <think>
            response_text = re.sub(r'<think>.*?</think>', '', response_text, flags=re.DOTALL).strip()
            
            # Если нейросеть почему-то вернула пустой результат, возвращаем оригинал
            if not response_text:
                return raw_text
                
            return response_text
        except Exception as e:
            print(f"LLM Proofread Error: {e}")
            return raw_text
