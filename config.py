# Modified config.py (aggiorna i weights per sommare a 1)
import os
import pytz

# Token (già configurato per Replit con secret)
TOKEN = os.environ['TOKEN']

# ID canali
SUBMISSIONS_CHANNEL_ID = 1412043411447611504  # 📝-submissions
LEADERBOARD_CHANNEL_ID = 1412065710091276408  # 📊-leaderboard
LOG_CHANNEL_ID = 1412065659990573169  # 📚-mod-logs
HALL_OF_FAME_CHANNEL_ID = 1413891338184949931  # 👑-hall-of-fame
SPOTLIGHT_CHANNEL_ID = 1414897584060764243  # ⚡-spotlight 
SPOTLIGHT_ARCHIVE_CHANNEL_ID = 1414918993289936999  # 📦-spotlight-archive

# ID ruoli
FOUNDER_ROLE_ID = 1412039943986872361  # 👑 Founder
ADMIN_ROLE_ID = 1412017806265815102  # 🛡️ Admin
CHALLENGER_ROLE_ID = 1413108254455631922  # ⚔️ Challenger
VIP_ROLE_ID = 1412024635993620511  # 🌟 VIP

# Hashtag ufficiali
HASHTAGS = ['#trendduelofficial', '#trendduelchallenge']

# Timezone per l'Italia
ITALY_TZ = pytz.timezone('Europe/Rome')

# Pesi per i bonus casuali (aggiornati per sommare a 1: 35%,35%,10%,10%,10%)
BONUS_POINTS_WEIGHTS = [0.35, 0.35, 0.1, 0.1, 0.1]  # Per +3,+4,+5,+6,+7
BONUS_REPUTATION_WEIGHTS = [0.35, 0.35, 0.1, 0.1, 0.1]  # Per +1,+2,+3,+4,+5

# Bonus multipiattaforma
MULTIPLATFORM_BONUS_PER_EXTRA = 3        # +3 punti per ogni piattaforma aggiuntiva oltre la prima
MULTIPLATFORM_MAX_USES_PER_WEEK = 2     # massimo usi del bonus per utente a settimana
MULTIPLATFORM_DOMAINS = ['tiktok.com', 'instagram.com', 'youtube.com']  # domini considerati

#Test Assegnazione Badge
TEST_BADGE_MODE = False
TEST_BADGE_WINDOW_HOURS = 1
