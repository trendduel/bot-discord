import discord
from discord.ext import commands
import logging
from datetime import datetime
import os
import time
import threading
import asyncio
from flask import Flask

# Setup logging
logging.basicConfig(level=logging.DEBUG)  # Impostiamo livello DEBUG per log più dettagliati
logger = logging.getLogger(__name__)

# Importa configurazioni e database
from config import TOKEN, ITALY_TZ, LOG_CHANNEL_ID, LEADERBOARD_CHANNEL_ID, HALL_OF_FAME_CHANNEL_ID
from database import conn, c
import database

# Configura intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True

# Inizializza il bot
bot = commands.Bot(command_prefix='!', intents=intents)

# Variabile globale per tracciare lo stato del bot
bot.bot_status = {
    'start_time': datetime.now(),
    'uptime': 0,
    'messages_processed': 0,
    'reactions_processed': 0,
    'last_activity': datetime.now()
}

# Flask app per uptime monitoring
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive!"

def run_flask():
    port = int(os.environ.get('PORT', 8080))  # Usa PORT da env, fallback 8080 per locale
    app.run(host='0.0.0.0', port=port, debug=False)

async def check_permissions():
    """Controlla i permessi del bot nei canali rilevanti."""
    logger.debug("🛠️ Inizio controllo permessi del bot")
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    leaderboard_channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    hof_channel = bot.get_channel(HALL_OF_FAME_CHANNEL_ID)

    errors = []
    if log_channel:
        permissions = log_channel.permissions_for(log_channel.guild.me)
        if not (permissions.send_messages and permissions.embed_links):
            errors.append(f"⚠️ Permessi insufficienti in 📚-mod-logs (ID: {LOG_CHANNEL_ID})")
    else:
        errors.append(f"❌ Canale 📚-mod-logs non trovato (ID: {LOG_CHANNEL_ID})")

    if leaderboard_channel:
        permissions = leaderboard_channel.permissions_for(leaderboard_channel.guild.me)
        if not (permissions.send_messages and permissions.embed_links):
            errors.append(f"⚠️ Permessi insufficienti in 📊-leaderboard (ID: {LEADERBOARD_CHANNEL_ID})")
    else:
        errors.append(f"❌ Canale 📊-leaderboard non trovato (ID: {LEADERBOARD_CHANNEL_ID})")

    if hof_channel:
        permissions = hof_channel.permissions_for(hof_channel.guild.me)
        if not (permissions.send_messages and permissions.embed_links):
            errors.append(f"⚠️ Permessi insufficienti in 👑-hall-of-fame (ID: {HALL_OF_FAME_CHANNEL_ID})")
    else:
        errors.append(f"❌ Canale 👑-hall-of-fame non trovato (ID: {HALL_OF_FAME_CHANNEL_ID})")

    if errors:
        logger.error("\n".join(errors))
        if log_channel and log_channel.permissions_for(log_channel.guild.me).send_messages:
            await log_channel.send("\n".join(errors))
    else:
        logger.info("✅ Tutti i permessi nei canali sono corretti")
        if log_channel and log_channel.permissions_for(log_channel.guild.me).send_messages:
            await log_channel.send("✅ Tutti i permessi nei canali sono corretti")

# Funzione per caricare i cogs
async def load_cogs():
    logger.debug("🚀 Inizio caricamento cogs")
    cogs = ['cogs.events', 'cogs.leaderboard', 'cogs.stats', 'cogs.admin', 'cogs.commands', 'cogs.spotlight']
    for cog in cogs:
        try:
            await bot.load_extension(cog)
            logger.info(f"✅ Cog {cog} caricato con successo")
        except Exception as e:
            logger.error(f"❌ Errore caricamento cog {cog}: {e}")
    logger.info("🏁 Tutti i cogs caricati")

@bot.event
async def on_ready():
    logger.info(f'🤖 Bot online: {bot.user}')
    bot.bot_status['start_time'] = datetime.now()
    bot.bot_status['last_activity'] = datetime.now()
    current_time = datetime.now(ITALY_TZ)
    logger.info(f"🕐 Orario corrente (CET): {current_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")

    # Controllo permessi
    await check_permissions()

    # Sincronizza i comandi slash
    try:
        synced = await bot.tree.sync()
        logger.info(f"✅ Sincronizzati {len(synced)} comandi slash")
        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel and log_channel.permissions_for(log_channel.guild.me).send_messages:
            await log_channel.send(f"✅ Bot online: {bot.user}, sincronizzati {len(synced)} comandi slash")
    except Exception as e:
        logger.error(f"❌ Errore sincronizzazione comandi: {e}")

    # Avvia il web server Flask in un thread separato per uptime 24/7
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("🌐 Web server Flask avviato per monitoring uptime (porta 8080)")

# Funzione principale per eseguire il bot con retry
def run_bot():
    logger.debug("🚀 Avvio run_bot")
    max_retries = 5
    retry_count = 0

    while retry_count < max_retries:
        try:
            logger.info(f"🔄 Tentativo di connessione {retry_count + 1}/{max_retries}")
            bot.run(TOKEN)
            break
        except Exception as e:
            retry_count += 1
            logger.error(f"❌ Errore nell'avvio del bot (tentativo {retry_count}): {e}")
            if retry_count < max_retries:
                logger.info(f"⏳ Riprovo tra 30 secondi...")
                time.sleep(30)
            else:
                logger.error("🚫 Massimo numero di tentativi raggiunto. Bot terminato.")
                raise

if __name__ == "__main__":
    # Cleanup iniziale
    from utils import cleanup_lock_files
    logger.debug("🗑️ Esecuzione cleanup_lock_files")
    cleanup_lock_files()

    # Log di avvio
    logger.info("🚀 Avvio TrendDuel Bot con Weekly Leaderboard System")
    logger.info(f"📅 Timezone configurato: {ITALY_TZ}")
    logger.info(f"📊 Canale Leaderboard: {LEADERBOARD_CHANNEL_ID}")
    logger.info(f"👑 Canale Hall of Fame: {HALL_OF_FAME_CHANNEL_ID}")
    logger.info(f"📚 Canale Mod Logs: {LOG_CHANNEL_ID}")
    logger.info("⏰ Pubblicazione automatica: Domenica 20:00 CET")

    # Carica cogs e avvia
    asyncio.run(load_cogs())
    run_bot()
