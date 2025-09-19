import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
import logging
import os
import json
from config import LEADERBOARD_CHANNEL_ID, LOG_CHANNEL_ID, FOUNDER_ROLE_ID, ADMIN_ROLE_ID, ITALY_TZ
from database import get_weekly_leaderboard, reset_weekly_metrics
from utils import get_week_boundaries, create_leaderboard_embed, archive_leaderboard
from translations import get_translation

logger = logging.getLogger(__name__)

class Leaderboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.last_action = {"type": "nessuna", "timestamp": None}
        logger.debug("🧪 Inizializzazione cog Leaderboard")

    @tasks.loop(minutes=1)
    async def weekly_leaderboard(self):
        try:
            now = datetime.now(ITALY_TZ)
            logger.debug(f"📅 Controllo pubblicazione classifica - Ora: {now.strftime('%Y-%m-%d %H:%M:%S %Z')} (UTC: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')})")
            if now.weekday() == 6 and now.hour == 20 and now.minute == 0 and now.second < 30:  # Domenica 20:00:00–20:00:30
                logger.info("🕐 Orario pubblicazione classifica raggiunto - avvio processo...")
                log_channel = self.bot.get_channel(LOG_CHANNEL_ID)
                if not log_channel:
                    logger.error(f"Canale mod-logs non trovato: {LOG_CHANNEL_ID}")
                    return

                today_key = now.strftime("%Y-%m-%d-20")
                lock_file = f"leaderboard_published_{today_key}.lock"
                if os.path.exists(lock_file):
                    try:
                        with open(lock_file, 'r') as f:
                            lock_timestamp = datetime.fromisoformat(f.read())
                        if (now - lock_timestamp).total_seconds() < 24 * 3600:
                            logger.info("⚠️ Classifica già pubblicata oggi - skip")
                            if log_channel.permissions_for(log_channel.guild.me).send_messages:
                                await log_channel.send("⚠️ Classifica già pubblicata oggi - skip")
                            return
                        else:
                            logger.info("🗑️ Rimosso file di lock obsoleto")
                            os.remove(lock_file)
                    except Exception as e:
                        logger.error(f"Errore nella lettura del file di lock {lock_file}: {e}")
                        os.remove(lock_file)

                with open(lock_file, 'w') as f:
                    f.write(now.isoformat())

                try:
                    # Archiviazione ed eliminazione della classifica precedente
                    leaderboard_channel = self.bot.get_channel(LEADERBOARD_CHANNEL_ID)
                    if not leaderboard_channel:
                        logger.error(f"Canale leaderboard non trovato: {LEADERBOARD_CHANNEL_ID}")
                        if log_channel.permissions_for(log_channel.guild.me).send_messages:
                            await log_channel.send(f"❌ Canale leaderboard non trovato: {LEADERBOARD_CHANNEL_ID}")
                        return

                    week_start, week_end = get_week_boundaries()
                    async for message in leaderboard_channel.history(limit=10):
                        if message.author == self.bot.user and message.embeds and "Leaderboard Settimanale" in message.embeds[0].title and "TEST" not in message.embeds[0].title:
                            logger.info("📚 Archiviazione classifica precedente...")
                            if log_channel.permissions_for(log_channel.guild.me).send_messages:
                                await log_channel.send("📚 Archiviazione classifica precedente...")
                            try:
                                await archive_leaderboard(
                                    self.bot,
                                    message.embeds[0],
                                    week_start - timedelta(days=7),
                                    week_start,
                                    len(get_weekly_leaderboard(week_start - timedelta(days=7), week_start))
                                )
                                logger.info("✅ Classifica precedente archiviata con successo")
                                if log_channel.permissions_for(log_channel.guild.me).send_messages:
                                    await log_channel.send("✅ Classifica precedente archiviata con successo")
                                self.last_action = {"type": "archiviazione", "timestamp": now.isoformat()}

                                if leaderboard_channel.permissions_for(leaderboard_channel.guild.me).manage_messages:
                                    await message.delete()
                                    logger.info("🗑️ Messaggio classifica precedente eliminato dal canale leaderboard")
                                    if log_channel.permissions_for(log_channel.guild.me).send_messages:
                                        await log_channel.send("🗑️ Messaggio classifica precedente eliminato dal canale leaderboard")
                                    self.last_action = {"type": "eliminazione", "timestamp": now.isoformat()}
                                else:
                                    logger.error("Permessi insufficienti per eliminare il messaggio nel canale leaderboard")
                                    if log_channel.permissions_for(log_channel.guild.me).send_messages:
                                        await log_channel.send("❌ Permessi insufficienti per eliminare il messaggio nel canale leaderboard")
                            except Exception as e:
                                logger.error(f"Errore nell'archiviazione o eliminazione: {e}")
                                if log_channel.permissions_for(log_channel.guild.me).send_messages:
                                    await log_channel.send(f"❌ Errore nell'archiviazione o eliminazione: {str(e)[:1000]}")
                            break

                    # Pubblicazione nuova classifica
                    await self.publish_weekly_leaderboard(is_automatic=True)
                    logger.info("✅ Classifica pubblicata con successo")
                    self.last_action = {"type": "pubblicazione", "timestamp": now.isoformat()}

                    # Reset dei punti
                    week_start, week_end = get_week_boundaries()
                    affected_rows = reset_weekly_metrics(week_start, week_end)
                    logger.info(f"♻️ Punti settimanali resettati per {week_start.strftime('%d/%m/%Y')} - {week_end.strftime('%d/%m/%Y')}, eventi archiviati: {affected_rows}")
                    if log_channel.permissions_for(log_channel.guild.me).send_messages:
                        await log_channel.send(f"♻️ Punti settimanali resettati per {week_start.strftime('%d/%m/%Y')} - {week_end.strftime('%d/%m/%Y')}, eventi archiviati: {affected_rows}")
                    self.last_action = {"type": "reset", "timestamp": now.isoformat()}

                except Exception as e:
                    if os.path.exists(lock_file):
                        os.remove(lock_file)
                    logger.error(f"Errore nella pubblicazione automatica: {e}")
                    if log_channel.permissions_for(log_channel.guild.me).send_messages:
                        await log_channel.send(f"❌ Errore nella pubblicazione automatica: {str(e)[:1000]}")
                    raise e
            else:
                logger.debug(f"Condizione pubblicazione non soddisfatta - Ora: {now.hour}:{now.minute}, Giorno: {now.weekday()}")
        except Exception as e:
            logger.error(f"Errore nel task classifica settimanale: {e}")
            log_channel = self.bot.get_channel(LOG_CHANNEL_ID)
            if log_channel and log_channel.permissions_for(log_channel.guild.me).send_messages:
                await log_channel.send(f"❌ Errore task classifica settimanale: {str(e)[:1000]}")

    @tasks.loop(hours=72)  # Ogni 3 giorni
    async def status_update(self):
        try:
            now = datetime.now(ITALY_TZ)
            logger.info(f"📢 Invio aggiornamento stato - Ora: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            log_channel = self.bot.get_channel(LOG_CHANNEL_ID)
            if not log_channel:
                logger.error(f"Canale mod-logs non trovato: {LOG_CHANNEL_ID}")
                return

            # Calcola la prossima domenica alle 20:00
            days_until_sunday = (6 - now.weekday()) % 7
            next_sunday = (now + timedelta(days=days_until_sunday)).replace(hour=20, minute=0, second=0, microsecond=0)
            if now.weekday() == 6 and now.hour >= 20:
                next_sunday += timedelta(days=7)

            # Messaggio di aggiornamento
            status = "in esecuzione" if self.weekly_leaderboard.is_running() else "non in esecuzione"
            last_action_text = f"{self.last_action['type'].capitalize()} alle {datetime.fromisoformat(self.last_action['timestamp']).strftime('%d/%m/%Y %H:%M:%S %Z')}" if self.last_action['timestamp'] else "Nessuna azione recente"
            embed = discord.Embed(
                title="📢 Aggiornamento Stato Leaderboard",
                description=(
                    f"**Stato Task:** {status}\n"
                    f"**Ora Corrente:** {now.strftime('%d/%m/%Y %H:%M:%S %Z')}\n"
                    f"**Ultima Azione:** {last_action_text}\n"
                    f"**Prossima Pubblicazione:** {next_sunday.strftime('%d/%m/%Y alle 20:00 %Z')}"
                ),
                color=0x00FFFF
            )
            if log_channel.permissions_for(log_channel.guild.me).send_messages:
                await log_channel.send(embed=embed)
            logger.info("📢 Aggiornamento stato inviato con successo")
        except Exception as e:
            logger.error(f"Errore nell'aggiornamento stato: {e}")
            log_channel = self.bot.get_channel(LOG_CHANNEL_ID)
            if log_channel and log_channel.permissions_for(log_channel.guild.me).send_messages:
                await log_channel.send(f"❌ Errore nell'aggiornamento stato: {str(e)[:1000]}")

    async def publish_weekly_leaderboard(self, is_automatic=True, custom_week=None, is_test=False):
        try:
            log_channel = self.bot.get_channel(LOG_CHANNEL_ID)
            leaderboard_channel = self.bot.get_channel(LEADERBOARD_CHANNEL_ID)
            if not leaderboard_channel:
                logger.error(f"Canale leaderboard non trovato: {LEADERBOARD_CHANNEL_ID}")
                if log_channel and log_channel.permissions_for(log_channel.guild.me).send_messages:
                    await log_channel.send(f"❌ Canale leaderboard non trovato: {LEADERBOARD_CHANNEL_ID}")
                return False

            if custom_week:
                week_start, week_end = custom_week
            else:
                week_start, week_end = get_week_boundaries()

            logger.info(f"📊 Generazione classifica per periodo: {week_start} - {week_end}")
            leaderboard_data = get_weekly_leaderboard(week_start, week_end)
            embed, winners = await create_leaderboard_embed(self.bot, leaderboard_data, week_start, week_end, is_test)

            message = await leaderboard_channel.send(embed=embed)
            await message.add_reaction('🎉')

            log_type = "🧪 TEST" if is_test else ("🤖 AUTOMATICA" if is_automatic else "🔧 MANUALE")
            logger.info(f"✅ Classifica pubblicata ({log_type}): messaggio {message.id}")
            if log_channel and log_channel.permissions_for(log_channel.guild.me).send_messages:
                log_embed = discord.Embed(
                    title=f"📊 Classifica Pubblicata ({log_type})",
                    description=f"**Periodo:** {week_start.strftime('%d/%m/%Y')} - {week_end.strftime('%d/%m/%Y')}\n**Messaggio ID:** {message.id}",
                    color=0x00FF00
                )
                await log_channel.send(embed=log_embed)
                if is_automatic and not is_test:
                    self.last_action = {"type": "pubblicazione", "timestamp": datetime.now(ITALY_TZ).isoformat()}

            return True

        except Exception as e:
            logger.error(f"Errore nella pubblicazione: {e}")
            if log_channel and log_channel.permissions_for(log_channel.guild.me).send_messages:
                await log_channel.send(f"❌ Errore pubblicazione classifica: {str(e)[:1000]}")
            return False

    @app_commands.command(name="publish-leaderboard", description="Forza la pubblicazione della classifica settimanale")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_any_role(FOUNDER_ROLE_ID, ADMIN_ROLE_ID)
    async def publish_leaderboard(self, interaction: discord.Interaction):
        locale = str(interaction.locale)
        try:
            success = await self.publish_weekly_leaderboard(is_automatic=False)
            if success:
                week_start, week_end = get_week_boundaries()
                embed = discord.Embed(
                    title=get_translation('publish_leaderboard_success', locale),
                    description=get_translation('publish_leaderboard_success_text', locale).format(
                        week_start=week_start.strftime('%d/%m/%Y'),
                        week_end=week_end.strftime('%d/%m/%Y')
                    ),
                    color=0x00FF00
                )
                self.last_action = {"type": "pubblicazione manuale", "timestamp": datetime.now(ITALY_TZ).isoformat()}
            else:
                embed = discord.Embed(
                    title=get_translation('publish_leaderboard_failed', locale),
                    description=get_translation('publish_leaderboard_failed_text', locale),
                    color=0xFF0000
                )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Errore comando publish-leaderboard: {e}")
            error_embed = discord.Embed(
                title="❌ Errore",
                description=f"Errore durante la pubblicazione: {str(e)[:1000]}",
                color=0xFF0000
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

    @app_commands.command(name="test-leaderboard", description="Genera una classifica di test senza archiviare")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_any_role(FOUNDER_ROLE_ID, ADMIN_ROLE_ID)
    async def test_leaderboard(self, interaction: discord.Interaction):
        locale = str(interaction.locale)
        try:
            week_start, week_end = get_week_boundaries()
            success = await self.publish_weekly_leaderboard(is_automatic=False, is_test=True)
            if success:
                embed = discord.Embed(
                    title="🧪 Test Classifica Pubblicata",
                    description=f"Classifica di test generata per {week_start.strftime('%d/%m/%Y')} - {week_end.strftime('%d/%m/%Y')}",
                    color=0x00FFFF
                )
            else:
                embed = discord.Embed(
                    title="❌ Test Fallito",
                    description="Impossibile generare la classifica di test",
                    color=0xFF0000
                )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Errore comando test-leaderboard: {e}")
            error_embed = discord.Embed(
                title="❌ Errore",
                description=f"Errore durante il test: {str(e)[:1000]}",
                color=0xFF0000
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

    @app_commands.command(name="reset-weekly", description="Reset manuale delle metriche settimanali")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_any_role(FOUNDER_ROLE_ID, ADMIN_ROLE_ID)
    async def reset_weekly(self, interaction: discord.Interaction):
        locale = str(interaction.locale)
        try:
            week_start, week_end = get_week_boundaries()
            affected_rows = reset_weekly_metrics(week_start, week_end)
            embed = discord.Embed(
                title="♻️ Reset Settimanale",
                description=f"Metriche settimanali resettate per {week_start.strftime('%d/%m/%Y')} - {week_end.strftime('%d/%m/%Y')}.\n**Eventi archiviati:** {affected_rows}",
                color=0x00FF00
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

            log_channel = self.bot.get_channel(LOG_CHANNEL_ID)
            if log_channel and log_channel.permissions_for(log_channel.guild.me).send_messages:
                log_embed = discord.Embed(
                    title="♻️ Reset Settimanale Eseguito",
                    description=f"**Eseguito da:** {interaction.user.name}\n**Periodo:** {week_start.strftime('%d/%m/%Y')} - {week_end.strftime('%d/%m/%Y')}\n**Eventi archiviati:** {affected_rows}",
                    color=0x00FF00
                )
                await log_channel.send(embed=log_embed)
                self.last_action = {"type": "reset manuale", "timestamp": datetime.now(ITALY_TZ).isoformat()}

        except Exception as e:
            logger.error(f"Errore comando reset-weekly: {e}")
            error_embed = discord.Embed(
                title="❌ Errore",
                description=f"Errore durante il reset: {str(e)[:1000]}",
                color=0xFF0000
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

    @app_commands.command(name="get-leaderboard", description="Visualizza una classifica archiviata")
    @app_commands.describe(settimana="ID della classifica o 'lista' per l'elenco")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_any_role(FOUNDER_ROLE_ID, ADMIN_ROLE_ID)
    async def get_leaderboard(self, interaction: discord.Interaction, settimana: str):
        locale = str(interaction.locale)
        from database import c
        await interaction.response.defer(ephemeral=True)

        try:
            if settimana.lower() == "lista":
                c.execute('''SELECT id, week_start, week_end, participants_count, archived_at 
                             FROM weekly_archives ORDER BY week_start DESC LIMIT 20''')
                archives = c.fetchall()

                if not archives:
                    embed = discord.Embed(
                        title="📚 Archivi Classifiche",
                        description="Nessun archivio disponibile.",
                        color=0xFF9900
                    )
                else:
                    embed = discord.Embed(
                        title="📚 Archivi Classifiche Disponibili",
                        description="Ultimi 20 archivi salvati:",
                        color=0x800080
                    )

                    archive_list = ""
                    for archive_id, week_start, week_end, participants, archived_at in archives:
                        start_date = datetime.fromisoformat(week_start).strftime("%d/%m")
                        end_date = datetime.fromisoformat(week_end).strftime("%d/%m/%Y")
                        archive_date = datetime.fromisoformat(archived_at).strftime("%d/%m/%Y")
                        archive_list += f"**ID {archive_id}:** {start_date}-{end_date} ({participants} partecipanti) - {archive_date}\n"

                    embed.add_field(
                        name="📋 Lista Archivi",
                        value=archive_list,
                        inline=False
                    )
                    embed.add_field(
                        name="💡 Come usare",
                        value="Usa `/get-leaderboard <ID>` per visualizzare un archivio specifico",
                        inline=False
                    )
            else:
                try:
                    archive_id = int(settimana)
                    c.execute('''SELECT week_start, week_end, embed_data, participants_count, archived_at, hall_of_fame_message_id
                                 FROM weekly_archives WHERE id = ?''', (archive_id,))
                    archive = c.fetchone()

                    if not archive:
                        embed = discord.Embed(
                            title="❌ Archivio Non Trovato",
                            description=f"Nessun archivio trovato con ID {archive_id}",
                            color=0xFF0000
                        )
                        embed.add_field(
                            name="💡 Suggerimento",
                            value="Usa `/get-leaderboard lista` per vedere gli archivi disponibili",
                            inline=False
                        )
                    else:
                        week_start, week_end, embed_data, participants, archived_at, hof_msg_id = archive
                        embed_dict = json.loads(embed_data)
                        embed = discord.Embed(
                            title=f"📚 {embed_dict['title']} (Archivio)",
                            description=embed_dict.get('description', ''),
                            color=0x800080
                        )

                        for field in embed_dict.get('fields', []):
                            embed.add_field(
                                name=field['name'],
                                value=field['value'],
                                inline=field.get('inline', False)
                            )

                        embed.add_field(
                            name="📚 Info Archivio",
                            value=f"**ID:** {archive_id}\n**Archiviato:** {datetime.fromisoformat(archived_at).strftime('%d/%m/%Y alle %H:%M')}\n**Partecipanti:** {participants}",
                            inline=False
                        )

                        from config import HALL_OF_FAME_CHANNEL_ID
                        if hof_msg_id:
                            embed.add_field(
                                name="🔗 Hall of Fame",
                                value=f"[Messaggio #{hof_msg_id}](https://discord.com/channels/{interaction.guild_id}/{HALL_OF_FAME_CHANNEL_ID}/{hof_msg_id})",
                                inline=True
                            )

                except ValueError:
                    embed = discord.Embed(
                        title="❌ Formato Non Valido",
                        description="Inserisci un ID numerico valido o 'lista'",
                        color=0xFF0000
                    )
                    embed.add_field(
                        name="📖 Esempi",
                        value="`/get-leaderboard 1` - Visualizza archivio ID 1\n`/get-leaderboard lista` - Mostra tutti gli archivi",
                        inline=False
                    )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Errore comando get-leaderboard: {e}")
            error_embed = discord.Embed(
                title="❌ Errore",
                description=f"Errore durante il recupero dell'archivio: {str(e)[:1000]}",
                color=0xFF0000
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_ready(self):
        try:
            logger.info("🧪 Evento on_ready per cog Leaderboard")
            log_channel = self.bot.get_channel(LOG_CHANNEL_ID)

            if not self.weekly_leaderboard.is_running():
                self.weekly_leaderboard.start()
                logger.info("📊 Task weekly_leaderboard avviato con successo")
                if log_channel and log_channel.permissions_for(log_channel.guild.me).send_messages:
                    await log_channel.send("📊 Task weekly_leaderboard avviato con successo")
            else:
                logger.info("📊 Task weekly_leaderboard già in esecuzione")
                if log_channel and log_channel.permissions_for(log_channel.guild.me).send_messages:
                    await log_channel.send("📊 Task weekly_leaderboard già in esecuzione")

            if not self.status_update.is_running():
                self.status_update.start()
                logger.info("📢 Task status_update avviato con successo")
                if log_channel and log_channel.permissions_for(log_channel.guild.me).send_messages:
                    await log_channel.send("📢 Task status_update avviato con successo")
            else:
                logger.info("📢 Task status_update già in esecuzione")
                if log_channel and log_channel.permissions_for(log_channel.guild.me).send_messages:
                    await log_channel.send("📢 Task status_update già in esecuzione")

        except Exception as e:
            logger.error(f"Errore in on_ready: {e}")
            log_channel = self.bot.get_channel(LOG_CHANNEL_ID)
            if log_channel and log_channel.permissions_for(log_channel.guild.me).send_messages:
                await log_channel.send(f"❌ Errore in on_ready: {str(e)[:1000]}")

async def setup(bot):
    logger.debug("🧪 Setup cog Leaderboard")
    await bot.add_cog(Leaderboard(bot))