import asyncio
import os

import aiomysql
import discord
import httpx
from discord import app_commands
from discord.ext import commands

from bot_i18n import get_ui_language, localized
from cogs.role import LANGUAGE_LEVEL_ROLE_IDS


GAME_CHANNEL_ID = 1528787386153304105
GAME_MESSAGE_HEADING = (
    "## 관심 있는 게임을 골라주세요 / "
    "気になるゲームを選んでください"
)
GAME_SEARCH_BUTTON_LABEL = "게임 검색 / ゲームを検索"
GAME_SEARCH_BUTTON_CUSTOM_ID = "rawg_game:search"
RAWG_GAMES_URL = "https://api.rawg.io/api/games"


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
                "추후 같은 게임을 하는 사람이 인원을 모집할 때 알려드릴게요.",
                "今後、同じゲームをプレイする人がメンバーを募集した際にお知らせします。",
                "We'll notify you when someone who plays the same game is recruiting players.",
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
        self.add_item(
            discord.ui.TextDisplay(
                localized(
                    language,
                    "[게임 정보 제공: RAWG](https://rawg.io/)",
                    "[ゲーム情報提供: RAWG](https://rawg.io/)",
                    "[Game data: RAWG](https://rawg.io/)",
                )
            )
        )

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
        label=GAME_SEARCH_BUTTON_LABEL,
        style=discord.ButtonStyle.primary,
        custom_id=GAME_SEARCH_BUTTON_CUSTOM_ID,
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
            role_cog = self.bot.get_cog("ReactionRole")
            if role_cog is not None:
                await role_cog.ensure_role_messages()
            await self._ensure_search_message()

    def _has_current_search_button(self, message):
        for row in message.components:
            for component in getattr(row, "children", []):
                if (
                    getattr(component, "custom_id", None)
                    == GAME_SEARCH_BUTTON_CUSTOM_ID
                ):
                    return (
                        getattr(component, "label", None)
                        == GAME_SEARCH_BUTTON_LABEL
                        and getattr(component, "style", None)
                        == discord.ButtonStyle.primary
                    )
        return False

    async def _ensure_search_message(self):
        channel = self.bot.get_channel(GAME_CHANNEL_ID)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(GAME_CHANNEL_ID)
            except discord.HTTPException as error:
                print(f"[ERROR] 게임 검색 채널을 불러오지 못했습니다: {error}")
                return

        content = GAME_MESSAGE_HEADING
        search_message = None
        latest_role_message_id = 0

        try:
            async for message in channel.history(limit=200):
                component_ids = {
                    getattr(component, "custom_id", None)
                    for row in message.components
                    for component in getattr(row, "children", [])
                }
                has_search_button = (
                    GAME_SEARCH_BUTTON_CUSTOM_ID in component_ids
                )
                has_role_select = any(
                    custom_id is not None
                    and custom_id.startswith("language_level:")
                    for custom_id in component_ids
                )
                if message.author.id == self.bot.user.id and has_role_select:
                    latest_role_message_id = max(
                        latest_role_message_id,
                        message.id,
                    )
                if (
                    message.author.id == self.bot.user.id
                    and (
                        message.content.startswith(GAME_MESSAGE_HEADING)
                        or has_search_button
                    )
                ):
                    if search_message is None:
                        search_message = message

            if search_message is None:
                await channel.send(content, view=self.view)
            elif (
                search_message.id <= latest_role_message_id
                or search_message.content != content
                or not self._has_current_search_button(search_message)
                or search_message.edited_at is not None
            ):
                await search_message.delete()
                await channel.send(content, view=self.view)
        except discord.HTTPException as error:
            print(f"[ERROR] 게임 검색 메시지를 준비하지 못했습니다: {error}")

    def get_ui_language(self, interaction):
        return get_ui_language(interaction)

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

    async def get_user_games(self, user_id, query=""):
        point_cog = self.bot.get_cog("Point")
        if point_cog is None or point_cog.pool is None:
            return []

        async with point_cog.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT rawg_game_id, game_name
                    FROM user_games
                    WHERE user_id = %s AND game_name LIKE %s
                    ORDER BY game_name
                    LIMIT 25
                    """,
                    (user_id, f"%{query}%"),
                )
                return await cur.fetchall()

    async def get_user_game(self, user_id, rawg_game_id):
        point_cog = self.bot.get_cog("Point")
        if point_cog is None or point_cog.pool is None:
            raise RuntimeError("DB 연결을 사용할 수 없습니다.")

        async with point_cog.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT rawg_game_id, game_name
                    FROM user_games
                    WHERE user_id = %s AND rawg_game_id = %s
                    """,
                    (user_id, rawg_game_id),
                )
                return await cur.fetchone()

    async def get_all_user_games(self, user_id):
        point_cog = self.bot.get_cog("Point")
        if point_cog is None or point_cog.pool is None:
            raise RuntimeError("DB 연결을 사용할 수 없습니다.")

        async with point_cog.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT rawg_game_id, game_name
                    FROM user_games
                    WHERE user_id = %s
                    ORDER BY game_name
                    LIMIT 50
                    """,
                    (user_id,),
                )
                return await cur.fetchall()

    async def get_game_members(self, rawg_game_id, excluded_user_id):
        point_cog = self.bot.get_cog("Point")
        if point_cog is None or point_cog.pool is None:
            raise RuntimeError("DB 연결을 사용할 수 없습니다.")

        async with point_cog.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT user_id
                    FROM user_games
                    WHERE rawg_game_id = %s AND user_id <> %s
                    """,
                    (rawg_game_id, excluded_user_id),
                )
                return [row[0] for row in await cur.fetchall()]

    def member_meets_language_level(self, member, language, required_level):
        eligible_role_ids = {
            role_id
            for role_level, role_id in LANGUAGE_LEVEL_ROLE_IDS[language].items()
            if role_level >= required_level
        }
        return any(role.id in eligible_role_ids for role in member.roles)

    @app_commands.command(
        name="recruit",
        description="같은 게임을 등록한 사용자에게 모집 알림을 보냅니다.",
    )
    @app_commands.describe(
        game="본인이 등록한 게임",
        language="모집에서 사용할 언어",
        level="요구하는 언어 수준",
        note="추가 모집 내용",
    )
    async def recruit(
        self,
        interaction: discord.Interaction,
        game: str,
        language: str,
        level: int,
        note: str | None = None,
    ):
        await interaction.response.defer(thinking=True)
        ui_language = self.get_ui_language(interaction)

        if language not in {"ko", "ja"} or level not in {0, 1, 2, 3}:
            await interaction.edit_original_response(
                content=localized(
                    ui_language,
                    "언어와 수준을 자동완성 목록에서 선택해주세요.",
                    "言語とレベルを候補から選択してください。",
                    "Select a language and level from the autocomplete lists.",
                )
            )
            return

        try:
            rawg_game_id = int(game)
        except ValueError:
            await interaction.edit_original_response(
                content=localized(
                    ui_language,
                    "등록된 게임을 자동완성 목록에서 선택해주세요.",
                    "登録済みのゲームを候補から選択してください。",
                    "Select a registered game from the autocomplete list.",
                )
            )
            return

        try:
            selected_game = await self.get_user_game(
                interaction.user.id,
                rawg_game_id,
            )
            if selected_game is None:
                await interaction.edit_original_response(
                    content=localized(
                        ui_language,
                        "먼저 해당 게임을 관심 게임으로 등록해주세요.",
                        "先にそのゲームを気になるゲームとして登録してください。",
                        "Register that game as an interested game first.",
                    )
                )
                return

            user_ids = await self.get_game_members(
                rawg_game_id,
                interaction.user.id,
            )
        except (aiomysql.MySQLError, RuntimeError):
            await interaction.edit_original_response(
                content=localized(
                    ui_language,
                    "모집 대상을 불러오지 못했습니다. 잠시 후 다시 시도해주세요.",
                    "募集対象を取得できませんでした。しばらくしてからもう一度お試しください。",
                    "Could not load recruitment targets. Please try again later.",
                )
            )
            return

        game_name = discord.utils.escape_mentions(
            discord.utils.escape_markdown(selected_game[1])
        )
        members = [
            member
            for user_id in user_ids
            if (member := interaction.guild.get_member(user_id)) is not None
            and not member.bot
            and self.member_meets_language_level(member, language, level)
        ]
        if not members:
            await interaction.edit_original_response(
                content=localized(
                    ui_language,
                    f'조건에 맞는 "{game_name}"을 등록한 구성원을 찾지 못했어요.',
                    f'条件に合う「{game_name}」を登録したメンバーが見つかりませんでした。',
                    f'Could not find any members who registered "{game_name}" and meet the conditions.',
                )
            )
            return

        language_labels = {
            "ko": localized(ui_language, "한국어", "韓国語", "Korean"),
            "ja": localized(ui_language, "일본어", "日本語", "Japanese"),
        }
        level_labels = {
            0: localized(ui_language, "불가", "不可", "Unavailable"),
            1: localized(ui_language, "초급", "初級", "Beginner"),
            2: localized(ui_language, "중급", "中級", "Intermediate"),
            3: localized(ui_language, "상급", "上級", "Advanced"),
        }
        safe_note = discord.utils.escape_mentions(
            discord.utils.escape_markdown(note or "")
        )[:800]
        lines = [
            f"## {game_name}",
            localized(
                ui_language,
                f"**모집 언어:** {language_labels[language]}",
                f"**募集言語:** {language_labels[language]}",
                f"**Recruitment language:** {language_labels[language]}",
            ),
            localized(
                ui_language,
                f"**언어 수준:** {level_labels[level]}",
                f"**言語レベル:** {level_labels[level]}",
                f"**Language level:** {level_labels[level]}",
            ),
        ]
        if safe_note:
            lines.extend(("", safe_note))
        header = "\n".join(lines)
        message_chunks = []
        current_chunk = f"{header}\n\n"
        for member in members:
            mention = member.mention
            if len(current_chunk) + len(mention) + 1 > 1950:
                message_chunks.append(current_chunk.rstrip())
                current_chunk = ""
            current_chunk += f"{mention} "
        if current_chunk.strip():
            message_chunks.append(current_chunk.rstrip())

        allowed_mentions = discord.AllowedMentions(
            users=True,
            roles=False,
            everyone=False,
            replied_user=False,
        )
        await interaction.edit_original_response(
            content=message_chunks[0],
            allowed_mentions=allowed_mentions,
        )
        for chunk in message_chunks[1:]:
            await interaction.followup.send(
                chunk,
                allowed_mentions=allowed_mentions,
            )

    @recruit.autocomplete("game")
    async def recruit_game_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ):
        try:
            games = await self.get_user_games(interaction.user.id, current)
        except aiomysql.MySQLError:
            return []

        return [
            app_commands.Choice(
                name=game_name[:100],
                value=str(rawg_game_id),
            )
            for rawg_game_id, game_name in games
        ]

    @recruit.autocomplete("language")
    async def recruit_language_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ):
        language = self.get_ui_language(interaction)
        return [
            app_commands.Choice(
                name=localized(language, "한국어", "韓国語", "Korean"),
                value="ko",
            ),
            app_commands.Choice(
                name=localized(language, "일본어", "日本語", "Japanese"),
                value="ja",
            ),
        ]

    @recruit.autocomplete("level")
    async def recruit_level_autocomplete(
        self,
        interaction: discord.Interaction,
        current: int,
    ):
        language = self.get_ui_language(interaction)
        labels = (
            (0, "불가", "不可", "Unavailable"),
            (1, "초급", "初級", "Beginner"),
            (2, "중급", "中級", "Intermediate"),
            (3, "상급", "上級", "Advanced"),
        )
        return [
            app_commands.Choice(
                name=localized(language, korean, japanese, english),
                value=value,
            )
            for value, korean, japanese, english in labels
        ]

    @app_commands.command(
        name="mygames",
        description="내가 등록한 관심 게임 목록을 확인합니다.",
    )
    async def my_games(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        language = self.get_ui_language(interaction)

        try:
            games = await self.get_all_user_games(interaction.user.id)
        except (aiomysql.MySQLError, RuntimeError):
            await interaction.edit_original_response(
                content=localized(
                    language,
                    "게임 목록을 불러오지 못했습니다. 잠시 후 다시 시도해주세요.",
                    "ゲーム一覧を取得できませんでした。しばらくしてからもう一度お試しください。",
                    "Could not load your game list. Please try again later.",
                )
            )
            return

        if not games:
            await interaction.edit_original_response(
                content=localized(
                    language,
                    "아직 등록한 관심 게임이 없습니다.",
                    "登録した気になるゲームはまだありません。",
                    "You haven't registered any games yet.",
                )
            )
            return

        display_name = discord.utils.escape_markdown(
            interaction.user.display_name
        )
        title = localized(
            language,
            f"## {display_name}님의 등록 게임",
            f"## {display_name}さんの登録ゲーム",
            f"## {display_name}'s registered games",
        )
        game_lines = [
            f"• {discord.utils.escape_markdown(game_name)}"
            for _, game_name in games
        ]
        content = "\n".join((title, *game_lines))
        await interaction.edit_original_response(content=content[:2000])


async def setup(bot):
    cog = GameSearch(bot)
    await bot.add_cog(cog)
    bot.add_view(cog.view)
