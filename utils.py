from datetime import datetime, timedelta
import pytz
import logging
import discord
import json
import os
from datetime import datetime, timedelta
from config import ITALY_TZ

logger = logging.getLogger(__name__)

def get_week_boundaries(target_date=None):
    """
    Calcola l'inizio e fine settimana (domenica 20:00 - domenica 20:00)
    """
    if target_date is None:
        target_date = datetime.now(ITALY_TZ)
    elif target_date.tzinfo is None:
        target_date = ITALY_TZ.localize(target_date)

    # Trova la domenica corrente o precedente
    days_since_sunday = target_date.weekday() + 1  # Lunedì=1, Domenica=7
    if days_since_sunday == 7:  # È domenica
        if target_date.hour < 20:  # Prima delle 20:00
            # Settimana precedente
            week_end = target_date.replace(hour=20, minute=0, second=0, microsecond=0)
            week_start = week_end - timedelta(days=7)
        else:  # Dopo le 20:00
            # Settimana corrente che sta per finire
            week_end = target_date.replace(hour=20, minute=0, second=0, microsecond=0)
            week_start = week_end - timedelta(days=7)
    else:
        # Non è domenica, trova la domenica precedente
        days_to_subtract = days_since_sunday
        last_sunday = target_date - timedelta(days=days_to_subtract)
        week_start = last_sunday.replace(hour=20, minute=0, second=0, microsecond=0)
        week_end = week_start + timedelta(days=7)

    return week_start, week_end

async def create_leaderboard_embed(bot, leaderboard_data, week_start, week_end, is_test=False):
    """
    Crea l'embed per la classifica settimanale
    """
    # Formatta le date per il display
    start_str = week_start.strftime("%d/%m/%Y")
    end_str = week_end.strftime("%d/%m/%Y")

    title = "🧪 TEST Classifica Settimanale" if is_test else "🏆 TrendDuel — Leaderboard Settimanale"
    embed = discord.Embed(
        title=title,
        description=f"**Periodo:** {start_str} — {end_str}\n*Chiusura classifica: domenica ore 20:00 CET*",
        color=0x2F3136  # Grigio scuro professionale, ispirato a design moderni come Tatsu
    )

    # Aggiungi thumbnail per un tocco elegante (sostituisci con URL reale del logo o icona del bot)
    embed.set_thumbnail(url="https://example.com/trendduel-logo.png")  # Inserisci un URL valido per un'immagine quadrata piccola

    if not leaderboard_data:
        embed.add_field(
            name="📭 Nessun partecipante",
            value="Nessuno ha partecipato questa settimana. Sii il primo a inviare una submission!",
            inline=False
        )
        return embed, []

    # Emoji per i primi 3 posti, più minimalisti e eleganti
    position_emojis = {1: "🥇", 2: "🥈", 3: "🥉"}

    leaderboard_text = "```yaml\n"  # Usa code block YAML per un look moderno, pulito e allineato (simile a Tatsu)

    # Intestazione tabella-like per chiarezza
    leaderboard_text += f"{'Pos':<4} {'Utente':<20} {'Punti Sett.':<12} {'Rep Tot.':<10} {'Part.':<6}\n"
    leaderboard_text += "-" * 52 + "\n"

    winners = []  # Per le menzioni

    for i, (user_id, weekly_points, weekly_reputation, weekly_participations, first_participation, total_reputation) in enumerate(leaderboard_data, 1):
        try:
            user = await bot.fetch_user(user_id)
            username = user.name[:18] + "..." if len(user.name) > 18 else user.name  # Troncamento per allineamento
            user_mention = user.mention
        except:
            username = f"User-{user_id}"[:18]
            user_mention = f"<@{user_id}>"

        # Emoji per posizione solo per top 3, altrimenti numero pulito
        position = position_emojis.get(i, f"{i:02d}.")

        # Formatta la riga con allineamento preciso
        weekly_rep_display = weekly_reputation if weekly_reputation else 0
        total_rep_display = total_reputation if total_reputation else 0

        leaderboard_text += f"{position:<4} {username:<20} {weekly_points:<12} ⭐{total_rep_display:<10} {weekly_participations:<6}\n"

        # Salva i primi 3 per le menzioni
        if i <= 3:
            winners.append((i, user_mention, weekly_points))

    leaderboard_text += "```"

    embed.add_field(
        name="📊 Classifica Settimanale",
        value=leaderboard_text,
        inline=False
    )

    # Sezione vincitori più elegante e separata
    if winners:
        winner_mentions = []
        for pos, mention, points in winners:
            emoji = position_emojis[pos]
            winner_mentions.append(f"{emoji} **{mention}** — {points} punti")

        embed.add_field(
            name="🎉 Vincitori della Settimana",
            value="\n".join(winner_mentions),
            inline=False
        )

    embed.set_footer(
        text="Aggiornata automaticamente • TrendDuel — Challenge the world, conquer the hype.",
        icon_url=bot.user.avatar.url if bot.user and bot.user.avatar else None
    )

    return embed, winners

async def archive_leaderboard(bot, embed, week_start, week_end, participants_count):
    """
    Archivia la classifica nel Hall of Fame
    """
    from config import HALL_OF_FAME_CHANNEL_ID, ITALY_TZ
    try:
        hall_of_fame_channel = bot.get_channel(HALL_OF_FAME_CHANNEL_ID)
        if not hall_of_fame_channel:
            logger.error(f"Canale Hall of Fame non trovato: {HALL_OF_FAME_CHANNEL_ID}")
            return None

        # Modifica l'embed per l'archivio
        archive_embed = embed.copy()
        archive_embed.title = f"📚 {embed.title} (Archiviata)"
        archive_embed.color = 0x5865F2  # Blu Discord per archivio, moderno
        archive_embed.set_footer(
            text=f"Archiviata il {datetime.now(ITALY_TZ).strftime('%d/%m/%Y alle %H:%M')} • TrendDuel"
        )

        # Invia nel Hall of Fame
        message = await hall_of_fame_channel.send(embed=archive_embed)

        # Salva nel database
        from database import c, conn
        embed_data = json.dumps({
            'title': embed.title,
            'description': embed.description,
            'color': embed.color.value if embed.color else None,
            'fields': [{'name': f.name, 'value': f.value, 'inline': f.inline} for f in embed.fields]
        })

        c.execute('''INSERT INTO weekly_archives
                     (week_start, week_end, embed_data, participants_count, archived_at, hall_of_fame_message_id)
                     VALUES (?, ?, ?, ?, ?, ?)''',
                 (week_start.isoformat(), week_end.isoformat(), embed_data, 
                  participants_count, datetime.now(ITALY_TZ).isoformat(), message.id))
        conn.commit()

        logger.info(f"Classifica archiviata nel Hall of Fame: messaggio {message.id}")
        return message.id

    except Exception as e:
        logger.error(f"Errore nell'archiviazione: {e}")
        return None

def cleanup_lock_files():
    now = datetime.now(ITALY_TZ)
    lock_dir = "."
    for file in os.listdir(lock_dir):
        if file.startswith("leaderboard_published_") and file.endswith(".lock"):
            file_path = os.path.join(lock_dir, file)
            try:
                with open(file_path, 'r') as f:
                    timestamp = datetime.fromisoformat(f.read())
                if (now - timestamp).total_seconds() > 24 * 3600:  # Più vecchio di 24 ore
                    os.remove(file_path)
                    logger.info(f"🗑️ Rimosso file di lock obsoleto: {file}")
            except Exception as e:
                logger.error(f"Errore nella rimozione del file di lock {file}: {e}")