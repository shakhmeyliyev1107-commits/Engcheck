"""API xatolari: yagona shakl {code, message}, xabar foydalanuvchi tilida."""

MESSAGES: dict[str, tuple[str, str, str]] = {  # (uz, en, ru)
    "unauthorized": ("Davom etish uchun tizimga kiring", "Sign in to continue",
                     "Войдите в систему, чтобы продолжить"),
    "forbidden": ("Bu amal uchun ruxsatingiz yo‘q", "You do not have permission for this action",
                  "Недостаточно прав для этого действия"),
    "not_found": ("So‘ralgan obyekt topilmadi", "The requested item was not found",
                  "Запрошенный объект не найден"),
    "bad_credentials": ("Login yoki parol noto‘g‘ri", "Incorrect login or password",
                        "Неверный логин или пароль"),
    "setup_done": ("Dastlabki sozlash allaqachon bajarilgan", "Initial setup has already been completed",
                   "Первоначальная настройка уже выполнена"),
    "password_too_short": ("Parol kamida 8 belgidan iborat bo‘lishi kerak",
                           "The password must be at least 8 characters long",
                           "Пароль должен содержать не менее 8 символов"),
    "login_taken": ("Bu login band", "This login is already taken", "Этот логин уже занят"),
    "login_empty": ("Login bo‘sh bo‘lmasligi kerak", "The login must not be empty",
                    "Логин не должен быть пустым"),
    "validation_error": ("Yuborilgan ma'lumot noto‘g‘ri: {detail}", "The submitted data is invalid: {detail}",
                         "Переданные данные некорректны: {detail}"),
    "duplicate_document": ("Bu fayl loyihaga allaqachon yuklangan",
                           "This file has already been uploaded to the project",
                           "Этот файл уже загружен в проект"),
    "invalid_transition": ("Topilmaning hozirgi holatida bu amalni bajarib bo‘lmaydi",
                           "This action is not allowed in the finding's current status",
                           "Это действие недоступно в текущем статусе замечания"),
    "comment_required": ("Rad etish uchun izoh yozing", "A comment is required to reject a finding",
                         "Для отклонения замечания нужен комментарий"),
    "last_admin": ("Oxirgi faol administratorni o‘chirib bo‘lmaydi",
                   "The last active administrator cannot be disabled",
                   "Нельзя отключить последнего активного администратора"),
    "base_url_required": ("Bu provayder turi uchun manzil (URL) kerak", "This provider type requires a base URL",
                          "Для этого типа провайдера нужен адрес (URL)"),
    "base_url_invalid": ("Manzil http:// yoki https:// bilan boshlanishi kerak",
                         "The URL must start with http:// or https://", "Адрес должен начинаться с http:// или https://"),
    "model_required": ("Model nomini kiriting", "Enter the model name", "Укажите название модели"),
    "name_taken": ("Bu nom band", "This name is already taken", "Это имя уже занято"),
    "ai_unavailable": ("AI ishlatib bo‘lmadi: {reason}", "AI could not be used: {reason}",
                       "Не удалось использовать ИИ: {reason}"),
    "ai_bad_response": ("AI javobini o‘qib bo‘lmadi. Qayta urinib ko‘ring yoki boshqa modelni tanlang.",
                        "The AI reply could not be read. Try again or choose another model.",
                        "Не удалось разобрать ответ ИИ. Повторите попытку или выберите другую модель."),
    "embeddings_unsupported": ("Tanlangan provayderda embedding modeli sozlanmagan",
                               "The selected provider has no embedding model configured",
                               "У выбранного провайдера не настроена модель эмбеддингов"),
    "kb_empty": ("Manbada matn topilmadi", "No text was found in the source", "В источнике не найден текст"),
    "kb_unreadable": ("Faylni o‘qib bo‘lmadi (buzilgan, skanerlangan yoki formati noma'lum)",
                      "The file could not be read (damaged, scanned or unknown format)",
                      "Не удалось прочитать файл (повреждён, отсканирован или неизвестный формат)"),
    "kb_duplicate": ("Bu fayl bilimlar bazasida allaqachon bor", "This file is already in the knowledge base",
                     "Этот файл уже есть в базе знаний"),
    "lesson_not_allowed": ("Dars faqat tasdiqlangan, rad etilgan yoki tuzatilgan topilmadan taklif qilinadi",
                           "A lesson can only be proposed from a confirmed, rejected or fixed finding",
                           "Урок можно предложить только по подтверждённому, отклонённому или исправленному замечанию"),
    "internal_error": ("Ichki xato yuz berdi", "An internal error occurred", "Произошла внутренняя ошибка"),
}

