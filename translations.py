# translations.py

translations = {
  'it': {
      # generale / comandi
      'stats_title': "📊 Le tue Stats TrendDuel",
      'stats_no_data': "Nessuna stat trovata. Partecipa a una challenge!",
      'stats_total': "📈 Totali",
      'stats_weekly': "📅 Questa Settimana",
      'stats_level': "🎯 Livello",
      'stats_badges': "🏅 Badge",
      'stats_footer': "Stats aggiornate in tempo reale • TrendDuel",
      'stats_value': "**{points}** pts • **{rep}** rep • **{parts}** partecipazioni",
      'stats_level_value': "**{level}** (prossimo a {next_level} pts)",
      'stats_no_badges': "🚫 Nessun achievement sbloccato",
      'stats_week_period': "Settimana: {week_start} - {week_end}",

      # NUOVO SISTEMA DI LIVELLI - TRADUZIONI ITALIANE
      'level_1_title': "🌱 Rookie",
      'level_2_title': "⚔️ Challenger", 
      'level_3_title': "🔥 Hype Challenger",
      'level_4_title': "⚡ Trend Fighter",
      'level_5_title': "🌟 Viral Maker",
      'level_6_title': "🦸 Hype Hero",
      'level_7_title': "🎯 Trendsetter",
      'level_8_title': "🏆 Duel Pro",
      'level_9_title': "🏗️ Viral Architect",
      'level_10_title': "👑 Duel Master",
      'level_11_title': "🌟 Legend",
      'level_12_title': "✨ Viral Legend",

      # STATUS ATTIVITÀ SETTIMANALE
      'activity_status_sleeping': "💤 TRANQUILLO",
      'activity_status_stable': "📊 STABILE", 
      'activity_status_active': "⚡ ATTIVO",
      'activity_status_hot': "🔥 INFUOCATO",

      # comandi (lista)
      'commands_title': "📜 Comandi Disponibili",
      'commands_user_description': "Ecco i comandi che puoi utilizzare:",
      'commands_staff_description': "Comandi disponibili per lo staff:",
      'commands_commands': "📜 `/commands` - Mostra l'elenco dei comandi disponibili",
      'commands_stats': "📊 `/stats` - Mostra le tue statistiche personali",
      'commands_weekly_stats': "📈 `/weekly-stats` - Mostra le statistiche settimanali del server",
      'commands_publish_leaderboard': "📊 `/publish-leaderboard` - Forza la pubblicazione della classifica settimanale",
      'commands_test_leaderboard': "🧪 `/test-leaderboard` - Genera una classifica di test senza archiviare",
      'commands_reset_weekly': "♻️ `/reset-weekly` - Reset manuale delle metriche settimanali",
      'commands_get_leaderboard': "📚 `/get-leaderboard` - Visualizza una classifica archiviata",
      'commands_botstats': "🤖 `/botstats` - Mostra le statistiche del bot",
      'commands_checkpermissions': "🔧 `/checkpermissions` - Verifica i permessi del bot",
      'commands_clear_archives': "🗑️ `/clear-archives` - Svuota l'archivio delle classifiche settimanali",
      'commands_manage_user_stats': "📄 `/manage-user-stats` - Aggiunge o rimuove punti/reputazione a un utente",
      'commands_footer': "TrendDuel • Challenge the world, conquer the hype!",

      # botstats (se usati altrove)
      'botstats_title': "🤖 Statistiche Bot TrendDuel",
      'botstats_uptime': "⏱️ Uptime",
      'botstats_messages': "📨 Messaggi",
      'botstats_reactions': "👍 Reazioni",
      'botstats_users': "👥 Utenti DB",
      'botstats_servers': "🗄️ Server",
      'botstats_active_events': "📅 Eventi Attivi",
      'botstats_archives': "📚 Archivi",
      'botstats_last_activity': "🕐 Ultima attività",
      'botstats_next_leaderboard': "⏰ Prossima classifica",
      'botstats_footer': "Bot versione Weekly Leaderboard • {datetime}",

      # checkpermissions
      'checkpermissions_title': "🔧 Verifica Permessi Bot",
      'checkpermissions_status': "Status Permessi:",
      'checkpermissions_missing': "⚠️ Azioni richieste:",
      'checkpermissions_missing_text': "Il bot potrebbe non funzionare correttamente. Contatta un amministratore del server per aggiungere i permessi mancanti.",
      'checkpermissions_ok': "✅ Tutto OK:",
      'checkpermissions_ok_text': "Il bot ha tutti i permessi necessari per funzionare correttamente!",

      # gestione / errori / duplicati
      'manage_user_stats_success_title': "✅ Modifica Statistiche Completata",
      'manage_user_stats_self_error': "Non puoi modificare le tue statistiche!",
      'duplicate_message': "⚠️ Messaggio duplicato: non assegnati punti o partecipazioni.",
      'duplicate_same_user': "Hai già pubblicato questo messaggio, non verranno assegnati punti aggiuntivi.",
      'duplicate_other_user': "Non puoi pubblicare lo stesso messaggio già inviato da un altro utente.",
      'publish_leaderboard_success': "📊 Classifica pubblicata con successo",
      'publish_leaderboard_success_text': "La classifica per la settimana {week_start} - {week_end} è stata pubblicata nel canale #leaderboard.",
      'publish_leaderboard_failed': "⌐ Errore nella pubblicazione",
      'publish_leaderboard_failed_text': "Impossibile pubblicare la classifica, controlla i log per dettagli.",
      'invalid_no_hashtag': "⚠️ Messaggio rimosso: devi includere almeno un hashtag ufficiale (#trendduelofficial o #trendduelchallenge).",
      'invalid_no_permitted_link': "⚠️ Messaggio rimosso: il tuo messaggio non contiene un link social valido. Sono consentiti solo Instagram, TikTok e YouTube.",
      'duplicate_reaction_spotlight': "⚠️ Non puoi reagire in #⚡-spotlight se hai già reagito con 💯 o 👍 al messaggio originale in #📝-submissions.",
      'multiplatform_limit_reached': "Hai raggiunto il limite settimanale di {max_uses} bonus multipiattaforma. Il bonus multipiattaforma non è stato applicato a questo messaggio, ma i +10 punti di partecipazione sono stati comunque assegnati secondo le regole.",

      # CHIAVI AGGIUNTE PER /stats (IT)
      'stats_profile_header': "📊 PROFILO STATISTICHE",
      'stats_rank_title': "CLASSIFICA GLOBALE",
      'stats_position': "Posizione",
      'stats_percentile': "Top {percentile}% dei giocatori",
      'stats_overview_title': "STATISTICHE GENERALI",
      'stats_total_points': "💎 Punti Totali",
      'stats_reputation': "⭐ Reputazione", 
      'stats_participations': "🎮 Partecipazioni",
      'stats_progress': "🎯 Progresso al Livello",
      'stats_weekly_title': "ATTIVITÀ SETTIMANALE",
      'stats_weekly_points': "🚀 Punti",
      'stats_weekly_reputation': "⭐ Reputazione",
      'stats_weekly_activities': "🎯 Attività",
      'stats_activity_index': "🔥 Status",
      'stats_achievement_title': "ACHIEVEMENTS SBLOCCATI",
      'stats_congratulations_title': "CONGRATULAZIONI!",
      'stats_congratulations_text': "🌟 Hai raggiunto il rango di **{label}**!\nSei tra i giocatori più dedicati della community! 🏆",
      'stats_error_loading': "❌ Si è verificato un errore nel caricamento delle statistiche. Riprova tra poco!",
      'stats_footer_long': "{base_text} • Aggiornato: {timestamp}",
      'author_veteran': "GIOCATORE VETERANO",
      'author_expert': "GIOCATORE ESPERTO", 
      'author_legendary': "GIOCATORE LEGGENDARIO",
      'legend_label': "LEGGENDA",
      'points_to_next_level': "Mancano {points} punti",
      'max_level_reached': "LIVELLO MASSIMO!",

      # badge translations (keeper: puoi modificare come preferisci)
      'badge_Hype_Starter': '🌟 Hype Starter',
      'badge_Trend_Conqueror': '👑 Trend Conqueror',
      'badge_Community_Leader': '🚀 Community Leader',
      'badge_Engagement_Master': '💎 Engagement Master',
      'badge_Weekly_Champion': '🏆 Weekly Champion',
      'badge_Streak_Legend': '⚡ Streak Legend'
  },
  'en': {
      # generale / comandi
      'stats_title': "📊 Your TrendDuel Stats",
      'stats_no_data': "No stats found. Participate in a challenge!",
      'stats_total': "📈 Totals",
      'stats_weekly': "📅 This Week",
      'stats_level': "🎯 Level",
      'stats_badges': "🏅 Badges",
      'stats_footer': "Stats updated in real-time • TrendDuel",
      'stats_value': "**{points}** pts • **{rep}** rep • **{parts}** participations",
      'stats_level_value': "**{level}** (next at {next_level} pts)",
      'stats_no_badges': "🚫 No achievements unlocked",
      'stats_week_period': "Week: {week_start} - {week_end}",

      # NEW LEVEL SYSTEM - ENGLISH TRANSLATIONS
      'level_1_title': "🌱 Rookie",
      'level_2_title': "⚔️ Challenger",
      'level_3_title': "🔥 Hype Challenger", 
      'level_4_title': "⚡ Trend Fighter",
      'level_5_title': "🌟 Viral Maker",
      'level_6_title': "🦸 Hype Hero",
      'level_7_title': "🎯 Trendsetter",
      'level_8_title': "🏆 Duel Pro",
      'level_9_title': "🏗️ Viral Architect",
      'level_10_title': "👑 Duel Master",
      'level_11_title': "🌟 Legend",
      'level_12_title': "✨ Viral Legend",

      # WEEKLY ACTIVITY STATUS
      'activity_status_sleeping': "💤 SLEEPING",
      'activity_status_stable': "📊 STABLE",
      'activity_status_active': "⚡ ACTIVE", 
      'activity_status_hot': "🔥 HOT",

      # comandi
      'commands_title': "📜 Available Commands",
      'commands_user_description': "Here are the commands you can use:",
      'commands_staff_description': "Commands available for staff:",
      'commands_commands': "📜 `/commands` - Shows the list of available commands",
      'commands_stats': "📊 `/stats` - Shows your personal statistics",
      'commands_weekly_stats': "📈 `/weekly-stats` - Shows the server's weekly statistics",
      'commands_publish_leaderboard': "📊 `/publish-leaderboard` - Force the publication of the weekly leaderboard",
      'commands_test_leaderboard': "🧪 `/test-leaderboard` - Generate a test leaderboard without archiving",
      'commands_reset_weekly': "♻️ `/reset-weekly` - Manually reset weekly metrics",
      'commands_get_leaderboard': "📚 `/get-leaderboard` - View an archived leaderboard",
      'commands_botstats': "🤖 `/botstats` - Show bot statistics",
      'commands_checkpermissions': "🔧 `/checkpermissions` - Check bot permissions",
      'commands_clear_archives': "🗑️ `/clear-archives` - Clear the archive of weekly leaderboards",
      'commands_manage_user_stats': "📄 `/manage-user-stats` - Add or remove points/reputation for a user",
      'commands_footer': "TrendDuel • Challenge the world, conquer the hype!",

      # botstats
      'botstats_title': "🤖 TrendDuel Bot Statistics",
      'botstats_uptime': "⏱️ Uptime",
      'botstats_messages': "📨 Messages",
      'botstats_reactions': "👍 Reactions",
      'botstats_users': "👥 Users in DB",
      'botstats_servers': "🗄️ Servers",
      'botstats_active_events': "📅 Active Events",
      'botstats_archives': "📚 Archives",
      'botstats_last_activity': "🕐 Last Activity",
      'botstats_next_leaderboard': "⏰ Next Leaderboard",
      'botstats_footer': "Bot version Weekly Leaderboard • {datetime}",

      # checkpermissions
      'checkpermissions_title': "🔧 Bot Permissions Check",
      'checkpermissions_status': "Permissions Status:",
      'checkpermissions_missing': "⚠️ Actions Required:",
      'checkpermissions_missing_text': "The bot may not function properly. Contact a server administrator to add the missing permissions.",
      'checkpermissions_ok': "✅ All Good:",
      'checkpermissions_ok_text': "The bot has all necessary permissions to function correctly!",

      # gestione / errori / duplicati
      'manage_user_stats_success_title': "✅ Statistics Update Completed",
      'manage_user_stats_self_error': "You cannot modify your own statistics!",
      'duplicate_message': "⚠️ Duplicate message: no points or participations awarded.",
      'duplicate_same_user': "You have already posted this message, no additional points will be awarded.",
      'duplicate_other_user': "You cannot post the same message already sent by another user.",
      'publish_leaderboard_success': "📊 Leaderboard published successfully",
      'publish_leaderboard_success_text': "The leaderboard for the week {week_start} - {week_end} has been published in the #leaderboard channel.",
      'publish_leaderboard_failed': "⌐ Publication failed",
      'publish_leaderboard_failed_text': "Unable to publish the leaderboard, check logs for details.",
      'invalid_no_hashtag': "⚠️ Message removed: you must include at least one official hashtag (#trendduelofficial or #trendduelchallenge).",
      'invalid_no_permitted_link': "⚠️ Message removed: your message does not contain a valid social link. Only Instagram, TikTok, and YouTube are allowed.",
      'duplicate_reaction_spotlight': "⚠️ You cannot react in #⚡-spotlight if you have already reacted with 💯 or 👍 to the original message in #📝-submissions.",
      'multiplatform_limit_reached': "You've reached the weekly limit of {max_uses} multiplatform bonuses. The multiplatform bonus was not applied to this message, but the +10 participation points have already been awarded according to the rules.",

      # KEYS ADDED FOR /stats (EN)
      'stats_profile_header': "📊 STATISTICS PROFILE",
      'stats_rank_title': "GLOBAL RANKING",
      'stats_position': "Position",
      'stats_percentile': "Top {percentile}% of players",
      'stats_overview_title': "GENERAL STATISTICS",
      'stats_total_points': "💎 Total Points",
      'stats_reputation': "⭐ Reputation",
      'stats_participations': "🎮 Participations",
      'stats_progress': "🎯 Progress to Level",
      'stats_weekly_title': "WEEKLY ACTIVITY",
      'stats_weekly_points': "🚀 Points",
      'stats_weekly_reputation': "⭐ Reputation",
      'stats_weekly_activities': "🎯 Activities",
      'stats_activity_index': "🔥 Status",
      'stats_achievement_title': "UNLOCKED ACHIEVEMENTS",
      'stats_congratulations_title': "CONGRATULATIONS!",
      'stats_congratulations_text': "🌟 You've reached the rank of **{label}**!\nYou're among the most dedicated players in the community! 🏆",
      'stats_error_loading': "❌ An error occurred while loading your statistics. Please try again shortly.",
      'stats_footer_long': "{base_text} • Updated: {timestamp}",
      'author_veteran': "VETERAN PLAYER",
      'author_expert': "EXPERT PLAYER",
      'author_legendary': "LEGENDARY PLAYER", 
      'legend_label': "LEGEND",
      'points_to_next_level': "{points} points needed",
      'max_level_reached': "MAX LEVEL!",

      # badge translations (keep / edit as needed)
      'badge_Hype_Starter': '🌟 Hype Starter',
      'badge_Trend_Conqueror': '👑 Trend Conqueror',
      'badge_Community_Leader': '🚀 Community Leader',
      'badge_Engagement_Master': '💎 Engagement Master',
      'badge_Weekly_Champion': '🏆 Weekly Champion',
      'badge_Streak_Legend': '⚡ Streak Legend'
  }
}

def get_translation(key, locale, **kwargs):
  """Restituisce la traduzione per la chiave specificata in base alla lingua."""
  lang = 'it' if isinstance(locale, str) and locale.startswith('it') else 'en'
  text = translations.get(lang, translations['en']).get(key, key)
  try:
    return text.format(**kwargs)
  except Exception:
    # fallback: ritorna il testo raw in caso di problemi di formatting
    return text