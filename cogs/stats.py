import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
import logging
from config import ITALY_TZ, FOUNDER_ROLE_ID, ADMIN_ROLE_ID
from database import c, conn
from utils import get_week_boundaries
from translations import get_translation
import asyncio

logger = logging.getLogger(__name__)
# --- TEST BADGE MODE ---
# Se abilitato, permette di assegnare badge rapidamente per testing.
# Per testare: usa `record_weekly_event(user_id, 'test_trendsetter')`, ecc.
try:
    from config import TEST_BADGE_MODE, TEST_BADGE_WINDOW_HOURS
except Exception:
    # Default: abilitato per test rapido. Imposta TEST_BADGE_MODE=False in config.py per disabilitare.
    TEST_BADGE_MODE = True
    TEST_BADGE_WINDOW_HOURS = 24

def _test_badge_event_types():
    return {
        'Trendsetter': 'test_trendsetter',
        'Viral Catalyst': 'test_viral_catalyst',
        'Hype Hero': 'test_hype_hero',
        'Viral Architect': 'test_viral_architect',
        'Duel Master': 'test_duel_master',
        'Legendary Duelist': 'test_legendary_duelist'
    }
# --- END TEST BADGE MODE ---


class Stats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_level_info(self, points):
        """Calcola livello, progresso e titolo basato sul nuovo sistema"""
        # Nuovo sistema di livelli
        levels = [
            (0, "🌟 Rookie"),
            (100, "⚡ Challenger"),
            (300, "🔥 Hype Challenger"),
            (700, "🎯 Trend Fighter"),
            (1500, "🚀 Viral Maker"),
            (3000, "💎 Hype Hero"),
            (6000, "👑 Trendsetter"),
            (12000, "🎪 Duel Pro"),
            (25000, "🌌 Viral Architect"),
            (50000, "⭐ Duel Master"),
            (100000, "🏆 Legend"),
            (200000, "💫 Viral Legend")
        ]

        # Trova il livello corrente
        current_level = 1
        current_title = "🌟 Rookie"
        next_level_points = 100
        current_level_points = 0

        for i, (required_points, title) in enumerate(levels):
            if points >= required_points:
                current_level = i + 1
                current_title = title
                current_level_points = required_points
                # Prossimo livello
                if i + 1 < len(levels):
                    next_level_points = levels[i + 1][0]
                else:
                    next_level_points = required_points  # Max level reached
            else:
                break

        # Calcola progresso verso il prossimo livello
        progress = points - current_level_points
        progress_needed = next_level_points - current_level_points

        return current_level, progress, progress_needed, current_title, next_level_points

    def get_rank_emoji(self, rank):
        """Restituisce emoji speciali per i primi posti"""
        rank_emojis = {
            1: "🥇", 2: "🥈", 3: "🥉",
            4: "4️⃣", 5: "5️⃣"
        }
        return rank_emojis.get(rank, f"#{rank}")

    def create_progress_bar(self, current, max_val, length=12):
        """Crea una barra di progresso basata su current / max_val (punti totali vs prossimo livello).
           Visualizza la percentuale senza decimali se il valore è un numero intero.
        """
        if max_val <= 0:
            return "▰▱▱▱▱▱▱▱▱▱▱▱ 0%"

        ratio = current / max_val
        ratio = max(0.0, min(ratio, 1.0))  # clamp tra 0 e 1

        filled = int(ratio * length)
        bar = "▰" * filled + "▱" * (length - filled)
        percentage = ratio * 100

        # Se il numero è intero (o molto vicino), non mostrare decimali
        if abs(percentage - round(percentage)) < 1e-6:
            return f"{bar} {int(round(percentage))}%"
        else:
            return f"{bar} {percentage:.1f}%"

    def get_achievement_display(self, badges, locale='en'):
        """Crea un display ordinato dei badge con estetica a blocchi e wrapping su più righe."""

        if not badges:
            return "│ Nessun badge ottenuto"

        # Lista dei badge nell'ordine desiderato
        BADGE_DISPLAY_ORDER = [
            "Trendsetter",
            "Viral Catalyst",
            "Hype Hero",
            "Viral Architect",
            "Duel Master",
            "Legendary Duelist"
        ]

        # Suddivide la stringa in singoli badge
        badge_list = [b.strip() for b in badges.split(',') if b.strip()]

        # Ordina secondo l'ordine desiderato
        display_order = {name: i for i, name in enumerate(BADGE_DISPLAY_ORDER)}
        badge_list.sort(key=lambda x: display_order.get(x, 999))  # badge non previsti finiscono in fondo

        # Traduci eventuali badge (se presente la funzione get_translation)
        display_badges = []
        for badge in badge_list[:6]:  # massimo 6 badge
            key = 'badge_' + badge.replace(' ', '_')
            translated = get_translation(key, locale)
            if translated == key:
                translated = badge
            display_badges.append(translated)

        # Se ci sono più di 6 badge, aggiungi indicazione
        if len(badge_list) > 6:
            display_badges.append(f"+{len(badge_list)-6} altri...")

        # Raggruppa in righe da massimo 3 badge
        lines = []
        for i in range(0, len(display_badges), 3):
            chunk = display_badges[i:i+3]
            lines.append(" | ".join(chunk))

        # Aggiunge il prefisso │ per mantenere lo stile a blocchi
        return "\n".join([f"│ {line}" for line in lines])

    async def get_user_rank(self, user_id):
        """Ottiene il ranking globale dell'utente"""
        c.execute('SELECT user_id, points FROM users ORDER BY points DESC')
        all_users = c.fetchall()

        for rank, (uid, points) in enumerate(all_users, 1):
            if uid == user_id:
                return rank, len(all_users)
        return None, len(all_users)

    def get_level_color(self, level):
        """Restituisce colore dinamico basato sul livello"""
        color_map = {
            1: 0x95A5A6,   # Rookie - Grigio
            2: 0x3498DB,   # Challenger - Blu
            3: 0xE67E22,   # Hype Challenger - Arancione
            4: 0x9B59B6,   # Trend Fighter - Viola
            5: 0x1ABC9C,   # Viral Maker - Turchese
            6: 0xF39C12,   # Hype Hero - Oro
            7: 0xE74C3C,   # Trendsetter - Rosso
            8: 0x8E44AD,   # Duel Pro - Viola scuro
            9: 0x2C3E50,   # Viral Architect - Blu scuro
            10: 0xD4AC0D,  # Duel Master - Oro scuro
            11: 0xFFD700,  # Legend - Oro brillante
            12: 0xFF69B4   # Viral Legend - Rosa brillante
        }
        return color_map.get(level, 0x95A5A6)

    
    # --- BADGE LOGIC START ---
    def _weeks_with_min_points(self, user_id: int, min_points: int):
        """
        Conta quante settimane distinte (week_start) in weekly_events hanno SUM(points_earned) >= min_points.
        """
        try:
            c.execute("""
                SELECT COUNT(*) FROM (
                    SELECT week_start, SUM(points_earned) as pts
                    FROM weekly_events
                    WHERE user_id = ?
                    GROUP BY week_start
                    HAVING pts >= ?
                ) tmp
            """, (user_id, min_points))
            return c.fetchone()[0] or 0
        except Exception as e:
            logger.debug(f"_weeks_with_min_points error for {user_id}: {e}")
            return 0

    def _distinct_challenges_participated(self, user_id: int):
        """Conta i message_id distinti in weekly_events per l'utente (partecipazioni differenti)."""
        try:
            c.execute("""
                SELECT COUNT(DISTINCT message_id) FROM weekly_events
                WHERE user_id = ? AND message_id IS NOT NULL
            """, (user_id,))
            return c.fetchone()[0] or 0
        except Exception as e:
            logger.debug(f"_distinct_challenges_participated error for {user_id}: {e}")
            return 0

    def _count_total_reactions_from_community(self, user_id: int):
        """
        Conta il numero di reazioni community ricevute dall'utente (reputation_given > 0)
        usando la tabella reactions (participant_id è il destinatario della reazione).
        """
        try:
            c.execute("""
                SELECT COUNT(*) FROM reactions
                WHERE participant_id = ? AND reputation_given > 0
            """, (user_id,))
            return c.fetchone()[0] or 0
        except Exception as e:
            logger.debug(f"_count_total_reactions_from_community error for {user_id}: {e}")
            return 0

    def _avg_reactions_per_challenge(self, user_id: int):
        """
        Calcola la media di reazioni per challenge per l'utente.
        Raggruppa le righe di reactions per message_id (participant_id = user_id).
        """
        try:
            c.execute("""
                SELECT AVG(cnt) FROM (
                    SELECT message_id, COUNT(*) as cnt
                    FROM reactions
                    WHERE participant_id = ?
                    GROUP BY message_id
                )
            """, (user_id,))
            v = c.fetchone()[0]
            return float(v) if v else 0.0
        except Exception as e:
            logger.debug(f"_avg_reactions_per_challenge error for {user_id}: {e}")
            return 0.0

    def _count_creativity_bonus_from_staff(self, user_id: int):
        """
        Conta i Bonus Creatività dallo staff cercando event_type coerenti in weekly_events.
        """
        try:
            c.execute("""
                SELECT COUNT(*) FROM weekly_events
                WHERE user_id = ? AND (
                    lower(event_type) LIKE '%creativ%' OR
                    lower(event_type) LIKE '%staff_creativity%' OR
                    lower(event_type) LIKE '%creativity_bonus%' OR
                    lower(event_type) LIKE '%staff_bonus%'
                )
            """, (user_id,))
            return c.fetchone()[0] or 0
        except Exception as e:
            logger.debug(f"_count_creativity_bonus_from_staff error for {user_id}: {e}")
            return 0

    def _spotlight_weeks(self, user_id: int):
        """Conta in quante settimane distinte l'utente è stato repostato nello spotlight (spotlight_reposts.week_start)."""
        try:
            c.execute("""
                SELECT COUNT(DISTINCT week_start) FROM spotlight_reposts
                WHERE user_id = ?
            """, (user_id,))
            return c.fetchone()[0] or 0
        except Exception as e:
            logger.debug(f"_spotlight_weeks error for {user_id}: {e}")
            return 0

    def _challenges_with_3_plus_platforms(self, user_id: int):
        """
        Usa submitted_links: per ogni message_id di questo autore contiamo quanti domini distinti sono stati inviati.
        Restituisce il conteggio di message_id con >=3 domini distinti.
        """
        try:
            c.execute("""
                SELECT message_id, raw_link FROM submitted_links
                WHERE user_id = ?
            """, (user_id,))
            rows = c.fetchall()
            if not rows:
                return 0
            from urllib.parse import urlparse
            domains_by_msg = {}
            for message_id, raw_link in rows:
                try:
                    parsed = urlparse(raw_link)
                    netloc = (parsed.netloc or "").lower().lstrip('www.')
                    if not netloc:
                        continue
                    domains_by_msg.setdefault(message_id, set()).add(netloc)
                except Exception:
                    continue
            count = sum(1 for s in domains_by_msg.values() if len(s) >= 3)
            return count
        except Exception as e:
            logger.debug(f"_challenges_with_3_plus_platforms error for {user_id}: {e}")
            return 0

    async def evaluate_and_update_badges(self, user_id: int):
        """
        Valuta e aggiorna i badge dell'utente (colonna users.badges).
        Restituisce la stringa badges salvata (es. "Trendsetter,Viral Catalyst").
        """
        try:
            c.execute("SELECT points, badges FROM users WHERE user_id = ?", (user_id,))
            row = c.fetchone()
            if not row:
                return ""
            total_points = row[0] or 0
            current_badges = row[1] or ""
            badge_set = set(b.strip() for b in current_badges.split(',') if b.strip())

            weeks_500 = self._weeks_with_min_points(user_id, 500)
            weeks_1000 = self._weeks_with_min_points(user_id, 1000)
            distinct_challenges = self._distinct_challenges_participated(user_id)
            creativity_count = self._count_creativity_bonus_from_staff(user_id)
            spotlight_weeks = self._spotlight_weeks(user_id)
            challenges_multi_platform = self._challenges_with_3_plus_platforms(user_id)
            avg_reactions = self._avg_reactions_per_challenge(user_id)
            community_reactions_total = self._count_total_reactions_from_community(user_id)

            # 1) Trendsetter (Livello 7 - 6000 punti)
            if total_points >= 6000 and distinct_challenges >= 10 and weeks_500 >= 5:
                badge_set.add("Trendsetter")
            else:
                badge_set.discard("Trendsetter")

            # 2) Viral Catalyst
            if total_points >= 3000 and spotlight_weeks >= 3 and avg_reactions >= 15 and weeks_1000 >= 1:
                badge_set.add("Viral Catalyst")
            else:
                badge_set.discard("Viral Catalyst")

            # 3) Hype Hero (Livello 6 - 3000 punti)
            if total_points >= 3000 and creativity_count >= 10 and community_reactions_total >= 50 and distinct_challenges >= 5 and spotlight_weeks >= 2:
                badge_set.add("Hype Hero")
            else:
                badge_set.discard("Hype Hero")

            # 4) Viral Architect (Livello 9 - 25000 punti)
            if total_points >= 25000 and challenges_multi_platform >= 3 and avg_reactions >= 20:
                badge_set.add("Viral Architect")
            else:
                badge_set.discard("Viral Architect")

            # 5) Duel Master (Livello 10 - 50.000 punti)
            if total_points >= 40000 and distinct_challenges >= 10 and weeks_1000 >= 5:
                badge_set.add("Duel Master")
            else:
                badge_set.discard("Duel Master")

            # 6) Legendary Duelist (Livello 12 - 200.000 punti)
            creative_every_challenge = (distinct_challenges > 0 and creativity_count >= distinct_challenges)
            if total_points >= 200000 and distinct_challenges >= 12 and spotlight_weeks >= 5 and creative_every_challenge:
                badge_set.add("Legendary Duelist")
            else:
                badge_set.discard("Legendary Duelist")


            # --- TEST MODE: assegna badge di test se presenti eventi di test recenti ---
            if TEST_BADGE_MODE:
                try:
                    from config import ITALY_TZ as _ITZ
                except Exception:
                    _ITZ = None
                try:
                    # Calcola cutoff temporale
                    now_dt = datetime.now(_ITZ) if _ITZ else datetime.utcnow()
                    cutoff = now_dt - timedelta(hours=TEST_BADGE_WINDOW_HOURS)
                    cutoff_iso = cutoff.isoformat()
                    # Mappa badge -> event_type di test
                    test_map = _test_badge_event_types()
                    for badge_name, evt in test_map.items():
                        c.execute("""SELECT 1 FROM weekly_events WHERE user_id = ? AND event_type = ? AND timestamp >= ? LIMIT 1""", (user_id, evt, cutoff_iso))
                        if c.fetchone():
                            badge_set.add(badge_name)
                except Exception as e:
                    logger.debug(f"Test badge mode error: {e}")
            # --- END TEST MODE ---

                        # Limite massimo 6 badge e priorità
            priority = ["Legendary Duelist", "Duel Master", "Viral Architect", "Trendsetter", "Viral Catalyst", "Hype Hero"]
            final_badges = [b for b in priority if b in badge_set]

            if len(final_badges) < 6:
                for b in badge_set:
                    if b not in final_badges:
                        final_badges.append(b)
                        if len(final_badges) >= 6:
                            break

            final_badges = final_badges[:6]
            final_badges_str = ",".join(final_badges)

            if final_badges_str != (row[1] or ""):
                c.execute("UPDATE users SET badges = ? WHERE user_id = ?", (final_badges_str, user_id))
                conn.commit()

            return final_badges_str

        except Exception as e:
            logger.exception(f"Errore evaluate_and_update_badges per {user_id}: {e}")
            return current_badges if 'current_badges' in locals() else ""
    # --- BADGE LOGIC END ---

    @app_commands.command(name="stats", description="Visualizza il riepilogo delle tue statistiche.")
    async def stats(self, interaction: discord.Interaction):
        locale = str(interaction.locale)
        user_id = interaction.user.id

        await interaction.response.defer(ephemeral=True)

        # Aggiorna i badge prima di costruire l'embed (se possibile)
        try:
            await self.evaluate_and_update_badges(user_id)
        except Exception as e:
            logger.warning(f"Impossibile valutare badge per {user_id}: {e}")

        try:
            # Recupera dati utente
            c.execute('SELECT points, reputation, participations, badges FROM users WHERE user_id = ?', (user_id,))
            row = c.fetchone()

            if not row:
                error_embed = discord.Embed(
                    title="📊 Profilo Utente",
                    description=get_translation('stats_no_data', locale),
                    color=0xFF6B9D
                )
                error_embed.set_thumbnail(url=interaction.user.display_avatar.url)
                await interaction.followup.send(embed=error_embed, ephemeral=True)
                return

            points, rep, parts, badges = row
            level, progress, progress_needed, title, next_level_points = self.get_level_info(points)
            user_rank, total_users = await self.get_user_rank(user_id)

            # Dati settimanali
            week_start, week_end = get_week_boundaries()
            c.execute('''SELECT SUM(points_earned), SUM(reputation_earned), COUNT(DISTINCT message_id)
                         FROM weekly_events 
                         WHERE user_id = ? AND timestamp >= ? AND timestamp < ? AND archived = 0''',
                     (user_id, week_start.isoformat(), week_end.isoformat()))
            weekly_data = c.fetchone()
            weekly_points = weekly_data[0] if weekly_data and weekly_data[0] else 0
            weekly_rep = weekly_data[1] if weekly_data and weekly_data[1] else 0
            weekly_activities = weekly_data[2] if weekly_data and weekly_data[2] else 0

            # EMBED PRINCIPALE con design moderno
            embed = discord.Embed(color=self.get_level_color(level))

            # Header elegante
            embed.set_author(
                name=f"{interaction.user.display_name}",
                icon_url=interaction.user.display_avatar.url
            )

            # Titolo principale
            embed.title = f"{title} • Livello {level}"

            # Progress bar verso prossimo livello
            if level < 12:  # Non max level
                progress_bar = self.create_progress_bar(points, next_level_points)
                progress_text = f"{points:,}/{next_level_points:,} pts"
            else:
                progress_bar = "▰▰▰▰▰▰▰▰▰▰▰▰ MAX"
                progress_text = "Livello Massimo Raggiunto!"

            # Sezione principale con statistiche
            main_stats = f"""
┌─ 🎯 **PROGRESSIONE LIVELLO**
│ {progress_bar}
│ `{progress_text}`
│
│
├─ 🏆 **POSIZIONE GLOBALE**
│ **{self.get_rank_emoji(user_rank) if user_rank else 'N/A'}** su **{total_users:,}** giocatori
│ Top **{((user_rank/total_users)*100):.1f}%** della community
│
│
├─ 📊 **STATISTICHE GENERALI**
│ Punti Totali: **{points:,}**
│ Reputazione: **{rep:,}**
│ Partecipazioni: **{parts:,}**
│
│
├─ 📅 **PERFORMANCE SETTIMANALE**
│  Punti Guadagnati: **+{weekly_points:,}**
│ Reputazione Ottenuta: **+{weekly_rep:,}**
│ Attività Completate: **{weekly_activities:,}**
│
├───────────────────────
"""
            embed.description = main_stats + "\n"

            # Campo per i badge se presenti
            if badges and badges.strip():
                achievement_display = self.get_achievement_display(badges, locale)
                badge_section = f"""
            ┌─ 🏅 **BADGE ACQUISITI**
            {achievement_display}
            ├───────────────────────
            """
                
                embed.description += badge_section + "\n"

            # Indice attività settimanale
            if weekly_points > 50:
                activity_status = "🔥 **ARDENTE** - Settimana incredibile!"
            elif weekly_points > 20:
                activity_status = "⚡ **ATTIVO** - Ottima performance!"
            elif weekly_points > 0:
                activity_status = "💪 **IN CRESCITA** - Continua così!"
            else:
                activity_status = "💤 **IN PAUSA** - È ora di attivarsi!"

            embed.add_field(
                name="📈 **INDICE ATTIVITÀ**",
                value=f"\n\n{activity_status}",
                inline=True
            )

            # Campo vuoto per creare spazio tra le due colonne
            embed.add_field(name="\u200b", value="\u200b", inline=True)

            # Milestone successiva
            if level < 12:
                embed.add_field(
                    name="🎯 **PROSSIMO OBIETTIVO**",
                    value=f"\n\n**{next_level_points - points:,}** punti al prossimo livello",
                    inline=True
                )
            else:
                embed.add_field(
                    name="👑 **STATUS**",
                    value=f"\n\n**LEGGENDA SUPREMA**\nHai raggiunto l'apice!",
                    inline=True
                )

            # Thumbnail con avatar
            embed.set_thumbnail(url=interaction.user.display_avatar.url)

            # Footer elegante
            now = datetime.now(ITALY_TZ)
            embed.set_footer(
                text=f"TrendDuel • Stats aggiornate il {now.strftime('%d/%m/%Y alle %H:%M')}",
                icon_url="https://cdn.discordapp.com/emojis/741243929555525633.png"
            )

            await asyncio.sleep(0.3)
            await interaction.followup.send(embed=embed, ephemeral=True)

            # Messaggio congratulazioni per livelli alti
            if level >= 10:  # Duel Master o superiore
                await asyncio.sleep(0.8)
                congrats_embed = discord.Embed(
                    title="🎊 CONGRATULAZIONI! 🎊",
                    description=f"Sei un **{title.split(' ', 1)[1]}** di questo server!\nIl tuo livello **{level}** ti colloca tra l'élite assoluta della community TrendDuel.",
                    color=0xFFD700
                )
                congrats_embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/672240286853849098.gif")
                await interaction.followup.send(embed=congrats_embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Errore durante l'esecuzione del comando stats: {e}")
            error_embed = discord.Embed(
                title="⚠️ Errore",
                description="Si è verificato un errore nel caricamento delle tue statistiche. Riprova tra poco.",
                color=0xFF0000
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)

    # Resto del codice rimane invariato per compatibilità
    @app_commands.command(name="weekly-stats", description="Mostra statistiche dettagliate della settimana corrente")
    @app_commands.default_permissions(administrator=True) 
    @app_commands.checks.has_any_role(FOUNDER_ROLE_ID, ADMIN_ROLE_ID)
    async def weekly_stats_command(self, interaction: discord.Interaction):
        locale = str(interaction.locale)
        from database import c, conn
        await interaction.response.defer(ephemeral=True)

        try:
            week_start, week_end = get_week_boundaries()
            c.execute('''
                SELECT 
                    event_type,
                    COUNT(*) as event_count,
                    SUM(points_earned) as total_points,
                    SUM(reputation_earned) as total_reputation
                FROM weekly_events 
                WHERE timestamp >= ? AND timestamp < ? AND archived = 0
                GROUP BY event_type
            ''', (week_start.isoformat(), week_end.isoformat()))
            event_stats = c.fetchall()

            c.execute('''
                SELECT COUNT(DISTINCT user_id) as unique_users
                FROM weekly_events 
                WHERE timestamp >= ? AND timestamp < ? AND archived = 0
            ''', (week_start.isoformat(), week_end.isoformat()))
            unique_users = c.fetchone()[0]

            c.execute('''
                SELECT 
                    user_id,
                    SUM(points_earned) as weekly_points,
                    COUNT(*) as activity_count
                FROM weekly_events 
                WHERE timestamp >= ? AND timestamp < ? AND archived = 0
                GROUP BY user_id
                ORDER BY weekly_points DESC
                LIMIT 1
            ''', (week_start.isoformat(), week_end.isoformat()))
            top_contributor = c.fetchone()

            embed = discord.Embed(
                title="📊 Statistiche Settimana Corrente",
                description=f"**Periodo:** {week_start.strftime('%d/%m/%Y')} - {week_end.strftime('%d/%m/%Y')}",
                color=0x00FFFF
            )

            if not event_stats:
                embed.add_field(
                    name="🔭 Nessuna Attività",
                    value="Nessun evento registrato questa settimana.",
                    inline=False
                )
            else:
                total_events = sum(stat[1] for stat in event_stats)
                total_points = sum(stat[2] for stat in event_stats)
                total_rep = sum(stat[3] for stat in event_stats)

                embed.add_field(
                    name="📈 Panoramica",
                    value=f"**Partecipanti unici:** {unique_users}\n**Eventi totali:** {total_events}\n**Punti distribuiti:** {total_points}\n**Reputazione data:** {total_rep}",
                    inline=True
                )

                event_breakdown = ""
                for event_type, count, points, reputation in event_stats:
                    event_breakdown += f"**{event_type.title()}:** {count} eventi ({points} pts, {reputation} rep)\n"

                embed.add_field(
                    name="🎯 Dettaglio Eventi",
                    value=event_breakdown,
                    inline=True
                )

                if top_contributor:
                    user_id_top, weekly_points, activity_count = top_contributor
                    try:
                        user = await self.bot.fetch_user(user_id_top)
                        username = user.name
                    except:
                        username = f"User-{user_id_top}"

                    embed.add_field(
                        name="🏆 Top Contributor",
                        value=f"**{username}**\n{weekly_points} punti ({activity_count} attività)",
                        inline=True
                    )

            now = datetime.now(ITALY_TZ)
            next_sunday = now + timedelta(days=(6-now.weekday()) if now.weekday() != 6 else 0)
            next_publish = next_sunday.replace(hour=20, minute=0, second=0, microsecond=0)
            if now.weekday() == 6 and now.hour >= 20:  # Se è domenica dopo le 20:00
                next_publish = next_publish + timedelta(days=7)  # Sposta alla prossima domenica
            time_remaining = next_publish - now

            embed.add_field(
                name="⏰ Prossima Pubblicazione",
                value=f"**{next_publish.strftime('%d/%m/%Y alle %H:%M')}**\nMancano: {time_remaining.days}d {time_remaining.seconds//3600}h {(time_remaining.seconds%3600)//60}m",
                inline=False
            )

            embed.set_footer(
                text=f"Stats aggiornate in tempo reale • Richieste da {interaction.user.name}",
                icon_url=interaction.user.avatar.url if interaction.user.avatar else None
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Errore comando weekly-stats: {e}")
            error_embed = discord.Embed(
                title="⌘ Errore",
                description=f"Errore nel recupero delle statistiche: {str(e)[:1000]}",
                color=0xFF0000
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Stats(bot))
