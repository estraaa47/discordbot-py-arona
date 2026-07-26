import asyncio

import aiomysql
import discord
from discord.ext import commands

from bot_i18n import (
    JAPANESE_NATIONALITY_ROLE_ID,
    KOREAN_NATIONALITY_ROLE_ID,
)


ROLE_CHANNEL_ID = 1528787386153304105
NATIONALITY_WELCOME_CHANNEL_ID = 1530655522821243034
LEAVE_LOG_CHANNEL_ID = 1530659152643227749
NATIONALITY_WELCOME_TABLE = "arona_nationality_welcomes"
NATIONALITY_WELCOME_MESSAGES = {
    KOREAN_NATIONALITY_ROLE_ID: (
        "{mention} 선생님, 반가워요! 환영합니다!\n"
        "-# 韓国からいらした先生です！これからみんなで楽しく過ごしましょう～！"
    ),
    JAPANESE_NATIONALITY_ROLE_ID: (
        "{mention}先生、はじめまして！ようこそ！\n"
        "-# 일본에서 오신 선생님이에요! 앞으로 다 같이 즐겁게 지내봐요~!"
    ),
}
ROLE_SELECTIONS = (
    {
        "key": "nationality",
        "heading": "## 🌏 당신의 국적을 선택해주세요 / あなたの国籍を選択してください",
        "subheading": None,
        "legacy_headings": (
            "## 🌏 국적을 선택해주세요 / 国籍を選択してください",
            "## 🌏 당신의 국적을 선택해주세요",
        ),
        "placeholder": "국적 선택 / 国籍を選択",
        "roles": (
            (KOREAN_NATIONALITY_ROLE_ID, "한국", "韓国"),
            (JAPANESE_NATIONALITY_ROLE_ID, "日本", "일본"),
        ),
    },
    {
        "key": "korean",
        "heading": "## 🇰🇷 あなたの韓国語レベルを選択してください",
        "subheading": "당신의 한국어 레벨을 선택해주세요",
        "legacy_headings": (
            "## 🇰🇷 韓国語レベルを選択してください",
            "## 🇰🇷 あなたの韓国語レベルを選択してください",
            "## 🇰🇷 당신의 한국어 레벨을 선택해주세요",
            "## 🇰🇷 당신의 한국어 레벨을 선택해주세요 / あなたの韓国語レベルを選択してください",
        ),
        "placeholder": "韓国語レベルを選択 / 한국어 레벨 선택",
        "roles": (
            (1528791795582898286, "不可", "불가"),
            (1528789614989545542, "初級", "초급"),
            (1528790289999859822, "中級", "중급"),
            (1528790367644811264, "上級", "상급"),
        ),
    },
    {
        "key": "japanese",
        "heading": "## 🇯🇵 당신의 일본어 레벨을 선택해주세요",
        "subheading": "あなたの日本語レベルを選択してください",
        "legacy_headings": (
            "## 🇯🇵 일본어 레벨을 선택해주세요",
            "## 🇯🇵 あなたの日本語レベルを選択してください",
            "## 🇯🇵 당신의 일본어 레벨을 선택해주세요 / あなたの日本語レベルを選択してください",
        ),
        "placeholder": "일본어 레벨 선택 / 日本語レベルを選択",
        "roles": (
            (1528792331623596052, "불가", "不可"),
            (1528792010465480856, "초급", "初級"),
            (1528792142997098626, "중급", "中級"),
            (1528792261188391183, "상급", "上級"),
        ),
    },
)

LANGUAGE_LEVEL_ROLE_IDS = {
    language: {
        level: role_id
        for level, (role_id, _, _) in enumerate(
            next(
                selection["roles"]
                for selection in ROLE_SELECTIONS
                if selection["key"] == selection_key
            )
        )
    }
    for language, selection_key in (("ko", "korean"), ("ja", "japanese"))
}


class LevelSelect(discord.ui.Select):
    def __init__(self, cog, selection):
        self.cog = cog
        self.selection = selection
        options = [
            discord.SelectOption(
                label=f"{label} / {description}",
                value=str(role_id),
            )
            for role_id, label, description in selection["roles"]
        ]
        super().__init__(
            placeholder=selection["placeholder"],
            min_values=1,
            max_values=1,
            options=options,
            custom_id=f"language_level:{selection['key']}",
        )

    async def callback(self, interaction):
        await interaction.response.defer()
        await self.cog.apply_role_selection(
            interaction,
            self.selection,
            int(self.values[0]),
        )


