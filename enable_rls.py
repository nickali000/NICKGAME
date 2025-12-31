import psycopg2
import sys
import urllib.parse

# Credenziali
DB_HOST = "aws-1-eu-west-3.pooler.supabase.com"
DB_PORT = "6543"
DB_NAME = "postgres"
DB_USER = "postgres.mgkpvswtxapndwfgsqow"
DB_PASS = "D8%N-.jFyj/ihY4"

# Tabelle segnalate
TABLES = [
    "spy_roles",
    "players",
    "rooms",
    "games",
    "player_roles",
    "secret_hitler_states",
    "spy_locations"
]

print("Connessione al database per abilitare RLS (metodo DSN)...")

try:
    encoded_password = urllib.parse.quote_plus(DB_PASS)
    dsn = f"postgresql://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    
    conn = psycopg2.connect(dsn)
    cur = conn.cursor()
    
    for table in TABLES:
        try:
            # Abilita RLS
            print(f"Abilitazione RLS su {table}...")
            cur.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY;")
            
            # Crea policy permissiva
            policy_name = f"allow_all_{table}"
            print(f"Creazione policy {policy_name}...")
            cur.execute(f"""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_policies 
                        WHERE tablename = '{table}' AND policyname = '{policy_name}'
                    ) THEN
                        CREATE POLICY {policy_name} ON public.{table} FOR ALL USING (true) WITH CHECK (true);
                    END IF;
                END
                $$;
            """)
            conn.commit()
            print(f"OK: {table}")
        except Exception as e:
            conn.rollback()
            print(f"ERRORE su {table}: {e}")
            
    conn.close()
    print("Operazione completata.")

except Exception as e:
    print(f"Errore di connessione: {e}")
