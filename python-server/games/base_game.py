from abc import ABC, abstractmethod

class BaseGame(ABC):
    def __init__(self, room_id, db):
        self.room_id = room_id
        self.db = db
        self.players = []
        self.state = "LOBBY"

    @abstractmethod
    def add_player(self, player_id, nickname):
        """Adds a player to the game."""
        pass

    @abstractmethod
    def start_game(self):
        """Starts the game logic."""
        pass

    @abstractmethod
    def handle_action(self, player_id, action_data):
        """
        Handles player actions (vote, move, etc.).
        Returns a dictionary with 'html' (for web) and 'json' (for C++) updates.
        """
        pass

    @abstractmethod
    def get_web_view(self, player_id):
        """Returns the HTML view for a specific player (mobile/web)."""
        pass

    @abstractmethod
    def get_json_state(self):
        """Returns the full JSON state for the display client (C++)."""
        pass
