from db_manager import DBManager

db = DBManager()
with db.get_cursor() as cur:
    cur.execute("SELECT * FROM games")
    games = cur.fetchall()
    print("Games in DB:")
    for game in games:
        print(f"- {game['id']}: {game['name']}")
