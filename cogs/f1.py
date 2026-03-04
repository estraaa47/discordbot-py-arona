import discord
from discord.ext import tasks, commands
import fastf1
import datetime
import os

class F1(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        self.map_path = "./f1_data/maps" 
        self.NOTI_CHANNEL_ID = 1343958648476667935 
        self.last_sent_event = ""
        self.check_f1_schedule.start()

    def cog_unload(self):
        self.check_f1_schedule.cancel()

    @tasks.loop(hours=12) # 하루 두 번만 체크 (서버 부하 최소화)
    async def check_f1_schedule(self):
        now = datetime.datetime.now()
        try:
            # 캐시가 없으므로 호출 시마다 F1 서버에서 직접 받아옵니다. (약 5~10초 소요)
            schedule = fastf1.get_event_schedule(now.year)
            upcoming = schedule[schedule['EventDate'] > now]

            if upcoming.empty:
                return

            event = upcoming.iloc[0]
            event_name = event['EventName']
            race_date = event['Session5DateUtc']
            
            days_until = (race_date - now).days
            
            # 6일 전일 때만 DB 체크 시작
            if days_until == 6:
                point_cog = self.bot.get_cog('Point')
                if not point_cog: return
                
                pool = point_cog.pool
                async with pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        await cur.execute("SELECT last_event FROM f1_status WHERE id = 1")
                        res = await cur.fetchone()
                        last_sent = res[0] if res else ""

                        # DB에 기록된 대회와 다를 때만 발송
                        if last_sent != event_name:
                            await self.send_f1_notification(event)
                            await cur.execute("UPDATE f1_status SET last_event = %s WHERE id = 1", (event_name,))
                            await conn.commit()

        except Exception as e:
            print(f"[F1 Cog Error] {e}")

    async def send_f1_notification(self, event):
        channel = self.bot.get_channel(self.NOTI_CHANNEL_ID)
        if not channel: return

        def to_kst(utc_dt):
            return (utc_dt + datetime.timedelta(hours=9)).strftime('%d %b %H:%M')

        # 세션 시간 (KST 변환)
        p1 = f"{to_kst(event['Session1DateUtc'])} - {(event['Session1DateUtc'] + datetime.timedelta(hours=10)).strftime('%H:%M')}"
        p2 = f"{to_kst(event['Session2DateUtc'])} - {(event['Session2DateUtc'] + datetime.timedelta(hours=10)).strftime('%H:%M')}"
        p3 = f"{to_kst(event['Session3DateUtc'])} - {(event['Session3DateUtc'] + datetime.timedelta(hours=10)).strftime('%H:%M')}"
        qual = f"{to_kst(event['Session4DateUtc'])} - {(event['Session4DateUtc'] + datetime.timedelta(hours=10)).strftime('%H:%M')}"
        race = to_kst(event['Session5DateUtc'])

        content = (
            f"# {event['OfficialEventName']}\n"
            f"## {event['Location']}\n"
            f"## KST(UTC+09:00)\n"
            f"### {p1} Practice 1\n"
            f"### {p2} Practice 2\n"
            f"### {p3} Practice 3\n"
            f"### {qual} Qualifying\n"
            f"### {race} Race"
        )

        location_file = f"{event['Location'].lower().replace(' ', '_')}.avif"
        full_image_path = os.path.join(self.map_path, location_file)

        if os.path.exists(full_image_path):
            file = discord.File(full_image_path, filename=location_file)
            await channel.send(content=content, file=file)
        else:
            await channel.send(content=content)

async def setup(bot):
    await bot.add_cog(F1(bot))