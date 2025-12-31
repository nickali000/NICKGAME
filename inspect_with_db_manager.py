import sys
import os

# Carica variabili d'ambiente da .env
try:
    with open('.env', 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                key, value = line.split('=', 1)
                os.environ[key] = value
                print(f"Caricata env: {key}")
except Exception as e:
    print(f"Errore caricamento .env: {e}")

# Aggiungi la directory python-server al path per importare i moduli
sys.path.append(os.path.join(os.getcwd(), 'python-server'))

from db_manager import DBManager

print("Inizializzazione DBManager...")
try:
    db = DBManager()
    # DBManager si connette nel costruttore
    
    if db.conn is None:
        print("Errore: DBManager non è riuscito a connettersi.")
        sys.exit(1)

    print("Connessione riuscita. Recupero schema...")
    
    tables = ["spy_locations", "spy_roles"]
    
    with db.get_cursor() as cur:
        for table in tables:
            print(f"\n--- Schema: {table} ---")
            try:
                cur.execute(f"""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_name = '{table}'
                    ORDER BY ordinal_position;
                """)
                columns = cur.fetchall()
                if not columns:
                    print(f"Tabella {table} non trovata o vuota.")
                for col in columns:
                    print(f"{col['column_name']} ({col['data_type']}) - Nullable: {col['is_nullable']}")
                
                # Fetch sample data
                print(f"\n--- Sample Data: {table} ---")
                cur.execute(f"SELECT * FROM public.{table} LIMIT 3;")
                rows = cur.fetchall()
                for row in rows:
                    print(row)
            except Exception as e:
                print(f"Errore query su {table}: {e}")
                db.conn.rollback()

    print("\nFinito.")

except Exception as e:
    print(f"Errore critico: {e}")
