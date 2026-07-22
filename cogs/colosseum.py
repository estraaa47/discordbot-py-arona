import asyncio
import datetime
from zoneinfo import ZoneInfo

import aiomysql
import discord
from discord.ext import commands, tasks


COLOSSEUM_CHANNEL_ID = 1529413109591179414
COLOSSEUM_BUTTON_CUSTOM_ID = "colosseum:apply"
COLOSSEUM_MESSAGE_FOOTER = "Arona Colosseum"
KST = ZoneInfo("Asia/Seoul")


def get_colosseum_language(interaction):
    locale = getattr(interaction, "locale", None)
    locale_code = getattr(locale, "value", str(locale or "")).lower()
    return "ja" if locale_code.startswith("ja") else "ko"


def colosseum_text(language, korean, japanese):
    return japanese if language == "ja" else korean


class ColosseumApplicationModal(discord.ui.Modal):
    def __init__(self, cog, language, tickets):
        super().__init__(
            title=colosseum_text(
                language,
                f"콜로세움 도전 신청 · 보유 {tickets}장",
                f"コロシアム挑戦申請・所持{tickets}枚",
            )
        )
        self.cog = cog
        self.language = language

        self.character_name = discord.ui.TextInput(
            label=colosseum_text(
                language,
                "캐릭터 이름",
                "キャラクター名",
            ),
            placeholder=colosseum_text(
                language,
                "캐릭터 이름을 입력해 주세요.",
                "キャラクター名を入力してください。",
            ),
            min_length=1,
            max_length=15,
            required=True,
        )
        self.ability = discord.ui.TextInput(
            label=colosseum_text(language, "능력", "能力"),
            placeholder=colosseum_text(
                language,
                "캐릭터의 능력을 설명해 주세요.",
                "キャラクターの能力を入力してください。",
            ),
            min_length=1,
            max_length=150,
            required=True,
            style=discord.TextStyle.paragraph,
        )
        self.add_item(self.character_name)
        self.add_item(self.ability)

    async def on_submit(self, interaction: discord.Interaction):
        character_name = str(self.character_name).strip()
        ability = str(self.ability).strip()

        if not character_name or not ability:
            await interaction.response.send_message(
                colosseum_text(
                    self.language,
                    "캐릭터 이름과 능력은 공백으로만 입력할 수 없어요.",
                    "キャラクター名と能力を空白だけで入力することはできません。",
                ),
                ephemeral=True,
            )
            return

        if len(character_name) > 15 or len(ability) > 150:
            await interaction.response.send_message(
                colosseum_text(
                    self.language,
                    "캐릭터 이름은 15자, 능력은 150자 이내로 입력해 주세요.",
                    "キャラクター名は15文字以内、能力は150文字以内で入力してください。",
                ),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            submitted = await self.cog.submit_application(
                interaction.user.id,
                character_name,
                ability,
            )
        except (aiomysql.MySQLError, RuntimeError):
            await interaction.followup.send(
                colosseum_text(
                    self.language,
                    "도전 신청을 저장하지 못했어요. 잠시 후 다시 시도해 주세요. "
                    "참여권은 차감되지 않았습니다.",
                    "挑戦申請を保存できませんでした。しばらくしてからもう一度お試しください。"
                    "参加券は消費されていません。",
                ),
                ephemeral=True,
            )
            return

        if not submitted:
            await interaction.followup.send(
                colosseum_text(
                    self.language,
                    "보유 참여권이 **0장**이에요. "
                    "참여권은 매일 00시에 최대 3장까지 충전됩니다.",
                    "所持している参加券は**0枚**です。"
                    "参加券は毎日0時に最大3枚まで補充されます。",
                ),
                ephemeral=True,
            )
            return

        safe_name = discord.utils.escape_markdown(character_name)
        await interaction.followup.send(
            colosseum_text(
                self.language,
                f"**{safe_name}** 캐릭터로 도전 신청을 완료했어요! "
                "참여권 1장을 사용했습니다.\n\n"
                "아로나가 선생님의 승리를 끝까지 응원할게요!",
                f"**{safe_name}**で挑戦申請が完了しました！"
                "参加券を1枚使用しました。\n\n"
                "アロナが先生の勝利を最後まで応援します！",
            ),
            ephemeral=True,
        )


class ColosseumApplicationView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="⚔️ 도전 신청 / 挑戦申請",
        style=discord.ButtonStyle.primary,
        custom_id=COLOSSEUM_BUTTON_CUSTOM_ID,
    )
    async def apply_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        language = get_colosseum_language(interaction)
        try:
            tickets = await self.cog.get_ticket_count(interaction.user.id)
        except (aiomysql.MySQLError, RuntimeError):
            await interaction.response.send_message(
                colosseum_text(
                    language,
                    "참여권을 확인하지 못했어요. 잠시 후 다시 시도해 주세요.",
                    "参加券を確認できませんでした。しばらくしてからもう一度お試しください。",
                ),
                ephemeral=True,
            )
            return

        if tickets < 1:
            await interaction.response.send_message(
                colosseum_text(
                    language,
                    "보유 참여권이 **0장**이에요. "
                    "참여권은 매일 00시에 최대 3장까지 충전됩니다.",
                    "所持している参加券は**0枚**です。"
                    "参加券は毎日0時に最大3枚まで補充されます。",
                ),
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(
            ColosseumApplicationModal(self.cog, language, tickets)
        )


class Colosseum(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.application_view = ColosseumApplicationView(self)
        self._database_ready = False
        self._database_lock = asyncio.Lock()
        self._message_lock = asyncio.Lock()
        self._message_is_ready = False

    async def cog_load(self):
        self.bot.add_view(self.application_view)
        self.daily_ticket_recharge.start()

    async def cog_unload(self):
        self.daily_ticket_recharge.cancel()

    def _get_pool(self):
        point_cog = self.bot.get_cog("Point")
        pool = getattr(point_cog, "pool", None)
        if pool is None:
            raise RuntimeError("MariaDB connection pool is not ready")
        return pool

    async def ensure_database(self):
        if self._database_ready:
            return

        async with self._database_lock:
            if self._database_ready:
                return

            pool = self._get_pool()
            async with pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS colosseum_tickets (
                            user_id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
                            tickets TINYINT UNSIGNED NOT NULL DEFAULT 3,
                            last_recharged_on DATE NOT NULL,
                            updated_at TIMESTAMP NOT NULL
                                DEFAULT CURRENT_TIMESTAMP
                                ON UPDATE CURRENT_TIMESTAMP
                        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
                        """
                    )
                    await cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS colosseum_applications (
                            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                            user_id BIGINT UNSIGNED NOT NULL,
                            character_name VARCHAR(15) NOT NULL,
                            ability VARCHAR(150) NOT NULL,
                            status VARCHAR(20) NOT NULL DEFAULT 'pending',
                            created_at TIMESTAMP NOT NULL
                                DEFAULT CURRENT_TIMESTAMP,
                            INDEX idx_colosseum_applications_user_created
                                (user_id, created_at)
                        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
                        """
                    )

            self._database_ready = True

    @staticmethod
    def _today_in_kst():
        return datetime.datetime.now(KST).date()

    async def _refresh_ticket(self, cur, user_id, today):
        await cur.execute(
            """
            INSERT INTO colosseum_tickets (
                user_id, tickets, last_recharged_on
            ) VALUES (%s, 3, %s)
            ON DUPLICATE KEY UPDATE user_id = user_id
            """,
            (user_id, today),
        )
        await cur.execute(
            """
            UPDATE colosseum_tickets
            SET tickets = 3, last_recharged_on = %s
            WHERE user_id = %s AND last_recharged_on < %s
            """,
            (today, user_id, today),
        )
        # 방어적으로 DB 값도 항상 최대 보유량인 3장 이하로 맞춘다.
        await cur.execute(
            """
            UPDATE colosseum_tickets
            SET tickets = 3
            WHERE user_id = %s AND tickets > 3
            """,
            (user_id,),
        )

    async def get_ticket_count(self, user_id):
        await self.ensure_database()
        today = self._today_in_kst()
        pool = self._get_pool()

        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await self._refresh_ticket(cur, user_id, today)
                await cur.execute(
                    """
                    SELECT tickets
                    FROM colosseum_tickets
                    WHERE user_id = %s
                    """,
                    (user_id,),
                )
                row = await cur.fetchone()

        return min(int(row[0]), 3) if row else 0

    async def submit_application(self, user_id, character_name, ability):
        await self.ensure_database()
        today = self._today_in_kst()
        pool = self._get_pool()

        async with pool.acquire() as conn:
            try:
                await conn.begin()
                async with conn.cursor() as cur:
                    await self._refresh_ticket(cur, user_id, today)
                    await cur.execute(
                        """
                        UPDATE colosseum_tickets
                        SET tickets = tickets - 1
                        WHERE user_id = %s AND tickets > 0
                        """,
                        (user_id,),
                    )
                    if cur.rowcount != 1:
                        await conn.rollback()
                        return False

                    await cur.execute(
                        """
                        INSERT INTO colosseum_applications (
                            user_id, character_name, ability
                        ) VALUES (%s, %s, %s)
                        """,
                        (user_id, character_name, ability),
                    )
                await conn.commit()
            except Exception:
                await conn.rollback()
                raise

        return True

    @staticmethod
    def _build_recruitment_embed():
        embed = discord.Embed(
            title="⚔️ 콜로세움 도전자 모집 / コロシアム挑戦者募集",
            description=(
                "**보유 참여권: 버튼을 눌러 확인 (최대 3장)**\n\n"
                "선생님, 콜로세움의 왕좌를 지키는 강대한 챔피언이 "
                "새로운 도전자를 기다리고 있어요!\n\n"
                "선생님만의 캐릭터를 만들어, 챔피언에게 도전해 주세요.\n"
                "도전권은 매일 00시에 3장으로 충전됩니다.\n\n\n"
                "아로나가 선생님의 승리를 끝까지 응원할게요!\n\n"
                "──────────────\n\n"
                "**所持参加券：ボタンを押して確認（最大3枚）**\n\n"
                "先生、コロシアムの王座を守る強大なチャンピオンが、"
                "新たな挑戦者を待っています！\n\n"
                "先生だけのキャラクターを作って、チャンピオンに挑戦してください。\n"
                "挑戦券は毎日0時に所持数が3枚まで補充されます。\n\n\n"
                "アロナが先生の勝利を最後まで応援します！"
            ),
            color=discord.Color.gold(),
        )
        embed.set_footer(text=COLOSSEUM_MESSAGE_FOOTER)
        return embed

    @staticmethod
    def _has_application_button(message):
        return any(
            getattr(component, "custom_id", None)
            == COLOSSEUM_BUTTON_CUSTOM_ID
            for row in message.components
            for component in getattr(row, "children", [])
        )

    async def ensure_recruitment_message(self):
        if self._message_is_ready:
            return

        async with self._message_lock:
            if self._message_is_ready:
                return

            channel = self.bot.get_channel(COLOSSEUM_CHANNEL_ID)
            if channel is None:
                channel = await self.bot.fetch_channel(COLOSSEUM_CHANNEL_ID)

            recruitment_message = None
            async for message in channel.history(limit=200):
                if (
                    message.author.id == self.bot.user.id
                    and (
                        self._has_application_button(message)
                        or any(
                            embed.footer.text == COLOSSEUM_MESSAGE_FOOTER
                            for embed in message.embeds
                            if embed.footer is not None
                        )
                    )
                ):
                    recruitment_message = message
                    break

            embed = self._build_recruitment_embed()
            if recruitment_message is None:
                await channel.send(embed=embed, view=self.application_view)
            else:
                await recruitment_message.edit(
                    content=None,
                    embed=embed,
                    view=self.application_view,
                )

            self._message_is_ready = True

    @commands.Cog.listener()
    async def on_ready(self):
        try:
            await self.ensure_database()
        except (aiomysql.MySQLError, RuntimeError) as error:
            print(f"[Colosseum] DB 초기화 실패: {error}")

        try:
            await self.ensure_recruitment_message()
        except (discord.HTTPException, AttributeError) as error:
            print(f"[Colosseum] 모집 메시지 준비 실패: {error}")

    @tasks.loop(time=datetime.time(hour=0, minute=0, tzinfo=KST))
    async def daily_ticket_recharge(self):
        try:
            await self.ensure_database()
            today = self._today_in_kst()
            pool = self._get_pool()
            async with pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        UPDATE colosseum_tickets
                        SET tickets = 3, last_recharged_on = %s
                        WHERE last_recharged_on < %s
                        """,
                        (today, today),
                    )
        except (aiomysql.MySQLError, RuntimeError) as error:
            print(f"[Colosseum] 참여권 충전 실패: {error}")

    @daily_ticket_recharge.before_loop
    async def before_daily_ticket_recharge(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(Colosseum(bot))
