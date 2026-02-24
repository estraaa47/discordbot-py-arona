import discord
from discord.ext import commands, tasks # 루프 기능을 위해 tasks 추가
from discord import app_commands
import aiomysql
import os
import random
import datetime # 로그 시간 표시용

class Point(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pool = None
        # 음성 보상 루프 시작
        self.vc_reward_loop.start()

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
        """봇 종료 시 DB 연결과 루프를 안전하게 닫습니다."""
        self.vc_reward_loop.cancel() # 루프 종료
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

    # --- 이벤트 리스너: 채팅 적립 ---
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or message.content.startswith('!'):
            return

        earned = random.randint(1, 5)
        await self.add_points(message.author.id, earned)

    # --- 백그라운드 태스크: 음성 체류 보상 (10분마다) ---
    @tasks.loop(minutes=10)
    async def vc_reward_loop(self):
        """음성 채널 접속자에게 조용히 포인트를 지급합니다."""
        reward_amount = 10 # 10분당 지급할 포인트 양
        
        # 봇이 연결된 모든 서버를 확인
        for guild in self.bot.guilds:
            for vc in guild.voice_channels:
                # 혼자 있을 때 적립되는 '채굴' 방지 (2명 이상일 때만)
                if len(vc.members) < 2:
                    continue
                
                for member in vc.members:
                    # 봇 제외 및 잠수(마이크/헤드셋 끔) 상태 제외
                    if not member.bot and not (member.voice.self_deaf and member.voice.self_mute):
                        await self.add_points(member.id, reward_amount)
                        # 콘솔 로그에만 기록 (채팅 도배 X)
                        print(f"[{datetime.datetime.now()}] 🎙️ VC 보상 완료: {member.display_name} (+{reward_amount}P)")

    @vc_reward_loop.before_loop
    async def before_vc_reward_loop(self):
        """봇이 완전히 켜질 때까지 루프를 대기시킵니다."""
        await self.bot.wait_until_ready()

    # --- 슬래시 커맨드: 포인트 확인 ---
    @app_commands.command(name="point", description="현재 보유한 포인트를 확인합니다.")
    async def check_point(self, interaction: discord.Interaction):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT points FROM users WHERE user_id = %s", (interaction.user.id,))
                result = await cur.fetchone()
                
                points = result[0] if result else 0
                
                await interaction.response.send_message(
                    f"💰 {interaction.user.mention}선생님의 현재 포인트는 **{points}P**에요!"
                )

async def setup(bot):
    await bot.add_cog(Point(bot))