"""
AudioGuard - Internationalization (i18n) Engine
Provides localized UI strings for English (en), Arabic (ar), and French (fr).
"""

from __future__ import annotations
from typing import Dict, Any

SUPPORTED_LANGUAGES = {
    "en": "English",
    "ar": "العربية (Arabic)",
    "fr": "Français (French)"
}

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "en": {
        # Navigation
        "nav_settings": "⚙️  Settings",
        "nav_dashboard": "← Dashboard",
        "app_title": "AudioGuard",

        # Status Banner
        "status_recording": "●  RECORDING LIVE",
        "status_standby": "READY / STANDBY",
        "status_paused": "RECORDING PAUSED",
        "status_overtime": "(Overtime Extension: Speech Detected)",
        "subtitle_recording": "Target: {filename} • {size_mb:.1f} MB written",
        "subtitle_standby_auto": "Input active on {device} • Auto-schedule armed",
        "subtitle_standby_manual": "Input active on {device} • Manual mode",
        "subtitle_standby_no_input": "Audio input inactive or disconnected",
        "subtitle_paused": "Scheduled recording suppressed for current window",

        # Audio Meter
        "meter_title": "Audio Level (Dual-Mono Summed):",
        "meter_peak": "Peak:",
        "meter_rms": "RMS:",

        # Summary Cards
        "sum_status": "Status:",
        "sum_storage": "Storage:",
        "sum_schedule": "Schedule:",
        "sum_active_schedule": "Active Schedule:",
        "sum_next_schedule": "Next Schedule:",
        "sum_schedule_paused": "Schedule Paused:",
        "sum_schedules_disabled": "Schedules Disabled (Manual Only)",
        "sum_no_upcoming": "No upcoming slots",
        "sum_daily": "Daily",
        "sum_free": "{free_gb:.1f} GB free",

        # Main Action Buttons
        "btn_start_manual": "⏺  Start Manual Recording",
        "btn_stop_recording": "⏹  Stop Recording",
        "btn_pause_schedule": "⏸  Pause Scheduled Recording",
        "btn_resume_schedule": "▶️  Resume Scheduled Recording",

        # Settings Section 1: Audio Input Device
        "sec_audio_device": "Audio Input Device:",
        "btn_refresh": "Refresh",

        # Settings Section 2: Schedules
        "sec_schedules": "Automated Daily Recording Schedules:",
        "btn_add_slot": "+ Add Time Slot",
        "btn_save_schedules": "💾 Save Schedules",
        "opt_schedule_master": "Automated Daily Recording",
        "slot_time_hint": "Window (24h):",
        "slot_days_hint": "Active Days:",
        "day_all": "All",
        "day_mon": "M",
        "day_tue": "T",
        "day_wed": "W",
        "day_thu": "T",
        "day_fri": "F",
        "day_sat": "S",
        "day_sun": "S",

        # Settings Section 3: Storage
        "sec_storage": "Backup Storage Directory:",
        "btn_browse": "Browse...",
        "sec_folder_grouping": "Organize Files Into Subfolders:",
        "group_monthly": "Monthly (YYYY-MM)",
        "group_daily": "Daily (YYYY-MM-DD)",
        "group_weekly": "Weekly (YYYY-Www)",
        "group_none": "None (Flat)",
        "sec_retention": "Auto-Delete Backups Older Than:",
        "retention_days": "{days} Days",
        "sec_naming": "Custom File Naming Pattern:",
        "naming_preview": "Preview: {preview}",
        "naming_tokens": "Tokens: {date}, {time}, {year}, {month}, {day}, {hour}, {min}, {sec}, {mode}",

        # Settings Section 4: System Options
        "sec_system": "System Options:",
        "opt_language": "App Language:",
        "opt_autostart": "Launch on System Startup",
        "opt_start_minimized": "Start Minimized in System Tray",
        "opt_mono_sum": "Mono-Sum (duplicate mono input to both channels)",
        "opt_export_mp3": "Also create MP3 copy after recording",
        "opt_headphone": "Headphone Monitor (Zero Latency)",
        "btn_open_log": "📄 Open Diagnostic Log File",

        # Dialogs & Prompts
        "dlg_save_title": "Schedules Saved",
        "dlg_stop_title": "Stop Recording",
        "dlg_stop_msg": "Are you sure you want to stop the current recording session?",
        "dlg_disable_sch_title": "Disable Automated Schedules",
        "dlg_disable_sch_msg": "Are you sure you want to disable automated daily recording schedules?\n\nAudioGuard will only record when manually started.",
        "dlg_enable_sch_title": "Enable Automated Schedules",
        "dlg_enable_sch_msg": "Enable automated daily recording schedules?\n\nAudioGuard will automatically start and stop recording during all configured time slots.",
        "dlg_quit_title": "Quit AudioGuard",
        "dlg_quit_msg": "Are you sure you want to exit AudioGuard?\n\nIf a scheduled time slot arrives while AudioGuard is closed, audio will NOT be recorded.",
        "dlg_merged_slots": "Overlapping schedule slots were automatically merged into unified windows.",
        "dlg_invalid_time": "Invalid time format (HH:MM) in schedule row: '{time}'"
    },

    "ar": {
        # Navigation
        "nav_settings": "⚙️  الإعدادات",
        "nav_dashboard": "← لوحة التحكم",
        "app_title": "AudioGuard (حارس الصوت)",

        # Status Banner
        "status_recording": "●  تسجيل مباشر الآن",
        "status_standby": "جاهز / وضع الاستعداد",
        "status_paused": "التسجيل متوقف مؤقتاً",
        "status_overtime": "(تمديد إضافي: تم رصد صوت مستمر)",
        "subtitle_recording": "الملف: {filename} • تم كتابة {size_mb:.1f} م.ب",
        "subtitle_standby_auto": "المدخل نشط: {device} • الجدولة الآلية مفعلة",
        "subtitle_standby_manual": "المدخل نشط: {device} • الوضع اليدوي",
        "subtitle_standby_no_input": "مدخل الصوت غير متصل أو غير نشط",
        "subtitle_paused": "تم إيقاف التسجيل مؤقتاً لهذه الفترة المجدولة",

        # Audio Meter
        "meter_title": "مستوى الصوت (دمج القناتين):",
        "meter_peak": "الذروة:",
        "meter_rms": "المتوسط:",

        # Summary Cards
        "sum_status": "الحالة:",
        "sum_storage": "التخزين:",
        "sum_schedule": "الجدول:",
        "sum_active_schedule": "الجدول النشط:",
        "sum_next_schedule": "الموعد القادم:",
        "sum_schedule_paused": "الجدول متوقف مؤقتاً:",
        "sum_schedules_disabled": "الجدولة معطلة (يدوي فقط)",
        "sum_no_upcoming": "لا توجد مواعيد قادمة",
        "sum_daily": "يومياً",
        "sum_free": "{free_gb:.1f} ج.ب متبقية",

        # Main Action Buttons
        "btn_start_manual": "⏺  بدء التسجيل اليدوي",
        "btn_stop_recording": "⏹  إيقاف التسجيل",
        "btn_pause_schedule": "⏸  إيقاف مؤقت للجدول",
        "btn_resume_schedule": "▶️  استئناف التسجيل المجدول",

        # Settings Section 1: Audio Input Device
        "sec_audio_device": "جهاز إدخال الصوت:",
        "btn_refresh": "تحديث",

        # Settings Section 2: Schedules
        "sec_schedules": "جداول التسجيل الآلي اليومية:",
        "btn_add_slot": "+ إضافة موعد",
        "btn_save_schedules": "💾 حفظ الجداول",
        "opt_schedule_master": "التسجيل الآلي اليومي",
        "slot_time_hint": "الفترة (24 ساعة):",
        "slot_days_hint": "أيام التفعيل:",
        "day_all": "الكل",
        "day_mon": "إث",
        "day_tue": "ثلا",
        "day_wed": "أرب",
        "day_thu": "خم",
        "day_fri": "جمع",
        "day_sat": "سبت",
        "day_sun": "أحد",

        # Settings Section 3: Storage
        "sec_storage": "مجلد حفظ التسجيلات:",
        "btn_browse": "استعراض...",
        "sec_folder_grouping": "تنظيم الملفات في مجلدات فرعية:",
        "group_monthly": "شهرياً (YYYY-MM)",
        "group_daily": "يومياً (YYYY-MM-DD)",
        "group_weekly": "أسبوعياً (YYYY-Www)",
        "group_none": "بدون (مجلد موحد)",
        "sec_retention": "حذف التسجيلات القديمة تلقائياً بعد:",
        "retention_days": "{days} يوماً",
        "sec_naming": "نمط تسمية الملفات المخصص:",
        "naming_preview": "معاينة: {preview}",
        "naming_tokens": "العناصر المتاحة: {date}, {time}, {year}, {month}, {day}, {hour}, {min}, {sec}, {mode}",

        # Settings Section 4: System Options
        "sec_system": "خيارات النظام:",
        "opt_language": "لغة التطبيق:",
        "opt_autostart": "تشغيل التطبيق تلقائياً عند إقلاع النظام",
        "opt_start_minimized": "بدء التشغيل مصغراً في شريط المهام",
        "opt_mono_sum": "دمج القناتين (تكرار الصوت الأحادي في كلتا السماعتين)",
        "opt_export_mp3": "إنشاء نسخة MP3 تلقائياً بعد التسجيل",
        "opt_headphone": "سماعة المراقبة (بدون تأخير)",
        "btn_open_log": "📄 فتح ملف السجل التشخيصي",

        # Dialogs & Prompts
        "dlg_save_title": "تم حفظ الجداول",
        "dlg_stop_title": "إيقاف التسجيل",
        "dlg_stop_msg": "هل أنت متأكد من رغبتك في إيقاف جلسة التسجيل الحالية؟",
        "dlg_disable_sch_title": "تعطيل الجداول الآلية",
        "dlg_disable_sch_msg": "هل أنت متأكد من رغبتك في تعطيل الجداول الآلية؟\n\nسيعمل AudioGuard في الوضع اليدوي فقط.",
        "dlg_enable_sch_title": "تفعيل الجداول الآلية",
        "dlg_enable_sch_msg": "تفعيل الجداول الآلية اليومية؟\n\nسيبدأ التطبيق وينهي التسجيل تلقائياً في جميع الأوقات المحددة.",
        "dlg_quit_title": "إغلاق AudioGuard",
        "dlg_quit_msg": "هل أنت متأكد من رغبتك في إغلاق التطبيق؟\n\nإذا حل موعد مجدول أثناء إغلاق البرنامج، فلن يتم تسجيل الصوت.",
        "dlg_merged_slots": "تم دمج الفترات الزمنية المتداخلة تلقائياً في نافذة موحدة.",
        "dlg_invalid_time": "صيغة الوقت غير صالحة (ساعة:دقيقة) في السطر: '{time}'"
    },

    "fr": {
        # Navigation
        "nav_settings": "⚙️  Paramètres",
        "nav_dashboard": "← Tableau de bord",
        "app_title": "AudioGuard",

        # Status Banner
        "status_recording": "●  ENREGISTREMENT EN COURS",
        "status_standby": "PRÊT / EN VEILLE",
        "status_paused": "ENREGISTREMENT EN PAUSE",
        "status_overtime": "(Prolongation : Voix détectée)",
        "subtitle_recording": "Cible : {filename} • {size_mb:.1f} Mo écrits",
        "subtitle_standby_auto": "Entrée active sur {device} • Planification armée",
        "subtitle_standby_manual": "Entrée active sur {device} • Mode manuel",
        "subtitle_standby_no_input": "Entrée audio inactive ou déconnectée",
        "subtitle_paused": "Enregistrement planifié suspendu pour le créneau en cours",

        # Audio Meter
        "meter_title": "Niveau audio (Somme double-mono) :",
        "meter_peak": "Crête :",
        "meter_rms": "RMS :",

        # Summary Cards
        "sum_status": "État :",
        "sum_storage": "Stockage :",
        "sum_schedule": "Programme :",
        "sum_active_schedule": "Programme actif :",
        "sum_next_schedule": "Prochain horaire :",
        "sum_schedule_paused": "Programme suspendu :",
        "sum_schedules_disabled": "Planification désactivée (Manuel uniquement)",
        "sum_no_upcoming": "Aucun créneau à venir",
        "sum_daily": "Quotidien",
        "sum_free": "{free_gb:.1f} Go libres",

        # Main Action Buttons
        "btn_start_manual": "⏺  Démarrer l'enregistrement manuel",
        "btn_stop_recording": "⏹  Arrêter l'enregistrement",
        "btn_pause_schedule": "⏸  Suspendre l'enregistrement planifié",
        "btn_resume_schedule": "▶️  Reprendre l'enregistrement planifié",

        # Settings Section 1: Audio Input Device
        "sec_audio_device": "Périphérique d'entrée audio :",
        "btn_refresh": "Actualiser",

        # Settings Section 2: Schedules
        "sec_schedules": "Horaires d'enregistrement quotidien :",
        "btn_add_slot": "+ Ajouter un créneau",
        "btn_save_schedules": "💾 Enregistrer les horaires",
        "opt_schedule_master": "Enregistrement automatique quotidien",
        "slot_time_hint": "Créneau (24h) :",
        "slot_days_hint": "Jours actifs :",
        "day_all": "Tous",
        "day_mon": "L",
        "day_tue": "M",
        "day_wed": "M",
        "day_thu": "J",
        "day_fri": "V",
        "day_sat": "S",
        "day_sun": "D",

        # Settings Section 3: Storage
        "sec_storage": "Dossier de sauvegarde :",
        "btn_browse": "Parcourir...",
        "sec_folder_grouping": "Organiser les fichiers en sous-dossiers :",
        "group_monthly": "Mensuel (YYYY-MM)",
        "group_daily": "Quotidien (YYYY-MM-DD)",
        "group_weekly": "Hebdomadaire (YYYY-Www)",
        "group_none": "Aucun (À plat)",
        "sec_retention": "Supprimer les sauvegardes de plus de :",
        "retention_days": "{days} Jours",
        "sec_naming": "Modèle de nom de fichier personnalisé :",
        "naming_preview": "Aperçu : {preview}",
        "naming_tokens": "Variables : {date}, {time}, {year}, {month}, {day}, {hour}, {min}, {sec}, {mode}",

        # Settings Section 4: System Options
        "sec_system": "Options système :",
        "opt_language": "Langue de l'application :",
        "opt_autostart": "Lancer au démarrage du système",
        "opt_start_minimized": "Démarrer réduit dans la barre d'état",
        "opt_mono_sum": "Mono-Somme (dupliquer le signal mono sur les deux canaux)",
        "opt_export_mp3": "Créer également une copie MP3 après l'enregistrement",
        "opt_headphone": "Moniteur casque (sans latence)",
        "btn_open_log": "📄 Ouvrir le fichier journal de diagnostic",

        # Dialogs & Prompts
        "dlg_save_title": "Horaires enregistrés",
        "dlg_stop_title": "Arrêter l'enregistrement",
        "dlg_stop_msg": "Êtes-vous sûr de vouloir arrêter la session d'enregistrement en cours ?",
        "dlg_disable_sch_title": "Désactiver les horaires automatiques",
        "dlg_disable_sch_msg": "Êtes-vous sûr de vouloir désactiver les horaires automatiques ?\n\nAudioGuard n'enregistrera qu'en mode manuel.",
        "dlg_enable_sch_title": "Activer les horaires automatiques",
        "dlg_enable_sch_msg": "Activer les horaires automatiques ?\n\nL'application démarrera et arrêtera l'enregistrement automatiquement pendant tous les créneaux configurés.",
        "dlg_quit_title": "Quitter AudioGuard",
        "dlg_quit_msg": "Êtes-vous sûr de vouloir quitter AudioGuard ?\n\nSi un créneau planifié arrive pendant que l'application est fermée, l'audio ne sera PAS enregistré.",
        "dlg_merged_slots": "Les créneaux horaires qui se chevauchent ont été automatiquement fusionnés.",
        "dlg_invalid_time": "Format d'heure invalide (HH:MM) dans la ligne : '{time}'"
    }
}

CURRENT_LANGUAGE = "en"

def set_current_language(lang: str):
    global CURRENT_LANGUAGE
    if lang in SUPPORTED_LANGUAGES:
        CURRENT_LANGUAGE = lang
    else:
        CURRENT_LANGUAGE = "en"

def get_current_language() -> str:
    return CURRENT_LANGUAGE

def t(key: str, **kwargs: Any) -> str:
    """
    Translates key for CURRENT_LANGUAGE with fallback to English.
    Interpolates any provided kwargs (e.g. {device}, {filename}).
    """
    lang_dict = TRANSLATIONS.get(CURRENT_LANGUAGE, TRANSLATIONS["en"])
    template = lang_dict.get(key, TRANSLATIONS["en"].get(key, key))
    if kwargs:
        try:
            return template.format(**kwargs)
        except Exception:
            return template
    return template
