import os
import psycopg2
from psycopg2.extras import RealDictCursor

# Connection string from user (password inserted via env var or direct string for now as requested)
# postgres://postgres.mgkpvswtxapndwfgsqow:[YOUR-PASSWORD]@aws-1-eu-west-3.pooler.supabase.com:6543/postgres
DB_HOST = "aws-1-eu-west-3.pooler.supabase.com"
DB_PORT = "6543"
DB_NAME = "postgres"
DB_USER = "postgres.mgkpvswtxapndwfgsqow"
DB_PASS = os.getenv("DB_PASS")

if not DB_PASS:
    # Fallback for local dev ONLY if explicitly allowed, otherwise warn/error
    # For now, we just print a warning to logs, but do NOT hardcode the production password here.
    print("WARNING: DB_PASS environment variable not set!")


class DBManager:
    def __init__(self):
        self.conn = None
        self.connect()
        self.init_db()

    def connect(self):
        try:
            # Use DSN with URL encoded password to handle special characters safely
            import urllib.parse
            encoded_password = urllib.parse.quote_plus(DB_PASS)
            dsn = f"postgresql://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
            
            self.conn = psycopg2.connect(dsn)
            print("Connected to Supabase DB")
        except Exception as e:
            print(f"Database connection failed: {e}")
            self.conn = None

    def get_cursor(self):
        if self.conn is None or self.conn.closed:
            self.connect()
        
        if self.conn is None:
            raise Exception("Database connection is unavailable")

        try:
            # Test connection
            with self.conn.cursor() as cur:
                cur.execute("SELECT 1")
        except psycopg2.OperationalError:
            print("DB Connection lost, reconnecting...")
            self.connect()
            if self.conn is None:
                raise Exception("Database connection is unavailable after reconnect")
            
        return self.conn.cursor(cursor_factory=RealDictCursor)

    def init_db(self):
        """Initialize tables if they don't exist"""
        with self.get_cursor() as cur:
            # For dev/scratchpad, let's drop to ensure schema matches
            # cur.execute("DROP TABLE IF EXISTS players;")
            # cur.execute("DROP TABLE IF EXISTS rooms;")
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS games (
                    id VARCHAR(50) PRIMARY KEY,
                    name VARCHAR(100),
                    min_players INT,
                    max_players INT,
                    description TEXT,
                    enabled BOOLEAN DEFAULT true
                );
                CREATE TABLE IF NOT EXISTS rooms (
                    id VARCHAR(10) PRIMARY KEY,
                    admin_id VARCHAR(50),
                    game_type VARCHAR(50),
                    state TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (game_type) REFERENCES games(id)
                );
                CREATE TABLE IF NOT EXISTS players (
                    id VARCHAR(50),
                    room_id VARCHAR(10),
                    nickname VARCHAR(50),
                    role VARCHAR(50),
                    PRIMARY KEY (id, room_id),
                    FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS player_roles (
                    room_id VARCHAR(50) NOT NULL,
                    player_id VARCHAR(50) NOT NULL,
                    role VARCHAR(50),
                    PRIMARY KEY (room_id, player_id),
                    FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS game_votes (
                    room_id VARCHAR(50) NOT NULL,
                    voter_id VARCHAR(50) NOT NULL,
                    target_id VARCHAR(50) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (room_id, voter_id, target_id),
                    FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS game_scores (
                    room_id VARCHAR(50) NOT NULL,
                    player_id VARCHAR(50) NOT NULL,
                    score INTEGER DEFAULT 0,
                    PRIMARY KEY (room_id, player_id),
                    FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE
                );
            """)
            self.conn.commit()
            
            # Insert default games (Upsert)
            games_to_insert = [
                ('secret_hitler', 'Secret Hitler', 5, 10, 'A social deduction game', True),
                ('dodgeball', 'Dodgeball', 4, 8, 'A fast-paced action game', True),
                ('spia', 'Spia', 3, 10, 'Find the spy!', True),
                ('parola_segreta', 'Parola Segreta', 3, 10, 'Find the impostor with a different word', True)
            ]
            
            for g in games_to_insert:
                cur.execute("""
                    INSERT INTO games (id, name, min_players, max_players, description, enabled)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        min_players = EXCLUDED.min_players,
                        max_players = EXCLUDED.max_players,
                        description = EXCLUDED.description,
                        enabled = EXCLUDED.enabled
                """, g)
            
            self.conn.commit()
            print("Upserted default games")

            # Create parola_segreta table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS parola_segreta (
                    id SERIAL PRIMARY KEY,
                    parola_impostore TEXT NOT NULL,
                    parola_giocatori TEXT NOT NULL
                );
            """)
            self.conn.commit()

            # Seed parola_segreta if empty
            cur.execute("SELECT COUNT(*) as count FROM parola_segreta")
            if cur.fetchone()['count'] == 0:
                cur.execute("""
                    INSERT INTO parola_segreta (parola_impostore, parola_giocatori) VALUES
                    ('Peter Pan', 'Pirata'),
                    ('Superman', 'Batman'),
                    ('Pizza', 'Pasta'),
                    ('Cane', 'Gatto'),
                    ('Sole', 'Luna'),
                    ('Mare', 'Montagna'),
                    ('Calcio', 'Basket'),
                    ('Mela', 'Pera'),
                    ('Vino', 'Birra'),
                    ('Estate', 'Inverno')
                """)
                self.conn.commit()
                print("Inserted default secret words")

    def create_room(self, room_id, admin_id):
        with self.get_cursor() as cur:
            cur.execute("INSERT INTO rooms (id, admin_id) VALUES (%s, %s)", (room_id, admin_id))
            self.conn.commit()

    def get_room(self, room_id):
        with self.get_cursor() as cur:
            cur.execute("SELECT * FROM rooms WHERE id = %s", (room_id,))
            return cur.fetchone()

    def add_player(self, room_id, player_id, nickname):
        with self.get_cursor() as cur:
            # Check if exists
            cur.execute("SELECT * FROM players WHERE id = %s AND room_id = %s", (player_id, room_id))
            if not cur.fetchone():
                cur.execute("INSERT INTO players (id, room_id, nickname) VALUES (%s, %s, %s)", 
                            (player_id, room_id, nickname))
                self.conn.commit()

    def get_players(self, room_id):
        with self.get_cursor() as cur:
            cur.execute("SELECT * FROM players WHERE room_id = %s", (room_id,))
            return cur.fetchall()

    def set_game(self, room_id, game_type):
        with self.get_cursor() as cur:
            cur.execute("UPDATE rooms SET game_type = %s WHERE id = %s", (game_type, room_id))
            self.conn.commit()
            
    def get_all_rooms(self):
        with self.get_cursor() as cur:
            cur.execute("""
                SELECT r.id, r.game_type, COUNT(p.id) as player_count 
                FROM rooms r 
                LEFT JOIN players p ON r.id = p.room_id 
                GROUP BY r.id, r.game_type
            """)
            return cur.fetchall()
    
    def get_available_games(self):
        """Get all enabled games"""
        with self.get_cursor() as cur:
            cur.execute("SELECT id, name, min_players, max_players, description FROM games WHERE enabled = true ORDER BY name")
            return cur.fetchall()
    
    def delete_room(self, room_id):
        """Delete a room and all associated players"""
        with self.get_cursor() as cur:
            # Delete players first (foreign key constraint)
            cur.execute("DELETE FROM players WHERE room_id = %s", (room_id,))
            # Delete room
            cur.execute("DELETE FROM rooms WHERE id = %s", (room_id,))
            self.conn.commit()
    
    def set_player_role(self, room_id, player_id, role):
        """Set the role for a player in a room using player_roles table"""
        with self.get_cursor() as cur:
            # Upsert role
            cur.execute("""
                INSERT INTO player_roles (room_id, player_id, role) 
                VALUES (%s, %s, %s)
                ON CONFLICT (room_id, player_id) 
                DO UPDATE SET role = EXCLUDED.role
            """, (room_id, player_id, role))
            self.conn.commit()
    
    def get_player_roles(self, room_id):
        """Get all player roles for a room"""
        with self.get_cursor() as cur:
            cur.execute("""
                SELECT p.id, p.nickname, pr.role 
                FROM players p
                LEFT JOIN player_roles pr ON p.id = pr.player_id AND p.room_id = pr.room_id
                WHERE p.room_id = %s
            """, (room_id,))
            return cur.fetchall()

    def set_room_state(self, room_id, state):
        """Update the state of a room (e.g. 'PLAYING', 'LOBBY')"""
        with self.get_cursor() as cur:
            cur.execute("UPDATE rooms SET state = %s WHERE id = %s", (state, room_id))
            self.conn.commit()

    def update_game_data(self, room_id, game_data):
        """Update the game_data JSONB column for a room"""
        import json
        with self.get_cursor() as cur:
            cur.execute("UPDATE rooms SET game_data = %s WHERE id = %s", (json.dumps(game_data), room_id))
            self.conn.commit()

    def get_game_data(self, room_id):
        """Get the game_data for a room"""
        with self.get_cursor() as cur:
            cur.execute("SELECT game_data FROM rooms WHERE id = %s", (room_id,))
            result = cur.fetchone()
            return result['game_data'] if result else {}

    def get_secret_hitler_state(self, room_id):
        """Get the Secret Hitler game state for a room"""
        with self.get_cursor() as cur:
            cur.execute("SELECT * FROM secret_hitler_states WHERE room_id = %s", (room_id,))
            return cur.fetchone()

    def update_secret_hitler_state(self, room_id, state_data):
        """Update or insert Secret Hitler game state"""
        import json
        with self.get_cursor() as cur:
            cur.execute("""
                INSERT INTO secret_hitler_states (
                    room_id, president_id, chancellor_id, chancellor_candidate_id,
                    liberal_policies, fascist_policies, election_tracker,
                    deck, discard_pile, phase, votes, turn_order, roles,
                    drawn_policies, last_enacted, winner,
                    veto_unlocked, investigated_player, peeked_policies, special_election_next, dead_players,
                    last_president_id, last_chancellor_id, public_investigation, purge_remaining
                ) VALUES (
                    %(room_id)s, %(president_id)s, %(chancellor_id)s, %(chancellor_candidate_id)s,
                    %(liberal_policies)s, %(fascist_policies)s, %(election_tracker)s,
                    %(deck)s, %(discard_pile)s, %(phase)s, %(votes)s, %(turn_order)s, %(roles)s,
                    %(drawn_policies)s, %(last_enacted)s, %(winner)s,
                    %(veto_unlocked)s, %(investigated_player)s, %(peeked_policies)s, %(special_election_next)s, %(dead_players)s,
                    %(last_president_id)s, %(last_chancellor_id)s, %(public_investigation)s, %(purge_remaining)s
                )
                ON CONFLICT (room_id) DO UPDATE SET
                    president_id = EXCLUDED.president_id,
                    chancellor_id = EXCLUDED.chancellor_id,
                    chancellor_candidate_id = EXCLUDED.chancellor_candidate_id,
                    liberal_policies = EXCLUDED.liberal_policies,
                    fascist_policies = EXCLUDED.fascist_policies,
                    election_tracker = EXCLUDED.election_tracker,
                    deck = EXCLUDED.deck,
                    discard_pile = EXCLUDED.discard_pile,
                    phase = EXCLUDED.phase,
                    votes = EXCLUDED.votes,
                    turn_order = EXCLUDED.turn_order,
                    roles = EXCLUDED.roles,
                    drawn_policies = EXCLUDED.drawn_policies,
                    last_enacted = EXCLUDED.last_enacted,
                    winner = EXCLUDED.winner,
                    veto_unlocked = EXCLUDED.veto_unlocked,
                    investigated_player = EXCLUDED.investigated_player,
                    peeked_policies = EXCLUDED.peeked_policies,
                    special_election_next = EXCLUDED.special_election_next,
                    dead_players = EXCLUDED.dead_players,
                    last_president_id = EXCLUDED.last_president_id,
                    last_chancellor_id = EXCLUDED.last_chancellor_id,
                    public_investigation = EXCLUDED.public_investigation,
                    purge_remaining = EXCLUDED.purge_remaining
            """, {
                'room_id': room_id,
                'president_id': state_data.get('president_candidate'),
                'chancellor_id': state_data.get('chancellor'),
                'chancellor_candidate_id': state_data.get('chancellor_candidate'),
                'liberal_policies': state_data.get('policies', {}).get('Liberal', 0),
                'fascist_policies': state_data.get('policies', {}).get('Fascist', 0),
                'election_tracker': state_data.get('election_tracker', 0),
                'deck': json.dumps(state_data.get('deck', [])),
                'discard_pile': json.dumps(state_data.get('discard_pile', [])),
                'phase': state_data.get('phase'),
                'votes': json.dumps(state_data.get('votes', {})),
                'turn_order': json.dumps(state_data.get('turn_order', [])),
                'roles': json.dumps(state_data.get('roles', {})),
                'drawn_policies': json.dumps(state_data.get('drawn_policies', [])),
                'last_enacted': state_data.get('last_enacted'),
                'winner': state_data.get('winner'),
                'veto_unlocked': state_data.get('veto_unlocked', False),
                'investigated_player': json.dumps(state_data.get('investigated_player')),
                'peeked_policies': json.dumps(state_data.get('peeked_policies', [])),
                'special_election_next': state_data.get('special_election_next'),
                'dead_players': json.dumps(state_data.get('dead_players', [])),
                'last_president_id': state_data.get('last_president_id'),
                'last_chancellor_id': state_data.get('last_chancellor_id'),
                'public_investigation': json.dumps(state_data.get('public_investigation')),
                'purge_remaining': state_data.get('purge_remaining', 0)
            })
            self.conn.commit()

    def delete_secret_hitler_state(self, room_id):
        """Delete the Secret Hitler game state for a room"""
        with self.get_cursor() as cur:
            cur.execute("DELETE FROM secret_hitler_states WHERE room_id = %s", (room_id,))
            self.conn.commit()

    def cast_vote(self, room_id, voter_id, target_id):
        """Cast a vote (can be called multiple times for multiple targets)"""
        with self.get_cursor() as cur:
            cur.execute("""
                INSERT INTO game_votes (room_id, voter_id, target_id)
                VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (room_id, voter_id, target_id))
            self.conn.commit()

    def get_votes(self, room_id):
        """Get all votes for a room"""
        with self.get_cursor() as cur:
            cur.execute("SELECT * FROM game_votes WHERE room_id = %s", (room_id,))
            return cur.fetchall()

    def clear_votes(self, room_id):
        """Clear all votes for a room"""
        with self.get_cursor() as cur:
            cur.execute("DELETE FROM game_votes WHERE room_id = %s", (room_id,))
            self.conn.commit()

    def update_score(self, room_id, player_id, points):
        with self.get_cursor() as cur:
            cur.execute("""
                INSERT INTO game_scores (room_id, player_id, score)
                VALUES (%s, %s, %s)
                ON CONFLICT (room_id, player_id)
                DO UPDATE SET score = game_scores.score + EXCLUDED.score
            """, (room_id, player_id, points))
            self.conn.commit()

    def get_scores(self, room_id):
        with self.get_cursor() as cur:
            cur.execute("SELECT player_id, score FROM game_scores WHERE room_id = %s ORDER BY score DESC", (room_id,))
            return cur.fetchall()

    def reset_scores(self, room_id):
        with self.get_cursor() as cur:
            cur.execute("DELETE FROM game_scores WHERE room_id = %s", (room_id,))
            self.conn.commit()

    def update_global_score(self, user_id, points):
        """Update the global score for a user"""
        with self.get_cursor() as cur:
            # Create users table if not exists (lazy init)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id VARCHAR(50) PRIMARY KEY,
                    global_score INTEGER DEFAULT 0
                )
            """)
            cur.execute("""
                INSERT INTO users (id, global_score)
                VALUES (%s, %s)
                ON CONFLICT (id)
                DO UPDATE SET global_score = users.global_score + EXCLUDED.global_score
            """, (user_id, points))
            self.conn.commit()

    def get_global_score(self, user_id):
        with self.get_cursor() as cur:
            cur.execute("SELECT global_score FROM users WHERE id = %s", (user_id,))
            res = cur.fetchone()
            return res['global_score'] if res else 0

    def get_random_word_pair(self):
        """Get a random word pair for Parola Segreta game"""
        with self.get_cursor() as cur:
            cur.execute("SELECT * FROM parola_segreta ORDER BY RANDOM() LIMIT 1")
            return cur.fetchone()
