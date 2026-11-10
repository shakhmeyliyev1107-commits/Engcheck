"""Topilma matnlari uch tilda: (tavsif, texnik izoh, tavsiya).

Matnlarda faqat hujjatlardan o'qilgan qiymatlar ishlatiladi; taxmin yozilmaydi.
"""

LOCALES = ("uz", "en", "ru")

PARAM_NAMES = {
    "uz": {"design_pressure": "loyiha bosimi", "operating_pressure": "ish bosimi",
           "design_temperature": "loyiha harorati", "operating_temperature": "ish harorati",
           "material": "material", "pipe_class": "quvur sinfi", "size": "o‘lcham",
           "fluid": "muhit", "flow_rate": "sarf", "power": "quvvat"},
    "en": {"design_pressure": "design pressure", "operating_pressure": "operating pressure",
           "design_temperature": "design temperature", "operating_temperature": "operating temperature",
           "material": "material", "pipe_class": "pipe class", "size": "size", "fluid": "fluid",
           "flow_rate": "flow rate", "power": "power"},
    "ru": {"design_pressure": "расчётное давление", "operating_pressure": "рабочее давление",
           "design_temperature": "расчётная температура", "operating_temperature": "рабочая температура",
           "material": "материал", "pipe_class": "класс трубопровода", "size": "размер",
           "fluid": "среда", "flow_rate": "расход", "power": "мощность"},
}

DOC_TYPE_NAMES = {
    "uz": {"PFD": "PFD", "PID": "P&ID", "DATASHEET": "datasheet", "EQUIPMENT_LIST": "uskunalar ro‘yxati",
           "LINE_LIST": "quvurlar ro‘yxati", "MATERIAL_SPEC": "material spetsifikatsiyasi",
           "CALCULATION": "hisob-kitob", "HAZOP": "HAZOP", "HAZID": "HAZID", "OTHER": "boshqa"},
    "en": {"PFD": "PFD", "PID": "P&ID", "DATASHEET": "datasheet", "EQUIPMENT_LIST": "equipment list",
           "LINE_LIST": "line list", "MATERIAL_SPEC": "material specification",
           "CALCULATION": "calculation", "HAZOP": "HAZOP", "HAZID": "HAZID", "OTHER": "other"},
    "ru": {"PFD": "PFD", "PID": "P&ID", "DATASHEET": "опросный лист", "EQUIPMENT_LIST": "перечень оборудования",
           "LINE_LIST": "перечень трубопроводов", "MATERIAL_SPEC": "спецификация материалов",
           "CALCULATION": "расчёт", "HAZOP": "HAZOP", "HAZID": "HAZID", "OTHER": "прочее"},
}

RULE_TITLES = {
    "R001": ("Parametr turli hujjatlarda turlicha", "Parameter differs between documents",
             "Параметр различается в документах"),
    "R002": ("Teg kutilgan hujjatda yo‘q", "Tag missing from an expected document",
             "Тег отсутствует в ожидаемом документе"),
    "R003": ("Majburiy parametr bo‘sh", "Mandatory parameter is empty",
             "Обязательный параметр не заполнен"),
    "R004": ("Loyiha qiymati ish qiymatidan past", "Design value below operating value",
             "Расчётное значение ниже рабочего"),
    "R005": ("Quvur sinfi spetsifikatsiyada yo‘q", "Pipe class not defined in the specification",
             "Класс трубопровода не определён в спецификации"),
    "R006": ("Eskirgan reviziyaga havola", "Reference to a superseded revision",
             "Ссылка на устаревшую ревизию"),
    "R007": ("O‘lchov birligi tanilmadi", "Unit of measure not recognised",
             "Единица измерения не распознана"),
}

INTERNAL_SOURCE = {
    "uz": "Loyiha hujjatlari o‘rtasidagi ichki nomuvofiqlik",
    "en": "Internal inconsistency between project documents",
    "ru": "Внутреннее несоответствие между документами проекта",
}

