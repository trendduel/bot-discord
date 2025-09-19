import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
import pytz
import logging
from config import FOUNDER_ROLE_ID, ADMIN_ROLE_ID, ITALY_TZ, LOG_CHANNEL_ID
from utils import get_week_boundaries, cleanup_lock_files
from translations import get_translation
from database import c, conn, record_weekly_event

logger = logging.getLogger(__name__)

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @tasks.loop(hours=24)
    async def check_weekly_leaderboard(self):
        log_channel = self.bot.get_channel(LOG_CHANNEL_ID)
        leaderboard_cog = self.bot.get_cog('Leaderboard')
        if leaderboard_cog and not leaderboard_cog.weekly_leaderboard.is_running():
            logger.error("⚠️ Task weekly_leaderboard non in esecuzione")
            if log_channel:
                await log_channel.send("⚠️ **Errore**: Il task di pubblicazione della classifica settimanale non è in esecuzione. Riavviare il bot.")
            leaderboard_cog.weekly_leaderboard.start()
            logger.info("📊 Task weekly_leaderboard riavviato")

    @check_weekly_leaderboard.before_loop
    async def before_check_weekly_leaderboard(self):
        await self.bot.wait_until_ready()
        logger.info("🕵️ Task di controllo weekly_leaderboard pronto")

    @tasks.loop(hours=6)
    async def cleanup_task(self):
        try:
            cleanup_lock_files()
            logger.info("🧹 Cleanup automatico completato")
        except Exception as e:
            logger.error(f"Errore nel cleanup task: {e}")

    @cleanup_task.before_loop
    async def before_cleanup(self):
        await self.bot.wait_until_ready()
        logger.info("🧹 Cleanup task pronto")

    @app_commands.command(name="botstats", description="Mostra le statistiche del bot")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_any_role(FOUNDER_ROLE_ID, ADMIN_ROLE_ID)
    async def botstats(self, interaction: discord.Interaction):
        locale = str(interaction.locale)
        from database import c
        uptime = datetime.now() - self.bot.bot_status['start_time']
        now = datetime.now(ITALY_TZ)
        last_activity = self.bot.bot_status['last_activity'].astimezone(ITALY_TZ)

        c.execute('SELECT COUNT(*) FROM users')
        total_users = c.fetchone()[0]

        c.execute('SELECT COUNT(*) FROM weekly_events WHERE archived = 0')
        active_events = c.fetchone()[0]

        c.execute('SELECT COUNT(*) FROM weekly_archives')
        total_archives = c.fetchone()[0]

        # Calcolo della prossima pubblicazione
        next_sunday = now + timedelta(days=(6-now.weekday()))
        next_publish = next_sunday.replace(hour=20, minute=0, second=0, microsecond=0)
        if now.weekday() == 6 and now.hour >= 20:  # Se è domenica dopo le 20:00
            next_publish = next_publish + timedelta(days=7)  # Sposta alla prossima domenica
        time_to_publish = next_publish - now

        embed = discord.Embed(
            title=get_translation('botstats_title', locale),
            color=0x00FF00
        )
        embed.add_field(
            name=get_translation('botstats_uptime', locale),
            value=f"{uptime.days}d {uptime.seconds//3600}h {(uptime.seconds%3600)//60}m",
            inline=True
        )
        embed.add_field(
            name=get_translation('botstats_messages', locale),
            value=f"{self.bot.bot_status['messages_processed']:,}",
            inline=True
        )
        embed.add_field(
            name=get_translation('botstats_reactions', locale),
            value=f"{self.bot.bot_status['reactions_processed']:,}",
            inline=True
        )
        embed.add_field(
            name=get_translation('botstats_users', locale),
            value=f"{total_users:,}",
            inline=True
        )
        embed.add_field(
            name=get_translation('botstats_servers', locale),
            value=len(self.bot.guilds),
            inline=True
        )
        embed.add_field(
            name=get_translation('botstats_active_events', locale),
            value=f"{active_events:,}",
            inline=True
        )
        embed.add_field(
            name=get_translation('botstats_archives', locale),
            value=f"{total_archives:,}",
            inline=True
        )
        embed.add_field(
            name=get_translation('botstats_last_activity', locale),
            value=last_activity.strftime("%d/%m/%Y %H:%M:%S"),
            inline=True
        )
        embed.add_field(
            name=get_translation('botstats_next_leaderboard', locale),
            value=f"{next_publish.strftime('%d/%m/%Y %H:%M')} ({time_to_publish.days}d {time_to_publish.seconds//3600}h {(time_to_publish.seconds%3600)//60}m)",
            inline=True
        )
        embed.set_footer(
            text=get_translation('botstats_footer', locale).format(datetime=now.strftime("%Y-%m-%d %H:%M")),
            icon_url=self.bot.user.avatar.url if self.bot.user and self.bot.user.avatar else None
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="checkpermissions", description="Verifica i permessi del bot")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_any_role(FOUNDER_ROLE_ID, ADMIN_ROLE_ID)
    async def checkpermissions(self, interaction: discord.Interaction):
        locale = str(interaction.locale)
        log_channel = self.bot.get_channel(LOG_CHANNEL_ID)
        guild = interaction.guild
        bot_member = guild.me

        required_permissions = {
            'send_messages': 'Inviare messaggi',
            'embed_links': 'Incorporare link',
            'read_message_history': 'Leggere la cronologia dei messaggi',
            'add_reactions': 'Aggiungere reazioni',
            'manage_messages': 'Gestire messaggi'
        }

        missing_permissions = []
        for perm, desc in required_permissions.items():
            if not getattr(bot_member.guild_permissions, perm, False):
                missing_permissions.append(f"• {desc}")

        embed = discord.Embed(
            title=get_translation('checkpermissions_title', locale),
            color=0xFF0000 if missing_permissions else 0x00FF00
        )

        if missing_permissions:
            embed.add_field(
                name=get_translation('checkpermissions_missing', locale),
                value=get_translation('checkpermissions_missing_text', locale),
                inline=False
            )
            embed.add_field(
                name=get_translation('checkpermissions_status', locale),
                value="\n".join(missing_permissions),
                inline=False
            )
            if log_channel and log_channel.permissions_for(guild.me).send_messages:
                await log_channel.send(f"⚠️ **Verifica permessi** da {interaction.user.mention}: Permessi mancanti: {', '.join(missing_permissions)}")
        else:
            embed.add_field(
                name=get_translation('checkpermissions_ok', locale),
                value=get_translation('checkpermissions_ok_text', locale),
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="clear-archives", description="Svuota l'archivio delle classifiche settimanali")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_any_role(FOUNDER_ROLE_ID, ADMIN_ROLE_ID)
    async def clear_archives(self, interaction: discord.Interaction):
        locale = str(interaction.locale)
        log_channel = self.bot.get_channel(LOG_CHANNEL_ID)

        try:
            # Conta il numero di archivi prima di eliminarli
            c.execute('SELECT COUNT(*) FROM weekly_archives')
            archive_count = c.fetchone()[0]

            # Elimina tutti i record dalla tabella weekly_archives
            c.execute('DELETE FROM weekly_archives')
            conn.commit()

            logger.info(f"🗑️ Archivio classifiche svuotato: {archive_count} record eliminati da {interaction.user.name}")
            embed = discord.Embed(
                title="✅ Archivio Svuotato",
                description=f"Sono stati eliminati {archive_count} archivi delle classifiche settimanali.",
                color=0x00FF00
            )

            if log_channel and log_channel.permissions_for(log_channel.guild.me).send_messages:
                await log_channel.send(f"🗑️ **Archivio svuotato**: {interaction.user.mention} ha eliminato {archive_count} archivi delle classifiche settimanali.")

        except Exception as e:
            logger.error(f"Errore nello svuotamento dell'archivio: {e}")
            embed = discord.Embed(
                title="❌ Errore",
                description=f"Errore durante lo svuotamento dell'archivio: {str(e)[:1000]}",
                color=0xFF0000
            )
            if log_channel and log_channel.permissions_for(log_channel.guild.me).send_messages:
                await log_channel.send(f"❌ **Errore svuotamento archivio**: {str(e)[:1000]}")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="manage-user-stats", description="Aggiunge o rimuove punti/reputazione a un utente")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_any_role(FOUNDER_ROLE_ID, ADMIN_ROLE_ID)
    @app_commands.describe(
        user="Utente a cui modificare le statistiche",
        points="Punti da aggiungere (positivo) o rimuovere (negativo)",
        reputation="Reputazione da aggiungere (positivo) o rimuovere (negativo)"
    )
    async def manage_user_stats(self, interaction: discord.Interaction, user: discord.User, points: int = 0, reputation: int = 0):
        locale = str(interaction.locale)
        log_channel = self.bot.get_channel(LOG_CHANNEL_ID)

        # Verifica se l'utente sta cercando di modificare se stesso
        if user.id == interaction.user.id:
            embed = discord.Embed(
                title="❌ Errore",
                description=get_translation('manage_user_stats_self_error', locale),
                color=0xFF0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            if log_channel and log_channel.permissions_for(interaction.guild.me).send_messages:
                await log_channel.send(f"❌ **Errore modifica statistiche**: {interaction.user.mention} ha tentato di modificare le proprie statistiche.")
            return

        try:
            # Verifica se l'utente esiste nel database
            c.execute('SELECT points, reputation, participations FROM users WHERE user_id = ?', (user.id,))
            user_data = c.fetchone()

            if not user_data:
                # Crea un nuovo record per l'utente se non esiste
                c.execute('INSERT INTO users (user_id, points, reputation, participations, badges) VALUES (?, ?, ?, ?, ?)',
                          (user.id, 0, 0, 0, ''))
                conn.commit()
                logger.info(f"Creato nuovo record utente per {user.name} ({user.id})")
                user_data = (0, 0, 0)

            # Calcola punti settimanali
            week_start, week_end = get_week_boundaries()
            c.execute('''
                SELECT SUM(points_earned) FROM weekly_events
                WHERE user_id = ? AND timestamp >= ? AND timestamp < ? AND archived = 0
            ''', (user.id, week_start.isoformat(), week_end.isoformat()))
            weekly_points = c.fetchone()[0] or 0

            # Aggiorna punti e reputazione
            new_points = max(0, user_data[0] + points)
            new_reputation = max(0, user_data[1] + reputation)
            new_weekly_points = max(0, weekly_points + points)

            c.execute('UPDATE users SET points = ?, reputation = ? WHERE user_id = ?',
                      (new_points, new_reputation, user.id))
            conn.commit()

            # Registra l'evento settimanale
            if points != 0:
                record_weekly_event(
                    user_id=user.id,
                    event_type='staff_adjusted_points',
                    points=points,
                    message_id=None
                )
            if reputation != 0:
                record_weekly_event(
                    user_id=user.id,
                    event_type='staff_adjusted_reputation',
                    reputation=reputation,
                    message_id=None
                )

            # Crea l'embed di risposta
            embed = discord.Embed(
                title=get_translation('manage_user_stats_success_title', locale),
                color=0x00FF00
            )
            embed.add_field(
                name="Utente modificato",
                value=user.mention,
                inline=True
            )
            embed.add_field(
                name="Modifiche",
                value=f"Punti: {points:+}\nReputazione: {reputation:+}",
                inline=True
            )
            embed.add_field(
                name="Valori aggiornati",
                value=f"Settimanali: {new_weekly_points} punti\nTotali: {new_points} punti, {new_reputation} reputazione",
                inline=True
            )

            # Log dell'azione
            logger.info(f"Modifica statistiche: {interaction.user.name} ha modificato {user.name} ({user.id}): {points} punti, {reputation} reputazione")
            if log_channel and log_channel.permissions_for(interaction.guild.me).send_messages:
                await log_channel.send(f"📝 **Modifica statistiche**: {interaction.user.mention} ha modificato {user.mention}: {points:+} punti, {reputation:+} reputazione (Settimanali: {new_weekly_points} pts, Totali: {new_points} pts, {new_reputation} rep)")

        except Exception as e:
            logger.error(f"Errore nella modifica delle statistiche per {user.name}: {e}")
            embed = discord.Embed(
                title="❌ Errore",
                description=f"Errore durante la modifica delle statistiche: {str(e)[:1000]}",
                color=0xFF0000
            )
            if log_channel and log_channel.permissions_for(interaction.guild.me).send_messages:
                await log_channel.send(f"❌ **Errore modifica statistiche**: {user.mention}: {str(e)[:1000]}")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @tasks.loop(minutes=5)
    async def keep_alive_task(self):
        try:
            self.bot.bot_status['uptime'] = (datetime.now() - self.bot.bot_status['start_time']).total_seconds()
            logger.info(f"Keep-alive ping - Bot attivo da {self.bot.bot_status['uptime']//3600:.0f}h { (self.bot.bot_status['uptime']%3600)//60:.0f}m")
        except Exception as e:
            logger.error(f"Errore nel keep-alive task: {e}")

    @keep_alive_task.before_loop
    async def before_keep_alive(self):
        await self.bot.wait_until_ready()
        logger.info("💓 Keep-alive task pronto")

    @tasks.loop(minutes=15)
    async def status_updater(self):
        try:
            uptime_hours = (datetime.now() - self.bot.bot_status['start_time']).total_seconds() // 3600
            await self.bot.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.watching, 
                    name=f"TrendDuel | Uptime: {uptime_hours:.0f}h"
                ),
                status=discord.Status.online
            )
            logger.info(f"Status aggiornato - Uptime: {uptime_hours:.0f}h")
        except Exception as e:
            logger.error(f"Errore nell'aggiornamento status: {e}")

    @status_updater.before_loop
    async def before_status(self):
        await self.bot.wait_until_ready()
        logger.info("📊 Status updater pronto")

    @commands.Cog.listener()
    async def on_cog_load(self):
        if not self.cleanup_task.is_running():
            self.cleanup_task.start()
        if not self.keep_alive_task.is_running():
            self.keep_alive_task.start()
        if not self.status_updater.is_running():
            self.status_updater.start()
        if not self.check_weekly_leaderboard.is_running():
            self.check_weekly_leaderboard.start()
            logger.info("🕵️ Task check_weekly_leaderboard avviato")

async def setup(bot):
    await bot.add_cog(Admin(bot))