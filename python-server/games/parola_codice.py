import random
from .base_game import BaseGame
from flask import render_template

class ParoleCodiceGame(BaseGame):
    """Parolecodice (Codenames-style) game implementation"""
    
    GRID_ROWS = 4
    GRID_COLS = 6
    TOTAL_WORDS = 24
    
    # Colors: 9 red, 8 blue, 6 neutral, 1 black = 24
    COLOR_DISTRIBUTION = {
        'red': 9,
        'blue': 8,
        'neutral': 6,
        'black': 1
    }
    
    def __init__(self, room_id, db):
        super().__init__(room_id, db)
        self.game_type = "parolecodice"
        
        # Teams
        self.teams = {'red': [], 'blue': []}  # player IDs
        self.captains = {'red': None, 'blue': None}
        
        # Grid
        self.grid = []  # [{word, color, revealed}]
        
        # Turn state
        self.current_team = 'red'  # Red starts
        self.current_clue = None  # {word, number}
        self.guesses_remaining = 0
        
        # Votes for current turn
        self.word_votes = {}  # player_id -> word_index
        
        # Game state
        self.state = "LOBBY"  # LOBBY -> TEAM_SELECT -> PLAYING -> GAME_OVER
        self.winner = None
        self.winner_reason = None
        self.scores = {'red': 0, 'blue': 0}
        
        self._load_state()

    def _save_state(self):
        state_data = {
            "teams": self.teams,
            "captains": self.captains,
            "grid": self.grid,
            "current_team": self.current_team,
            "current_clue": self.current_clue,
            "guesses_remaining": self.guesses_remaining,
            "word_votes": self.word_votes,
            "state": self.state,
            "winner": self.winner,
            "winner_reason": self.winner_reason,
            "scores": self.scores
        }
        self.db.update_game_data(self.room_id, state_data)

    def _load_state(self):
        data = self.db.get_game_data(self.room_id)
        if data:
            self.teams = data.get("teams", {'red': [], 'blue': []})
            self.captains = data.get("captains", {'red': None, 'blue': None})
            self.grid = data.get("grid", [])
            self.current_team = data.get("current_team", "red")
            self.current_clue = data.get("current_clue")
            self.guesses_remaining = data.get("guesses_remaining", 0)
            self.word_votes = data.get("word_votes", {})
            self.state = data.get("state", "LOBBY")
            self.winner = data.get("winner")
            self.winner_reason = data.get("winner_reason")
            self.scores = data.get("scores", {'red': 0, 'blue': 0})

    def add_player(self, player_id, nickname):
        if player_id not in [p['id'] for p in self.players]:
            self.players.append({'id': player_id, 'nickname': nickname})

    def start_game(self):
        """Initialize the game - generate grid and assign colors"""
        try:
            # Get 24 random words
            words = self.db.get_codenames_words(self.TOTAL_WORDS)
            if len(words) < self.TOTAL_WORDS:
                print(f"Error: Not enough words ({len(words)}/{self.TOTAL_WORDS})")
                return False
            
            # Assign colors
            colors = []
            for color, count in self.COLOR_DISTRIBUTION.items():
                colors.extend([color] * count)
            random.shuffle(colors)
            
            # Build grid
            self.grid = []
            for i, word in enumerate(words):
                self.grid.append({
                    'word': word,
                    'color': colors[i],
                    'revealed': False
                })
            
            # Set initial state
            self.state = "TEAM_SELECT"
            self.current_team = 'red'
            self.winner = None
            self.winner_reason = None
            self.scores = {'red': 0, 'blue': 0}
            self.current_clue = None
            self.guesses_remaining = 0
            self.word_votes = {}
            
            self._save_state()
            return True
            
        except Exception as e:
            print(f"Error starting Parolecodice: {e}")
            import traceback
            traceback.print_exc()
            return False

    def handle_action(self, player_id, action_data):
        action = action_data.get('type')
        
        # Join team
        if action == 'join_team':
            team = action_data.get('team')  # 'red' or 'blue'
            if team in ['red', 'blue']:
                # Remove from other team if present
                for t in ['red', 'blue']:
                    if player_id in self.teams[t]:
                        self.teams[t].remove(player_id)
                # Add to selected team
                self.teams[team].append(player_id)
                self._save_state()
                return {'status': 'ok', 'message': f'Joined team {team}'}
        
        # Become captain
        elif action == 'become_captain':
            team = self._get_player_team(player_id)
            if team:
                self.captains[team] = player_id
                self._save_state()
                return {'status': 'ok', 'message': f'You are now captain of team {team}'}
        
        # Start playing (admin only, after teams are set)
        elif action == 'start_playing':
            room = self.db.get_room(self.room_id)
            if room and room['admin_id'] == player_id:
                # Validate teams
                if len(self.teams['red']) < 2 or len(self.teams['blue']) < 2:
                    return {'status': 'error', 'message': 'Each team needs at least 2 players'}
                if not self.captains['red'] or not self.captains['blue']:
                    return {'status': 'error', 'message': 'Each team needs a captain'}
                
                self.state = "PLAYING"
                self._save_state()
                return {'status': 'ok'}
        
        # Captain gives clue
        elif action == 'give_clue':
            if self._is_captain(player_id) and self._get_player_team(player_id) == self.current_team:
                word = action_data.get('word', '').strip()
                number = action_data.get('number', 1)
                
                if not word:
                    return {'status': 'error', 'message': 'Clue word required'}
                
                self.current_clue = {'word': word, 'number': number}
                self.guesses_remaining = number + 1  # Can guess N+1 times
                self.word_votes = {}
                self._save_state()
                return {'status': 'ok'}
        
        # Team member votes for a word
        elif action == 'vote_word':
            team = self._get_player_team(player_id)
            if team == self.current_team and not self._is_captain(player_id):
                word_index = action_data.get('word_index')
                if word_index is not None and 0 <= word_index < len(self.grid):
                    if not self.grid[word_index]['revealed']:
                        self.word_votes[player_id] = word_index
                        self._save_state()
                        
                        # Check if all team members (non-captain) voted
                        team_members = [p for p in self.teams[team] if p != self.captains[team]]
                        if len(self.word_votes) >= len(team_members):
                            return self._resolve_votes()
                        
                        return {'status': 'waiting_for_votes'}
        
        # End turn (pass)
        elif action == 'end_turn':
            team = self._get_player_team(player_id)
            if team == self.current_team:
                self._switch_turn()
                return {'status': 'ok', 'message': 'Turn ended'}
        
        # Restart game
        elif action == 'restart_game':
            room = self.db.get_room(self.room_id)
            if room and room['admin_id'] == player_id:
                if self.start_game():
                    return {'status': 'ok'}
        
        return {'status': 'ok'}

    def _get_player_team(self, player_id):
        for team in ['red', 'blue']:
            if player_id in self.teams[team]:
                return team
        return None

    def _is_captain(self, player_id):
        return player_id in [self.captains['red'], self.captains['blue']]

    def _resolve_votes(self):
        """Count votes and reveal the most voted word"""
        from collections import Counter
        if not self.word_votes:
            return {'status': 'no_votes'}
        
        vote_counts = Counter(self.word_votes.values())
        most_voted_index, _ = vote_counts.most_common(1)[0]
        
        # Reveal the word
        word_data = self.grid[most_voted_index]
        word_data['revealed'] = True
        
        result = self._check_word_result(word_data['color'])
        
        self.word_votes = {}
        self._save_state()
        
        return result

    def _check_word_result(self, color):
        """Check what happens when a word is revealed"""
        current = self.current_team
        other = 'blue' if current == 'red' else 'red'
        
        if color == 'black':
            # Hit assassin - instant lose
            self.winner = other.capitalize()
            self.winner_reason = "L'altra squadra ha colpito l'Assassino!"
            self.state = "GAME_OVER"
            self._save_state()
            return {'status': 'game_over', 'winner': self.winner}
        
        elif color == current:
            # Correct! Continue or check win
            self.scores[current] += 1
            self.guesses_remaining -= 1
            
            # Check if team won
            target = self.COLOR_DISTRIBUTION[current]
            if self.scores[current] >= target:
                self.winner = current.capitalize()
                self.winner_reason = f"Tutte le parole {current} sono state trovate!"
                self.state = "GAME_OVER"
                self._save_state()
                return {'status': 'game_over', 'winner': self.winner}
            
            if self.guesses_remaining <= 0:
                self._switch_turn()
                return {'status': 'turn_ended', 'reason': 'Tentativi esauriti'}
            
            return {'status': 'correct', 'remaining': self.guesses_remaining}
        
        elif color == other:
            # Hit opponent's word - give them point and end turn
            self.scores[other] += 1
            
            # Check if opponent won
            target = self.COLOR_DISTRIBUTION[other]
            if self.scores[other] >= target:
                self.winner = other.capitalize()
                self.winner_reason = f"Tutte le parole {other} sono state trovate!"
                self.state = "GAME_OVER"
                self._save_state()
                return {'status': 'game_over', 'winner': self.winner}
            
            self._switch_turn()
            return {'status': 'wrong_team', 'reason': "Parola dell'altra squadra!"}
        
        else:  # neutral
            self._switch_turn()
            return {'status': 'neutral', 'reason': 'Parola neutra - turno finito'}

    def _switch_turn(self):
        self.current_team = 'blue' if self.current_team == 'red' else 'red'
        self.current_clue = None
        self.guesses_remaining = 0
        self.word_votes = {}
        self._save_state()

    def get_web_view(self, player_id):
        player = next((p for p in self.players if p['id'] == player_id), None)
        if not player:
            return "Player not found"
        
        room = self.db.get_room(self.room_id)
        is_admin = (room['admin_id'] == player_id) if room else False
        
        player_team = self._get_player_team(player_id)
        is_captain = self._is_captain(player_id)
        
        # Build team player lists with nicknames
        team_players = {'red': [], 'blue': []}
        for team in ['red', 'blue']:
            for pid in self.teams[team]:
                p = next((x for x in self.players if x['id'] == pid), None)
                if p:
                    team_players[team].append({
                        'id': pid,
                        'nickname': p['nickname'],
                        'is_captain': pid == self.captains[team]
                    })
        
        return render_template('parola_codice.html',
                             game=self,
                             player_id=player_id,
                             player_team=player_team,
                             is_captain=is_captain,
                             is_admin=is_admin,
                             team_players=team_players,
                             grid_rows=self.GRID_ROWS,
                             grid_cols=self.GRID_COLS)

    def get_json_state(self, user_id=None):
        # Determine if user can see all colors
        see_all = False
        if user_id:
            room = self.db.get_room(self.room_id)
            is_admin = (room['admin_id'] == user_id) if room else False
            is_captain = self._is_captain(user_id)
            see_all = is_admin or is_captain or self.state == "GAME_OVER"
        
        # Filter grid
        public_grid = []
        for cell in self.grid:
            public_cell = {
                'word': cell['word'],
                'revealed': cell['revealed']
            }
            if see_all or cell['revealed']:
                public_cell['color'] = cell['color']
            else:
                public_cell['color'] = None # Hide color
            public_grid.append(public_cell)

        return {
            "state": self.state,
            "players": self.players,
            "winner": self.winner,
            "winner_reason": self.winner_reason,
            "current_team": self.current_team,
            "scores": self.scores,
            "teams": self.teams,
            "captains": self.captains,
            "current_clue": self.current_clue,
            "guesses_remaining": self.guesses_remaining,
            "grid": public_grid
        }