TEMPLATES: dict[str, dict[str, tuple[str, str, str]]] = {
    "r001_mismatch": {
        "uz": ("{tag}: {param_name} hujjatlarda turlicha ko‘rsatilgan",
               "Hujjatlardan o‘qilgan qiymatlar: {values}. Farq 1 % bardoshlik chegarasidan katta.",
               "Qaysi qiymat to‘g‘riligini aniqlang va qolgan hujjatlarni shu qiymatga keltiring."),
        "en": ("{tag}: {param_name} differs between documents",
               "Values read from the documents: {values}. The difference exceeds the 1 % tolerance.",
               "Establish which value is correct and align the other documents with it."),
        "ru": ("{tag}: {param_name} различается в документах",
               "Значения, прочитанные из документов: {values}. Расхождение превышает допуск 1 %.",
               "Определите верное значение и приведите остальные документы в соответствие."),
    },
    "r002_missing": {
        "uz": ("{tag}: {present_name} hujjatida bor, {missing_name} hujjatida yo‘q",
               "Teg {docs} hujjatida uchraydi, lekin loyihaning {missing_name} hujjatlarida topilmadi.",
               "Tegni {missing_name} hujjatiga qo‘shing yoki ortiqcha bo‘lsa {present_name} hujjatidan olib tashlang."),
        "en": ("{tag}: present in the {present_name}, missing from the {missing_name}",
               "The tag appears in {docs} but was not found in the project's {missing_name}.",
               "Add the tag to the {missing_name}, or remove it from the {present_name} if it is obsolete."),
        "ru": ("{tag}: есть в документе «{present_name}», отсутствует в документе «{missing_name}»",
               "Тег встречается в {docs}, но не найден в документах «{missing_name}» проекта.",
               "Добавьте тег в документ «{missing_name}» либо удалите его из документа «{present_name}», если он лишний."),
    },
    "r003_missing_param": {
        "uz": ("{tag}: {param_name} ko‘rsatilmagan ({doc})",
               "{doc} hujjatida {tag} uchun boshqa parametrlar bor, lekin {param_name} maydoni bo‘sh.",
               "{doc} hujjatida {param_name} maydonini to‘ldiring."),
        "en": ("{tag}: {param_name} is not specified ({doc})",
               "{doc} contains other parameters for {tag}, but the {param_name} field is empty.",
               "Fill in the {param_name} field in {doc}."),
        "ru": ("{tag}: не указан параметр «{param_name}» ({doc})",
               "В документе {doc} для {tag} указаны другие параметры, но поле «{param_name}» пусто.",
               "Заполните поле «{param_name}» в документе {doc}."),
    },
    "r004_design_below_operating": {
        "uz": ("{tag}: {param_name} {operating_name} qiymatidan past",
               "Loyiha qiymati — {design}; ish qiymati — {operating}.",
               "Loyiha va ish sharoitlarini tekshiring; loyiha qiymati ish qiymatidan past bo‘lmasligi kerak."),
        "en": ("{tag}: {param_name} is below the {operating_name}",
               "Design value — {design}; operating value — {operating}.",
               "Check the design and operating conditions; the design value must not be below the operating value."),
        "ru": ("{tag}: {param_name} ниже, чем {operating_name}",
               "Расчётное значение — {design}; рабочее значение — {operating}.",
               "Проверьте расчётные и рабочие условия; расчётное значение не должно быть ниже рабочего."),
    },
    "r005_class_undefined": {
        "uz": ("{pipe_class}: quvur sinfi material spetsifikatsiyasida aniqlanmagan",
               "Bu sinf quyidagi quvurlarda ishlatilgan: {lines}. {spec} hujjatida bunday sinf yo‘q.",
               "Sinfni spetsifikatsiyaga qo‘shing yoki quvurlar ro‘yxatidagi sinfni tuzating."),
        "en": ("{pipe_class}: pipe class is not defined in the material specification",
               "The class is used on these lines: {lines}. {spec} does not define it.",
               "Add the class to the specification or correct the class in the line list."),
        "ru": ("{pipe_class}: класс трубопровода не определён в спецификации материалов",
               "Класс использован на линиях: {lines}. В документе {spec} такой класс отсутствует.",
               "Добавьте класс в спецификацию или исправьте класс в перечне трубопроводов."),
    },
    "r006_stale_revision": {
        "uz": ("{doc}: {ref_doc} hujjatining eskirgan Rev {ref_rev} reviziyasiga havola",
               "{doc} hujjati {ref_doc} Rev {ref_rev} ga havola qiladi; loyihadagi joriy reviziya — Rev {current_rev}.",
               "{doc} hujjatini {ref_doc} Rev {current_rev} bo‘yicha qayta tekshiring va havolani yangilang."),
        "en": ("{doc}: refers to superseded Rev {ref_rev} of {ref_doc}",
               "{doc} refers to {ref_doc} Rev {ref_rev}; the current revision in the project is Rev {current_rev}.",
               "Re-check {doc} against {ref_doc} Rev {current_rev} and update the reference."),
        "ru": ("{doc}: ссылка на устаревшую ревизию Rev {ref_rev} документа {ref_doc}",
               "Документ {doc} ссылается на {ref_doc} Rev {ref_rev}; текущая ревизия в проекте — Rev {current_rev}.",
               "Проверьте документ {doc} по {ref_doc} Rev {current_rev} и обновите ссылку."),
    },
    "r007_unknown_unit": {
        "uz": ("{tag}: {param_name} qiymatining o‘lchov birligi tanilmadi",
               "{doc} hujjatida qiymat «{value}» deb yozilgan; birlik ko‘rsatilmagan yoki tanilmadi, shuning uchun qiymat boshqa hujjatlar bilan solishtirilmadi.",
               "Qiymat yoniga yoki ustun sarlavhasiga o‘lchov birligini yozing."),
        "en": ("{tag}: unit of the {param_name} value was not recognised",
               "{doc} gives the value as “{value}”; the unit is missing or not recognised, so the value was not compared with other documents.",
               "State the unit next to the value or in the column header."),
        "ru": ("{tag}: не распознана единица измерения параметра «{param_name}»",
               "В документе {doc} значение записано как «{value}»; единица не указана или не распознана, поэтому значение не сравнивалось с другими документами.",
               "Укажите единицу измерения рядом со значением или в заголовке столбца."),
    },
    "r004_min_design_above_operating": {
        "uz": ("{tag}: {operating_name} minimal {param_name} qiymatidan past",
               "Minimal loyiha qiymati — {design}; ish qiymati — {operating}. Manfiy yoki nol loyiha harorati minimal loyiha harorati deb olindi.",
               "Qiymat minimal loyiha harorati ekanini tasdiqlang; shunday bo‘lsa, u eng past ish haroratidan yuqori bo‘lmasligi kerak."),
        "en": ("{tag}: {operating_name} is below the minimum {param_name}",
               "Minimum design value — {design}; operating value — {operating}. A zero or negative design temperature was taken as the minimum design temperature.",
               "Confirm that the value is the minimum design temperature; if so, it must not be above the lowest operating temperature."),
        "ru": ("{tag}: {operating_name} ниже минимального значения параметра «{param_name}»",
               "Минимальное расчётное значение — {design}; рабочее значение — {operating}. Нулевая или отрицательная расчётная температура принята за минимальную расчётную.",
               "Подтвердите, что значение является минимальной расчётной температурой; в этом случае оно не должно быть выше наименьшей рабочей температуры."),
    },
    "r006_newer_revision": {
        "uz": ("{doc}: {ref_doc} hujjatining loyihaga yuklanmagan Rev {ref_rev} reviziyasiga havola",
               "{doc} hujjati {ref_doc} Rev {ref_rev} ga havola qiladi; loyihaga yuklangan eng yuqori reviziya — Rev {current_rev}.",
               "{ref_doc} Rev {ref_rev} ni loyihaga yuklang yoki havolani tekshiring."),
        "en": ("{doc}: refers to Rev {ref_rev} of {ref_doc}, which is not loaded in the project",
               "{doc} refers to {ref_doc} Rev {ref_rev}; the highest revision loaded in the project is Rev {current_rev}.",
               "Upload {ref_doc} Rev {ref_rev} to the project or check the reference."),
        "ru": ("{doc}: ссылка на ревизию Rev {ref_rev} документа {ref_doc}, не загруженную в проект",
               "Документ {doc} ссылается на {ref_doc} Rev {ref_rev}; старшая загруженная в проект ревизия — Rev {current_rev}.",
               "Загрузите {ref_doc} Rev {ref_rev} в проект или проверьте ссылку."),
    },
    "r007_unparsed_value": {
        "uz": ("{tag}: {param_name} qiymati o‘qilmadi va solishtirilmadi",
               "{doc} hujjatida qiymat «{value}» deb yozilgan. Bu diapazon yoki bir ma'noli bo‘lmagan yozuv, shuning uchun tizim uni songa aylantirmadi va boshqa hujjatlar bilan solishtirmadi.",
               "Qiymatni qo‘lda tekshiring; iloji bo‘lsa, hujjatda bitta son va birlik ko‘rinishida yozing."),
        "en": ("{tag}: the {param_name} value could not be read and was not compared",
               "{doc} gives the value as “{value}”. This is a range or an ambiguous notation, so the system did not convert it to a number or compare it with other documents.",
               "Check the value manually; where possible, state it in the document as a single number with a unit."),
        "ru": ("{tag}: значение параметра «{param_name}» не прочитано и не сравнивалось",
               "В документе {doc} значение записано как «{value}». Это диапазон или неоднозначная запись, поэтому система не преобразовала его в число и не сравнила с другими документами.",
               "Проверьте значение вручную; по возможности укажите в документе одно число с единицей измерения."),
    },
}


def render(description_key: str, args: dict, locale: str) -> tuple[str, str, str]:
    """(tavsif, texnik izoh, tavsiya) berilgan tilda; noma'lum til -> uz."""
    loc = locale if locale in LOCALES else "uz"
    names, doc_types = PARAM_NAMES[loc], DOC_TYPE_NAMES[loc]
    values = dict(args)
    if "param" in args:
        values["param_name"] = names.get(args["param"], args["param"])
    if "operating_param" in args:
        values["operating_name"] = names.get(args["operating_param"], args["operating_param"])
    if "present_in" in args:
        values["present_name"] = doc_types.get(args["present_in"], args["present_in"])
        values["missing_name"] = doc_types.get(args["missing_in"], args["missing_in"])
    description, rationale, recommendation = TEMPLATES[description_key][loc]
    return (description.format(**values), rationale.format(**values), recommendation.format(**values))
