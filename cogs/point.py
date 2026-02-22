import discord
from discord.ext import commands
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
                # 'ON DUPLICATE KEY UPDATE'를 써서 유저가 있으면 더하고, 없으면 새로 만듭니다.
                sql = """
                INSERT INTO users (user_id, points) VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE points = points + %s
                """
                await cur.execute(sql, (user_id, amount, amount))

    @commands.Cog.listener()
    async def on_message(self, message):
        # 봇이 쓴 글이나 명령어(!로 시작)는 무시합니다.
        if message.author.bot or message.content.startswith('!'):
            return

        # 1~5점 사이의 랜덤 포인트 지급
        earned = random.randint(1, 5)
        await self.add_points(message.author.id, earned)

    @commands.command(name="포인트")
    async def check_point(self, ctx):
        """현재 내 포인트를 확인합니다."""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT points FROM users WHERE user_id = %s", (ctx.author.id,))
                result = await cur.fetchone()
                
                points = result[0] if result else 0
                await ctx.send(f"💰 {ctx.author.mention}님의 현재 포인트는 **{points}P**입니다.")


async def setup(bot):
    await bot.add_cog(Point(bot))