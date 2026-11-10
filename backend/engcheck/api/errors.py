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

_IDX = {"uz": 0, "en": 1, "ru": 2}


def localize(table: dict, code: str, locale: str, **fmt) -> str:
    entry = table.get(code) or MESSAGES["internal_error"]
    return entry[_IDX.get(locale, 0)].format(**fmt) if fmt else entry[_IDX.get(locale, 0)]


class ApiError(Exception):
    def __init__(self, status: int, code: str, **fmt):
        super().__init__(code)
        self.status, self.code, self.fmt = status, code, fmt
