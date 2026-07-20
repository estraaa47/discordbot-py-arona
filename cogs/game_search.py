import asyncio
import os

import aiomysql
import discord
import httpx
from discord.ext import commands


GAME_CHANNEL_ID = 1528787386153304105
GAME_MESSAGE_HEADING = (
    "## 🎮 관심 있는 게임을 골라주세요. 추후 알림이 전송됩니다. / "
    "気になるゲームを選んでください。今後、お知らせが届きます。"
)
RAWG_GAMES_URL = "https://api.rawg.io/api/games"
KOREAN_NATIONALITY_ROLE_ID = 927148258885783582
JAPANESE_NATIONALITY_ROLE_ID = 888820786041880666


def localized(language, korean, japanese, english):
    if language == "ja":
        return japanese
    if language == "en":
        return english
    return korean


class GameResultSelect(discord.ui.Select):
    def __init__(self, cog, games, language):
        self.cog = cog
        self.language = language
        self.games = {str(game["id"]): game for game in games}
        options = []

        for game in games:
            release_year = (
                game.get("released")
                or localized(
                    language,
                    "날짜 미상",
                    "発売日不明",
                    "Release date unknown",
                )
            ).split("-")[0]
            platforms = ", ".join(
                item.get("platform", {}).get("name", "")
                for item in game.get("platforms") or []
            )
            details = " · ".join(
                value
                for value in (release_year, platforms)
                if value
            )
            options.append(
                discord.SelectOption(
                    label=game["name"][:100],
                    value=str(game["id"]),
                    description=details[:100] or None,
                )
            )

        super().__init__(
            placeholder=localized(
                language,
                "게임 선택",
                "ゲームを選択",
                "Select a game",
            ),
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction):
        await interaction.response.defer()
        game = self.games[self.values[0]]

        try:
            await self.cog.save_user_game(interaction.user.id, game)
        except (aiomysql.MySQLError, RuntimeError):
            await interaction.edit_original_response(
                content=localized(
                    self.language,
                    "게임을 저장하지 못했습니다. 잠시 후 다시 시도해주세요.",
                    "ゲームを保存できませんでした。しばらくしてからもう一度お試しください。",
                    "The game could not be saved. Please try again later.",
                ),
                view=None,
            )
            return

        await interaction.edit_original_response(
            content=localized(
                self.language,
                f"✅ **{game['name']}** 저장 완료",
                f"✅ **{game['name']}** を保存しました",
                f"✅ **{game['name']}** saved",
            ),
            view=None,
        )


class GameResultView(discord.ui.View):
    def __init__(self, cog, games, language):
        super().__init__(timeout=300)
        self.add_item(GameResultSelect(cog, games, language))


class GameSearchModal(discord.ui.Modal):
    def __init__(self, cog, language):
        super().__init__(
            title=localized(language, "게임 검색", "ゲーム検索", "Game Search")
        )
        self.cog = cog
        self.language = language
        self.game_query = discord.ui.TextInput(
            label=localized(language, "게임 이름", "ゲーム名", "Game name"),
            placeholder=localized(
                language,
                "검색할 게임 이름을 입력해주세요",
                "検索するゲーム名を入力してください",
                "Enter the name of a game",
            ),
            min_length=2,
            max_length=100,
        )
        self.add_item(self.game_query)

    async def on_submit(self, interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            games = await self.cog.search_games(str(self.game_query))
        except (httpx.HTTPError, RuntimeError):
            await interaction.followup.send(
                localized(
                    self.language,
                    "RAWG에서 게임을 검색하지 못했습니다. 잠시 후 다시 시도해주세요.",
                    "RAWGでゲームを検索できませんでした。しばらくしてからもう一度お試しください。",
                    "RAWG could not search for games. Please try again later.",
                ),
                ephemeral=True,
            )
            return

        if not games:
            await interaction.followup.send(
                localized(
                    self.language,
                    "검색 결과가 없습니다. 다른 이름으로 검색해주세요.",
                    "検索結果がありません。別の名前で検索してください。",
                    "No results found. Please try another name.",
                ),
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            localized(
                self.language,
                "검색 결과에서 게임을 선택해주세요.",
                "検索結果からゲームを選択してください。",
                "Select a game from the search results.",
            ),
            view=GameResultView(
                self.cog,
                games,
                self.language,
            ),
            ephemeral=True,
        )


class GameSearchView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="게임 검색 / ゲームを検索 / Search games",
        style=discord.ButtonStyle.primary,
        custom_id="rawg_game:search",
    )
    async def search_button(self, interaction, button):
        language = self.cog.get_ui_language(interaction)
        await interaction.response.send_modal(
            GameSearchModal(self.cog, language)
        )


