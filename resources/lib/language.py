from __future__ import print_function, unicode_literals

import re
import xbmc

from resources.lib.constants import ADDON, PY2


class Strings:
    SETUP_VIDEO_CACHE_MSG1 = 30120
    SETUP_VIDEO_CACHE_MSG2 = 30121
    SETUP_VIDEO_CACHE_MSG3 = 30122
    SETUP_VIDEO_CACHE_MSG4 = 30123

    INTRO_STEP1_H1 = 30100
    INTRO_STEP1_L1 = 30101

    INTRO_STEP2_H1 = 30012

    INTRO_STEP3_H1 = 30013

    INTRO_STEP4_H1 = 30102
    INTRO_STEP4_L1 = 30103

    INTRO_STEP5_H1 = 30104
    INTRO_STEP5_L1 = 30105

    KRASKA_NOTIFY_LOW_DAYS_LEFT = 30106
    KRASKA_NOTIFY_CREDENTIAL_H1 = 30107
    KRASKA_NOTIFY_CREDENTIAL_L1 = 30108
    KRASKA_NOTIFY_NO_SUBSCRIPTION = 30131

    SYSTEM_H1 = 30109
    SYSTEM_DEBUG_ENABLED = 30110
    SYSTEM_DEBUG_DISABLED = 30111
    SYSTEM_NOT_INSTALLED_FROM_REPOSITORY = 30127

    RESOLVE_ERROR_H1 = 30112
    RESOLVE_ERROR_L1 = 30113

    SYSTEM_API_ERROR_L1 = 30114

    CONTEXT_PIN_UNPIN = 30115
    CONTEXT_SELECT_STREAM = 30116
    CONTEXT_DOWNLOAD = 30119
    CONTEXT_ADD_TO_ANDROID_TV = 30124
    CONTEXT_PIN_TO_HP = 30125
    CONTEXT_REMOVE = 30126
    CONTEXT_ADD_TO_LIBRARY = 30128
    CONTEXT_ADD_TO_LIBRARY_WITH_SUB = 30129
    CONTEXT_REMOVE_FROM_SUB = 30130
    CONTEXT_DEL_PREF_LANG = 30132
    CONTEXT_ADD_PREF_LANG = 30133

    EMPTY_HISTORY_H1 = 30117
    EMPTY_HISTORY_L1 = 30118


    @staticmethod
    def interpolate(id):
        return '${}'.format(id)

    @staticmethod
    def txt(id):
        return get_localized_string(id)


def get_localized_string(string_id):
    if PY2:
        return ADDON.getLocalizedString(string_id).encode('utf-8')
    return ADDON.getLocalizedString(string_id)


def get_language_code():
    return xbmc.getLanguage(xbmc.ISO_639_1)


def translate(text):
    if PY2:
        text = text.encode('utf-8')
    if text is not None and '$' in text:
        translation_strings = list(
            re.finditer(r'\$([0-9]+)', text, re.IGNORECASE | re.DOTALL)
        )
        for i in translation_strings:
            try:
                translated = get_localized_string(int(i.group(1)))
                text = text.replace('${0}'.format(i.group(1)), translated)
            except Exception as e:
                pass

    return text
