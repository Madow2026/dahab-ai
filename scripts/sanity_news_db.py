import os
import sqlite3


def main() -> int:
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dahab_ai.db")
    if not os.path.exists(db_path):
        print("db_missing", db_path)
        return 2

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM news")
    print("news_count", cur.fetchone()[0])

    cur.execute("SELECT MAX(fetched_at) FROM news")
    print("max_fetched_at", cur.fetchone()[0])

    cur.execute("SELECT source, COUNT(*) FROM news GROUP BY source ORDER BY COUNT(*) DESC")
    print("by_source", cur.fetchall())

    cur.execute(
        "SELECT id, source, fetched_at, substr(title_en,1,90), url FROM news ORDER BY id DESC LIMIT 10"
    )
    rows = cur.fetchall()
    print("latest_10")
    for r in rows:
        print(r)

    # Basic URL sanity
    cur.execute("SELECT COUNT(*) FROM news WHERE url IS NULL OR TRIM(url) = ''")
    print("missing_url_rows", cur.fetchone()[0])

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