class LevelRoleView(discord.ui.View):
    def __init__(self, cog, selection):
        super().__init__(timeout=None)
        self.add_item(LevelSelect(cog, selection))


class ReactionRole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._message_setup_lock = asyncio.Lock()
        self._nationality_backfill_lock = asyncio.Lock()
        self._nationality_backfill_complete = False
        self.views = {
            selection["key"]: LevelRoleView(self, selection)
            for selection in ROLE_SELECTIONS
        }

    @commands.Cog.listener()
    async def on_ready(self):
        try:
            await self._backfill_existing_nationality_roles()
        except (aiomysql.MySQLError, RuntimeError) as error:
            print(f"[ERROR] 기존 국적 역할 DB 등록 실패: {error}")
        await self.ensure_role_messages()

    async def ensure_role_messages(self):
        async with self._message_setup_lock:
            await self._ensure_role_messages()

    def _has_current_select(self, message, selection):
        expected_custom_id = f"language_level:{selection['key']}"
        expected_options = [
            (f"{label} / {description}", str(role_id))
            for role_id, label, description in selection["roles"]
        ]

        for row in message.components:
            for component in getattr(row, "children", []):
                if getattr(component, "custom_id", None) != expected_custom_id:
                    continue

                actual_options = [
                    (option.label, option.value)
                    for option in getattr(component, "options", [])
                ]
                return (
                    getattr(component, "placeholder", None)
                    == selection["placeholder"]
                    and getattr(component, "min_values", None) == 1
                    and getattr(component, "max_values", None) == 1
                    and actual_options == expected_options
                )

        return False

    async def _ensure_role_messages(self):
        channel = self.bot.get_channel(ROLE_CHANNEL_ID)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(ROLE_CHANNEL_ID)
            except discord.HTTPException as error:
                print(f"[ERROR] 레벨 선택 채널을 불러오지 못했습니다: {error}")
                return

        headings = {}
        for selection in ROLE_SELECTIONS:
            headings[selection["heading"]] = selection
            for legacy_heading in selection.get("legacy_headings", ()):
                headings[legacy_heading] = selection
        existing_messages = {}
        found_messages = []

        try:
            async for message in channel.history(limit=200):
                if message.author.id != self.bot.user.id:
                    continue

                for heading, selection in headings.items():
                    if message.content.startswith(heading):
                        existing_messages[selection["key"]] = message
                        found_messages.append((selection["key"], message))
                        break


            current_order = [
                key
                for key, _ in reversed(found_messages)
            ]
            desired_order = [
                selection["key"]
                for selection in ROLE_SELECTIONS
            ]
            needs_rebuild = (
                current_order != desired_order
                or len(existing_messages) != len(ROLE_SELECTIONS)
                or any(
                    message.content != self._build_role_message(selection)
                    or not self._has_current_select(message, selection)
                    or message.edited_at is not None
                    for selection in ROLE_SELECTIONS
                    if (message := existing_messages.get(selection["key"]))
                )
            )
            if needs_rebuild:
                for _, message in found_messages:
                    await message.delete()
                existing_messages.clear()

            for selection in ROLE_SELECTIONS:
                content = self._build_role_message(selection)
                view = self.views[selection["key"]]
                role_message = existing_messages.get(selection["key"])

                if role_message is None:
                    role_message = await channel.send(content, view=view)
                elif role_message.reactions:
                    try:
                        await role_message.clear_reactions()
                    except discord.HTTPException:
                        for reaction in role_message.reactions:
                            if not reaction.me:
                                continue
                            try:
                                await role_message.remove_reaction(
                                    reaction.emoji,
                                    self.bot.user,
                                )
                            except discord.HTTPException:
                                pass
        except discord.HTTPException as error:
            print(f"[ERROR] 레벨 선택 안내 메시지를 준비하지 못했습니다: {error}")

    def _build_role_message(self, selection):
        if selection["subheading"]:
            return f'{selection["heading"]}\n-# {selection["subheading"]}'
        return selection["heading"]

    async def apply_role_selection(self, interaction, selection, selected_role_id):
        guild = interaction.guild
        if guild is None:
            return

        level_role_ids = {
            role_id
            for role_id, _, _ in selection["roles"]
        }
        if selected_role_id not in level_role_ids:
            return

        member = interaction.user
        if not isinstance(member, discord.Member):
            try:
                member = await guild.fetch_member(interaction.user.id)
            except (discord.NotFound, discord.HTTPException):
                return

        selected_role = guild.get_role(selected_role_id)
        if selected_role is None:
            return

        other_level_roles = [
            role
            for role in member.roles
            if role.id in level_role_ids and role.id != selected_role_id
        ]
        is_first_nationality_selection = (
            selection["key"] == "nationality"
            and not any(role.id in level_role_ids for role in member.roles)
        )

        try:
            if selected_role not in member.roles:
                await member.add_roles(selected_role)
            if other_level_roles:
                await member.remove_roles(*other_level_roles)
        except discord.HTTPException:
            return

        if selection["key"] == "nationality":
            try:
                is_new_welcome = await self._record_nationality_welcome(
                    guild.id,
                    member.id,
                    selected_role_id,
                )
            except (aiomysql.MySQLError, RuntimeError) as error:
                print(f"[ERROR] 국적 역할 환영 기록 실패: {error}")
                return

            if is_first_nationality_selection and is_new_welcome:
                await self._send_nationality_welcome(
                    member,
                    selected_role_id,
                )

    def _get_pool(self):
        point_cog = self.bot.get_cog("Point")
        pool = getattr(point_cog, "pool", None)
        if pool is None:
            raise RuntimeError("MariaDB connection pool is not ready")
        return pool

    async def _backfill_existing_nationality_roles(self):
        """기능 도입 전에 국적 역할을 받은 구성원을 인사 없이 최초 1회 등록."""
        async with self._nationality_backfill_lock:
            if self._nationality_backfill_complete:
                return

            nationality_role_ids = (
                KOREAN_NATIONALITY_ROLE_ID,
                JAPANESE_NATIONALITY_ROLE_ID,
            )
            records = []
            for guild in self.bot.guilds:
                for member in guild.members:
                    if member.bot:
                        continue

                    member_role_ids = {
                        role.id
                        for role in member.roles
                    }
                    selected_role_id = next(
                        (
                            role_id
                            for role_id in nationality_role_ids
                            if role_id in member_role_ids
                        ),
                        None,
                    )
                    if selected_role_id is not None:
                        records.append(
                            (guild.id, member.id, selected_role_id)
                        )

            if records:
                pool = self._get_pool()
                async with pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        guild_ids = tuple(sorted({
                            guild_id
                            for guild_id, _, _ in records
                        }))
                        placeholders = ", ".join(
                            "%s"
                            for _ in guild_ids
                        )
                        await cur.execute(
                            f"""
                            SELECT guild_id, user_id
                            FROM `{NATIONALITY_WELCOME_TABLE}`
                            WHERE guild_id IN ({placeholders})
                            """,
                            guild_ids,
                        )
                        existing_keys = {
                            (int(guild_id), int(user_id))
                            for guild_id, user_id in await cur.fetchall()
                        }
                        new_records = [
                            record
                            for record in records
                            if (record[0], record[1]) not in existing_keys
                        ]

                        if new_records:
                            await cur.executemany(
                                f"""
                                INSERT INTO `{NATIONALITY_WELCOME_TABLE}` (
                                    guild_id,
                                    user_id,
                                    selected_role_id
                                )
                                VALUES (%s, %s, %s)
                                ON DUPLICATE KEY UPDATE
                                    user_id = VALUES(user_id)
                                """,
                                new_records,
                            )
                            inserted_count = max(cur.rowcount, 0)
                        else:
                            inserted_count = 0
                print(
                    "[Role] 기존 국적 역할 DB 등록 완료: "
                    f"{inserted_count}/{len(records)}명 신규 등록"
                )

            self._nationality_backfill_complete = True

    async def _record_nationality_welcome(
        self,
        guild_id,
        user_id,
        selected_role_id,
    ):
        pool = self._get_pool()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    f"""
                    INSERT INTO `{NATIONALITY_WELCOME_TABLE}` (
                        guild_id,
                        user_id,
                        selected_role_id
                    )
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        user_id = VALUES(user_id)
                    """,
                    (guild_id, user_id, selected_role_id),
                )
                return cur.rowcount == 1

    async def _send_nationality_welcome(self, member, selected_role_id):
        message = NATIONALITY_WELCOME_MESSAGES.get(selected_role_id)
        if message is None:
            return

        channel = self.bot.get_channel(NATIONALITY_WELCOME_CHANNEL_ID)
        if channel is None:
            return

        await channel.send(message.format(mention=member.mention))

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        channel = self.bot.get_channel(LEAVE_LOG_CHANNEL_ID)
        if channel is None:
            return

        name = member.display_name
        await channel.send(f"↳ **{name}**님이 서버에서 떠났어요.")


async def setup(bot):
    cog = ReactionRole(bot)
    await bot.add_cog(cog)
    for view in cog.views.values():
        bot.add_view(view)
