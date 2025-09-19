import sqlite3
import sys

DB_PATH = "trendduel.db"  # cambialo col nome del tuo DB

def query(message_id, author_id=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    print("== reactions for message_id =", message_id)
    c.execute("SELECT message_id, user_id, emoji, points_given, reputation_given FROM reactions WHERE message_id = ?", (message_id,))
    rows = c.fetchall()
    for r in rows:
        print(r)
    if not rows:
        print("  (no reactions rows)")

    print("\n== user row for author_id =", author_id)
    if author_id:
        c.execute("SELECT user_id, points, reputation, participations, badges FROM users WHERE user_id = ?", (author_id,))
        u = c.fetchone()
        print(u if u else "  (no user row)")

    print("\n== spotlight_reposts mapping")
    c.execute("SELECT original_message_id, spotlight_message_id, user_id, week_start, timestamp FROM spotlight_reposts WHERE original_message_id = ? OR spotlight_message_id = ?", (message_id, message_id))
    m = c.fetchall()
    for mm in m:
        print(mm)
    if not m:
        print("  (no spotlight_reposts mapping)")

    conn.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python check_db.py <message_id> [author_id]")
        sys.exit(1)
    mid = int(sys.argv[1])
    aid = int(sys.argv[2]) if len(sys.argv) > 2 else None
    query(mid, aid)
