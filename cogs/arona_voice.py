import discord
from discord.ext import commands
from discord import app_commands
from discord.oggparse import OggStream
import os
import asyncio
import tempfile
from pathlib import Path
import httpx
import tts_registry

from bot_i18n import interaction_text


class OggOpusAudio(discord.AudioSource):
    """미리 인코딩된 Ogg-Opus 파일을 읽어 read() 호출마다 Opus 패킷 1개를 반환한다.

    - is_opus()=True 이므로 discord.py는 재인코딩(libopus)을 하지 않고 그대로 송신한다.
      → Cloudtype에 ffmpeg / libopus 불필요.
    - Ogg-Opus 스트림 선두의 OpusHead / OpusTags 헤더 패킷은 오디오가 아니므로 건너뛴다.
    - 로컬에서 반드시 `-frame_duration 20` 으로 인코딩해야 패킷 1개 = 20ms 프레임이 되어
      discord.py의 20ms 송신 주기와 맞는다.
    """

    def __init__(self, path: str, cleanup_path: bool = True):
        self._path = path
        self._cleanup_path = cleanup_path
        self._file = open(path, "rb")
        self._packets = OggStream(self._file).iter_packets()

    def is_opus(self) -> bool:
        return True

    def read(self) -> bytes:
        packet = next(self._packets, b"")
        # Ogg-Opus는 OpusHead, OpusTags 헤더 패킷으로 시작한다. 오디오 프레임이 아니므로 스킵.
        while packet[:8] in (b"OpusHead", b"OpusTags"):
            packet = next(self._packets, b"")
        return packet

    def cleanup(self) -> None:
        try:
            self._file.close()
        except Exception:
            pass
        if self._cleanup_path:
            try:
                os.remove(self._path)
            except OSError:
                pass


