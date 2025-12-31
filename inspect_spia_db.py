import psycopg2
import urllib.parse

# Credenziali
DB_HOST = "aws-1-eu-west-3.pooler.supabase.com"
DB_PORT = "6543"
DB_NAME = "postgres"
DB_USER = "postgres.mgkpvswtxapndwfgsqow"
DB_PASS = "D8%N-.jFyj/ihY4"

print("Recupero schema tabelle Spia...")

try:
    encoded_password = urllib.parse.quote_plus(DB_PASS)
    dsn = f"postgresql://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    conn = psycopg2.connect(dsn)
    cur = conn.cursor()
    
    tables = ["spy_locations", "spy_roles"]
    
    for table in tables:
        print(f"\n--- Schema: {table} ---")
        cur.execute(f"""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = '{table}'
            ORDER BY ordinal_position;
        """)
        columns = cur.fetchall()
        for col in columns:
            print(f"{col[0]} ({col[1]}) - Nullable: {col[2]}")
            
        # Fetch sample data
        print(f"\n--- Sample Data: {table} ---")
        cur.execute(f"SELECT * FROM public.{table} LIMIT 3;")
        rows = cur.fetchall()
        for row in rows:
            print(row)

    conn.close()

except Exception as e:
    print(f"Errore: {e}")
