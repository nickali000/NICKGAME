import random
from .base_game import BaseGame
from flask import render_template

class ParolaSegretaGame(BaseGame):
    def __init__(self, room_id, db):
        super().__init__(room_id, db)
        self.game_type = "parola_segreta"
        self.word_pair = None  # (word1, word2) from DB
        self.player_words = {}  # player_id -> assigned word
        self.votes = {}
        self.winner = None
        self.winner_reason = None
        self.state = "LOBBY"
        self.last_round_results = []
        self.player_actions = {}
        
        self._load_state()

    def _save_state(self):
        state_data = {
            "word_pair": self.word_pair,
            "player_words": self.player_words,
            "votes": self.votes,
            "winner": self.winner,
            "winner_reason": self.winner_reason,
            "state": self.state,
            "last_round_results": self.last_round_results,
            "player_actions": self.player_actions
        }
        self.db.update_game_data(self.room_id, state_data)

    def _load_state(self):
        data = self.db.get_game_data(self.room_id)
        if data:
            self.word_pair = data.get("word_pair")
            self.player_words = data.get("player_words", {})
            self.votes = data.get("votes", {})
            self.winner = data.get("winner")
            self.winner_reason = data.get("winner_reason")
            self.state = data.get("state", "LOBBY")
            self.last_round_results = data.get("last_round_results", [])
            self.player_actions = data.get("player_actions", {})
        
        # Sync player words from DB
        roles = self.db.get_player_roles(self.room_id)
        for r in roles:
            if r.get('role'):
                self.player_words[r['id']] = r['role']

    def add_player(self, player_id, nickname):
        if player_id not in [p['id'] for p in self.players]:
            self.players.append({'id': player_id, 'nickname': nickname})

    def start_game(self):
        try:
            # 1. Fetch Random Word Pair from parola_segreta table
            word_pair = self.db.get_random_word_pair()
            if not word_pair:
                print("Error: No word pairs found in DB")
                return False
            
            word_impostor = word_pair['parola_impostore']
            word_players = word_pair['parola_giocatori']
            self.word_pair = (word_impostor, word_players)
            
            # 2. Assign words: random 1 to N/2 players get impostor word
            num_players = len(self.players)
            max_impostors = max(1, num_players // 2)
            num_impostors = random.randint(1, max_impostors)
            
            # Randomly select who gets impostor word
            impostor_players = random.sample([p['id'] for p in self.players], num_impostors)
            
            self.player_words = {}
            for p in self.players:
                if p['id'] in impostor_players:
                    assigned_word = word_impostor
                else:
                    assigned_word = word_players
                self.player_words[p['id']] = assigned_word
                self.db.set_player_role(self.room_id, p['id'], assigned_word)
            
            # 3. Reset Game State
            self.state = "PLAYING"
            self.winner = None
            self.winner_reason = None
            self.votes = {}
            self.player_actions = {}
            self.last_round_results = []
            self.db.clear_votes(self.room_id)
            
            self._save_state()
            return True

        except Exception as e:
            print(f"Error starting Parola Segreta game: {e}")
            import traceback
            traceback.print_exc()
            return False

    def handle_action(self, player_id, action_data):
        action = action_data.get('type')
        
        if action == 'start_voting':
            room = self.db.get_room(self.room_id)
            if room and room['admin_id'] == player_id:
                self.state = "VOTING"
                self._save_state()
                return {'status': 'ok'}
            return {'status': 'error', 'message': 'Only admin can start voting'}

        elif action == 'restart_game':
            room = self.db.get_room(self.room_id)
            if room and room['admin_id'] == player_id:
                if self.start_game():
                    return {'status': 'ok', 'message': 'Game restarted'}
                return {'status': 'error', 'message': 'Failed to restart game'}
            return {'status': 'error', 'message': 'Only admin can restart game'}

        elif action == 'vote':
            target_ids = action_data.get('target_ids', [])
            if not isinstance(target_ids, list):
                target_ids = [target_ids] if target_ids else []
                
            if target_ids:
                for target_id in target_ids:
                    self.db.cast_vote(self.room_id, player_id, target_id)
                
                self.player_actions[player_id] = {'type': 'vote'}
                self._save_state()
                return self._check_round_completion()

        elif action == 'pass':
            # Player passes (doesn't vote)
            self.player_actions[player_id] = {'type': 'pass'}
            self._save_state()
            return self._check_round_completion()

        elif action == 'guess_word':
            # Impostor guesses the other word
            word = action_data.get('word', '')
            self.player_actions[player_id] = {'type': 'guess', 'word': word}
            self._save_state()
            return self._check_round_completion()

        return {'status': 'ok'}

    def _check_round_completion(self):
        players_acted = len(self.player_actions)
        total_players = len(self.players)
        
        print(f"DEBUG ParolaSegreta: players_acted={players_acted}, total_players={total_players}")
        
        if players_acted >= total_players:
            print(f"DEBUG ParolaSegreta: All players acted, resolving round")
            return self._resolve_round()
        
        return {'status': 'waiting_for_others'}

    def _resolve_round(self):
        # Get all votes
        all_votes = self.db.get_votes(self.room_id)
        from collections import Counter
        vote_counts = Counter(v['target_id'] for v in all_votes)
        
        # Find most voted player
        most_voted_id = None
        max_votes = 0
        if vote_counts:
            most_voted_id, max_votes = vote_counts.most_common(1)[0]
        
        # Determine winner logic (simplified for now)
        # The player with most votes "loses" or gets eliminated
        if most_voted_id:
            most_voted_word = self.player_words.get(most_voted_id, "?")
            most_voted_nickname = next((p['nickname'] for p in self.players if p['id'] == most_voted_id), "Unknown")
            self.winner = "Round Complete"
            self.winner_reason = f"{most_voted_nickname} ha ricevuto più voti ({max_votes}). La sua parola era: {most_voted_word}"
        else:
            self.winner = "Round Complete"
            self.winner_reason = "Nessuno ha votato!"

        # Calculate scores
        self.last_round_results = self._calculate_scores(all_votes, vote_counts)
        
        print(f"DEBUG ParolaSegreta: Setting winner={self.winner}")
        self._save_state()
        
        return {'status': 'game_over', 'winner': self.winner, 'reason': self.winner_reason}

    def _calculate_scores(self, all_votes, vote_counts):
        round_results = []
        word_impostor = self.word_pair[0] if self.word_pair else ""
        word_players = self.word_pair[1] if self.word_pair else ""
        
        print(f"DEBUG _calculate_scores: word_impostor={word_impostor}, word_players={word_players}")
        print(f"DEBUG _calculate_scores: player_words={self.player_words}")
        print(f"DEBUG _calculate_scores: player_actions={self.player_actions}")
        print(f"DEBUG _calculate_scores: all_votes={all_votes}")
        
        # Build list of impostor player IDs
        impostor_ids = [pid for pid, word in self.player_words.items() if word == word_impostor]
        print(f"DEBUG _calculate_scores: impostor_ids={impostor_ids}")
        
        for p in self.players:
            pid = p['id']
            word = self.player_words.get(pid, "?")
            is_impostor = (word == word_impostor)
            points = 0
            reasons = []
            
            if is_impostor:
                # Check if impostor guessed correctly
                action = self.player_actions.get(pid, {})
                if action.get('type') == 'guess':
                    guessed_word = action.get('word', '').strip().lower()
                    correct_word = word_players.strip().lower()
                    print(f"DEBUG: {pid} guessed '{guessed_word}' vs correct '{correct_word}'")
                    if guessed_word == correct_word:
                        points += 2
                        reasons.append("Indovinato parola (+2)")
                    else:
                        reasons.append(f"Tentativo sbagliato: {action.get('word', '')}")
            else:
                # Normal player - check if voted for an impostor
                for vote in all_votes:
                    if vote['voter_id'] == pid:
                        target_id = vote['target_id']
                        print(f"DEBUG: {pid} voted for {target_id}, impostor_ids={impostor_ids}")
                        if target_id in impostor_ids:
                            points += 1
                            reasons.append("Votato impostore (+1)")
                        else:
                            reasons.append("Votato innocente")
            
            print(f"DEBUG: {pid} gets {points} points, reasons={reasons}")
            
            # Update score in DB
            if points != 0:
                self.db.update_score(self.room_id, pid, points)
                self.db.update_global_score(pid, points)
            
            round_results.append({
                "player_id": pid,
                "nickname": p['nickname'],
                "role": word,
                "points": points,
                "reasons": ", ".join(reasons) if reasons else "Nessuna azione"
            })
        
        print(f"DEBUG _calculate_scores: FINAL round_results={round_results}")
        return round_results

    def get_web_view(self, player_id):
        player = next((p for p in self.players if p['id'] == player_id), None)
        if not player:
            return "Player not found"
        
        # Get player's word
        player_word = self.player_words.get(player_id, "")
        
        # Check if player has the impostor word
        is_impostor = False
        word_to_guess = ""
        if self.word_pair:
            is_impostor = (player_word == self.word_pair[0])  # parola_impostore
            word_to_guess = self.word_pair[1] if is_impostor else ""  # parola_giocatori
        
        room = self.db.get_room(self.room_id)
        is_admin = (room['admin_id'] == player_id) if room else False
        has_acted = player_id in self.player_actions

        # Leaderboard
        total_scores = self.db.get_scores(self.room_id)
        leaderboard = []
        for row in total_scores:
            p_nick = next((p['nickname'] for p in self.players if p['id'] == row['player_id']), "Unknown")
            g_score = self.db.get_global_score(row['player_id'])
            leaderboard.append({'nickname': p_nick, 'score': row['score'], 'global_score': g_score})

        print(f"DEBUG get_web_view: last_round_results = {self.last_round_results}")
        
        return render_template('parola_segreta.html',
                             game=self,
                             player_id=player_id,
                             location=player_word,
                             is_impostor=is_impostor,
                             word_to_guess=word_to_guess,
                             is_admin=is_admin,
                             has_acted=has_acted,
                             last_round_results=self.last_round_results,
                             leaderboard=leaderboard,
                             special_event=None)

    def get_json_state(self):
        return {
            "state": self.state,
            "players": self.players,
            "winner": self.winner
        }
