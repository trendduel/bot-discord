# events.py (aggiornato)
import discord
from discord.ext import commands
from discord import app_commands
import re
from datetime import datetime
import logging
from config import SUBMISSIONS_CHANNEL_ID, LOG_CHANNEL_ID, HASHTAGS, FOUNDER_ROLE_ID, ADMIN_ROLE_ID
from database import record_weekly_event, c, conn, add_submitted_link, link_exists
from translations import get_translation
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

logger = logging.getLogger(__name__)

class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.message_cache = {}  # Cache per tracciare messaggi con link social

    def normalize_message(self, content):
        """Normalizza il contenuto del messaggio per il confronto dei duplicati."""
        normalized = content.lower()
        for hashtag in HASHTAGS:
            normalized = normalized.replace(hashtag.lower(), '')
        return ' '.join(sorted(normalized.split()))

    def extract_url(self, content):
        """Estrae il primo URL valido dal messaggio."""
        url_pattern = r'(https?://(?:www\.)?(?:instagram\.com|tiktok\.com|youtube\.com)[^\s]*)'
        match = re.search(url_pattern, content, re.IGNORECASE)
        return match.group(0) if match else None

    @commands.Cog.listener()
    async def on_ready(self):
        # Ricostruisci cache dei messaggi submissions (utile dopo restart)
        try:
            logger.info("ðŸ“¢ Events on_ready: ricostruzione message_cache dallo storico submissions")
            submissions_channel = self.bot.get_channel(SUBMISSIONS_CHANNEL_ID)
            if not submissions_channel:
                logger.warning("Canale submissions non trovato in on_ready")
                return

            async for message in submissions_channel.history(limit=1000):
                # Ignora bot
                if message.author.bot:
                    continue
                normalized = self.normalize_message(message.content)
                url = self.extract_url(message.content)
                self.message_cache[message.id] = {
                    'user_id': message.author.id,
                    'normalized': normalized,
                    'url': url,
                    'reactions': []  # verrÃ  popolato dalle righe in DB se presenti
                }
            # Popola reazioni esistenti dalla tabella reactions
            c.execute('SELECT message_id, user_id, emoji FROM reactions')
            rows = c.fetchall()
            for msg_id, user_id, emoji in rows:
                if msg_id in self.message_cache:
                    self.message_cache[msg_id]['reactions'].append(emoji)
            logger.info(f"ðŸ“¦ message_cache ricostruita: {len(self.message_cache)} messaggi")
        except Exception as e:
            logger.error(f"Errore ricostruzione message_cache in on_ready: {e}")

    def extract_urls_all(self, content):
        """
        Estrae tutti gli URL presenti nel messaggio relativi alle piattaforme consentite.
        Restituisce lista di raw URLs (rimuove punteggiatura terminale comune).
        """
        pattern = r'(https?://[^\s\)\]\}>]+)'
        matches = re.findall(pattern, content)
        results = []
        for m in matches:
            if re.search(r'(instagram\.com|tiktok\.com|youtube\.com)', m, re.IGNORECASE):
                m_clean = m.rstrip('.,;:!?)]}')
                results.append(m_clean)
        # dedup mantenendo ordine
        return list(dict.fromkeys(results))

    def normalize_url(self, url):
        """
        Normalizza l'URL per confronto:
        - scheme e netloc lowercase
        - rimuove slash finale
        - rimuove frammento
        - rimuove parametri utm_*
        - ordina query string
        """
        try:
            p = urlparse(url)
            scheme = p.scheme.lower() if p.scheme else 'https'
            netloc = p.netloc.lower()
            path = p.path.rstrip('/')
            qs = parse_qsl(p.query, keep_blank_values=True)
            qs_filtered = [(k, v) for (k, v) in qs if not k.lower().startswith('utm_')]
            qs_sorted = sorted(qs_filtered)
            query = urlencode(qs_sorted)
            normalized = urlunparse((scheme, netloc, path, '', query, ''))
            return normalized
        except Exception:
            return url.strip()

    @commands.Cog.listener()
    async def on_message(self, message):
        self.bot.bot_status['messages_processed'] += 1
        self.bot.bot_status['last_activity'] = datetime.now()

        if message.channel.id != SUBMISSIONS_CHANNEL_ID or message.author.bot:
            await self.bot.process_commands(message)
            return

        content_lower = message.content.lower()
        locale = str(message.guild.preferred_locale) if message.guild and message.guild.preferred_locale else 'it'
        log_channel = self.bot.get_channel(LOG_CHANNEL_ID)

        # Controlla validitÃ  del messaggio: deve avere almeno un hashtag ufficiale E almeno un link social consentito
        has_hashtag = any(tag.lower() in content_lower for tag in HASHTAGS)
        has_permitted_link = bool(re.search(r'(instagram\.com|tiktok\.com|youtube\.com)', content_lower, re.IGNORECASE))

        if not has_hashtag or not has_permitted_link:
            try:
                await message.delete()
                if not has_hashtag:
                    await message.author.send(get_translation('invalid_no_hashtag', locale))
                    if log_channel:
                        await log_channel.send(f"ðŸ—‘ï¸ Messaggio rimosso da {message.author.mention}: manca hashtag ufficiale.")
                else:
                    await message.author.send(get_translation('invalid_no_permitted_link', locale))
                    if log_channel:
                        await log_channel.send(f"ðŸ—‘ï¸ Messaggio rimosso da {message.author.mention}: link non consentito o assente.")
            except discord.Forbidden:
                logger.warning(f"Impossibile eliminare messaggio o inviare DM a {message.author.name}: permessi insufficienti.")
                if log_channel:
                    await log_channel.send(f"âš ï¸ Impossibile eliminare messaggio o inviare DM a {message.author.name}: permessi insufficienti.")
            await self.bot.process_commands(message)
            return

        # Se valido, procedi con check duplicati
        user_id = message.author.id
        normalized_content = self.normalize_message(message.content)
        message_url = self.extract_url(message.content)

        # Se valido, procedi con check duplicati link giÃ  pubblicati
        urls = self.extract_urls_all(message.content)
        if urls:
            for raw in urls:
                norm = self.normalize_url(raw)
                if link_exists(norm):
                    # duplicato: elimina e non assegnare punti
                    try:
                        await message.delete()
                        # prova a mandare DM all'autore (usa le traduzioni giÃ  presenti)
                        try:
                            await message.author.send(get_translation('duplicate_link_submitted', locale))
                        except Exception:
                            pass
                        if log_channel:
                            await log_channel.send(f"ðŸ—‘ï¸ Messaggio di {message.author.mention} eliminato: contiene link giÃ  pubblicato ({raw})")
                    except discord.Forbidden:
                        logger.warning(f"Impossibile eliminare messaggio o inviare DM a {message.author}.")
                        if log_channel:
                            await log_channel.send(f"âš ï¸ Impossibile eliminare/DM {message.author.mention} per duplicato link ({raw}).")
                    await self.bot.process_commands(message)
                    return

        # Controlla se il messaggio Ã¨ duplicato (stesso URL o stesso contenuto normalizzato)
        is_duplicate = False
        original_message_id = None
        for cached_id, cached_data in self.message_cache.items():
            if cached_id == message.id:
                continue
            # Controlla duplicato per URL
            if message_url and message_url == cached_data.get('url'):
                is_duplicate = True
                original_message_id = cached_id
                break
            # Controlla duplicato per contenuto normalizzato
            if normalized_content == cached_data['normalized']:
                is_duplicate = True
                original_message_id = cached_id
                break

        if is_duplicate:
            # Rimuovi il messaggio in ogni caso
            try:
                await message.delete()
                if original_message_id in self.message_cache:
                    cached_data = self.message_cache[original_message_id]
                    if cached_data['user_id'] == user_id:
                        await message.author.send(get_translation('duplicate_same_user', locale))
                        if log_channel:
                            await log_channel.send(f"âš ï¸ Utente {message.author.name} ha ripubblicato un proprio messaggio: messaggio rimosso, nessun punto assegnato.")
                    else:
                        await message.author.send(get_translation('duplicate_other_user', locale))
                        if log_channel:
                            await log_channel.send(f"âš ï¸ Utente {message.author.name} ha pubblicato un messaggio duplicato di un altro utente: messaggio rimosso.")
            except discord.Forbidden:
                logger.warning(f"Impossibile inviare DM o eliminare messaggio di {message.author.name}: permessi insufficienti.")
                if log_channel:
                    await log_channel.send(f"âš ï¸ Impossibile inviare DM o eliminare messaggio di {message.author.name}: permessi insufficienti.")
            await self.bot.process_commands(message)
            return

        # Se non Ã¨ duplicato, aggiungi alla cache e procedi (assegnazione punti, ecc.)
        self.message_cache[message.id] = {
            'user_id': user_id,
            'normalized': normalized_content,
            'url': message_url,
            'reactions': []
        }

        # Assegna punti e partecipazione per la submission (questo Ã¨ corretto)
        c.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))
        c.execute('UPDATE users SET points = points + 10, participations = participations + 1 WHERE user_id = ?', (user_id,))
        conn.commit()

        # Registra evento settimanale per partecipazione
        record_weekly_event(user_id, 'participation', points=10, message_id=message.id)

        # registra nel DB tutti i link inviati da questo messaggio
        from datetime import datetime as _dt
        now_iso = _dt.now().isoformat()
        if urls:
            for raw in urls:
                norm = self.normalize_url(raw)
                add_submitted_link(norm, raw, user_id, message.id, now_iso)

        from config import MULTIPLATFORM_BONUS_PER_EXTRA, MULTIPLATFORM_MAX_USES_PER_WEEK, MULTIPLATFORM_DOMAINS
        from database import count_weekly_event_type

        # Estrai tutti i domini presenti nel messaggio (case-insensitive)
        found = set()
        for domain in MULTIPLATFORM_DOMAINS:
            if domain in message.content.lower():
                found.add(domain)

        platform_count = len(found)
        if platform_count > 1:
            extra = platform_count - 1
            bonus_points = extra * MULTIPLATFORM_BONUS_PER_EXTRA

            # Controllo: il bonus non deve essere stato giÃ  applicato per questo message_id (protezione "una sola volta per challenge")
            c.execute('SELECT 1 FROM weekly_events WHERE user_id = ? AND event_type = ? AND message_id = ? LIMIT 1',
                      (user_id, 'multiplatform_bonus', message.id))
            if not c.fetchone():
                # Controllo limite settimanale
                used_this_week = count_weekly_event_type(user_id, 'multiplatform_bonus')
                if used_this_week < MULTIPLATFORM_MAX_USES_PER_WEEK:
                    # Applica bonus
                    c.execute('UPDATE users SET points = points + ? WHERE user_id = ?', (bonus_points, user_id))
                    conn.commit()
                    record_weekly_event(user_id, 'multiplatform_bonus', points=bonus_points, message_id=message.id)
                    if log_channel:
                        await log_channel.send(f"âœ¨ **Bonus multipiattaforma**: +{bonus_points} punti a {message.author.mention} (+{extra} extra platform). (Uso {used_this_week+1}/{MULTIPLATFORM_MAX_USES_PER_WEEK} questa settimana)")
                else:
                    if log_channel:
                        await log_channel.send(f"âš ï¸ {message.author.mention} ha raggiunto il limite settimanale per il Bonus multipiattaforma ({MULTIPLATFORM_MAX_USES_PER_WEEK}). Bonus non applicato.")

                    # Invia DM all'utente informandolo che ha esaurito i bonus multipiattaforma
                    try:
                        dm_text = get_translation('multiplatform_limit_reached', locale, max_uses=MULTIPLATFORM_MAX_USES_PER_WEEK)
                    except Exception:
                        dm_text = f"Hai raggiunto il limite settimanale di {MULTIPLATFORM_MAX_USES_PER_WEEK} bonus multipiattaforma. Il bonus multipiattaforma non Ã¨ stato applicato per questo messaggio, ma i +10 punti di partecipazione sono giÃ  stati assegnati come da regolamento."
                    try:
                        await message.author.send(dm_text)
                    except discord.Forbidden:
                        if log_channel:
                            await log_channel.send(f"âš ï¸ Impossibile inviare DM a {message.author.mention} per informarlo del limite multipiattaforma.")

        await message.add_reaction('âœ…')  # SOLO IL BOT puÃ² aggiungere questa emoji
        if log_channel:
            await log_channel.send(f'âœ… Utente {message.author.name} ha partecipato: +10 punti.')

        await self.bot.process_commands(message)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        self.bot.bot_status['reactions_processed'] += 1
        self.bot.bot_status['last_activity'] = datetime.now()

        if user.bot:
            return

        log_channel = self.bot.get_channel(LOG_CHANNEL_ID)
        from config import SPOTLIGHT_CHANNEL_ID  # assicurati sia importato in cima

        # BLOCCA REAZIONI AI MESSAGGI DEL BOT (eccetto spotlight)
        if reaction.message.author.bot:
            if reaction.message.channel.id == SPOTLIGHT_CHANNEL_ID:
                return  # gestione nel cog spotlight
            if log_channel:
                try:
                    await log_channel.send(f"ðŸš« **REAZIONE BLOCCATA**: {user.mention} ha tentato di reagire ({reaction.emoji}) a un messaggio del bot")
                except Exception:
                    pass
            try:
                await reaction.remove(user)
            except Exception:
                try:
                    await reaction.clear()
                except Exception:
                    pass
            return

        # BLOCCA EMOJI âœ… per tutti
        if str(reaction.emoji) == 'âœ…':
            if log_channel:
                try:
                    await log_channel.send(f"ðŸš« **EMOJI BLOCCATA**: {user.mention} ha tentato di usare âœ… (riservata al bot)")
                except Exception:
                    pass
            try:
                await reaction.remove(user)
            except Exception:
                try:
                    await reaction.clear()
                except Exception:
                    pass
            return

        # Processa solo nel canale submissions
        if reaction.message.channel.id != SUBMISSIONS_CHANNEL_ID:
            return

        # Processa solo emoji valide
        if reaction.emoji not in ['ðŸ’¯', 'ðŸ‘']:
            return

        # Ignora self-vote
        if user.id == reaction.message.author.id:
            return

        # Ignora reazioni su messaggi duplicati
        if reaction.message.id in self.message_cache and self.message_cache[reaction.message.id].get('is_duplicate', False):
            return

        participant_id = reaction.message.author.id
        message_id = reaction.message.id
        emoji_str = str(reaction.emoji)

        # Se l'utente ha giÃ  reagito ad un repost collegato a questo original, ignoralo (blocca doppio bonus cross-channel)
        try:
            c.execute('''
                SELECT 1 FROM reactions r
                JOIN spotlight_reposts s ON r.message_id = s.spotlight_message_id
                WHERE s.original_message_id = ? AND r.user_id = ?
                LIMIT 1
            ''', (message_id, user.id))
            if c.fetchone():
                # L'utente ha giÃ  reagito al repost -> non assegnare bonus anche qui
                if log_channel:
                    await log_channel.send(f"ðŸš« Reazione ignorata: {user.mention} ha giÃ  reagito al repost relativo al messaggio {message_id}")
                try:
                    await reaction.remove(user)
                except Exception:
                    pass
                return
        except Exception as e:
            logger.error(f"Errore controllo cross-channel reactions: {e}")

        # Controlla se l'utente ha giÃ  reagito allo stesso messaggio (duplicato)
        try:
            c.execute('SELECT 1 FROM reactions WHERE message_id = ? AND user_id = ?', (message_id, user.id))
            if c.fetchone():
                if log_channel:
                    await log_channel.send(f"ðŸš« **Reazione ignorata**: {user.mention} ha giÃ  reagito al messaggio di {reaction.message.author.mention}")
                return

            c.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (participant_id,))
            conn.commit()

            if log_channel:
                await log_channel.send(f"âœ… **Reazione rilevata**: {reaction.emoji} da {user.mention} su messaggio di {reaction.message.author.mention}")

            points_to_give = 0
            reputation_to_give = 0

            if any(role.id in [FOUNDER_ROLE_ID, ADMIN_ROLE_ID] for role in user.roles):
                points_to_give = 5
                c.execute('UPDATE users SET points = points + 5 WHERE user_id = ?', (participant_id,))
                record_weekly_event(participant_id, 'staff_bonus', points=5, message_id=message_id)
                if log_channel:
                    await log_channel.send(f"ðŸ‘‘ **Bonus Staff**: +5 punti a {reaction.message.author.mention}")
            else:
                reputation_to_give = 1
                c.execute('UPDATE users SET reputation = reputation + 1 WHERE user_id = ?', (participant_id,))
                record_weekly_event(participant_id, 'community_bonus', reputation=1, message_id=message_id)
                if log_channel:
                    await log_channel.send(f"â­ **Bonus Community**: +1 reputazione a {reaction.message.author.mention}")

            c.execute('''INSERT INTO reactions 
                         (message_id, user_id, participant_id, emoji, points_given, reputation_given) 
                         VALUES (?, ?, ?, ?, ?, ?)''', 
                     (message_id, user.id, participant_id, emoji_str, points_to_give, reputation_to_give))
            conn.commit()

            # Aggiorna badge se necessario (logica invariata)
            c.execute('SELECT points, badges FROM users WHERE user_id = ?', (participant_id,))
            row = c.fetchone()
            if row:
                points, badges = row
                badge_list = badges.split(',') if badges else []
                updated = False
                if points >= 50 and 'Hype Starter' not in badge_list:
                    badge_list.append('Hype Starter')
                    updated = True
                if points >= 100 and 'Trend Conqueror' not in badge_list:
                    badge_list.append('Trend Conqueror')
                    updated = True
                if updated:
                    new_badges = ','.join(badge_list)
                    c.execute('UPDATE users SET badges = ? WHERE user_id = ?', (new_badges, participant_id))
                    conn.commit()
                    if log_channel:
                        await log_channel.send(f"ðŸ† **Nuovo Badge**: {reaction.message.author.mention} ha ottenuto: {new_badges}")

        except Exception as e:
            logger.error(f"Errore in on_reaction_add: {e}")
            if log_channel:
                try:
                    await log_channel.send(f"âŒ **Errore aggiunta reazione**: {e}")
                except Exception:
                    pass

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction, user):
        self.bot.bot_status['reactions_processed'] += 1
        self.bot.bot_status['last_activity'] = datetime.now()

        if user.bot:
            return
        if reaction.message.author.bot:
            return
        if str(reaction.emoji) == 'âœ…':
            return
        if reaction.message.channel.id != SUBMISSIONS_CHANNEL_ID:
            return
        if reaction.emoji not in ['ðŸ’¯', 'ðŸ‘']:
            return
        if user.id == reaction.message.author.id:
            return
        if reaction.message.id in self.message_cache and self.message_cache[reaction.message.id].get('is_duplicate', False):
            return

        participant_id = reaction.message.author.id
        message_id = reaction.message.id
        emoji_str = str(reaction.emoji)
        log_channel = self.bot.get_channel(LOG_CHANNEL_ID)

        # Aggiorna la cache delle reazioni locale
        if message_id in self.message_cache and emoji_str in self.message_cache[message_id]['reactions']:
            try:
                self.message_cache[message_id]['reactions'].remove(emoji_str)
            except ValueError:
                pass

        try:
            c.execute('''SELECT emoji, points_given, reputation_given FROM reactions 
                         WHERE message_id = ? AND user_id = ? AND emoji = ?''', 
                     (message_id, user.id, emoji_str))
            existing_reaction = c.fetchone()

            if not existing_reaction:
                logger.debug(f"Rimozione ignorata: {user.name} non aveva una reazione registrata con emoji '{emoji_str}' per il messaggio {message_id}")
                return

            emoji, points_given, reputation_given = existing_reaction
            if log_channel:
                await log_channel.send(f"ðŸ”» **Reazione rimossa**: {reaction.emoji} da {user.mention} su messaggio di {reaction.message.author.mention}")

            c.execute('DELETE FROM reactions WHERE message_id = ? AND user_id = ? AND emoji = ?', 
                     (message_id, user.id, emoji_str))

            if points_given > 0:
                c.execute('UPDATE users SET points = points - ? WHERE user_id = ?', (points_given, participant_id))
                record_weekly_event(participant_id, 'staff_bonus_removed', points=-points_given, message_id=message_id)
                if log_channel:
                    await log_channel.send(f"ðŸ‘‘ **Bonus Staff rimosso**: -{points_given} punti a {reaction.message.author.mention}")

            if reputation_given > 0:
                c.execute('UPDATE users SET reputation = reputation - ? WHERE user_id = ?', (reputation_given, participant_id))
                record_weekly_event(participant_id, 'community_bonus_removed', reputation=-reputation_given, message_id=message_id)
                if log_channel:
                    await log_channel.send(f"â­ **Bonus Community rimosso**: -{reputation_given} reputazione a {reaction.message.author.mention}")

            conn.commit()

            # Aggiorna badges se necessario (logica invariata)
            c.execute('SELECT points, badges FROM users WHERE user_id = ?', (participant_id,))
            row = c.fetchone()
            if row:
                points, badges = row
                badge_list = badges.split(',') if badges else []
                updated = False
                if points < 50 and 'Hype Starter' in badge_list:
                    badge_list.remove('Hype Starter')
                    updated = True
                if points < 100 and 'Trend Conqueror' in badge_list:
                    badge_list.remove('Trend Conqueror')
                    updated = True
                if updated:
                    new_badges = ','.join(badge_list)
                    c.execute('UPDATE users SET badges = ? WHERE user_id = ?', (new_badges, participant_id))
                    conn.commit()
                    if log_channel:
                        await log_channel.send(f"ðŸ† **Badge aggiornati**: {reaction.message.author.mention} ora ha: {new_badges}")

        except Exception as e:
            logger.error(f"Errore in on_reaction_remove: {e}")
            if log_channel:
                await log_channel.send(f"âŒ **Errore rimozione reazione**: {e}")

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        logger.info(f"Bot aggiunto al server: {guild.name} (ID: {guild.id})")
        bot_member = guild.me
        critical_permissions = [
            'manage_messages', 'add_reactions', 'send_messages', 'read_messages', 'view_channel'
        ]
        missing_permissions = []
        for perm in critical_permissions:
            if not getattr(bot_member.guild_permissions, perm, False):
                missing_permissions.append(perm)
        if missing_permissions:
            logger.warning(f"Permessi mancanti in {guild.name}: {missing_permissions}")
            try:
                owner = guild.owner
                if owner:
                    embed = discord.Embed(
                        title="âš ï¸ Permessi Bot Insufficienti",
                        description=f"Il bot TrendDuel ha bisogno di permessi aggiuntivi nel server **{guild.name}**",
                        color=0xFF0000
                    )
                    embed.add_field(
                        name="Permessi mancanti:",
                        value="\n".join([f"â€¢ {perm.replace('_', ' ').title()}" for perm in missing_permissions]),
                        inline=False
                    )
                    await owner.send(embed=embed)
            except Exception as e:
                logger.warning(f"Impossibile contattare l'owner di {guild.name}: {e}")

    @commands.Cog.listener()
    async def on_error(self, event, *args, **kwargs):
        logger.error(f"Errore nell'evento {event}: {args}, {kwargs}")

async def setup(bot):
    await bot.add_cog(Events(bot))
