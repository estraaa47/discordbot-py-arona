import discord
from discord.ext import commands
from discord import app_commands # 슬래시 커맨드를 위해 추가
import aiomysql
import os
import random

class Point(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pool = None

    async def cog_load(self):
        """Cog이 로드될 때 MariaDB 커넥션 풀을 생성합니다."""
        self.pool = await aiomysql.create_pool(
            host=os.getenv('DB_HOST'),
            port=int(os.getenv('DB_PORT', 3306)),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASS'),
            db=os.getenv('DB_NAME'),
            autocommit=True
        )

    async def cog_unload(self):
        """봇 종료 시 DB 연결을 안전하게 닫습니다."""
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()

    async def add_points(self, user_id, amount):
        """DB에 포인트를 추가하거나 유저가 없으면 새로 생성합니다."""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """
                INSERT INTO users (user_id, points) VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE points = points + %s
                """
                await cur.execute(sql, (user_id, amount, amount))

    @commands.Cog.listener()
    async def on_message(self, message):
        """채팅 적립 로직 (이건 기존처럼 메시지를 감지해야 하므로 유지합니다)"""
        if message.author.bot or message.content.startswith('!'):
            return

        earned = random.randint(1, 5)
        await self.add_points(message.author.id, earned)

    # ✨ 슬래시 커맨드 (/Point)
    @app_commands.command(name="point", description="현재 보유한 포인트를 확인합니다.")
    async def check_point(self, interaction: discord.Interaction):
        """슬래시 커맨드 전용 포인트 확인 함수"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                # interaction.user.id를 사용합니다.
                await cur.execute("SELECT points FROM users WHERE user_id = %s", (interaction.user.id,))
                result = await cur.fetchone()
                
                points = result[0] if result else 0
                
                # 대답은 interaction.response.send_message를 사용합니다.
                await interaction.response.send_message(
                    f"💰 {interaction.user.mention}님의 현재 포인트는 **{points}P**입니다."
                )

async def setup(bot):
    await bot.add_cog(Point(bot))