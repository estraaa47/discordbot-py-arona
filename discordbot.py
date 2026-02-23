import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import threading  
from web_app import run_flask  

load_dotenv()

class AronaBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    print(f'✅ Extension Loaded: {filename}')
                except Exception as e:
                    print(f'❌ Failed to load extension {filename}: {e}')
        
 
        guild = discord.Object(id=888816297784262736)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)

    async def on_ready(self):
        print(f"✅ 로그인 완료: {self.user} (ID: {self.user.id})")


if __name__ == "__main__":

    print("🌐 웹 서버를 시작합니다...")
    web_thread = threading.Thread(target=run_flask, daemon=True)
    web_thread.start()
    
    bot = AronaBot()
    bot.run(os.getenv('TOKEN'))
