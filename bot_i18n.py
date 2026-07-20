from discord import app_commands


KOREAN_NATIONALITY_ROLE_ID = 927148258885783582
JAPANESE_NATIONALITY_ROLE_ID = 888820786041880666

COMMAND_TRANSLATIONS = {
    # Command names
    "arona": {"ko": "아로나", "ja": "アロナ", "en": "arona"},
    "point": {"ko": "포인트", "ja": "ポイント", "en": "point"},
    "gacha": {"ko": "가챠", "ja": "ガチャ", "en": "gacha"},
    "collection": {"ko": "도감", "ja": "コレクション", "en": "collection"},
    "join": {"ko": "음성참여", "ja": "ボイス参加", "en": "join"},
    "leave": {"ko": "음성퇴장", "ja": "ボイス退出", "en": "leave"},
    "recruit": {"ko": "모집", "ja": "募集", "en": "recruit"},
    "mygames": {"ko": "내게임", "ja": "マイゲーム", "en": "mygames"},
    # Option names
    "message": {"ko": "메시지", "ja": "メッセージ", "en": "message"},
    "game": {"ko": "게임", "ja": "ゲーム", "en": "game"},
    "language": {"ko": "언어", "ja": "言語", "en": "language"},
    "level": {"ko": "수준", "ja": "レベル", "en": "level"},
    "note": {"ko": "추가내용", "ja": "追記", "en": "note"},
    # Command descriptions
    "Chat with Arona": {
        "ko": "아로나와 대화합니다.",
        "ja": "アロナと会話します。",
        "en": "Chat with Arona.",
    },
    "현재 보유한 포인트를 확인합니다.": {
        "ko": "현재 보유한 포인트를 확인합니다.",
        "ja": "現在のポイントを確認します。",
        "en": "Check your current points.",
    },
    "120P를 소모하여 가챠를 뽑습니다!": {
        "ko": "120P를 소모하여 가챠를 뽑습니다!",
        "ja": "120Pを消費してガチャを引きます！",
        "en": "Spend 120P to pull the gacha!",
    },
    "등급별 수집 현황을 확인합니다.": {
        "ko": "등급별 수집 현황을 확인합니다.",
        "ja": "ランク別の収集状況を確認します。",
        "en": "Check your collection by rarity.",
    },
    "아로나를 음성 채널에 부릅니다": {
        "ko": "아로나를 음성 채널에 부릅니다.",
        "ja": "アロナをボイスチャンネルに呼びます。",
        "en": "Call Arona into your voice channel.",
    },
    "아로나를 음성 채널에서 내보냅니다": {
        "ko": "아로나를 음성 채널에서 내보냅니다.",
        "ja": "アロナをボイスチャンネルから退出させます。",
        "en": "Disconnect Arona from the voice channel.",
    },
    "같은 게임을 등록한 사용자에게 모집 알림을 보냅니다.": {
        "ko": "같은 게임을 등록한 사용자에게 모집 알림을 보냅니다.",
        "ja": "同じゲームを登録したユーザーに募集通知を送ります。",
        "en": "Notify users who registered the same game.",
    },
    "내가 등록한 관심 게임 목록을 확인합니다.": {
        "ko": "내가 등록한 관심 게임 목록을 확인합니다.",
        "ja": "登録した気になるゲームの一覧を確認します。",
        "en": "View your registered games.",
    },
    # Option descriptions
    "아로나에게 보낼 메시지": {
        "ko": "아로나에게 보낼 메시지",
        "ja": "アロナに送るメッセージ",
        "en": "Message to send to Arona",
    },
    "본인이 등록한 게임": {
        "ko": "본인이 등록한 게임",
        "ja": "自分が登録したゲーム",
        "en": "A game you registered",
    },
    "모집에서 사용할 언어": {
        "ko": "모집에서 사용할 언어",
        "ja": "募集で使用する言語",
        "en": "Language used for recruitment",
    },
    "요구하는 언어 수준": {
        "ko": "요구하는 언어 수준",
        "ja": "必要な言語レベル",
        "en": "Required language level",
    },
    "추가 모집 내용": {
        "ko": "추가 모집 내용",
        "ja": "追加の募集内容",
        "en": "Additional recruitment details",
    },
}


class AronaTranslator(app_commands.Translator):
    async def translate(self, string, locale, context):
        translations = COMMAND_TRANSLATIONS.get(string.message)
        if translations is None:
            return None

        locale_code = getattr(locale, "value", str(locale)).lower()
        if locale_code.startswith("ja"):
            language = "ja"
        elif locale_code.startswith("ko"):
            language = "ko"
        else:
            language = "en"
        return translations[language]


def get_ui_language(interaction):
    role_ids = {
        role.id
        for role in getattr(interaction.user, "roles", [])
    }
    has_korean_role = KOREAN_NATIONALITY_ROLE_ID in role_ids
    has_japanese_role = JAPANESE_NATIONALITY_ROLE_ID in role_ids

    if has_korean_role != has_japanese_role:
        return "ko" if has_korean_role else "ja"

    locale = getattr(interaction, "locale", None)
    locale_code = getattr(locale, "value", str(locale or "")).lower()
    if locale_code.startswith("ja"):
        return "ja"
    if locale_code.startswith("ko"):
        return "ko"
    return "en"


def localized(language, korean, japanese, english):
    if language == "ja":
        return japanese
    if language == "en":
        return english
    return korean


def interaction_text(interaction, korean, japanese, english):
    return localized(
        get_ui_language(interaction),
        korean,
        japanese,
        english,
    )