class GameSearch(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.view = GameSearchView(self)
        self._message_setup_lock = asyncio.Lock()

    @commands.Cog.listener()
    async def on_ready(self):
        async with self._message_setup_lock:
            await self._ensure_search_message()

    async def _ensure_search_message(self):
        channel = self.bot.get_channel(GAME_CHANNEL_ID)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(GAME_CHANNEL_ID)
            except discord.HTTPException as error:
                print(f"[ERROR] 게임 검색 채널을 불러오지 못했습니다: {error}")
                return

        content = "\n".join(
            (
                GAME_MESSAGE_HEADING,
                "-# [게임 정보 제공 / ゲーム情報提供 / Game data: RAWG](https://rawg.io/)",
            )
        )
        search_message = None

        try:
            async for message in channel.history(limit=200):
                has_search_button = any(
                    getattr(component, "custom_id", None) == "rawg_game:search"
                    for row in message.components
                    for component in getattr(row, "children", [])
                )
                if (
                    message.author.id == self.bot.user.id
                    and (
                        message.content.startswith(GAME_MESSAGE_HEADING)
                        or has_search_button
                    )
                ):
                    search_message = message
                    break

            if search_message is None:
                await channel.send(content, view=self.view)
            else:
                await search_message.edit(content=content, view=self.view)
        except discord.HTTPException as error:
            print(f"[ERROR] 게임 검색 메시지를 준비하지 못했습니다: {error}")

    def get_ui_language(self, interaction):
        role_ids = {
            role.id
            for role in getattr(interaction.user, "roles", [])
        }
        has_korean_role = KOREAN_NATIONALITY_ROLE_ID in role_ids
        has_japanese_role = JAPANESE_NATIONALITY_ROLE_ID in role_ids

        if has_korean_role != has_japanese_role:
            return "ko" if has_korean_role else "ja"

        locale = getattr(interaction, "locale", None)
        locale_code = getattr(locale, "value", str(locale or ""))
        locale_code = locale_code.lower()
        if locale_code.startswith("ja"):
            return "ja"
        if locale_code.startswith("ko"):
            return "ko"
        return "en"

    async def search_games(self, query):
        api_key = os.getenv("RAWG_API_KEY")
        if not api_key:
            raise RuntimeError("RAWG_API_KEY가 설정되지 않았습니다.")

        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                RAWG_GAMES_URL,
                params={
                    "key": api_key,
                    "search": query,
                    "page_size": 10,
                },
            )
            response.raise_for_status()

        return [
            game
            for game in response.json().get("results", [])
            if game.get("id") and game.get("name")
        ]

    async def save_user_game(self, user_id, game):
        point_cog = self.bot.get_cog("Point")
        if point_cog is None or point_cog.pool is None:
            raise RuntimeError("DB 연결을 사용할 수 없습니다.")

        async with point_cog.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO user_games (user_id, rawg_game_id, game_name)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE game_name = VALUES(game_name)
                    """,
                    (user_id, game["id"], game["name"]),
                )


async def setup(bot):
    cog = GameSearch(bot)
    await bot.add_cog(cog)
    bot.add_view(cog.view)
