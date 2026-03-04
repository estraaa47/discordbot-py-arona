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
        # 봇이 완전히 준비된 후 루프를 시작하도록 설정
        self.bot.loop.create_task(self.initialize_f1_loop())

    async def initialize_f1_loop(self):
        await self.bot.wait_until_ready()
        print(f"[F1] 봇 준비 완료. 채널 {self.NOTI_CHANNEL_ID} 상태 확인 중...")
        if not self.check_f1_schedule.is_running():
            self.check_f1_schedule.start()

    def cog_unload(self):
        self.check_f1_schedule.cancel()

    @tasks.loop(hours=12)
    async def check_f1_schedule(self):
        print("\n[F1] 🔍 일정 체크 루프 시작")
        now = datetime.datetime.now()
        try:
            # F1 일정 가져오기
            schedule = fastf1.get_event_schedule(now.year)
            upcoming = schedule[schedule['Session5DateUtc'] > now]

            if upcoming.empty:
                print("[F1] ❌ 남은 경기가 없습니다.")
                return

            event = upcoming.iloc[0]
            event_name = event['EventName']
            race_date = event['Session5DateUtc']
            
            days_until = (race_date - now).days
            print(f"[F1] 🏎️ 다음 경기: {event_name} / 결승까지: {days_until}일 남음")

            # 7일 이내일 때 알림 로직 작동
            if days_until <= 7:
                point_cog = self.bot.get_cog('Point')
                if not point_cog:
                    print("[F1] ❌ 'Point' 코그를 찾을 수 없습니다.")
                    return
                
                pool = point_cog.pool
                async with pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        await cur.execute("SELECT last_event FROM f1_status WHERE id = 1")
                        res = await cur.fetchone()
                        last_sent = res[0] if res else ""

                        if last_sent != event_name:
                            print(f"[F1] 🚀 발송 조건 충족! 전송 시도 중...")
                            success = await self.send_f1_notification(event)
                            
                            if success:
                                await cur.execute("UPDATE f1_status SET last_event = %s WHERE id = 1", (event_name,))
                                await conn.commit()
                                print(f"[F1] 🎉 {event_name} 알림 발송 및 DB 업데이트 성공!")
                            else:
                                print(f"[F1] ❌ 전송 실패로 인해 DB를 업데이트하지 않았습니다.")
                        else:
                            print(f"[F1] ⏭️ 이미 알림을 보낸 경기입니다: {event_name}")

        except Exception as e:
            print(f"[F1 Cog Error] ❌ 루프 에러: {e}")

    async def send_f1_notification(self, event):
        try:
            # get_channel(캐시) 대신 fetch_channel(API 직접 호출) 사용 시도
            channel = self.bot.get_channel(self.NOTI_CHANNEL_ID)
            if not channel:
                print(f"   [정보] 캐시에 채널이 없음. API로 직접 채널을 가져옵니다...")
                try:
                    channel = await self.bot.fetch_channel(self.NOTI_CHANNEL_ID)
                    print(f"   [정보] 채널 연결 성공: {channel.name}")
                except Exception as e:
                    print(f"   [발송에러] ❌ 채널 ID를 찾을 수 없거나 권한이 없습니다: {e}")
                    return False

            def to_kst(utc_dt):
                return (utc_dt + datetime.timedelta(hours=9)).strftime('%d %b %H:%M')

            # 세션 정보 구성
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

            # 이미지 경로 확인
            location_file = f"{event['Location'].lower().replace(' ', '_')}.avif"
            full_image_path = os.path.join(self.map_path, location_file)

            if os.path.exists(full_image_path):
                file = discord.File(full_image_path, filename=location_file)
                await channel.send(content=content, file=file)
            else:
                print(f"   [경고] 이미지가 없습니다: {full_image_path}")
                await channel.send(content=content)
            
            return True

        except Exception as e:
            print(f"   [발송에러] ❌ 전송 중 치명적 에러: {e}")
            return False

async def setup(bot):
    await bot.add_cog(F1(bot))