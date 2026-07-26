import sqlite3

conn = sqlite3.connect('games.db')
cur = conn.cursor()

cur.execute('SELECT COUNT(*) FROM games WHERE platform="gog"')
gog_count = cur.fetchone()[0]
print(f'GOG games: {gog_count}')

cur.execute('SELECT COUNT(*) FROM games')
total_count = cur.fetchone()[0]
print(f'Total games: {total_count}')

if gog_count > 0:
    cur.execute('SELECT id, title, platform FROM games WHERE platform="gog" LIMIT 5')
    print('\nSample GOG games:')
    for row in cur.fetchall():
        print(f'  {row}')

conn.close()