class AronaVoice(commands.Cog):
    """음성 채널 연결 + 로컬 TTS 서버가 만든 Opus 오디오 재생."""

    def __init__(self, bot):
        self.bot = bot
        self.active = {}   # guild_id -> voice_client (음성 활성 길드)
        self.locks = {}    # guild_id -> asyncio.Lock (길드별 재생 직렬화)
        self.local_tts_url = os.getenv("LOCAL_TTS_URL")
        self.tts_secret = os.getenv("TTS_SHARED_SECRET")
        self.assets_dir = Path(__file__).resolve().parent.parent / "arona_assets"

    def _get_lock(self, guild_id: int) -> asyncio.Lock:
        if guild_id not in self.locks:
            self.locks[guild_id] = asyncio.Lock()
        return self.locks[guild_id]

    def is_active(self, guild_id: int) -> bool:
        vc = self.active.get(guild_id)
        return vc is not None and vc.is_connected()

    def is_member_in_channel(self, guild_id: int, member) -> bool:
        """호출자(member)가 봇과 '같은' 음성 채널에 있는지."""
        vc = self.active.get(guild_id)
        if vc is None or not vc.is_connected() or vc.channel is None:
            return False
        voice_state = getattr(member, "voice", None)
        if voice_state is None or voice_state.channel is None:
            return False
        return voice_state.channel.id == vc.channel.id

    # ==========================================================
    # 음성 채널 접속 / 해제
    # ==========================================================
    @app_commands.command(name="join", description="아로나를 음성 채널에 부릅니다")
    async def join(self, interaction: discord.Interaction):
        user = interaction.user
        if not isinstance(user, discord.Member) or user.voice is None or user.voice.channel is None:
            await interaction.response.send_message(
                interaction_text(
                    interaction,
                    "선생님, 먼저 음성 채널에 들어가 주세요!",
                    "先生、先にボイスチャンネルに入ってください！",
                    "Please join a voice channel first!",
                ),
                ephemeral=True,
            )
            return

        channel = user.voice.channel
        guild_id = interaction.guild_id
        vc = interaction.guild.voice_client

        try:
            if vc and vc.is_connected():
                await vc.move_to(channel)
            else:
                vc = await channel.connect()
            self.active[guild_id] = vc
            await interaction.response.send_message(
                interaction_text(
                    interaction,
                    f"음성 채널 **{channel.name}**에 들어왔어요, 선생님! ☆",
                    f"ボイスチャンネル **{channel.name}** に入りました、先生！☆",
                    f"I joined **{channel.name}**! ☆",
                )
            )
        except Exception as e:
            print(f"[voice] join error: {e}")
            await interaction.response.send_message(
                interaction_text(
                    interaction,
                    "음성 채널 접속에 실패했어요, 선생님...",
                    "ボイスチャンネルへの接続に失敗しました、先生…",
                    "I couldn't connect to the voice channel...",
                ),
                ephemeral=True,
            )

    @app_commands.command(name="leave", description="아로나를 음성 채널에서 내보냅니다")
    async def leave(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        vc = interaction.guild.voice_client

        if not (vc and vc.is_connected()):
            self.active.pop(guild_id, None)
            await interaction.response.send_message(
                interaction_text(
                    interaction,
                    "저 지금 음성 채널에 없는데요, 선생님?",
                    "私は今ボイスチャンネルにいませんよ、先生？",
                    "I'm not in a voice channel right now.",
                ),
                ephemeral=True,
            )
            return

        # 봇과 같은 음성 채널에 있는 사람만 내보낼 수 있음
        vs = getattr(interaction.user, "voice", None)
        if vs is None or vs.channel is None or vs.channel.id != vc.channel.id:
            await interaction.response.send_message(
                interaction_text(
                    interaction,
                    "같은 음성 채널에 있는 선생님만 저를 내보낼 수 있어요!",
                    "同じボイスチャンネルにいる先生だけが私を退出させられます！",
                    "Only someone in the same voice channel can disconnect me!",
                ),
                ephemeral=True,
            )
            return

        await vc.disconnect(force=True)
        self.active.pop(guild_id, None)
        await interaction.response.send_message(
            interaction_text(
                interaction,
                "음성 채널에서 나왔어요, 선생님! 다음에 또 불러주세요~",
                "ボイスチャンネルから退出しました、先生！また呼んでくださいね～",
                "I left the voice channel. Call me again anytime!",
            )
        )

    # ==========================================================
    # 재생 코어 (길드별 Lock 으로 직렬화)
    # ==========================================================
    async def _play_file(self, guild_id: int, path: str, cleanup: bool):
        vc = self.active.get(guild_id)
        if vc is None or not vc.is_connected():
            if cleanup:
                try:
                    os.remove(path)
                except OSError:
                    pass
            return

        lock = self._get_lock(guild_id)
        async with lock:
            # Lock 획득 후에도 이전 재생이 남아있으면 끝날 때까지 대기
            while vc.is_playing():
                await asyncio.sleep(0.1)

            source = OggOpusAudio(path, cleanup_path=cleanup)
            done = asyncio.Event()

            def _after(err):
                if err:
                    print(f"[voice] playback error: {err}")
                # after 콜백은 음성 송신 스레드에서 호출됨 → 스레드 안전하게 이벤트 set
                self.bot.loop.call_soon_threadsafe(done.set)

            try:
                vc.play(source, after=_after)
            except Exception as e:
                print(f"[voice] play() error: {e}")
                source.cleanup()
                return

            await done.wait()

    # ==========================================================
    # speak(): 로컬 TTS 서버 호출 → Opus 스트리밍 저장 → 재생
    # ==========================================================
    async def speak(self, guild_id: int, text_jp: str):
        if not self.is_active(guild_id):
            return

        # 로컬이 자기등록한 URL 우선, 없으면 env 고정값(LOCAL_TTS_URL) 폴백
        base_url = tts_registry.get_url() or self.local_tts_url
        if not base_url:
            print("[voice] 등록된 TTS URL 없음 — 음성 스킵 (로컬 PC/터널 확인)")
            return

        text_jp = (text_jp or "").strip()
        if not text_jp:
            return

        tmp_path = None
        try:
            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".ogg", prefix="arona_tts_")
            os.close(tmp_fd)

            url = base_url.rstrip("/") + "/tts"
            headers = {"X-TTS-Secret": self.tts_secret or ""}
            timeout = httpx.Timeout(60.0, connect=10.0)

            # 응답을 통째로 메모리에 올리지 않고 64KB 청크로 임시 파일에 스트리밍 저장 (1GB RAM 대비)
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST", url, json={"text": text_jp}, headers=headers
                ) as resp:
                    if resp.status_code != 200:
                        await resp.aread()
                        print(f"[voice] TTS 서버 응답 {resp.status_code} — 음성 스킵")
                        return
                    with open(tmp_path, "wb") as f:
                        async for chunk in resp.aiter_bytes(chunk_size=65536):
                            f.write(chunk)

            # 재생 (재생/실패 시 _play_file 이 임시파일 삭제 책임을 가짐)
            path_to_play = tmp_path
            tmp_path = None
            await self._play_file(guild_id, path_to_play, cleanup=True)
        except Exception as e:
            print(f"[voice] speak error: {e}")
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

async def setup(bot):
    await bot.add_cog(AronaVoice(bot))
