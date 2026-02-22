import discord
from discord.ext import commands

class ReactionRole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ROLE_MSG_ID = 1087701328928706570
        self.ROLES = {
            "🇰🇷": 927148258885783582,
            "🇯🇵": 888820786041880666,
        }

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
        if payload.message_id != self.ROLE_MSG_ID: return
        guild = self.bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)
        if member.bot: return
        
        if payload.emoji.name in self.ROLES:
            role = guild.get_role(self.ROLES[payload.emoji.name])
            await member.add_roles(role)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        if payload.message_id != self.ROLE_MSG_ID: return
        guild = self.bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)
        if member.bot: return
        
        if payload.emoji.name in self.ROLES:
            role = guild.get_role(self.ROLES[payload.emoji.name])
            await member.remove_roles(role)

async def setup(bot):
    await bot.add_cog(ReactionRole(bot))