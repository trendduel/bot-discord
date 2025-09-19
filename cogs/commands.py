import discord
from discord.ext import commands
from discord import app_commands
from config import FOUNDER_ROLE_ID, ADMIN_ROLE_ID
from translations import get_translation

class Commands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="commands", description="Mostra l'elenco dei comandi disponibili")
    async def commands(self, interaction: discord.Interaction):
        is_staff = any(role.id in [FOUNDER_ROLE_ID, ADMIN_ROLE_ID] for role in interaction.user.roles)
        locale = str(interaction.locale)

        embed = discord.Embed(
            title=get_translation('commands_title', locale),
            color=0x00FFFF,
        )

        if is_staff:
            embed.description = get_translation('commands_staff_description', locale)
            commands_list = [
                get_translation('commands_commands', locale),
                get_translation('commands_stats', locale),
                get_translation('commands_weekly_stats', locale),
                get_translation('commands_publish_leaderboard', locale),
                get_translation('commands_test_leaderboard', locale),
                get_translation('commands_reset_weekly', locale),
                get_translation('commands_get_leaderboard', locale),
                get_translation('commands_botstats', locale),
                get_translation('commands_checkpermissions', locale),
                get_translation('commands_clear_archives', locale),
                get_translation('commands_manage_user_stats', locale),  # Aggiunto /manage-user-stats
            ]
        else:
            embed.description = get_translation('commands_user_description', locale)
            commands_list = [
                get_translation('commands_commands', locale),
                get_translation('commands_stats', locale),
            ]

        embed.add_field(
            name="Comandi",
            value="\n".join(commands_list),
            inline=False
        )
        embed.set_footer(
            text=get_translation('commands_footer', locale),
            icon_url=self.bot.user.avatar.url if self.bot.user and self.bot.user.avatar else None
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Commands(bot))