PARSE_MESSAGES: dict[str, tuple[str, str, str]] = {
    "unsupported_dwg": ("DWG formati o‘qilmaydi. Chizmani DXF ga o‘girib yuklang.",
                        "DWG is not supported. Convert the drawing to DXF and upload it again.",
                        "Формат DWG не поддерживается. Преобразуйте чертёж в DXF и загрузите снова."),
    "unknown_format": ("Fayl formati tanilmadi. PDF, DOCX, XLSX yoki DXF yuklang.",
                       "The file format was not recognised. Upload PDF, DOCX, XLSX or DXF.",
                       "Формат файла не распознан. Загрузите PDF, DOCX, XLSX или DXF."),
    "needs_ocr": ("PDF da matn qatlami yo‘q (skanerlangan). OCR bu versiyada yo‘q, hujjat tahlil qilinmadi.",
                  "The PDF has no text layer (scanned). OCR is not available in this version; the document was not analysed.",
                  "В PDF нет текстового слоя (скан). OCR в этой версии недоступен, документ не проанализирован."),
    "error": ("Faylni o‘qib bo‘lmadi: u buzilgan yoki bo‘sh.", "The file could not be read: it is damaged or empty.",
              "Не удалось прочитать файл: он повреждён или пуст."),
}

# AI ishlatilmagan sabablar (rejim tanlash va provayder xatolari)
AI_REASONS: dict[str, tuple[str, str, str]] = {
    "no_provider": ("yoqilgan AI provayder yo‘q", "no AI provider is enabled", "нет включённого провайдера ИИ"),
    "cloud_not_allowed": ("bu loyihada bulutli AI ga ruxsat berilmagan va lokal model sozlanmagan",
                          "cloud AI is not allowed for this project and no local model is configured",
                          "для этого проекта облачный ИИ не разрешён, а локальная модель не настроена"),
    "unreachable": ("provayderga ulanib bo‘lmadi (internet yoki lokal xizmatni tekshiring)",
                    "the provider could not be reached (check the internet or the local service)",
                    "не удалось подключиться к провайдеру (проверьте интернет или локальную службу)"),
    "auth": ("API kaliti noto‘g‘ri yoki ruxsat yo‘q", "the API key is invalid or lacks permission",
             "неверный ключ API или нет доступа"),
    "rate_limit": ("provayder so‘rovlar chegarasiga yetdi, keyinroq urinib ko‘ring",
                   "the provider's rate limit was reached, try again later",
                   "достигнут лимит запросов провайдера, повторите позже"),
    "bad_request": ("provayder so‘rovni qabul qilmadi (model nomi yoki manzilni tekshiring)",
                    "the provider rejected the request (check the model name or URL)",
                    "провайдер отклонил запрос (проверьте название модели или адрес)"),
    "refused": ("model bu so‘rovga javob berishdan bosh tortdi", "the model declined to answer this request",
                "модель отказалась отвечать на этот запрос"),
    "server": ("provayder tomonida xato", "an error on the provider's side", "ошибка на стороне провайдера"),
    "rule_disabled": ("AI tekshiruvi qoidasi (AI01) o‘chirilgan", "the AI review rule (AI01) is disabled",
                      "правило проверки ИИ (AI01) отключено"),
    "embeddings_unsupported": ("embedding modeli sozlanmagan", "no embedding model is configured",
                               "модель эмбеддингов не настроена"),
}

_IDX = {"uz": 0, "en": 1, "ru": 2}


def ai_reason(code: str | None, locale: str) -> str | None:
    if not code:
        return None
    entry = AI_REASONS.get(code) or AI_REASONS["server"]
    return entry[_IDX.get(locale, 0)]


def localize(table: dict, code: str, locale: str, **fmt) -> str:
    entry = table.get(code) or MESSAGES["internal_error"]
    return entry[_IDX.get(locale, 0)].format(**fmt) if fmt else entry[_IDX.get(locale, 0)]


class ApiError(Exception):
    def __init__(self, status: int, code: str, **fmt):
        super().__init__(code)
        self.status, self.code, self.fmt = status, code, fmt
