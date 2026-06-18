"""Lightweight UI translation layer (English / Gujarati / Hindi).

Strings are looked up by key with a graceful fallback to English and then to the
key itself, so a missing translation never breaks the UI.
"""

from __future__ import annotations

from .config import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES

_TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        "title_settings": "SmartMirror RAID — Settings",
        "mirror_configuration": "Mirror configuration",
        "status": "Status",
        "mirror_pair": "Mirror pair:",
        "source_path": "Source path:",
        "mirror_path": "Mirror path:",
        "not_configured": "(not configured)",
        "no_pairs": "No mirror pairs configured yet. Open Settings to add one.",
        "watcher_active": "Watcher: active",
        "watcher_idle": "Watcher: idle",
        "usage": "Usage",
        "disk_free": "Disk free",
        "start_sync": "Start Sync",
        "stop_sync": "Stop Sync",
        "start_all": "Start All",
        "stop_all": "Stop All",
        "pause": "Pause",
        "resume": "Resume",
        "restore_from_mirror": "Restore from Mirror",
        "browse_versions": "Browse / Restore Files…",
        "settings": "Settings",
        "activity_log": "Activity log",
        "copied": "Copied",
        "unchanged": "Unchanged",
        "removed": "Removed",
        "moved": "Moved",
        "errors": "Errors",
        "state_stopped": "Stopped",
        "state_running": "Running",
        "state_paused": "Paused",
        "state_starting": "Starting",
        "state_error": "Error",
        "not_real_raid": (
            "This is NOT real RAID — it makes software copies of files on disk "
            "and does not protect against hardware failure."
        ),
        "restore_title": "Restore from Mirror",
        "restore_text": (
            "Restore copies files from the mirror back into the source folder."
        ),
        "restore_overwrite": "Overwrite existing source files that differ",
        "restore_complete": "Restore complete",
        "restore_result": (
            "Restored {copied} file(s).\nSkipped {skipped}.\nErrors: {errors}."
        ),
        "restoring": "Restoring from mirror…",
        "source_folder": "Source folder",
        "mirror_folder": "Mirror folder",
        "pair_name": "Display name (optional)",
        "mirror_size": "Mirror size (allocation)",
        "keep_versions": "Keep previous versions of changed files",
        "versions_to_keep": "Versions to keep",
        "hash_verify": "Verify file contents with a hash (slower, more precise)",
        "exclude_patterns": "Exclude patterns (one per line, e.g. *.tmp)",
        "language": "Language",
        "start_on_login": "Start automatically on login",
        "browse": "Browse…",
        "mirror_pairs": "Mirror pairs",
        "add": "Add",
        "edit": "Edit",
        "remove": "Remove",
        "ok": "OK",
        "cancel": "Cancel",
        "close": "Close",
        "invalid_settings": "Invalid settings",
        "pair_settings_title": "Mirror pair settings",
        "global_settings": "Application settings",
        "settings_note": (
            "Note: This is NOT real RAID. It mirrors files and does not protect "
            "against disk hardware failure."
        ),
        "select_pair_first": "Select or configure a mirror pair first.",
        "vb_title": "Browse & Restore Files",
        "vb_intro": (
            "Select a mirrored file to restore it, or pick an older version."
        ),
        "vb_files": "Mirrored files",
        "vb_versions": "Versions of selected file",
        "vb_current": "Current (mirror copy)",
        "vb_restore_selected": "Restore selected file",
        "vb_restore_version": "Restore this version",
        "vb_overwrite": "Overwrite if it exists in the source",
        "vb_refresh": "Refresh",
        "vb_no_versions": "No earlier versions kept for this file.",
        "vb_restored": "Restored: {name}",
        "vb_search": "Filter…",
        "show_dashboard": "Show dashboard",
        "pause_resume": "Pause / Resume",
        "quit": "Quit",
        "storage_alert_title": "Storage almost full",
    },
    "gu": {
        "title_settings": "સ્માર્ટમિરર RAID — સેટિંગ્સ",
        "mirror_configuration": "મિરર રૂપરેખાંકન",
        "status": "સ્થિતિ",
        "mirror_pair": "મિરર જોડી:",
        "source_path": "સ્રોત પાથ:",
        "mirror_path": "મિરર પાથ:",
        "not_configured": "(રૂપરેખાંકિત નથી)",
        "no_pairs": "હજુ સુધી કોઈ મિરર જોડી ગોઠવી નથી. ઉમેરવા માટે સેટિંગ્સ ખોલો.",
        "watcher_active": "વોચર: સક્રિય",
        "watcher_idle": "વોચર: નિષ્ક્રિય",
        "usage": "વપરાશ",
        "disk_free": "ડિસ્ક ખાલી",
        "start_sync": "સિંક શરૂ કરો",
        "stop_sync": "સિંક બંધ કરો",
        "start_all": "બધા શરૂ કરો",
        "stop_all": "બધા બંધ કરો",
        "pause": "થોભો",
        "resume": "ફરી શરૂ કરો",
        "restore_from_mirror": "મિરરમાંથી પુનઃસ્થાપિત કરો",
        "browse_versions": "ફાઇલો બ્રાઉઝ / પુનઃસ્થાપિત કરો…",
        "settings": "સેટિંગ્સ",
        "activity_log": "પ્રવૃત્તિ લોગ",
        "copied": "કૉપિ થયેલ",
        "unchanged": "અપરિવર્તિત",
        "removed": "દૂર કરેલ",
        "moved": "ખસેડેલ",
        "errors": "ભૂલો",
        "state_stopped": "બંધ",
        "state_running": "ચાલુ",
        "state_paused": "થોભેલ",
        "state_starting": "શરૂ થઈ રહ્યું",
        "state_error": "ભૂલ",
        "not_real_raid": (
            "આ ખરું RAID નથી — તે ડિસ્ક પર ફાઇલોની સોફ્ટવેર નકલ બનાવે છે અને "
            "હાર્ડવેર નિષ્ફળતા સામે રક્ષણ આપતું નથી."
        ),
        "restore_title": "મિરરમાંથી પુનઃસ્થાપિત કરો",
        "restore_text": "પુનઃસ્થાપન મિરરમાંથી ફાઇલોને સ્રોત ફોલ્ડરમાં પાછી કૉપિ કરે છે.",
        "restore_overwrite": "ભિન્ન હોય તેવી હાલની સ્રોત ફાઇલો ઉપર લખો",
        "restore_complete": "પુનઃસ્થાપન પૂર્ણ",
        "restore_result": "{copied} ફાઇલ(ઓ) પુનઃસ્થાપિત.\nછોડેલ {skipped}.\nભૂલો: {errors}.",
        "restoring": "મિરરમાંથી પુનઃસ્થાપિત થઈ રહ્યું છે…",
        "source_folder": "સ્રોત ફોલ્ડર",
        "mirror_folder": "મિરર ફોલ્ડર",
        "pair_name": "પ્રદર્શન નામ (વૈકલ્પિક)",
        "mirror_size": "મિરર કદ (ફાળવણી)",
        "keep_versions": "બદલાયેલ ફાઇલોની અગાઉની આવૃત્તિઓ રાખો",
        "versions_to_keep": "રાખવાની આવૃત્તિઓ",
        "hash_verify": "હેશ વડે ફાઇલ સામગ્રી ચકાસો (ધીમું, વધુ ચોક્કસ)",
        "exclude_patterns": "બાકાત પેટર્ન (દરેક લાઇને એક, દા.ત. *.tmp)",
        "language": "ભાષા",
        "start_on_login": "લૉગિન પર આપમેળે શરૂ કરો",
        "browse": "બ્રાઉઝ…",
        "mirror_pairs": "મિરર જોડીઓ",
        "add": "ઉમેરો",
        "edit": "સંપાદિત કરો",
        "remove": "દૂર કરો",
        "ok": "બરાબર",
        "cancel": "રદ કરો",
        "close": "બંધ કરો",
        "invalid_settings": "અમાન્ય સેટિંગ્સ",
        "pair_settings_title": "મિરર જોડી સેટિંગ્સ",
        "global_settings": "એપ્લિકેશન સેટિંગ્સ",
        "settings_note": (
            "નોંધ: આ ખરું RAID નથી. તે ફાઇલોને મિરર કરે છે અને ડિસ્ક હાર્ડવેર "
            "નિષ્ફળતા સામે રક્ષણ આપતું નથી."
        ),
        "select_pair_first": "પહેલા મિરર જોડી પસંદ અથવા ગોઠવો.",
        "vb_title": "ફાઇલો બ્રાઉઝ અને પુનઃસ્થાપિત કરો",
        "vb_intro": "પુનઃસ્થાપિત કરવા માટે મિરર કરેલ ફાઇલ પસંદ કરો, અથવા જૂની આવૃત્તિ પસંદ કરો.",
        "vb_files": "મિરર કરેલ ફાઇલો",
        "vb_versions": "પસંદ કરેલ ફાઇલની આવૃત્તિઓ",
        "vb_current": "વર્તમાન (મિરર નકલ)",
        "vb_restore_selected": "પસંદ કરેલ ફાઇલ પુનઃસ્થાપિત કરો",
        "vb_restore_version": "આ આવૃત્તિ પુનઃસ્થાપિત કરો",
        "vb_overwrite": "સ્રોતમાં હોય તો ઉપર લખો",
        "vb_refresh": "તાજું કરો",
        "vb_no_versions": "આ ફાઇલ માટે કોઈ જૂની આવૃત્તિ રાખી નથી.",
        "vb_restored": "પુનઃસ્થાપિત: {name}",
        "vb_search": "ફિલ્ટર…",
        "show_dashboard": "ડેશબોર્ડ બતાવો",
        "pause_resume": "થોભો / ફરી શરૂ કરો",
        "quit": "બહાર નીકળો",
        "storage_alert_title": "સંગ્રહ લગભગ ભરાઈ ગયો",
    },
    "hi": {
        "title_settings": "स्मार्टमिरर RAID — सेटिंग्स",
        "mirror_configuration": "मिरर कॉन्फ़िगरेशन",
        "status": "स्थिति",
        "mirror_pair": "मिरर जोड़ी:",
        "source_path": "स्रोत पथ:",
        "mirror_path": "मिरर पथ:",
        "not_configured": "(कॉन्फ़िगर नहीं किया गया)",
        "no_pairs": "अभी तक कोई मिरर जोड़ी कॉन्फ़िगर नहीं की गई। जोड़ने के लिए सेटिंग्स खोलें।",
        "watcher_active": "वॉचर: सक्रिय",
        "watcher_idle": "वॉचर: निष्क्रिय",
        "usage": "उपयोग",
        "disk_free": "डिस्क खाली",
        "start_sync": "सिंक शुरू करें",
        "stop_sync": "सिंक बंद करें",
        "start_all": "सभी शुरू करें",
        "stop_all": "सभी बंद करें",
        "pause": "रोकें",
        "resume": "फिर से शुरू करें",
        "restore_from_mirror": "मिरर से पुनर्स्थापित करें",
        "browse_versions": "फ़ाइलें ब्राउज़ / पुनर्स्थापित करें…",
        "settings": "सेटिंग्स",
        "activity_log": "गतिविधि लॉग",
        "copied": "कॉपी किया",
        "unchanged": "अपरिवर्तित",
        "removed": "हटाया",
        "moved": "स्थानांतरित",
        "errors": "त्रुटियाँ",
        "state_stopped": "बंद",
        "state_running": "चालू",
        "state_paused": "रुका हुआ",
        "state_starting": "शुरू हो रहा है",
        "state_error": "त्रुटि",
        "not_real_raid": (
            "यह असली RAID नहीं है — यह डिस्क पर फ़ाइलों की सॉफ़्टवेयर प्रतिलिपि बनाता है "
            "और हार्डवेयर विफलता से सुरक्षा नहीं देता।"
        ),
        "restore_title": "मिरर से पुनर्स्थापित करें",
        "restore_text": "पुनर्स्थापना मिरर से फ़ाइलों को स्रोत फ़ोल्डर में वापस कॉपी करती है।",
        "restore_overwrite": "भिन्न मौजूदा स्रोत फ़ाइलों को अधिलेखित करें",
        "restore_complete": "पुनर्स्थापना पूर्ण",
        "restore_result": "{copied} फ़ाइल(ें) पुनर्स्थापित।\nछोड़ी गईं {skipped}।\nत्रुटियाँ: {errors}।",
        "restoring": "मिरर से पुनर्स्थापित किया जा रहा है…",
        "source_folder": "स्रोत फ़ोल्डर",
        "mirror_folder": "मिरर फ़ोल्डर",
        "pair_name": "प्रदर्शन नाम (वैकल्पिक)",
        "mirror_size": "मिरर आकार (आवंटन)",
        "keep_versions": "बदली गई फ़ाइलों के पिछले संस्करण रखें",
        "versions_to_keep": "रखने हेतु संस्करण",
        "hash_verify": "हैश से फ़ाइल सामग्री सत्यापित करें (धीमा, अधिक सटीक)",
        "exclude_patterns": "बहिष्करण पैटर्न (प्रति पंक्ति एक, उदा. *.tmp)",
        "language": "भाषा",
        "start_on_login": "लॉगिन पर स्वतः शुरू करें",
        "browse": "ब्राउज़…",
        "mirror_pairs": "मिरर जोड़ियाँ",
        "add": "जोड़ें",
        "edit": "संपादित करें",
        "remove": "हटाएँ",
        "ok": "ठीक है",
        "cancel": "रद्द करें",
        "close": "बंद करें",
        "invalid_settings": "अमान्य सेटिंग्स",
        "pair_settings_title": "मिरर जोड़ी सेटिंग्स",
        "global_settings": "एप्लिकेशन सेटिंग्स",
        "settings_note": (
            "नोट: यह असली RAID नहीं है। यह फ़ाइलों को मिरर करता है और डिस्क हार्डवेयर "
            "विफलता से सुरक्षा नहीं देता।"
        ),
        "select_pair_first": "पहले एक मिरर जोड़ी चुनें या कॉन्फ़िगर करें।",
        "vb_title": "फ़ाइलें ब्राउज़ और पुनर्स्थापित करें",
        "vb_intro": "पुनर्स्थापित करने हेतु मिरर की गई फ़ाइल चुनें, या पुराना संस्करण चुनें।",
        "vb_files": "मिरर की गई फ़ाइलें",
        "vb_versions": "चयनित फ़ाइल के संस्करण",
        "vb_current": "वर्तमान (मिरर प्रति)",
        "vb_restore_selected": "चयनित फ़ाइल पुनर्स्थापित करें",
        "vb_restore_version": "यह संस्करण पुनर्स्थापित करें",
        "vb_overwrite": "स्रोत में मौजूद हो तो अधिलेखित करें",
        "vb_refresh": "ताज़ा करें",
        "vb_no_versions": "इस फ़ाइल के लिए कोई पुराना संस्करण नहीं रखा गया।",
        "vb_restored": "पुनर्स्थापित: {name}",
        "vb_search": "फ़िल्टर…",
        "show_dashboard": "डैशबोर्ड दिखाएँ",
        "pause_resume": "रोकें / फिर से शुरू करें",
        "quit": "बाहर निकलें",
        "storage_alert_title": "संग्रहण लगभग भरा",
    },
}

_current_language = DEFAULT_LANGUAGE


def set_language(language: str) -> None:
    global _current_language
    _current_language = language if language in _TRANSLATIONS else DEFAULT_LANGUAGE


def current_language() -> str:
    return _current_language


def available_languages() -> dict[str, str]:
    """Map of language code -> native display name."""
    return dict(SUPPORTED_LANGUAGES)


def t(key: str, **kwargs: object) -> str:
    table = _TRANSLATIONS.get(_current_language, {})
    text = table.get(key) or _TRANSLATIONS["en"].get(key) or key
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):  # pragma: no cover - defensive
            return text
    return text


def state_label(state: str) -> str:
    return t(f"state_{state}")
