# spotlight.py (aggiornato)
import discord
from discord.ext import commands, tasks
import random
from datetime import datetime, timedelta, time as dt_time
import logging
import asyncio
import re
from config import SUBMISSIONS_CHANNEL_ID, SPOTLIGHT_CHANNEL_ID, SPOTLIGHT_ARCHIVE_CHANNEL_ID, LOG_CHANNEL_ID, ITALY_TZ, BONUS_POINTS_WEIGHTS, BONUS_REPUTATION_WEIGHTS, FOUNDER_ROLE_ID, ADMIN_ROLE_ID, VIP_ROLE_ID, CHALLENGER_ROLE_ID
from database import record_weekly_event, c, conn
from translations import get_translation
from utils import get_week_boundaries

logger = logging.getLogger(__name__)

class Spotlight(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.repost_cache = set()  # Cache per evitare repost duplicati nella settimana (message.id)
        self.daily_repost_count = 0  # Contatore giornaliero
        self.last_repost_date = None  # Data dell'ultimo repost (data locale IT)
        self.last_slot_datetime = None  # datetime dello slot eseguito per evitare ripetizioni
        # Nota: last_slot_datetime è in timezone ITALY_TZ

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.repost_to_spotlight.is_running():
            self.repost_to_spotlight.start()
            logger.info("📢 Task repost_to_spotlight avviato in on_ready")
        if not self.weekly_spotlight_cleanup.is_running():
            self.weekly_spotlight_cleanup.start()
            logger.info("🗑️ Task weekly_spotlight_cleanup avviato in on_ready")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignora i messaggi del bot
        if message.author.bot:
            return

        # Controlla solo il canale spotlight
        if message.channel.id != SPOTLIGHT_CHANNEL_ID:
            return

        # Regex per qualsiasi URL
        url_pattern = r'https?://\S+'
        if re.search(url_pattern, message.content):
            try:
                await message.delete()
                log_channel = self.bot.get_channel(LOG_CHANNEL_ID)
                if log_channel:
                    await log_channel.send(
                        f"🗑️ Messaggio con link rimosso in #⚡-spotlight da {message.author.mention}"
                    )
            except discord.Forbidden:
                logger.warning(f"Permessi insufficienti per eliminare messaggio di {message.author.name} in spotlight")
            except Exception as e:
                logger.error(f"Errore nell'eliminare messaggio con link in spotlight: {e}")

    # ---------- SCHEDULING HELPERS ----------
    def get_season(self, dt: datetime):
        """Ritorna 'spring','summer','autumn','winter' basato sul mese.
        Nota: mappatura standard:
          - Mar-Apr-Mag => spring
          - Jun-Jul-Aug => summer
          - Sep-Oct-Nov => autumn
          - Dec-Jan-Feb => winter
        """
        m = dt.month
        if m in (3, 4, 5):
            return 'spring'
        if m in (6, 7, 8):
            return 'summer'
        if m in (9, 10, 11):
            return 'autumn'
        return 'winter'

    def time_tuples(self, hh_mm_list):
        """Convert list of strings 'HH:MM' to list of (hour, minute) tuples."""
        out = []
        for s in hh_mm_list:
            h, m = map(int, s.split(':'))
            out.append((h, m))
        return out

    def get_schedule_for_date(self, date_dt: datetime):
        """Genera la lista di slot (hour, minute) da eseguire per la data fornita (timezone IT).
        Si applicano:
          - Lunedì: slot specifici serali (5)
          - Mart-Sab e Domenica: slot in base a stagione / sunday sets
        NOTE/ASSUNZIONE SCUOLA:
          - Ho interpretato 'Periodo scolastico: a partire dal 15 settembre' come
            un override per il periodo scuola; per semplicità ho applicato
            lo 'school period' dal 15 settembre fino al 30 giugno (incluso).
            Se vuoi un periodo diverso, posso cambiarlo.
        """
        weekday = date_dt.weekday()  # Mon=0 .. Sun=6
        season = self.get_season(date_dt)
        day = date_dt.day
        month = date_dt.month
        year = date_dt.year

        # Converti orari in string lists per chiarezza
        monday_slots = ['18:30', '19:30', '20:30', '21:30', '22:30']  # Lunedì: solo 5

        # School period definition (assunzione): dal 15 Settembre fino al 30 Giugno
        in_school_period = False
        school_start = datetime(year, 9, 15, tzinfo=ITALY_TZ)
        # school end = 30 June next year if date between Sep-Dec; else if date Jan-Jun treat as in range
        # Per semplicità: se la data è >= Sep 15 dello stesso anno OR <= June 30 dello stesso anno
        if date_dt >= school_start:
            in_school_period = True
        else:
            # se siamo nei mesi Jan-Jun e la data <= June 30 dello stesso anno
            if month in (1,2,3,4,5,6):
                in_school_period = True

        # Orari per Mart-Sab (school / normal) e per stagioni
        school_tues_sat = ['07:30', '09:30', '12:30', '15:30', '17:00', '18:30', '19:30', '20:30', '22:00', '23:00']

        summer_tues_sat = ['09:30', '11:30', '13:30', '15:30', '17:30', '19:00', '20:30', '22:00', '23:00', '23:45']
        spring_tues_sat = ['07:30', '10:00', '12:30', '15:00', '17:00', '18:30', '19:30', '20:30', '22:00', '23:00']
        autumn_tues_sat = ['07:30', '09:30', '12:30', '15:30', '17:30', '18:30', '19:30', '20:30', '21:30', '22:30']
        winter_tues_sat = ['08:00', '11:30', '13:00', '15:30', '17:00', '18:30', '19:30', '20:30', '21:30', '22:30']

        # Sunday per season
        sunday_summer = ['10:00', '12:00', '14:30', '16:30', '17:30', '18:00']
        sunday_spring = ['09:00', '11:00', '13:00', '15:30', '17:00', '18:00']
        sunday_autumn = ['09:30', '11:30', '13:30', '15:30', '17:00', '18:00']
        sunday_winter = ['10:00', '12:00', '14:00', '15:30', '17:00', '18:00']
        sunday_school = ['09:30', '11:30', '13:30', '15:30', '17:00', '18:00']  # default sunday in school period (matches autumn)

        schedule = []

        if weekday == 0:  # Lunedì
            schedule = monday_slots
        elif weekday == 6:  # Domenica
            # Domenica: scegli in base a season (o school)
            if in_school_period:
                schedule = sunday_school
            else:
                if season == 'summer':
                    schedule = sunday_summer
                elif season == 'spring':
                    schedule = sunday_spring
                elif season == 'autumn':
                    schedule = sunday_autumn
                else:
                    schedule = sunday_winter
        else:
            # Martedì-Sabato
            if in_school_period:
                schedule = school_tues_sat
            else:
                if season == 'summer':
                    schedule = summer_tues_sat
                elif season == 'spring':
                    schedule = spring_tues_sat
                elif season == 'autumn':
                    schedule = autumn_tues_sat
                else:
                    schedule = winter_tues_sat

        return self.time_tuples(schedule)

    # ---------- REPOST TASK ----------
    @tasks.loop(seconds=20)
    async def repost_to_spotlight(self):
        """Questo task controlla ogni 20s se l'orario corrente corrisponde a uno slot di repost.
           Se sì, esegue esattamente 1 repost per quello slot (se disponibili messaggi validi)
        """
        try:
            if not self.bot.is_ready():
                logger.debug("Bot non pronto, skip repost_to_spotlight")
                return

            now = datetime.now(ITALY_TZ)
            logger.debug(f"Controllo repost - ora IT: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")

            # Reset contatore giornaliero se nuovo giorno (ora IT)
            if self.last_repost_date is None or self.last_repost_date != now.date():
                self.daily_repost_count = 0
                self.last_repost_date = now.date()
                logger.info("Nuovo giorno rilevato: reset contatore repost giornaliero")

            # Determina la schedule di oggi e il limite giornaliero
            today_slots = self.get_schedule_for_date(now)
            weekday = now.weekday()  # Mon=0..Sun=6
            if weekday == 0:
                day_limit = 5
            elif weekday == 6:
                day_limit = 6
            else:
                day_limit = 10

            # Se limite giornaliero già raggiunto, non fare nulla oggi
            if self.daily_repost_count >= day_limit:
                logger.debug(f"Limite giornaliero per oggi ({self.daily_repost_count}/{day_limit}) raggiunto. Skip.")
                return

            # Controlla se ora corrente corrisponde ad uno slot (hour, minute)
            current_hm = (now.hour, now.minute)
            if current_hm not in today_slots:
                # non è uno slot programmato
                return

            # Evita esecuzione ripetuta nello stesso slot (possibile se il loop viene eseguito piu volte nello stesso minuto)
            # Consideriamo last_slot_datetime già eseguito se coincide con la stessa data e stesso slot (hour+minute)
            if self.last_slot_datetime and self.last_slot_datetime.astimezone(ITALY_TZ).date() == now.date():
                if (self.last_slot_datetime.hour, self.last_slot_datetime.minute) == current_hm:
                    logger.debug("Questo slot è già stato eseguito in questo minuto, skip per evitare duplicate.")
                    return

            # --- Se arrivati qui, è il momento di fare un repost per questo slot ---
            submissions_channel = self.bot.get_channel(SUBMISSIONS_CHANNEL_ID)
            spotlight_channel = self.bot.get_channel(SPOTLIGHT_CHANNEL_ID)
            log_channel = self.bot.get_channel(LOG_CHANNEL_ID)

            if not submissions_channel or not spotlight_channel:
                logger.error("Canale submissions o spotlight non trovato")
                if log_channel:
                    await log_channel.send("❌ Errore: Canale submissions o spotlight non trovato per repost programmato.")
                return

            # Ottieni messaggi validi della settimana corrente
            week_start, week_end = get_week_boundaries()
            valid_messages = []

            # Raccogli utenti già repostati questa settimana (per il vincolo '1 repost a settimana per utente')
            c.execute('SELECT user_id FROM spotlight_reposts WHERE week_start = ?', (week_start.isoformat(),))
            reposted_users_rows = c.fetchall()
            reposted_users_this_week = set(r[0] for r in reposted_users_rows) if reposted_users_rows else set()

            async for message in submissions_channel.history(limit=500):
                # condizioni: hashtag, link a social, entro la settimana, non repostato prima (cache) e autore non abbia già repost in settimana
                content = (message.content or "").lower()
                has_hashtag = any(hashtag in content for hashtag in ['#trendduelofficial', '#trendduelchallenge'])
                has_valid_link = any(domain in content for domain in ['instagram.com', 'tiktok.com', 'youtube.com'])
                # message.created_at è UTC naive/aware: convertire in timezone IT
                try:
                    created_local = message.created_at.astimezone(ITALY_TZ)
                except Exception:
                    # fallback: assume naive UTC and replace tzinfo
                    created_local = message.created_at.replace(tzinfo=ITALY_TZ)

                is_within_week = created_local >= week_start
                is_not_in_cache = message.id not in self.repost_cache
                author_not_reposted_this_week = message.author.id not in reposted_users_this_week

                if has_hashtag and has_valid_link and is_within_week and is_not_in_cache and author_not_reposted_this_week:
                    valid_messages.append(message)

            if not valid_messages:
                logger.info("Nessun messaggio valido disponibile per questo slot.")
                if log_channel:
                    await log_channel.send("⚠️ Nessun messaggio valido disponibile per il repost programmato in #📝-submissions.")
                # Aggiorniamo last_slot_datetime comunque per evitare ripetizioni nello stesso minuto
                self.last_slot_datetime = now
                return

            # Seleziona un messaggio (random)
            random.shuffle(valid_messages)
            selected_message = valid_messages[0]

            # --- ASSEGNA BONUS CASUALE (come nella logica originale) ---
            user_id = selected_message.author.id
            bonus_type = random.choice(['points', 'reputation'])

            if bonus_type == 'points':
                amounts = [3, 4, 5, 6, 7]
                weights = [0.35, 0.35, 0.1, 0.1, 0.1]
                bonus = random.choices(amounts, weights=weights)[0]
                c.execute('UPDATE users SET points = points + ? WHERE user_id = ?', (bonus, user_id))
                record_weekly_event(user_id, 'spotlight_bonus_points', points=bonus, message_id=selected_message.id)
                if log_channel:
                    await log_channel.send(f"🎁 Bonus punti spotlight: +{bonus} a {selected_message.author.mention}")
            else:
                amounts = [1, 2, 3, 4, 5]
                weights = [0.35, 0.35, 0.1, 0.1, 0.1]
                bonus = random.choices(amounts, weights=weights)[0]
                c.execute('UPDATE users SET reputation = reputation + ? WHERE user_id = ?', (bonus, user_id))
                record_weekly_event(user_id, 'spotlight_bonus_reputation', reputation=bonus, message_id=selected_message.id)
                if log_channel:
                    await log_channel.send(f"🎁 Bonus reputazione spotlight: +{bonus} a {selected_message.author.mention}")

            conn.commit()

            # --- COSTRUISCI EMBED SPOTLIGHT ---
            embed = discord.Embed(
                title="⚡ TrendDuel Spotlight",
                description=f"{selected_message.content}\n\n✨ Lanciata da {selected_message.author.mention}",
                color=discord.Color.from_rgb(138, 43, 226),
                timestamp=datetime.now(ITALY_TZ)
            )

            roles = [r for r in selected_message.author.roles if r.name not in ["@everyone"]]
            main_role = roles[-1].name if roles else "Challenger"

            embed.set_author(
                name=f"{selected_message.author.display_name} · {main_role}",
                icon_url=selected_message.author.display_avatar.url
            )

            embed.set_footer(text="🔥 Challenge the world, conquer the hype.")

            if bonus_type == 'points':
                embed.add_field(name="🎁 Bonus ottenuto", value=f"+{bonus} punti 💎", inline=False)
            else:
                embed.add_field(name="🎁 Bonus ottenuto", value=f"+{bonus} reputazione 🌟", inline=False)

            # Invia l’embed nel canale spotlight
            repost_message = await spotlight_channel.send(embed=embed)

            # Salva nel database
            now_iso = now.isoformat()
            c.execute(
                '''INSERT INTO spotlight_reposts 
                   (original_message_id, spotlight_message_id, user_id, week_start, timestamp)
                   VALUES (?, ?, ?, ?, ?)''',
                (selected_message.id, repost_message.id, selected_message.author.id,
                 week_start.isoformat(), now_iso)
            )
            conn.commit()

            # Aggiorna cache, contatori e last_slot_datetime
            self.repost_cache.add(selected_message.id)
            self.daily_repost_count += 1
            self.last_slot_datetime = now

            logger.info(f"Repost effettuato (slot): {selected_message.id} -> {repost_message.id} | Count oggi: {self.daily_repost_count}/{day_limit}")

        except Exception as e:
            logger.exception(f"Errore in repost_to_spotlight: {e}")
            log_channel = self.bot.get_channel(LOG_CHANNEL_ID)
            if log_channel:
                await log_channel.send(f"❌ Errore repost spotlight: {str(e)[:1000]}")

    # ---------- WEEKLY CLEANUP (archiviazione) ----------
    @tasks.loop(minutes=1)
    async def weekly_spotlight_cleanup(self):
        try:
            now = datetime.now(ITALY_TZ)
            logger.debug(f"🗑️ Controllo cleanup spotlight - Ora: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")

            # Condizione regolare: Domenica 20:00 (ora italiana)
            is_regular = now.weekday() == 6 and now.hour == 20 and now.minute == 0

            # Condizione test: (lasciata per compatibilità con testing)
            is_test = (
                now.year == 2025 and now.month == 9 and now.day == 12
                and now.hour == 12 and now.minute == 50
            )

            if is_test or is_regular:
                logger.warning("🚀 Avvio archiviazione spotlight (condizione test o regolare attivata)")

                spotlight_channel = self.bot.get_channel(SPOTLIGHT_CHANNEL_ID)
                archive_channel = self.bot.get_channel(SPOTLIGHT_ARCHIVE_CHANNEL_ID)
                log_channel = self.bot.get_channel(LOG_CHANNEL_ID)

                if not spotlight_channel or not archive_channel:
                    logger.error("Canali spotlight o archive non trovati")
                    if log_channel:
                        await log_channel.send("❌ Canali spotlight o archive non trovati")
                    return

                messages_archived = 0
                async for message in spotlight_channel.history(limit=None, oldest_first=True):
                    try:
                        if message.content and message.embeds:
                            await archive_channel.send(content=message.content, embeds=message.embeds)
                        elif message.content:
                            await archive_channel.send(content=message.content)
                        elif message.embeds:
                            await archive_channel.send(embeds=message.embeds)
                        else:
                            # Evita errore "Cannot send an empty message"
                            logger.warning(f"Messaggio {message.id} ignorato: nessun contenuto né embed")
                            continue

                        await message.delete()
                        messages_archived += 1
                    except Exception as e:
                        logger.error(f"Errore archiviazione messaggio {message.id}: {e}")

                # Pulisci database e cache
                week_start, _ = get_week_boundaries()
                c.execute('DELETE FROM spotlight_reposts WHERE week_start = ?', (week_start.isoformat(),))
                conn.commit()

                self.repost_cache.clear()
                self.daily_repost_count = 0
                self.last_slot_datetime = None

                logger.info(f"🗑️ Cleanup spotlight completato: {messages_archived} messaggi archiviati")
                if log_channel:
                    await log_channel.send(
                        f"🗑️ Cleanup spotlight completato: {messages_archived} messaggi archiviati in #📦-spotlight-archive"
                    )

        except Exception as e:
            logger.exception(f"Errore in weekly_spotlight_cleanup: {e}")
            log_channel = self.bot.get_channel(LOG_CHANNEL_ID)
            if log_channel:
                await log_channel.send(f"❌ Errore rimozione reazione spotlight: {str(e)[:1000]}")

    @weekly_spotlight_cleanup.before_loop
    async def before_weekly_spotlight_cleanup(self):
        await self.bot.wait_until_ready()
        logger.info("🗑️ Task weekly_spotlight_cleanup pronto")

    # ---------- REACTIONS HANDLERS (invariati - mantenuti dalla versione originale) ----------
    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if reaction.message.channel.id != SPOTLIGHT_CHANNEL_ID or user.bot:
            return

        log_channel = self.bot.get_channel(LOG_CHANNEL_ID)
        try:
            # Ottieni informazioni sul messaggio originale
            c.execute('SELECT original_message_id, user_id FROM spotlight_reposts WHERE spotlight_message_id = ?', 
                      (reaction.message.id,))
            result = c.fetchone()
            if not result:
                logger.debug(f"Nessun repost trovato per messaggio spotlight {reaction.message.id}")
                return

            original_message_id, participant_id = result
            emoji_str = str(reaction.emoji)

            # Verifica emoji valida
            if emoji_str not in ['💯', '👍']:
                return

            # Verifica no self-vote
            if user.id == participant_id:
                try:
                    await reaction.remove(user)
                except Exception:
                    pass
                await user.send(get_translation('duplicate_message', 'en'))
                if log_channel:
                    await log_channel.send(f"⚠️ Tentativo di self-vote da {user.mention} su messaggio {reaction.message.id}")
                return

            # Verifica no doppia reazione sullo stesso repost
            c.execute('SELECT emoji FROM reactions WHERE message_id = ? AND user_id = ?',
                      (reaction.message.id, user.id))
            existing_reaction = c.fetchone()
            if existing_reaction:
                try:
                    await reaction.remove(user)
                except Exception:
                    pass
                await user.send(get_translation('duplicate_reaction_spotlight', 'en'))
                if log_channel:
                    await log_channel.send(f"⚠️ Doppia reazione di {user.mention} su messaggio {reaction.message.id}")
                return

            # Verifica se l'utente ha già reagito al messaggio originale in submissions
            c.execute('SELECT 1 FROM reactions WHERE message_id = ? AND user_id = ? LIMIT 1',
                      (original_message_id, user.id))
            if c.fetchone():
                try:
                    await reaction.remove(user)
                except Exception:
                    pass
                await user.send(get_translation('duplicate_reaction_spotlight', 'en'))
                if log_channel:
                    await log_channel.send(
                        f"🚫 {user.mention} ha già reagito al messaggio originale {original_message_id}, quindi non può reagire anche al repost {reaction.message.id}"
                    )
                return

            # Verifica se l'utente ha già reagito a QUALSIASI repost collegato a questa original_message_id
            c.execute('''
                SELECT 1 FROM reactions r
                JOIN spotlight_reposts s ON r.message_id = s.spotlight_message_id
                WHERE s.original_message_id = ? AND r.user_id = ?
                LIMIT 1
            ''', (original_message_id, user.id))
            if c.fetchone():
                try:
                    await reaction.remove(user)
                except Exception:
                    pass
                await user.send(get_translation('duplicate_reaction_spotlight', 'en'))
                if log_channel:
                    await log_channel.send(
                        f"🚫 {user.mention} ha già reagito a un repost collegato al messaggio {original_message_id}, non può reagire a un altro repost."
                    )
                return

            # Recupera il Member per controllare ruoli in modo sicuro
            guild = reaction.message.guild
            member = None
            if guild:
                member = guild.get_member(user.id)
                if member is None:
                    try:
                        member = await guild.fetch_member(user.id)
                    except Exception:
                        member = None

            # Determina bonus in base al ruolo (ruolo determina BONUS, non l'emoji)
            is_staff = False
            if member:
                is_staff = any(role.id in [FOUNDER_ROLE_ID, ADMIN_ROLE_ID] for role in member.roles)

            points_to_add = 5 if is_staff else 0
            reputation_to_add = 0 if is_staff else 1

            # Se nessun bonus (es. ruoli particolari), ignora
            if points_to_add == 0 and reputation_to_add == 0:
                try:
                    await reaction.remove(user)
                except Exception:
                    pass
                return

            event_type = 'staff_reaction_spotlight' if is_staff else 'community_reaction_spotlight'

            # Salva participations correnti per prevenire incrementi accidentali da record_weekly_event
            c.execute('SELECT participations FROM users WHERE user_id = ?', (participant_id,))
            row = c.fetchone()
            prev_participations = row[0] if row and row[0] is not None else 0

            # Registra la reazione
            c.execute('INSERT OR REPLACE INTO reactions (message_id, user_id, participant_id, emoji, points_given, reputation_given) VALUES (?, ?, ?, ?, ?, ?)',
                      (reaction.message.id, user.id, participant_id, emoji_str, points_to_add, reputation_to_add))
            c.execute('UPDATE users SET points = points + ?, reputation = reputation + ? WHERE user_id = ?',
                      (points_to_add, reputation_to_add, participant_id))
            conn.commit()

            # Registra evento settimanale (colleghiamo l'evento al messaggio originale)
            try:
                record_weekly_event(participant_id, event_type, points=points_to_add, reputation=reputation_to_add, message_id=original_message_id)
            except Exception as e:
                logger.exception(f"Errore record_weekly_event in spotlight on_reaction_add: {e}")

            # Ripristina participations per essere CERTI che non venga aggiunto +1 partecipation da questa azione
            try:
                c.execute('UPDATE users SET participations = ? WHERE user_id = ?', (prev_participations, participant_id))
                conn.commit()
            except Exception as e:
                logger.exception(f"Errore ripristino participations: {e}")

            # Aggiorna bot status
            try:
                self.bot.bot_status['reactions_processed'] += 1
                self.bot.bot_status['last_activity'] = datetime.now()
            except Exception:
                pass

            # Recupera il vero autore del messaggio originale per il log (non il bot)
            participant_member = guild.get_member(participant_id) if guild else None
            target_mention = participant_member.mention if participant_member else f"<@{participant_id}>"

            if log_channel:
                if is_staff:
                    await log_channel.send(
                        f"✅ Reazione {emoji_str} staff aggiunta da {user.mention}: +{points_to_add} punti a {target_mention}"
                    )
                else:
                    await log_channel.send(
                        f"✅ Reazione {emoji_str} community aggiunta da {user.mention}: +{reputation_to_add} reputazione a {target_mention}"
                    )

        except Exception as e:
            logger.exception(f"Errore in on_reaction_add spotlight: {e}")
            if log_channel:
                await log_channel.send(f"❌ Errore reazione spotlight: {str(e)[:1000]}")

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction, user):
        if reaction.message.channel.id != SPOTLIGHT_CHANNEL_ID or user.bot:
            return

        log_channel = self.bot.get_channel(LOG_CHANNEL_ID)
        try:
            c.execute('SELECT original_message_id, user_id FROM spotlight_reposts WHERE spotlight_message_id = ?', 
                      (reaction.message.id,))
            result = c.fetchone()
            if not result:
                logger.debug(f"Nessun repost trovato per messaggio spotlight {reaction.message.id}")
                return

            original_message_id, participant_id = result
            emoji_str = str(reaction.emoji)

            c.execute('SELECT emoji, points_given, reputation_given FROM reactions WHERE message_id = ? AND user_id = ? AND emoji = ?',
                      (reaction.message.id, user.id, emoji_str))
            existing_reaction = c.fetchone()

            if not existing_reaction:
                logger.debug(f"Rimozione ignorata: {user.name} non aveva una reazione registrata con emoji '{emoji_str}'")
                return

            emoji, points_given, reputation_given = existing_reaction
            c.execute('DELETE FROM reactions WHERE message_id = ? AND user_id = ? AND emoji = ?', 
                      (reaction.message.id, user.id, emoji_str))

            # Salva participations correnti e poi ripristina per evitare incrementi indesiderati
            c.execute('SELECT participations FROM users WHERE user_id = ?', (participant_id,))
            row = c.fetchone()
            prev_participations = row[0] if row and row[0] is not None else 0

            if points_given > 0:
                c.execute('UPDATE users SET points = points - ? WHERE user_id = ?', (points_given, participant_id))
                conn.commit()
                try:
                    record_weekly_event(participant_id, 'reaction_removed_points_spotlight', points=-points_given, message_id=original_message_id)
                except Exception as e:
                    logger.exception(f"Errore record_weekly_event (remove points): {e}")
                # ripristina participations
                c.execute('UPDATE users SET participations = ? WHERE user_id = ?', (prev_participations, participant_id))
                if log_channel:
                    guild = reaction.message.guild
                    participant_member = guild.get_member(participant_id) if guild else None
                    target_mention = participant_member.mention if participant_member else f"<@{participant_id}>"
                    await log_channel.send(f"🔻 Reazione {emoji} rimossa: -{points_given} punti a {target_mention}")

            if reputation_given > 0:
                c.execute('UPDATE users SET reputation = reputation - ? WHERE user_id = ?', (reputation_given, participant_id))
                conn.commit()
                try:
                    record_weekly_event(participant_id, 'reaction_removed_reputation_spotlight', reputation=-reputation_given, message_id=original_message_id)
                except Exception as e:
                    logger.exception(f"Errore record_weekly_event (remove reputation): {e}")
                # ripristina participations
                c.execute('UPDATE users SET participations = ? WHERE user_id = ?', (prev_participations, participant_id))
                if log_channel:
                    guild = reaction.message.guild
                    participant_member = guild.get_member(participant_id) if guild else None
                    target_mention = participant_member.mention if participant_member else f"<@{participant_id}>"
                    await log_channel.send(f"🔻 Reazione {emoji} rimossa: -{reputation_given} reputazione a {target_mention}")

            conn.commit()

        except Exception as e:
            logger.exception(f"Errore in on_reaction_remove spotlight: {e}")
            if log_channel:
                await log_channel.send(f"❌ Errore rimozione reazione spotlight: {str(e)[:1000]}")

async def setup(bot):
    logger.debug("🧪 Setup cog Spotlight")
    await bot.add_cog(Spotlight(bot))
