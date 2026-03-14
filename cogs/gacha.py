import discord
from discord.ext import commands
from discord import app_commands
import os
import random

COLLECTION_URL = "https://port-0-discordbot-py-arona-6g2llfjm6s1m.sel3.cloudtype.app/"

class Gacha(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.rarities = ["Normal", "Rare", "Super Rare", "Ultra Rare"]
        self.weights = [70, 20, 8, 2]
        self.image_base_path = "./images"
        self.ALLOWED_CHANNEL_ID = 1475278313416163358

    @app_commands.command(name="gacha", description="120P를 소모하여 가챠를 뽑습니다!")
    async def pull_gacha(self, interaction: discord.Interaction):
        if interaction.channel.id != self.ALLOWED_CHANNEL_ID:
            return await interaction.response.send_message(f"❌ 가챠는 <#{self.ALLOWED_CHANNEL_ID}>에서만 가능합니다.", ephemeral=True)

        user_id = interaction.user.id
        cost = 120
        pool = self.bot.get_cog('Point').pool

        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                # 1. 포인트 확인
                await cur.execute("SELECT points FROM users WHERE user_id = %s", (user_id,))
                res = await cur.fetchone()
                if not res or res[0] < cost:
                    return await interaction.response.send_message("포인트가 부족해요! (120P 필요)", ephemeral=True)

                # 2. 카드 뽑기 로직
                rarity = random.choices(self.rarities, weights=self.weights, k=1)[0]
                folder_name = rarity.lower().replace(" ", "_")
                path = f"{self.image_base_path}/{folder_name}"

                if not os.path.exists(path):
                    return await interaction.response.send_message(f"❌ {rarity} 폴더를 찾을 수 없어요.", ephemeral=True)

                files = [f for f in os.listdir(path) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')) and f != 'hidden.jpg']
                
                if not files:
                    return await interaction.response.send_message(f"❌ {rarity} 등급에 뽑을 수 있는 카드가 없어요!", ephemeral=True)

                selected_file = random.choice(files)
                card_name = os.path.splitext(selected_file)[0]

                # 3. 💡 [핵심 변경] 도감(collection) 테이블에서 중복 여부 확인
                await cur.execute("SELECT 1 FROM collection WHERE user_id = %s AND item_name = %s", (user_id, selected_file))
                is_duplicate = await cur.fetchone()

                # 4. 포인트 차감
                await cur.execute("UPDATE users SET points = points - %s WHERE user_id = %s", (cost, user_id))
                
                # 4.5 기존 NEW 마크 초기화
                await cur.execute("UPDATE inventory SET is_new = 0 WHERE user_id = %s AND is_new = 1", (user_id,))
                
                # 5. 💡 도감에 없는 신규 카드라면 collection 테이블에 등록 (도감작)
                if not is_duplicate:
                    await cur.execute("INSERT INTO collection (user_id, item_name, rarity) VALUES (%s, %s, %s)", (user_id, selected_file, rarity))

                # 6. 💡 중복이든 신규든 실물 카드는 무조건 inventory 테이블에 추가 (강화/합성 재료용)
                await cur.execute("INSERT INTO inventory (user_id, item_name, rarity, is_new) VALUES (%s, %s, %s, 1)", (user_id, selected_file, rarity))
                
                # 7. UI 메시지 분기 처리 (신규 vs 중복)
                file = discord.File(f"{path}/{selected_file}", filename=selected_file)
                
                if is_duplicate:
                    embed = discord.Embed(title="🎴 중복 획득", description=f"**[{rarity}]** {card_name}", color=discord.Color.light_gray())
                else:
                    embed = discord.Embed(title="✨ 🌟 신규 🌟 ✨", description=f"**[{rarity}]** {card_name}!", color=self.get_color(rarity))

                
                embed.set_image(url=f"attachment://{selected_file}")
                await interaction.response.send_message(file=file, embed=embed)

    def get_color(self, rarity):
        colors = {"Ultra Rare": 0xa335ee, "Super Rare": 0xff8000, "Rare": 0x0070dd}
        return discord.Color(colors.get(rarity, 0x9d9d9d))

    @app_commands.command(name="collection", description="등급별 수집 현황을 확인합니다.")
    async def collection(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        pool = self.bot.get_cog('Point').pool
        
        rarity_stats = {}
        total_owned = 0
        total_all = 0

        for rarity in self.rarities:
            folder = rarity.lower().replace(" ", "_")
            path = f"{self.image_base_path}/{folder}"
            
            if os.path.exists(path):
                all_files = [f for f in os.listdir(path) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')) and f != 'hidden.jpg']
                total_in_rarity = len(all_files)
            else:
                total_in_rarity = 0
            
            async with pool.acquire() as conn:
                async with conn.cursor() as cur:
                    # 💡 [핵심 변경] 이제 도감 달성률은 inventory가 아닌 collection 테이블을 참조합니다!
                    # collection 테이블에는 고유 카드만 1장씩 들어가므로 COUNT(*)로 세어도 됩니다.
                    sql = "SELECT COUNT(*) FROM collection WHERE user_id = %s AND rarity = %s"
                    await cur.execute(sql, (user_id, rarity))
                    res = await cur.fetchone()
                    owned_in_rarity = res[0] if res else 0
            
            rarity_stats[rarity] = (owned_in_rarity, total_in_rarity)
            total_owned += owned_in_rarity
            total_all += total_in_rarity

        rate = (total_owned / total_all * 100) if total_all > 0 else 0
        
        embed = discord.Embed(
            title=f"🗃️ {interaction.user.display_name}님의 수집 현황",
            description=(
                f"**전체 수집률: {rate:.1f}% ({total_owned}/{total_all})**\n\n"
                f"🌐 [웹에서 상세 도감 보기]({COLLECTION_URL})"
            ),
            color=discord.Color.blue()
        )

        for rarity, (owned, total) in rarity_stats.items():
            embed.add_field(
                name=f"[{rarity}]", 
                value=f"**{owned} / {total}**", 
                inline=True
            )
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Gacha(bot))