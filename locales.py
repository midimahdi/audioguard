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
        "btn_scanning": "Scanning...",
        "btn_refreshed": "Updated",

        # Settings Section 2: Schedules
        "sec_schedules": "Automated Daily Recording Schedules:",
        "btn_add_slot": "+ Add Time Slot",
        "btn_save_schedules": "💾 Save Schedules",
        "opt_schedule_master": "Automated Daily Recording",
        "slot_time_hint": "Window (24h):",
        "slot_days_hint": "Active Days:",
        "slot_label_hint": "Label:",
        "slot_label_placeholder": "e.g. Main Session",
        "lbl_from": "From",
        "lbl_to": "to",
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
        "retention_hint": "Changes apply to new recordings; existing files retain their furthest duration.",
        "settings_locked_banner": "🔒 Recording in Progress — Critical audio, storage, and schedule settings are locked.",
        "sec_naming": "Custom File Naming Pattern:",
        "naming_preview": "Preview: {preview}",
        "naming_tokens": "Tokens: {slot}, {date}, {time}, {year}, {month}, {day}, {hour}, {min}, {sec}, {mode}",

        # Settings Section 4: System Options
        "sec_system": "System Options:",
        "opt_language": "App Language:",
        "opt_autostart": "Launch on System Startup",
        "opt_start_minimized": "Start Minimized in System Tray",
        "opt_mono_sum": "Mono-Sum (duplicate mono input to both channels)",
        "opt_companion_format": "Companion Audio Copy:",
        "fmt_mp3": "MP3 (Compact, ~10x smaller)",
        "fmt_wav": "WAV (Uncompressed PCM)",
        "fmt_ogg": "OGG (Vorbis Audio)",
        "fmt_none": "None (Lossless FLAC Only)",
        "opt_export_mp3": "Also create MP3 copy after recording",
        "opt_headphone": "Headphone Monitor (Zero Latency)",
        "opt_profile": "Active Profile:",
        "btn_open_log": "📄 Open Diagnostic Log File",

        # Settings Section 5: Audio Profiles (Multi-Tenancy)
        "sec_profiles": "Audio Profiles (Multiple Audio Inputs):",
        "sec_profiles_desc": "Record multiple microphones or inputs simultaneously in separate windows.",
        "btn_add_profile": "➕ Add Second Audio Input Profile",
        "dlg_add_prof_title": "Add Audio Profile",
        "lbl_prof_name": "Profile Name:",
        "lbl_prof_device": "Select Audio Input Device:",
        "lbl_prof_folder": "Backup Storage Folder:",
        "chk_launch_now": "Launch in new window immediately",
        "chk_create_shortcut": "Create 1-click Desktop shortcut",
        "chk_autostart_boot": "Launch on system startup (Autostart)",
        "btn_create_profile": "Create & Open",
        "btn_open_window": "🚀 Open Window",
        "btn_shortcut": "Desktop Shortcut",
        "btn_delete": "Delete",
        "status_running": "● Running",
        "status_inactive": "○ Inactive",
        "active_badge": "(Current Window)",
        "dlg_delete_prof_title": "Delete Profile",
        "dlg_delete_prof_msg": "Are you sure you want to delete profile '{name}'?\n\nThis will remove its configuration file and autostart registration.",

        # Dialogs & Prompts
        "dlg_save_title": "Schedules Saved",
        "dlg_saved_count": "Successfully saved {count} schedule time slots.",
        "dlg_stop_title": "Stop Recording",
        "dlg_stop_msg": "Are you sure you want to stop the current recording session?",
        "dlg_disable_sch_title": "Disable Automated Schedules",
        "dlg_disable_sch_msg": "Are you sure you want to disable automated daily recording schedules?\n\nAudioGuard will only record when manually started.",
        "dlg_enable_sch_title": "Enable Automated Schedules",
        "dlg_enable_sch_msg": "Enable automated daily recording schedules?\n\nAudioGuard will automatically start and stop recording during all configured time slots.",
        "dlg_quit_title": "Quit AudioGuard",
        "dlg_quit_msg": "Are you sure you want to exit AudioGuard?\n\nIf a scheduled time slot arrives while AudioGuard is closed, audio will NOT be recorded.",
        "dlg_merged_slots": "Overlapping schedule slots were automatically merged into unified windows.",
        "dlg_invalid_time": "Invalid time format (HH:MM) in schedule row: '{time}'",
        "slots_empty_hint": "No scheduled time frames configured. Click '+ Add Time Slot' to add one, or use manual recording.",
        "sum_manual_no_slots": "Manual Mode (No scheduled time frames)",
        "onboard_title": "Welcome to AudioGuard",
        "onboard_subtitle": "Let's configure your audio input and backup preferences.",
        "onboard_device": "1. Audio Input Device (Mixer / Microphone):",
        "onboard_meter": "Live Signal Test:",
        "onboard_mode": "2. Recording Mode:",
        "onboard_mode_manual": "Manual Only (Record on-demand with Start/Stop button)",
        "onboard_mode_auto": "Automated Daily Schedule (Record automatically at specific times)",
        "onboard_storage": "3. Backup Storage Directory:",
        "onboard_btn_finish": "Save & Launch AudioGuard",

        # Update Notifications & Checker
        "update_banner_title": "🚀 Update Available: {version}",
        "update_banner_sub": "A newer release of AudioGuard is available. Click below to download.",
        "btn_download_update": "📥 Download Update",
        "btn_release_notes": "What's New",
        "btn_dismiss_update": "✕",
        "sec_app_version": "Application Version:",
        "lbl_current_version": "Installed: {version}",
        "btn_check_updates": "🔄 Check for Updates",
        "msg_checking_updates": "Checking GitHub for updates...",
        "msg_up_to_date": "AudioGuard is up to date ({version}).",
        "msg_update_found": "A new version ({version}) is available!",
        "msg_check_failed": "Could not connect to GitHub to check for updates."
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
        "btn_scanning": "جارٍ البحث...",
        "btn_refreshed": "تم التحديث",

        # Settings Section 2: Schedules
        "sec_schedules": "جداول التسجيل الآلي اليومية:",
        "btn_add_slot": "+ إضافة موعد",
        "btn_save_schedules": "💾 حفظ الجداول",
        "opt_schedule_master": "التسجيل الآلي اليومي",
        "slot_time_hint": "الفترة (24 ساعة):",
        "slot_days_hint": "أيام التفعيل:",
        "slot_label_hint": "التسمية:",
        "slot_label_placeholder": "مثال: الجلسة الرئيسية",
        "lbl_from": "من",
        "lbl_to": "إلى",
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
        "retention_hint": "التغييرات تسري على التسجيلات الجديدة؛ الملفات السابقة تحتفظ بأطول مدة احتفاظ.",
        "settings_locked_banner": "🔒 التسجيل قيد التشغيل — تم قفل إعدادات الصوت والتخزين والجداول لمنع المقاطعة.",
        "sec_naming": "نمط تسمية الملفات المخصص:",
        "naming_preview": "معاينة: {preview}",
        "naming_tokens": "العناصر المتاحة: {slot}, {date}, {time}, {year}, {month}, {day}, {hour}, {min}, {sec}, {mode}",

        # Settings Section 4: System Options
        "sec_system": "خيارات النظام:",
        "opt_language": "لغة التطبيق:",
        "opt_autostart": "تشغيل التطبيق تلقائياً عند إقلاع النظام",
        "opt_start_minimized": "بدء التشغيل مصغراً في شريط المهام",
        "opt_mono_sum": "دمج القناتين (تكرار الصوت الأحادي في كلتا السماعتين)",
        "opt_companion_format": "نسخة صوتية إضافية:",
        "fmt_mp3": "MP3 (مضغوط، أصغر بـ 10 أضعاف)",
        "fmt_wav": "WAV (غير مضغوط PCM)",
        "fmt_ogg": "OGG (صوت فوربيس)",
        "fmt_none": "لا شيء (ملف FLAC الأصلي فقط)",
        "opt_export_mp3": "إنشاء نسخة MP3 تلقائياً بعد التسجيل",
        "opt_headphone": "سماعة المراقبة (بدون تأخير)",
        "opt_profile": "الملف التعريفي:",
        "btn_open_log": "📄 فتح ملف السجل التشخيصي",

        # Settings Section 5: Audio Profiles (Multi-Tenancy)
        "sec_profiles": "ملفات الصوت (تعدد مداخل الصوت):",
        "sec_profiles_desc": "تسجيل عدة لواقط أو مداخل صوتية في نفس الوقت عبر نوافذ منفصلة.",
        "btn_add_profile": "➕ إضافة مدخل صوت إضافي",
        "dlg_add_prof_title": "إضافة مدخل صوت",
        "lbl_prof_name": "اسم الملف التعريفي:",
        "lbl_prof_device": "اختر مدخل الصوت:",
        "lbl_prof_folder": "مجلد الحفظ الاحتياطي:",
        "chk_launch_now": "فتح في نافذة جديدة فوراً",
        "chk_create_shortcut": "إنشاء اختصار بنقرة واحدة على سطح المكتب",
        "chk_autostart_boot": "التشغيل التلقائي مع إقلاع النظام",
        "btn_create_profile": "إنشاء وفتح",
        "btn_open_window": "🚀 فتح النافذة",
        "btn_shortcut": "اختصار سطح المكتب",
        "btn_delete": "حذف",
        "status_running": "● يعمل الآن",
        "status_inactive": "○ غير نشط",
        "active_badge": "(النافذة الحالية)",
        "dlg_delete_prof_title": "حذف الملف التعريفي",
        "dlg_delete_prof_msg": "هل أنت متأكد من حذف الملف '{name}'؟\n\nسيتم حذف ملف الإعدادات وإلغاء التشغيل التلقائي.",

        # Dialogs & Prompts
        "dlg_save_title": "تم حفظ الجداول",
        "dlg_saved_count": "تم حفظ {count} مواعيد جدول بنجاح.",
        "dlg_stop_title": "إيقاف التسجيل",
        "dlg_stop_msg": "هل أنت متأكد من رغبتك في إيقاف جلسة التسجيل الحالية؟",
        "dlg_disable_sch_title": "تعطيل الجداول الآلية",
        "dlg_disable_sch_msg": "هل أنت متأكد من رغبتك في تعطيل الجداول الآلية؟\n\nسيعمل AudioGuard في الوضع اليدوي فقط.",
        "dlg_enable_sch_title": "تفعيل الجداول الآلية",
        "dlg_enable_sch_msg": "تفعيل الجداول الآلية اليومية؟\n\nسيبدأ التطبيق وينهي التسجيل تلقائياً في جميع الأوقات المحددة.",
        "dlg_quit_title": "إغلاق AudioGuard",
        "dlg_quit_msg": "هل أنت متأكد من رغبتك في إغلاق التطبيق؟\n\nإذا حل موعد مجدول أثناء إغلاق البرنامج، فلن يتم تسجيل الصوت.",
        "dlg_merged_slots": "تم دمج الفترات الزمنية المتداخلة تلقائياً في نافذة موحدة.",
        "dlg_invalid_time": "صيغة الوقت غير صالحة (ساعة:دقيقة) في السطر: '{time}'",
        "slots_empty_hint": "لا توجد فترات مجدولة. انقر على '+ إضافة فترة زمنية' أو استخدم التسجيل اليدوي.",
        "sum_manual_no_slots": "الوضع اليدوي (لا توجد فترات مجدولة)",
        "onboard_title": "مرحباً بك في AudioGuard",
        "onboard_subtitle": "لنقم بضبط مدخل الصوت وإعدادات التسجيل في ثوانٍ.",
        "onboard_device": "1. مدخل الصوت (الميكسر أو الميكروفون):",
        "onboard_meter": "اختبار الإشارة المباشرة:",
        "onboard_mode": "2. وضع التسجيل:",
        "onboard_mode_manual": "يدوي فقط (تسجيل عند الطلب بزر البدء/الإيقاف)",
        "onboard_mode_auto": "جدولة يومية آلية (تسجيل تلقائي في أوقات محددة)",
        "onboard_storage": "3. مجلد حفظ النسخ الاحتياطية:",
        "onboard_btn_finish": "حفظ وتشغيل AudioGuard",

        # Update Notifications & Checker
        "update_banner_title": "🚀 تحديث جديد متوفر: {version}",
        "update_banner_sub": "يتوفر إصدار جديد من AudioGuard. انقر أدناه للتحميل.",
        "btn_download_update": "📥 تحميل التحديث",
        "btn_release_notes": "ما الجديد",
        "btn_dismiss_update": "✕",
        "sec_app_version": "إصدار التطبيق:",
        "lbl_current_version": "الإصدار المثبت: {version}",
        "btn_check_updates": "🔄 التحقق من وجود تحديثات",
        "msg_checking_updates": "جارٍ التحقق من التحديثات...",
        "msg_up_to_date": "AudioGuard محدث إلى آخر إصدار ({version}).",
        "msg_update_found": "يتوفر إصدار جديد ({version})!",
        "msg_check_failed": "تعذر الاتصال بـ GitHub للتحقق من التحديثات."
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
        "btn_scanning": "Recherche...",
        "btn_refreshed": "Actualisé",

        # Settings Section 2: Schedules
        "sec_schedules": "Horaires d'enregistrement quotidien :",
        "btn_add_slot": "+ Ajouter un créneau",
        "btn_save_schedules": "💾 Enregistrer les horaires",
        "opt_schedule_master": "Enregistrement automatique quotidien",
        "slot_time_hint": "Créneau (24h) :",
        "slot_days_hint": "Jours actifs :",
        "slot_label_hint": "Libellé :",
        "slot_label_placeholder": "ex. Session principale",
        "lbl_from": "De",
        "lbl_to": "à",
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
        "retention_hint": "Les modifications s'appliquent aux nouveaux enregistrements ; les fichiers existants conservent leur durée la plus longue.",
        "settings_locked_banner": "🔒 Enregistrement en cours — Les paramètres audio, de stockage et d'horaires sont verrouillés.",
        "sec_naming": "Modèle de nom de fichier personnalisé :",
        "naming_preview": "Aperçu : {preview}",
        "naming_tokens": "Variables : {slot}, {date}, {time}, {year}, {month}, {day}, {hour}, {min}, {sec}, {mode}",

        # Settings Section 4: System Options
        "sec_system": "Options système :",
        "opt_language": "Langue de l'application :",
        "opt_autostart": "Lancer au démarrage du système",
        "opt_start_minimized": "Démarrer réduit dans la barre d'état",
        "opt_mono_sum": "Mono-Somme (dupliquer le signal mono sur les deux canaux)",
        "opt_companion_format": "Copie audio d'accompagnement :",
        "fmt_mp3": "MP3 (Compact, ~10x plus petit)",
        "fmt_wav": "WAV (PCM non compressé)",
        "fmt_ogg": "OGG (Audio Vorbis)",
        "fmt_none": "Aucun (FLAC sans perte uniquement)",
        "opt_export_mp3": "Créer également une copie MP3 après l'enregistrement",
        "opt_headphone": "Moniteur casque (sans latence)",
        "opt_profile": "Profil actif :",
        "btn_open_log": "📄 Ouvrir le fichier journal de diagnostic",

        # Settings Section 5: Audio Profiles (Multi-Tenancy)
        "sec_profiles": "Profils audio (Multi-entrées) :",
        "sec_profiles_desc": "Enregistrez plusieurs microphones ou entrées simultanément dans des fenêtres séparées.",
        "btn_add_profile": "➕ Ajouter un profil de deuxième entrée audio",
        "dlg_add_prof_title": "Ajouter un profil audio",
        "lbl_prof_name": "Nom du profil :",
        "lbl_prof_device": "Sélectionner le périphérique audio :",
        "lbl_prof_folder": "Dossier de sauvegarde :",
        "chk_launch_now": "Lancer dans une nouvelle fenêtre immédiatement",
        "chk_create_shortcut": "Créer un raccourci sur le bureau",
        "chk_autostart_boot": "Lancer au démarrage du système",
        "btn_create_profile": "Créer et ouvrir",
        "btn_open_window": "🚀 Ouvrir la fenêtre",
        "btn_shortcut": "Raccourci bureau",
        "btn_delete": "Supprimer",
        "status_running": "● En cours",
        "status_inactive": "○ Inactif",
        "active_badge": "(Fenêtre actuelle)",
        "dlg_delete_prof_title": "Supprimer le profil",
        "dlg_delete_prof_msg": "Êtes-vous sûr de vouloir supprimer le profil '{name}' ?\n\nSon fichier de configuration et son démarrage automatique seront supprimés.",

        # Dialogs & Prompts
        "dlg_save_title": "Horaires enregistrés",
        "dlg_saved_count": "Enregistré {count} créneaux horaires avec succès.",
        "dlg_stop_title": "Arrêter l'enregistrement",
        "dlg_stop_msg": "Êtes-vous sûr de vouloir arrêter la session d'enregistrement en cours ?",
        "dlg_disable_sch_title": "Désactiver les horaires automatiques",
        "dlg_disable_sch_msg": "Êtes-vous sûr de vouloir désactiver les horaires automatiques ?\n\nAudioGuard n'enregistrera qu'en mode manuel.",
        "dlg_enable_sch_title": "Activer les horaires automatiques",
        "dlg_enable_sch_msg": "Activer les horaires automatiques ?\n\nL'application démarrera et arrêtera l'enregistrement automatiquement pendant tous les créneaux configurés.",
        "dlg_quit_title": "Quitter AudioGuard",
        "dlg_quit_msg": "Êtes-vous sûr de vouloir quitter AudioGuard ?\n\nSi un créneau planifié arrive pendant que l'application est fermée, l'audio ne sera PAS enregistré.",
        "dlg_merged_slots": "Les créneaux horaires qui se chevauchent ont été automatiquement fusionnés.",
        "dlg_invalid_time": "Format d'heure invalide (HH:MM) dans la ligne : '{time}'",
        "slots_empty_hint": "Aucun créneau programmé. Cliquez sur '+ Ajouter un créneau' ou utilisez l'enregistrement manuel.",
        "sum_manual_no_slots": "Mode Manuel (Aucun créneau programmé)",
        "onboard_title": "Bienvenue dans AudioGuard",
        "onboard_subtitle": "Configurons votre entrée audio et vos préférences de sauvegarde.",
        "onboard_device": "1. Périphérique d'entrée audio (Mixeur / Micro) :",
        "onboard_meter": "Test du signal en direct :",
        "onboard_mode": "2. Mode d'enregistrement :",
        "onboard_mode_manual": "Manuel uniquement (Enregistrement avec bouton Marche/Arrêt)",
        "onboard_mode_auto": "Planification quotidienne automatique (Enregistrement à heures fixes)",
        "onboard_storage": "3. Répertoire de sauvegarde :",
        "onboard_btn_finish": "Enregistrer et lancer AudioGuard",

        # Update Notifications & Checker
        "update_banner_title": "🚀 Mise à jour disponible : {version}",
        "update_banner_sub": "Une nouvelle version d'AudioGuard est disponible. Cliquez ci-dessous pour télécharger.",
        "btn_download_update": "📥 Télécharger la mise à jour",
        "btn_release_notes": "Nouveautés",
        "btn_dismiss_update": "✕",
        "sec_app_version": "Version de l'application :",
        "lbl_current_version": "Installée : {version}",
        "btn_check_updates": "🔄 Rechercher des mises à jour",
        "msg_checking_updates": "Vérification des mises à jour sur GitHub...",
        "msg_up_to_date": "AudioGuard est à jour ({version}).",
        "msg_update_found": "Une nouvelle version ({version}) est disponible !",
        "msg_check_failed": "Impossible de contacter GitHub pour vérifier les mises à jour."
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
