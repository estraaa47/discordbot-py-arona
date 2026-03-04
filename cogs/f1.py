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
        self.check_f1_schedule.start()

    def cog_unload(self):
        self.check_f1_schedule.cancel()

    @tasks.loop(hours=12)
    async def check_f1_schedule(self):
        print("\n[F1] 🔍 스케줄 체크 시작...")
        now = datetime.datetime.now()
        try:
            # 일정 데이터 로드
            schedule = fastf1.get_event_schedule(now.year)
            upcoming = schedule[schedule['Session5DateUtc'] > now]

            if upcoming.empty:
                print("[F1] ❌ 남은 경기가 없습니다.")
                return

            event = upcoming.iloc[0]
            event_name = event['EventName']
            race_date = event['Session5DateUtc']
            
            # 남은 날짜 계산
            diff = race_date - now
            days_until = diff.days
            print(f"[F1] 🏎️ 다음 경기: {event_name} / 결승까지: {days_until}일 남음")

            # 6일 이내 조건 체크 (테스트 시 숫자를 15 정도로 늘려보세요)
            if days_until <= 6:
                print(f"[F1] ✅ {days_until}일 전! 알림 발송 조건을 만족합니다.")
                point_cog = self.bot.get_cog('Point')
                if not point_cog:
                    print("[F1] ❌ 에러: 'Point' 코그를 찾을 수 없습니다.")
                    return
                
                pool = point_cog.pool
                async with pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        await cur.execute("SELECT last_event FROM f1_status WHERE id = 1")
                        res = await cur.fetchone()
                        last_sent = res[0] if res else ""
                        print(f"[F1] 💾 DB 기록: {last_sent} | 현재 대상: {event_name}")

                        if last_sent != event_name:
                            print(f"[F1] 🚀 알림 전송 함수를 호출합니다...")
                            # 발송 성공 여부를 확인하기 위해 결과를 받음
                            success = await self.send_f1_notification(event)
                            
                            if success:
                                await cur.execute("UPDATE f1_status SET last_event = %s WHERE id = 1", (event_name,))
                                await conn.commit()
                                print(f"[F1] 🎉 {event_name} 전송 완료 및 DB 업데이트 성공!")
                            else:
                                print(f"[F1] ❌ 전송 함수 실행 중 문제가 발생했습니다.")
                        else:
                            print(f"[F1] ⏭️ 이미 알림을 보낸 경기입니다. (DB와 동일)")
            else:
                print(f"[F1] ⏳ 아직 알림 시점이 아닙니다. (현재 {days_until}일 남음)")

        except Exception as e:
            print(f"[F1 Cog Error] ❌ 루프 에러: {e}")

    async def send_f1_notification(self, event):
        try:
            channel = self.bot.get_channel(self.NOTI_CHANNEL_ID)
            if not channel:
                print(f"   [발송에러] ❌ 채널을 찾을 수 없습니다. (ID: {self.NOTI_CHANNEL_ID})")
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

            # 이미지 경로 디버그
            location_file = f"{event['Location'].lower().replace(' ', '_')}.avif"
            full_image_path = os.path.join(self.map_path, location_file)
            print(f"   [정보] 🖼️ 이미지 경로 확인: {full_image_path}")

            if os.path.exists(full_image_path):
                print(f"   [정보] 📁 이미지 발견! 파일을 전송합니다.")
                file = discord.File(full_image_path, filename=location_file)
                await channel.send(content=content, file=file)
            else:
                print(f"   [경고] 📁 이미지가 경로에 없습니다. 텍스트만 전송합니다.")
                await channel.send(content=content)
            
            return True

        except Exception as e:
            print(f"   [발송에러] ❌ 메시지 전송 중 치명적 에러: {e}")
            return False

async def setup(bot):
    await bot.add_cog(F1(bot))