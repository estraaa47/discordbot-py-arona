import asyncio

import discord
from discord.ext import commands


class ReactionRole(commands.Cog):
    ROLE_CHANNEL_ID = 1528787386153304105
    LEVEL_EMOJIS = ("0️⃣", "1️⃣", "2️⃣", "3️⃣")
    ROLE_SELECTIONS = (
        {
            "key": "japanese",
            "heading": "## 🇯🇵 일본어 레벨을 선택해주세요",
            "description": (
                "> 아래 숫자 중 자신의 일본어 수준에 맞는 항목을 눌러주세요.\n"
                "> 다른 레벨을 선택하면 기존 일본어 레벨 역할은 자동으로 변경됩니다."
            ),
            "section_heading": "### 레벨 안내",
            "roles": {
                "0️⃣": (1528792331623596052, "불가"),
                "1️⃣": (1528792010465480856, "초급"),
                "2️⃣": (1528792142997098626, "중급"),
                "3️⃣": (1528792261188391183, "상급"),
            },
        },
        {
            "key": "korean",
            "heading": "## 🇰🇷 韓国語レベルを選択してください",
            "description": (
                "> 下の数字から、自分の韓国語レベルに合うものを選んでください。\n"
                "> 別のレベルを選ぶと、現在の韓国語レベルロールが自動で変更されます。"
            ),
            "section_heading": "### レベル一覧",
            "roles": {
                "0️⃣": (1528791795582898286, "不可"),
                "1️⃣": (1528789614989545542, "初級"),
                "2️⃣": (1528790289999859822, "中級"),
                "3️⃣": (1528790367644811264, "上級"),
            },
        },
    )

    def __init__(self, bot):
        self.bot = bot
        self.role_message_ids = {}
        self._message_setup_lock = asyncio.Lock()

    @commands.Cog.listener()
    async def on_ready(self):
        async with self._message_setup_lock:
            await self._ensure_role_messages()

    async def _ensure_role_messages(self):
        channel = self.bot.get_channel(self.ROLE_CHANNEL_ID)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(self.ROLE_CHANNEL_ID)
            except discord.HTTPException as error:
                print(f"[ERROR] 레벨 선택 채널을 불러오지 못했습니다: {error}")
                return

        headings = {
            selection["heading"]: selection
            for selection in self.ROLE_SELECTIONS
        }
        existing_messages = {}

        try:
            async for message in channel.history(limit=200):
                if message.author.id != self.bot.user.id:
                    continue

                for heading, selection in headings.items():
                    if message.content.startswith(heading):
                        existing_messages[selection["key"]] = message
                        break

            for selection in self.ROLE_SELECTIONS:
                content = self._build_role_message(selection)
                role_message = existing_messages.get(selection["key"])

                if role_message is None:
                    role_message = await channel.send(content)
                elif role_message.content != content:
                    await role_message.edit(content=content)

                existing_reactions = {
                    str(reaction.emoji)
                    for reaction in role_message.reactions
                }
                for emoji in self.LEVEL_EMOJIS:
                    if emoji not in existing_reactions:
                        await role_message.add_reaction(emoji)

                self.role_message_ids[selection["key"]] = role_message.id
        except discord.HTTPException as error:
            print(f"[ERROR] 레벨 선택 안내 메시지를 준비하지 못했습니다: {error}")

    def _build_role_message(self, selection):
        role_lines = [
            f"{emoji} **{label}**"
            for emoji, (_, label) in selection["roles"].items()
        ]
        return "\n".join(
            [
                selection["heading"],
                "",
                selection["description"],
                "",
                selection["section_heading"],
                *role_lines,
            ]
        )

    def _get_selection(self, payload):
        if payload.channel_id != self.ROLE_CHANNEL_ID:
            return None

        for selection in self.ROLE_SELECTIONS:
            if (
                self.role_message_ids.get(selection["key"]) == payload.message_id
                and payload.emoji.name in selection["roles"]
            ):
                return selection
        return None

    async def _get_member(self, guild, user_id):
        member = guild.get_member(user_id)
        if member is not None:
            return member

        try:
            return await guild.fetch_member(user_id)
        except (discord.NotFound, discord.HTTPException):
            return None

    @commands.Cog.listener()
    async def on_member_join(self, member):
        channel = self.bot.get_channel(1087554522378948609)
        if member.bot:
            await member.add_roles(member.guild.get_role(888840043463053333))
            await channel.send(f'{member.mention}님 Bot 역할 지급 완료!')
        else:
            await channel.send(f'{member.mention}님 반갑습니다! rule 채널을 확인해주세요.')

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        selection = self._get_selection(payload)
        if selection is None:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return

        member = payload.member or await self._get_member(guild, payload.user_id)
        if member is None or member.bot:
            return

        selected_role_id = selection["roles"][payload.emoji.name][0]
        selected_role = guild.get_role(selected_role_id)
        if selected_role is None:
            return

        level_role_ids = {
            role_id
            for role_id, _ in selection["roles"].values()
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
    async def on_raw_reaction_remove(self, payload):
        selection = self._get_selection(payload)
        if selection is None:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return

        member = await self._get_member(guild, payload.user_id)
        if member is None or member.bot:
            return

        role_id = selection["roles"][payload.emoji.name][0]
        role = guild.get_role(role_id)
        if role is None or role not in member.roles:
            return

        try:
            await member.remove_roles(role)
        except discord.HTTPException:
            pass


async def setup(bot):
    await bot.add_cog(ReactionRole(bot))
