import random
from .base_game import BaseGame
from flask import render_template

class SpiaGame(BaseGame):
    def __init__(self, room_id, db):
        super().__init__(room_id, db)
        self.game_type = "spia"
        self.location = None
        self.spy_ids = []
        self.player_roles = {}  # player_id -> role_name
        self.special_event = None # "double_points", "all_spies" or None
        self.votes = {} # player_id -> voted_player_id
        self.winner = None
        self.winner_reason = None
        self.state = "LOBBY"
        self.spy_possible_locations = [] # Persisted list of options for spy
        self.last_round_results = [] # Results of the last round
        self.spy_actions = {} # player_id -> {type: 'guess'|'pass', location: ...}
        
        # Try to load state if game is already playing
        self._load_state()

    def _save_state(self):
        state_data = {
            "location": self.location,
            "spy_ids": self.spy_ids,
            "player_roles": self.player_roles,
            "special_event": self.special_event,
            "votes": self.votes,
            "winner": self.winner,
            "winner_reason": self.winner_reason,
            "state": self.state,
            "spy_possible_locations": self.spy_possible_locations,
            "last_round_results": self.last_round_results,
            "spy_actions": self.spy_actions
        }
        self.db.update_game_data(self.room_id, state_data)

    def _load_state(self):
        data = self.db.get_game_data(self.room_id)
        if data:
            self.location = data.get("location")
            self.spy_ids = data.get("spy_ids", [])
            self.player_roles = data.get("player_roles", {})
            self.special_event = data.get("special_event")
            self.votes = data.get("votes", {})
            self.winner = data.get("winner")
            self.winner_reason = data.get("winner_reason")
            self.state = data.get("state", "LOBBY")
            self.spy_possible_locations = data.get("spy_possible_locations", [])
            self.last_round_results = data.get("last_round_results", [])
            self.spy_actions = data.get("spy_actions", {})
            
            # Sync roles from player_roles table if available
            db_roles = self.db.get_player_roles(self.room_id)
            if db_roles:
                for r in db_roles:
                    if r['role']:
                        self.player_roles[r['id']] = r['role']

    def add_player(self, player_id, nickname):
        if player_id not in [p['id'] for p in self.players]:
            self.players.append({'id': player_id, 'nickname': nickname})

    def start_game(self):
        try:
            # 1. Fetch Random Location
            with self.db.get_cursor() as cur:
                cur.execute("SELECT * FROM spy_locations ORDER BY RANDOM() LIMIT 1")
                loc_row = cur.fetchone()
                if not loc_row:
                    print("Error: No locations found in DB")
                    return False
                self.location = loc_row['name']
                location_id = loc_row['id']

                # 2. Fetch Roles for Location
                cur.execute("SELECT name FROM spy_roles WHERE location_id = %s", (location_id,))
                roles_rows = cur.fetchall()
                available_roles = [r['name'] for r in roles_rows]

            # 3. Determine Special Events (10% chance each)
            rand = random.random()
            if rand < 0.1:
                self.special_event = "double_points"
            elif rand < 0.2:
                self.special_event = "all_spies"
            else:
                self.special_event = None

            # 4. Assign Roles
            num_players = len(self.players)
            if num_players < 3:
                 # Fallback for testing with few players
                 pass 

            # Determine Spies
            if self.special_event == "all_spies":
                self.spy_ids = [p['id'] for p in self.players]
                for p in self.players:
                    self.player_roles[p['id']] = "Spia"
                    self.db.set_player_role(self.room_id, p['id'], "Spia")
            else:
                # Dynamic Spy Count: Random between 1 and (Total - 1)
                # Ensure at least 1 spy and at least 1 innocent
                max_spies = max(1, num_players - 1)
                num_spies = random.randint(1, max_spies)
                
                self.spy_ids = random.sample([p['id'] for p in self.players], num_spies)
                
                # Assign roles to innocents
                innocents = [p for p in self.players if p['id'] not in self.spy_ids]
                random.shuffle(available_roles)
                
                for i, p in enumerate(innocents):
                    # Cycle roles if not enough unique ones
                    role = available_roles[i % len(available_roles)] if available_roles else "Cittadino"
                    self.player_roles[p['id']] = role
                    self.db.set_player_role(self.room_id, p['id'], role)
                
                for spy_id in self.spy_ids:
                    self.player_roles[spy_id] = "Spia"
                    self.db.set_player_role(self.room_id, spy_id, "Spia")

            # Generate Spy Possible Locations (Persistent)
            with self.db.get_cursor() as cur:
                cur.execute("SELECT name FROM spy_locations")
                all_locs_db = [r['name'] for r in cur.fetchall()]
                
                if self.location in all_locs_db:
                    other_locs = [l for l in all_locs_db if l != self.location]
                    num_others = min(len(other_locs), 5)
                    selected_others = random.sample(other_locs, num_others)
                    self.spy_possible_locations = selected_others + [self.location]
                    random.shuffle(self.spy_possible_locations)
                else:
                    self.spy_possible_locations = all_locs_db[:6]

            # Reset Game State
            self.state = "PLAYING"
            self.winner = None
            self.winner_reason = None
            self.votes = {}
            self.spy_actions = {}
            self.last_round_results = []
            self.db.clear_votes(self.room_id)
            
            self._save_state()
            return True

        except Exception as e:
            print(f"Error starting Spia game: {e}")
            return False

    def handle_action(self, player_id, action_data):
        action = action_data.get('type')
        
        if action == 'start_voting':
            # Check if admin
            room = self.db.get_room(self.room_id)
            if room and room['admin_id'] == player_id:
                self.state = "VOTING"
                self._save_state()
                return {'status': 'ok'}
            return {'status': 'error', 'message': 'Only admin can start voting'}

        elif action == 'restart_game':
            # Check if admin
            room = self.db.get_room(self.room_id)
            if room and room['admin_id'] == player_id:
                if self.start_game():
                    return {'status': 'ok', 'message': 'Game restarted'}
                return {'status': 'error', 'message': 'Failed to restart game'}
            return {'status': 'error', 'message': 'Only admin can restart game'}

        elif action == 'vote':
            if player_id in self.spy_ids:
                return {'status': 'error', 'message': 'Spies cannot vote'}
            
            target_ids = action_data.get('target_ids', [])
            if not isinstance(target_ids, list):
                target_ids = [target_ids] if target_ids else []
                
            if target_ids:
                for target_id in target_ids:
                    self.db.cast_vote(self.room_id, player_id, target_id)
                
                self.votes[player_id] = True
                self._save_state()
                return self._check_round_completion()
                
        elif action == 'guess_location':
            if player_id in self.spy_ids:
                guessed_loc = action_data.get('location')
                self.spy_actions[player_id] = {'type': 'guess', 'location': guessed_loc}
                self._save_state()
                return self._check_round_completion()

        elif action == 'spy_pass':
            if player_id in self.spy_ids:
                self.spy_actions[player_id] = {'type': 'pass'}
                self._save_state()
                return self._check_round_completion()

        return {'status': 'ok'}

    def _check_round_completion(self):
        # 1. Check Innocents (Votes)
        innocents = [p['id'] for p in self.players if p['id'] not in self.spy_ids]
        all_votes = self.db.get_votes(self.room_id)
        voters = set(v['voter_id'] for v in all_votes)
        innocents_done = len(voters) >= len(innocents)

        # 2. Check Spies (Actions)
        spies_done = len(self.spy_actions) >= len(self.spy_ids)

        if innocents_done and spies_done:
            return self._resolve_simultaneous_round()
        
        return {'status': 'waiting_for_others'}

    def _resolve_simultaneous_round(self):
        # Determine Winner
        spies_win = False
        innocents_win = False
        reason = ""

        # Check Spy Guesses
        correct_guesses = 0
        wrong_guesses = 0
        for spy_id, action in self.spy_actions.items():
            if action['type'] == 'guess':
                if action['location'].lower() == self.location.lower():
                    correct_guesses += 1
                else:
                    wrong_guesses += 1
        
        if correct_guesses > 0:
            spies_win = True
            reason = "La Spia ha indovinato il luogo!"
        elif wrong_guesses > 0:
            innocents_win = True
            reason = "La Spia ha sbagliato luogo!"
        else:
            # No guesses (or all passed). Check Votes.
            all_votes = self.db.get_votes(self.room_id)
            from collections import Counter
            vote_counts = Counter(v['target_id'] for v in all_votes)
            
            if not vote_counts:
                 most_voted_id = None
            else:
                most_voted_id, count = vote_counts.most_common(1)[0]
            
            if most_voted_id in self.spy_ids:
                innocents_win = True
                reason = "La Spia è stata smascherata!"
            else:
                spies_win = True
                reason = f"Avete votato un innocente ({self.player_roles.get(most_voted_id, 'Innocente')})!"

        if spies_win:
            self.winner = "Spia"
        else:
            self.winner = "Innocenti"
        self.winner_reason = reason

        # Calculate Scores
        self.last_round_results = self._calculate_scores_simultaneous()
        self._save_state()
        
        return {'status': 'game_over', 'winner': self.winner, 'reason': self.winner_reason, 'results': self.last_round_results}

    def _calculate_scores_simultaneous(self):
        round_results = []
        all_votes = self.db.get_votes(self.room_id)
        votes_received = {}
        for v in all_votes:
            votes_received[v['target_id']] = votes_received.get(v['target_id'], 0) + 1
            
        for p in self.players:
            pid = p['id']
            points = 0
            reasons = []
            is_spy = pid in self.spy_ids
            
            if is_spy:
                action = self.spy_actions.get(pid, {})
                if action.get('type') == 'guess':
                    if action['location'].lower() == self.location.lower():
                        points += 2
                        reasons.append("Indovinato luogo (+2)")
                    # No penalty for wrong guess in points? User didn't specify.
                
                if votes_received.get(pid, 0) == 0:
                    points += 2
                    reasons.append("Nessun voto ricevuto (+2)")
            else:
                # Innocent
                my_votes = [v for v in all_votes if v['voter_id'] == pid]
                for my_vote in my_votes:
                    target_id = my_vote['target_id']
                    if target_id in self.spy_ids:
                        points += 1
                        reasons.append("Trovata spia (+1)")
                    else:
                        points -= 1
                        reasons.append("Votato innocente (-1)")
                
                my_votes_received = votes_received.get(pid, 0)
                if my_votes_received > 2:
                    penalty = my_votes_received - 1
                    points -= penalty
                    reasons.append(f"Sospetto ({my_votes_received} voti) (-{penalty})")

            if points != 0:
                self.db.update_score(self.room_id, pid, points)
                self.db.update_global_score(pid, points)
            
            round_results.append({
                "player_id": pid,
                "nickname": p['nickname'],
                "role": "Spia" if is_spy else "Innocente",
                "points": points,
                "reasons": ", ".join(reasons) if reasons else "-"
            })
            
        return round_results

    def get_web_view(self, player_id):
        player = next((p for p in self.players if p['id'] == player_id), None)
        if not player:
            return "Player not found"
            
        role = self.player_roles.get(player_id, "Sconosciuto")
        is_spy = player_id in self.spy_ids
        
        # In "All Spies" mode, everyone is a spy but location is hidden
        location_to_show = self.location if not is_spy and self.special_event != "all_spies" else "???"
        
        # Use persisted locations for Spy
        all_locations = self.spy_possible_locations if is_spy else []

        # Fetch room to check admin
        room = self.db.get_room(self.room_id)
        is_admin = (room['admin_id'] == player_id) if room else False

        # Check if player has already voted
        has_voted = player_id in self.votes

        # Check if spy has acted
        spy_has_acted = player_id in self.spy_actions

        # Get total scores for leaderboard
        total_scores = self.db.get_scores(self.room_id)
        # Convert to dict for easier lookup or list of dicts
        leaderboard = []
        for row in total_scores:
            p_nick = next((p['nickname'] for p in self.players if p['id'] == row['player_id']), "Unknown")
            
            # Fetch global score
            g_score = self.db.get_global_score(row['player_id'])
            
            leaderboard.append({'nickname': p_nick, 'score': row['score'], 'global_score': g_score})

        return render_template('spia.html',
                             game=self,
                             player_id=player_id,
                             role=role,
                             location=location_to_show,
                             is_spy=is_spy,
                             is_admin=is_admin,
                             has_voted=has_voted,
                             spy_has_acted=spy_has_acted,
                             all_locations=all_locations,
                             last_round_results=self.last_round_results,
                             leaderboard=leaderboard,
                             special_event=self.special_event if self.special_event == "double_points" else None)

    def get_json_state(self):
        return {
            "state": self.state,
            "players": self.players,
            "special_event": self.special_event
        }
