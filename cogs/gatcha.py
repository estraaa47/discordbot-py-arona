import discord
from discord.ext import commands
from discord import app_commands
import os
import random

class Gacha(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.rarities = ["Normal", "Rare", "Super Rare", "Ultra Rare"]
        self.weights = [70, 20, 8, 2]
        self.image_base_path = "./images"
        self.ALLOWED_CHANNEL_ID = 1475278313416163358
        
        # ✅ 아주 짠 환급 비율 (절반 하향 버전)
        self.REFUND_RATES = {"Normal": 0.05, "Rare": 0.1, "Super Rare": 0.25, "Ultra Rare": 0.4}

    @app_commands.command(name="가챠", description="120P를 소모하여 가챠를 뽑습니다!")
    async def pull_gacha(self, interaction: discord.Interaction):
        if interaction.channel.id != self.ALLOWED_CHANNEL_ID:
            return await interaction.response.send_message(f"❌ 가챠는 <#{self.ALLOWED_CHANNEL_ID}>에서만 가능합니다.", ephemeral=True)

        user_id = interaction.user.id
        cost = 120
        pool = self.bot.get_cog('Point').pool

        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT points FROM users WHERE user_id = %s", (user_id,))
                res = await cur.fetchone()
                if not res or res[0] < cost:
                    return await interaction.response.send_message("포인트가 부족해요! (120P 필요)", ephemeral=True)

                rarity = random.choices(self.rarities, weights=self.weights, k=1)[0]
                folder_name = rarity.lower().replace(" ", "_")
                path = f"{self.image_base_path}/{folder_name}"
                files = os.listdir(path)
                selected_file = random.choice(files)
                card_name = os.path.splitext(selected_file)[0]

                # 중복 확인
                await cur.execute("SELECT 1 FROM inventory WHERE user_id = %s AND item_name = %s", (user_id, selected_file))
                if await cur.fetchone():
                    refund = int(cost * self.REFUND_RATES[rarity])
                    await cur.execute("UPDATE users SET points = points - %s WHERE user_id = %s", (cost - refund, user_id))
                    return await interaction.response.send_message(f"🎴 **{card_name}** 중복! [{refund}P 반환됨]")

                # 신규 획득
                await cur.execute("UPDATE users SET points = points - %s WHERE user_id = %s", (cost, user_id))
                await cur.execute("INSERT INTO inventory (user_id, item_name, rarity) VALUES (%s, %s, %s)", (user_id, selected_file, rarity))
                
                file = discord.File(f"{path}/{selected_file}", filename=selected_file)
                embed = discord.Embed(title="✨ 신규 획득!", description=f"**[{rarity}]** {card_name}!", color=self.get_color(rarity))
                embed.set_image(url=f"attachment://{selected_file}")
                await interaction.response.send_message(file=file, embed=embed)

    def get_color(self, rarity):
        colors = {"Ultra Rare": 0xa335ee, "Super Rare": 0xff8000, "Rare": 0x0070dd}
        return discord.Color(colors.get(rarity, 0x9d9d9d))

    @app_commands.command(name="도감", description="등급별 수집 현황을 확인합니다.")
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
                all_files = os.listdir(path)
                total_in_rarity = len(all_files)
            else:
                total_in_rarity = 0
            
            async with pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = "SELECT COUNT(DISTINCT item_name) FROM inventory WHERE user_id = %s AND rarity = %s"
                    await cur.execute(sql, (user_id, rarity))
                    res = await cur.fetchone()
                    owned_in_rarity = res[0] if res else 0
            
            rarity_stats[rarity] = (owned_in_rarity, total_in_rarity)
            total_owned += owned_in_rarity
            total_all += total_in_rarity

        rate = (total_owned / total_all * 100) if total_all > 0 else 0
        
        embed = discord.Embed(
            title=f"🗃️ {interaction.user.display_name}님의 수집 현황",
            description=f"**전체 수집률: {rate:.1f}% ({total_owned}/{total_all})**",
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