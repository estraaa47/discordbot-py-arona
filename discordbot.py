import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import asyncio

load_dotenv()

class AronaBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # cogs 폴더 내의 모든 .py 파일을 로드
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                await self.load_extension(f'cogs.{filename[:-3]}')
                print(f'✅ Extension Loaded: {filename}')
        
        # 슬래시 커맨드 동기화 (특정 길드 전용)
        guild = discord.Object(id=888816297784262736)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)

    async def on_ready(self):
        print(f"✅ 로그인 완료: {self.user} (ID: {self.user.id})")

bot = AronaBot()
bot.run(os.environ['TOKEN'])
