import asyncio

import discord
from discord.ext import commands


ROLE_CHANNEL_ID = 1528787386153304105
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
            (927148258885783582, "한국", "韓国"),
            (888820786041880666, "日本", "일본"),
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
        self.views = {
            selection["key"]: LevelRoleView(self, selection)
            for selection in ROLE_SELECTIONS
        }

    @commands.Cog.listener()
    async def on_ready(self):
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

        member = interaction.user
        if not isinstance(member, discord.Member):
            try:
                member = await guild.fetch_member(interaction.user.id)
            except (discord.NotFound, discord.HTTPException):
                return

        selected_role = guild.get_role(selected_role_id)
        if selected_role is None:
            return

        level_role_ids = {
            role_id
            for role_id, _, _ in selection["roles"]
        }
        other_level_roles = [
            role
            for role in member.roles
            if role.id in level_role_ids and role.id != selected_role_id
        ]

        try:
            if selected_role not in member.roles:
                await member.add_roles(selected_role)
            if other_level_roles:
                await member.remove_roles(*other_level_roles)
        except discord.HTTPException:
            pass

    @commands.Cog.listener()
    async def on_member_join(self, member):
        channel = self.bot.get_channel(1087554522378948609)
        if member.bot:
            await member.add_roles(member.guild.get_role(888840043463053333))
            await channel.send(f'{member.mention}님 Bot 역할 지급 완료!')
        else:
            await channel.send(f'{member.mention}님 반갑습니다! rule 채널을 확인해주세요.')


async def setup(bot):
    cog = ReactionRole(bot)
    await bot.add_cog(cog)
    for view in cog.views.values():
        bot.add_view(view)
