from .base_game import BaseGame

class DodgeballGame(BaseGame):
    def __init__(self, room_id, db):
        super().__init__(room_id, db)
        self.scores = {}

    def add_player(self, player_id, nickname):
        self.players.append({'id': player_id, 'nickname': nickname})
        self.scores[player_id] = 0

    def start_game(self):
        self.state = "PLAYING"

    def handle_action(self, player_id, action_data):
        if action_data.get('type') == 'hit':
            target_id = action_data.get('target_id')
            if target_id in self.scores:
                self.scores[target_id] -= 1
        
        return {
            "html": self.get_web_view(player_id),
            "json": self.get_json_state()
        }

    def get_web_view(self, player_id):
        return f"<h1>Dodgeball</h1><p>Score: {self.scores.get(player_id, 0)}</p>"

    def get_json_state(self):
        return {
            "scores": self.scores,
            "state": self.state
        }
