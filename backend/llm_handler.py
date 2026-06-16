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
            
        # Для Вихрь/Сайга (и других локальных 1.5B-8B моделей) лучше всего работает жесткий Few-Shot
        # Убираем лишние инструкции, даем четкий паттерн. 2 примера: полный и пустой, чтобы отучить галлюцинировать.
        prompt = f"""<|im_start|>system
Ты строгий парсер данных. Твоя задача — извлечь реквизиты из текста документа.
Отвечай СТРОГО в формате 5 строк. Никаких приветствий, рассуждений и лишних слов.
Формат ответа:
Стороны: [ТОЛЬКО краткие названия компаний или ФИО через запятую. УБИРАЙ должности, ИНН, ОГРНИП, и слова типа "Именуемое в дальнейшем", "Заказчик", "Исполнитель". Пример: ООО "Альфа", ИП Петров В.В.]
Тип: [Одно слово: Договор / Акт / Счет / Выписка / Свидетельство / Постановление / Письмо / Приложение / Документ]
Полное: [Тип документа + номер. Если нет номера - пиши без него]
Дата: [ДД.ММ.ГГГГ. Если даты в тексте НЕТ вообще - пиши "-"]
Уверенность: [от 0 до 100]<|im_end|>
<|im_start|>user
Текст документа:
ДОПОЛНИТЕЛЬНОЕ СОГЛАШЕНИЕ № 2
к Трудовому договору № 14 от 01.09.2022 г.
Работодатель: ООО "ТехКран"
Работник: Васильев Иван Николаевич<|im_end|>
<|im_start|>assistant
Стороны: ООО "ТехКран", Васильев Иван Николаевич
Тип: Соглашение
Полное: Дополнительное соглашение № 2
Дата: 01.09.2022
Уверенность: 100<|im_end|>
<|im_start|>user
Текст документа:
Копия справки МСЭ об установлении инвалидности. Выдана по запросу.<|im_end|>
<|im_start|>assistant
Стороны: -
Тип: Справка
Полное: Копия справки МСЭ об установлении инвалидности
Дата: -
Уверенность: 90<|im_end|>
<|im_start|>user
Текст документа:
{text[:2500]}<|im_end|>
<|im_start|>assistant
Стороны:"""

        try:
            output = self.llm(
                prompt,
                max_tokens=300,
                temperature=0.1,
                repeat_penalty=1.15,
                stop=["<|im_end|>", "\n\n", "user"]
            )
            
            response_text = "Стороны:" + output['choices'][0]['text'].strip()
            
            # Убираем теги <think> и их содержимое, если модель решила поразмышлять
            response_text = re.sub(r'<think>.*?</think>', '', response_text, flags=re.DOTALL)
            
            print(f"DEBUG LLM RAW:\n{response_text}")
            
            def extract(key, default=""):
                # Ищем ключ, берем все до конца строки, очищаем от мусора
                m = re.search(fr"(?im)^{key}[^:]*:\s*(.+)$", response_text)
                if not m:
                    # Fallback для кривого форматирования
                    m = re.search(fr"(?i){key}[^:]*:\s*(.+?)(?=\n|$)", response_text)
                
                val = m.group(1).strip() if m else ""
                val = val.replace("*", "").replace("`", "").strip()
                if val in ["-", "—", "нет", "None"] or not val:
                    return default
                return val
                
            def format_parties(text):
                if not text: return ""
                text = re.sub(r'(?i)общество\s+с\s+ограниченной\s+ответственностью', 'ООО', text)
                text = re.sub(r'(?i)публичное\s+акционерное\s+общество', 'ПАО', text)
                text = re.sub(r'(?i)акционерное\s+общество', 'АО', text)
                text = re.sub(r'(?i)индивидуальный\s+предприниматель', 'ИП', text)
                
                # Жесткая очистка от частых галлюцинаций LLM и лишних данных
                # Используем [^,;()] чтобы не удалять лишнее за пределами текущей фразы
                text = re.sub(r'(?i)\(?[^,;()]*\b(именуемое в дальнейшем|именуемый в дальнейшем|именуемое|именуемый|именуемая)\b[^,;()]*\)?', '', text)
                text = re.sub(r'(?i)\(?[^,;()]*\b(заказчик|исполнитель|покупатель|поставщик|подрядчик|арендатор|арендодатель|сторона)\b[^,;()]*\)?', '', text)
                text = re.sub(r'(?i)\(?[^,;()]*\b(генеральный\s+директор|директор|в лице|действующего на основании)\b[^,;()]*\)?', '', text)
                text = re.sub(r'(?i)ОГРНИП\s*\d+', '', text)
                text = re.sub(r'(?i)ОГРН\s*\d+', '', text)
                text = re.sub(r'(?i)ИНН\s*\d+', '', text)
                text = re.sub(r'(?i)\(ИНН[^)]*\)', '', text)
                text = re.sub(r'(?i)\(ОГРНИП[^)]*\)', '', text)
                
                # Убиваем "зависшие" цифры из-за глюков LLM
                text = re.sub(r'\d{10,}', '', text)
                
                # Очистка пустых скобок и лишних знаков препинания
                text = re.sub(r'\(\s*\)', '', text)
                text = re.sub(r'[;]', ',', text)
                text = re.sub(r',\s*,', ',', text)
                text = re.sub(r'^\s*,\s*|\s*,\s*$', '', text)
                
                # Если после всех чисток ничего не осталось
                if not text.strip(): return "-"
                
                # Разделяем по запятым, убираем пустые и слишком длинные куски (явно мусор)
                parts = [p.strip() for p in text.split(',') if p.strip()]
                clean_parts = []
                for p in parts:
                    # Убираем "и " в начале, если нейросеть прихватила союз
                    if p.lower().startswith('и '):
                        p = p[2:].strip()
                    # Если кусок похож на адекватное название (не более 60 символов)
                    if len(p) > 2 and len(p) < 80 and not p.lower().startswith('с одной стороны') and not p.lower().startswith('с другой стороны'):
                        clean_parts.append(p)
                
                result = "_".join(clean_parts)
                return result if result else "-"
                
            conf_str = extract("Уверенность", "0")
            nums = re.findall(r'\d+', conf_str)
            confidence_score = int(nums[0]) if nums else 0
                
            # Для небольших моделей лучше почистить тип программно, если они ошибаются
            raw_type_full = extract("Тип", "Документ")
            
            # Принудительно делаем Тип одним словом (первым) для единообразия
            first_word_match = re.search(r'^([А-Яа-яЁёA-Za-z]+)', raw_type_full)
            if first_word_match:
                raw_type = first_word_match.group(1).capitalize()
            else:
                raw_type = "Документ"
                
            full_name = extract("Полное", "Неизвестный документ")
            
            # Если LLM не выдала Полное, но выдала Тип (часто бывает у маленьких моделей)
            if full_name == "Неизвестный документ" and raw_type_full != "Документ" and raw_type_full:
                full_name = raw_type_full
            
            # Базовая очистка имени от галлюцинаций (если ИИ все же выдаст мусор)
            if len(full_name) > 100:
                full_name = full_name[:100] + "..."
                
            # Очистка от галлюцинаций в Полном имени
            full_name = re.sub(r'\(далее[^)]*\)', '', full_name, flags=re.IGNORECASE).strip()
            full_name = re.sub(r'\(возможно[^)]*\)', '', full_name, flags=re.IGNORECASE).strip()
                
            # Очистка OCR-артефактов
            raw_type = raw_type.replace('N&', '№').replace('Ng', '№').replace('N88', '№88').replace('N5', '№5').replace('P~', 'P-').replace('N@', '№')
            full_name = full_name.replace('N&', '№').replace('Ng', '№').replace('N88', '№88').replace('N5', '№5').replace('P~', 'P-').replace('N@', '№')
                
            # Строгая очистка даты (ищем только ДД.ММ.ГГГГ)
            raw_date = extract("Дата")
            date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', raw_date)
            clean_date = date_match.group(1) if date_match else "-"
            
            return {
                "parties": format_parties(extract("Стороны")),
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
