import random
import json
import time
import os
from enum import Enum
from .base_game import BaseGame

class Role(str, Enum):
    LIBERAL = "Liberal"
    FASCIST = "Fascist"
    HITLER = "Hitler"

class GamePhase(str, Enum):
    LOBBY = "Lobby"
    NOMINATION = "Nomination"
    ELECTION = "Election"
    VOTE = "Vote"
    LEGISLATIVE_PRESIDENT = "LegislativePresident"
    LEGISLATIVE_CHANCELLOR = "LegislativeChancellor"
    EXECUTIVE_ACTION = "ExecutiveAction" # Generic, maybe unused if specific ones are used
    # Powers
    POLICY_PEEK = "PolicyPeek"
    INVESTIGATION = "Investigation"
    EXECUTION = "Execution"
    SPECIAL_ELECTION = "SpecialElection"
    VETO_REQUEST = "VetoRequest" # Chancellor asked for veto, waiting for President
    # New Powers for Scalable Modes
    PUBLIC_INQUEST = "PublicInquest"
    MARTIAL_LAW = "MartialLaw"
    PURGE = "Purge"
    GAME_OVER = "GameOver"

class SecretHitlerGame(BaseGame):
    def __init__(self, room_id, db):
        super().__init__(room_id, db)
        self.roles = {} # player_id -> Role
        self.policies = {"Liberal": 0, "Fascist": 0}
        self.deck = []
        self.discard_pile = []
        self.phase = GamePhase.LOBBY
        self.president_candidate = None # The current president (turn owner)
        self.chancellor_candidate = None # The nominated chancellor
        self.chancellor = None # The elected chancellor
        self.votes = {} # player_id -> "ja" or "nein"
        self.turn_order = []
        self.current_president_index = 0
        self.election_tracker = 0
        self.hitler_knows_team = False
        self.drawn_policies = [] # Policies currently being looked at
        self.last_enacted = None
        self.winner = None
        
        # Power states
        self.veto_unlocked = False
        self.investigated_player = None # Result of investigation to show
        self.peeked_policies = [] # Result of peek to show
        self.special_election_next = None # If set, this player becomes president next
        self.dead_players = [] # List of executed player IDs
        self.last_president_id = None
        self.last_chancellor_id = None
        self.public_investigation = None
        self.purge_remaining = 0

        # Load state if exists
        self.load_state()

    def load_state(self):
        data = self.db.get_secret_hitler_state(self.room_id)
        if not data:
            return

        self.roles = {k: Role(v) for k, v in data.get('roles', {}).items()}
        self.policies = {"Liberal": data.get('liberal_policies', 0), "Fascist": data.get('fascist_policies', 0)}
        self.deck = data.get('deck', [])
        self.discard_pile = data.get('discard_pile', [])
        self.phase = GamePhase(data.get('phase', 'Lobby'))
        self.president_candidate = data.get('president_id')
        self.chancellor_candidate = data.get('chancellor_candidate_id')
        self.chancellor = data.get('chancellor_id')
        self.votes = data.get('votes', {})
        self.turn_order = data.get('turn_order', [])
        
        if self.president_candidate and self.turn_order:
            try:
                self.current_president_index = self.turn_order.index(self.president_candidate)
            except ValueError:
                self.current_president_index = 0
        
        self.election_tracker = data.get('election_tracker', 0)
        self.drawn_policies = data.get('drawn_policies') or []
        self.last_enacted = data.get('last_enacted')
        self.winner = data.get('winner')
        
        self.veto_unlocked = data.get('veto_unlocked', False)
        self.investigated_player = data.get('investigated_player')
        self.peeked_policies = data.get('peeked_policies') or []
        self.special_election_next = data.get('special_election_next')
        self.dead_players = data.get('dead_players') or []
        
        self.last_president_id = data.get('last_president_id')
        self.last_chancellor_id = data.get('last_chancellor_id')
        self.public_investigation = data.get('public_investigation')
        self.purge_remaining = data.get('purge_remaining', 0)

    def save_state(self):
        data = {
            'roles': {k: v.value for k, v in self.roles.items()},
            'policies': self.policies,
            'deck': self.deck,
            'discard_pile': self.discard_pile,
            'phase': self.phase.value,
            'president_candidate': self.president_candidate,
            'chancellor_candidate': self.chancellor_candidate,
            'chancellor': self.chancellor,
            'votes': self.votes,
            'turn_order': self.turn_order,
            'election_tracker': self.election_tracker,
            'drawn_policies': self.drawn_policies,
            'last_enacted': self.last_enacted,
            'winner': self.winner,
            'veto_unlocked': self.veto_unlocked,
            'investigated_player': self.investigated_player,
            'peeked_policies': self.peeked_policies,
            'special_election_next': self.special_election_next,
            'dead_players': self.dead_players,
            'last_president_id': self.last_president_id,
            'last_chancellor_id': self.last_chancellor_id,
            'public_investigation': self.public_investigation,
            'purge_remaining': self.purge_remaining
        }
        self.db.update_secret_hitler_state(self.room_id, data)

    def start_game(self):
        self.save_state()
        return True

    def get_team_info(self, player_id):
        # ... (unchanged)
        pass

    def handle_nomination(self, player_id, candidate_id):
        print(f"DEBUG: handle_nomination called. Phase: {self.phase}, President: {self.president_candidate}, Nominator: {player_id}, Candidate: {candidate_id}")
        if self.phase != GamePhase.NOMINATION:
            print("DEBUG: Nomination failed - wrong phase")
            return
        if player_id != self.president_candidate:
            print("DEBUG: Nomination failed - not president")
            return
        if player_id == candidate_id:
            print("DEBUG: Nomination failed - self nomination")
            return # Cannot nominate self
        if candidate_id in self.dead_players:
            print("DEBUG: Nomination failed - candidate is dead")
            return
            
        # Term Limits Check
        # If players >= 5, last President and last Chancellor are ineligible
        # (User requested >= 5. Standard is > 5 for President, but we follow user request)
        if len(self.players) >= 5:
            if candidate_id == self.last_chancellor_id:
                print("DEBUG: Nomination failed - term limit (last chancellor)")
                return
            if candidate_id == self.last_president_id:
                print("DEBUG: Nomination failed - term limit (last president)")
                return
        else:
            # For < 5 players, usually only last Chancellor is limited?
            # User didn't specify, but standard rules say only Chancellor.
            # Let's stick to standard for < 5 if user only specified >= 5.
            if candidate_id == self.last_chancellor_id:
                 print("DEBUG: Nomination failed - term limit (last chancellor)")
                 return
            
        self.chancellor_candidate = candidate_id
        self.phase = GamePhase.VOTE
        self.votes = {}
        print(f"DEBUG: Nomination successful. New phase: {self.phase}, Candidate: {self.chancellor_candidate}")

    # ... (handle_vote, resolve_votes, draw_policies, handle_president_discard, handle_chancellor_discard unchanged)

    def enact_policy(self, policy):
        self.policies[policy] += 1
        self.election_tracker = 0
        self.last_enacted = policy
        
        # Update Term Limits
        self.last_president_id = self.president_candidate
        self.last_chancellor_id = self.chancellor
        
        if policy == "Fascist":
            self.check_executive_power()
        else:
            self.advance_turn()

    def add_player(self, player_id, nickname):
        if player_id not in [p['id'] for p in self.players]:
            self.players.append({'id': player_id, 'nickname': nickname})
            # If game is running, this is a rejoin, logic handled by load_state usually

    def start_game(self):
        if len(self.players) < 3:
            return False, "Not enough players (min 3)"
        
        self.setup_game()
        self.save_state()
        return True, "Game started"

    def setup_game(self):
        num_players = len(self.players)
        
        # Role config
        if num_players == 3:
             # Special 3 player variant requested: 1 Hitler, 2 Liberals (No plain Fascist)
             config = {"liberals": 2, "fascists": 0, "hitler_knows_team": True}
        elif num_players == 4:
             config = {"liberals": 2, "fascists": 1, "hitler_knows_team": True}
        else:
            # Standard rules
            role_distribution = {
                5: {"liberals": 3, "fascists": 1, "hitler_knows_team": True},
                6: {"liberals": 4, "fascists": 1, "hitler_knows_team": True},
                7: {"liberals": 4, "fascists": 2, "hitler_knows_team": False},
                8: {"liberals": 5, "fascists": 2, "hitler_knows_team": False},
                9: {"liberals": 5, "fascists": 3, "hitler_knows_team": False},
                10: {"liberals": 6, "fascists": 3, "hitler_knows_team": False}
            }
            # Cap at 10
            eff_players = min(num_players, 10)
            config = role_distribution.get(eff_players, role_distribution[5])

        self.hitler_knows_team = config["hitler_knows_team"]
        
        roles_list = [Role.HITLER] + [Role.FASCIST] * config["fascists"] + [Role.LIBERAL] * config["liberals"]
        random.shuffle(roles_list)
        
        self.roles = {}
        for i, player in enumerate(self.players):
            role = roles_list[i]
            self.roles[player['id']] = role
            self.db.set_player_role(self.room_id, player['id'], role.value)
            
        # Deck: 6 Liberal, 11 Fascist
        self.deck = ["Liberal"] * 6 + ["Fascist"] * 11
        random.shuffle(self.deck)
        self.discard_pile = []
        
        self.turn_order = [p['id'] for p in self.players]
        random.shuffle(self.turn_order)
        self.current_president_index = 0
        self.president_candidate = self.turn_order[0]
        
        self.phase = GamePhase.NOMINATION
        self.policies = {"Liberal": 0, "Fascist": 0}
        self.election_tracker = 0
        self.votes = {}

    def handle_action(self, player_id, action_data):
        print(f"DEBUG: SecretHitlerGame.handle_action called with {action_data} from {player_id}")
        action_type = action_data.get('type')
        
        if action_type == 'nominate_chancellor':
            self.handle_nomination(player_id, action_data.get('candidate_id'))
        elif action_type == 'vote':
            self.handle_vote(player_id, action_data.get('vote'))
        elif action_type == 'president_discard':
            self.handle_president_discard(player_id, action_data.get('discarded_policy'))
        elif action_type == 'chancellor_discard':
            self.handle_chancellor_discard(player_id, action_data.get('discarded_policy'))
        elif action_type == 'investigate_player':
            self.handle_investigate_player(player_id, action_data.get('target_id'))
        elif action_type == 'investigation_confirm':
            self.handle_investigation_confirm(player_id)
        elif action_type == 'public_inquest':
            self.handle_public_inquest(player_id, action_data.get('target_id'))
        elif action_type == 'public_inquest_confirm':
            self.handle_public_inquest_confirm(player_id)
        elif action_type == 'special_election':
            self.handle_special_election(player_id, action_data.get('target_id'))
        elif action_type == 'martial_law':
            self.handle_martial_law(player_id, action_data.get('next_president_id'), action_data.get('next_chancellor_id'))
        elif action_type == 'policy_peek_done':
            self.handle_policy_peek_done(player_id)
        elif action_type == 'execution':
            self.handle_execution(player_id, action_data.get('target_id'))
        elif action_type == 'purge':
            self.handle_purge(player_id, action_data.get('target_id'))
        elif action_type == 'veto_request':
            self.handle_veto_request(player_id)
        elif action_type == 'veto_response':
            self.handle_veto_response(player_id, action_data.get('approved'))

        self.save_state()
        
        return {
            "type": "game_update",
            "html": self.get_web_view(player_id),
            "json": self.get_json_state()
        }

    def handle_nomination(self, player_id, candidate_id):
        print(f"DEBUG: handle_nomination called. Phase: {self.phase}, President: {self.president_candidate}, Nominator: {player_id}, Candidate: {candidate_id}")
        if self.phase != GamePhase.NOMINATION:
            print("DEBUG: Nomination failed - wrong phase")
            return
        if player_id != self.president_candidate:
            print("DEBUG: Nomination failed - not president")
            return
        if player_id == candidate_id:
            print("DEBUG: Nomination failed - self nomination")
            return # Cannot nominate self
        if candidate_id in self.dead_players:
            print("DEBUG: Nomination failed - candidate is dead")
            return
            
        self.chancellor_candidate = candidate_id
        self.phase = GamePhase.VOTE
        self.votes = {}
        print(f"DEBUG: Nomination successful. New phase: {self.phase}, Candidate: {self.chancellor_candidate}")

    def handle_vote(self, player_id, vote):
        if self.phase != GamePhase.VOTE:
            return
        if player_id in self.dead_players:
            return
        if vote not in ['ja', 'nein']:
            return
            
        self.votes[player_id] = vote
        
        # Check if all players voted
        alive_players = [p['id'] for p in self.players if p['id'] not in self.dead_players]
        if len(self.votes) == len(alive_players):
            self.resolve_votes()

    def resolve_votes(self):
        ja_votes = sum(1 for v in self.votes.values() if v == 'ja')
        nein_votes = sum(1 for v in self.votes.values() if v == 'nein')
        
        if ja_votes > nein_votes:
            # Election passes
            self.election_tracker = 0
            self.chancellor = self.chancellor_candidate
            
            # Check for Hitler Victory
            config = self.get_config()
            if self.policies['Fascist'] >= config['hitler_zone'] and self.roles[self.chancellor] == Role.HITLER:
                self.winner = "Fascist"
                self.phase = GamePhase.GAME_OVER
                self.db.set_room_state(self.room_id, "LOBBY")
                return

            self.phase = GamePhase.LEGISLATIVE_PRESIDENT
            self.draw_policies()
        else:
            # Election fails
            self.election_tracker += 1
            if self.election_tracker >= 3:
                self.chaos_policy()
            else:
                self.advance_turn()

    def draw_policies(self):
        if len(self.deck) < 3:
            # User request: regenerate full deck from scratch (11 Fascist, 6 Liberal)
            # instead of just shuffling discard pile.
            self.deck = ["Liberal"] * 6 + ["Fascist"] * 11
            self.discard_pile = []
            random.shuffle(self.deck)
            
        self.drawn_policies = [self.deck.pop(0) for _ in range(3)]

    def handle_president_discard(self, player_id, discarded_policy):
        if self.phase != GamePhase.LEGISLATIVE_PRESIDENT:
            return
        if player_id != self.president_candidate:
            return
        
        # Verify policy is in hand
        if discarded_policy in self.drawn_policies:
            self.drawn_policies.remove(discarded_policy)
            self.discard_pile.append(discarded_policy)
            self.phase = GamePhase.LEGISLATIVE_CHANCELLOR
    
    def handle_chancellor_discard(self, player_id, discarded_policy):
        if self.phase != GamePhase.LEGISLATIVE_CHANCELLOR:
            return
        if player_id != self.chancellor:
            return
            
        if discarded_policy in self.drawn_policies:
            self.drawn_policies.remove(discarded_policy)
            self.discard_pile.append(discarded_policy)
            
            # Enact the remaining one
            if self.drawn_policies:
                self.enact_policy(self.drawn_policies[0])
                self.drawn_policies = []

    def handle_veto_request(self, player_id):
        if self.phase != GamePhase.LEGISLATIVE_CHANCELLOR:
            return
        if player_id != self.chancellor:
            return
        if not self.veto_unlocked:
            return
            
        self.phase = GamePhase.VETO_REQUEST
        print(f"DEBUG: Veto requested by {player_id}")

    def handle_veto_response(self, player_id, approved):
        if self.phase != GamePhase.VETO_REQUEST:
            return
        if player_id != self.president_candidate:
            return
            
        if approved:
            # Veto accepted: discard all, advance turn, tracker +1
            print("DEBUG: Veto accepted")
            self.discard_pile.extend(self.drawn_policies)
            self.drawn_policies = []
            self.election_tracker += 1
            if self.election_tracker >= 3:
                self.chaos_policy()
            else:
                self.advance_turn()
        else:
            # Veto declined: Chancellor MUST enact
            print("DEBUG: Veto declined")
            self.phase = GamePhase.LEGISLATIVE_CHANCELLOR
            # No other change, Chancellor just sees the buttons again (minus Veto maybe? Or just forced to pick)
            # Logic in template can hide Veto button if we track 'veto_declined' state, or just let them try again (which is annoying).
            # For simplicity, we just go back to LEGISLATIVE_CHANCELLOR.

    def enact_policy(self, policy):
        self.policies[policy] += 1
        self.last_enacted = policy
        
        # Check Win Conditions
        if self.policies['Liberal'] >= 5:
            self.winner = "Liberal"
            self.phase = GamePhase.GAME_OVER
            self.db.set_room_state(self.room_id, "LOBBY")
            return
        if self.policies['Fascist'] >= 6:
            self.winner = "Fascist"
            self.phase = GamePhase.GAME_OVER
            self.db.set_room_state(self.room_id, "LOBBY")
            return
            
        # Check Executive Powers (if Fascist policy enacted)
        if policy == "Fascist":
            self.check_executive_power()
        else:
            self.advance_turn()

    # Configuration for Scalable Game Modes
    GAME_CONFIG = {
        "intima": { # 3-4 Players
            "range": range(3, 5), # 3, 4
            "lib_win": 4,
            "fasc_win": 5,
            "hitler_zone": 2,
            "powers": {
                # In questa modalità i poteri sono fissi per tutti i player counts
                "default": {
                    1: GamePhase.POLICY_PEEK,
                    2: GamePhase.INVESTIGATION,
                    3: GamePhase.SPECIAL_ELECTION,
                    4: GamePhase.EXECUTION
                }
            },
            "roles": {
                3: {Role.LIBERAL: 2, Role.HITLER: 1, Role.FASCIST: 0}, # Hitler gioca da solo
                4: {Role.LIBERAL: 2, Role.HITLER: 1, Role.FASCIST: 1}
            }
        },
        "classica": { # 5-10 Players
            "range": range(5, 11),
            "lib_win": 5,
            "fasc_win": 6,
            "hitler_zone": 3,
            "powers": {
                # Qui i poteri cambiano in base al numero di giocatori
                5: {3: GamePhase.POLICY_PEEK, 4: GamePhase.EXECUTION, 5: GamePhase.EXECUTION},
                6: {3: GamePhase.POLICY_PEEK, 4: GamePhase.EXECUTION, 5: GamePhase.EXECUTION},
                7: {2: GamePhase.INVESTIGATION, 3: GamePhase.SPECIAL_ELECTION, 4: GamePhase.EXECUTION, 5: GamePhase.EXECUTION},
                8: {2: GamePhase.INVESTIGATION, 3: GamePhase.SPECIAL_ELECTION, 4: GamePhase.EXECUTION, 5: GamePhase.EXECUTION},
                9: {1: GamePhase.INVESTIGATION, 2: GamePhase.INVESTIGATION, 3: GamePhase.SPECIAL_ELECTION, 4: GamePhase.EXECUTION, 5: GamePhase.EXECUTION},
                10: {1: GamePhase.INVESTIGATION, 2: GamePhase.INVESTIGATION, 3: GamePhase.SPECIAL_ELECTION, 4: GamePhase.EXECUTION, 5: GamePhase.EXECUTION}
            },
            "roles": {
                5: {Role.LIBERAL: 3, Role.HITLER: 1, Role.FASCIST: 1},
                6: {Role.LIBERAL: 4, Role.HITLER: 1, Role.FASCIST: 1},
                7: {Role.LIBERAL: 4, Role.HITLER: 1, Role.FASCIST: 2},
                8: {Role.LIBERAL: 5, Role.HITLER: 1, Role.FASCIST: 2},
                9: {Role.LIBERAL: 5, Role.HITLER: 1, Role.FASCIST: 3},
                10: {Role.LIBERAL: 6, Role.HITLER: 1, Role.FASCIST: 3}
            }
        },
        "massa": { # 11-15 Players
            "range": range(11, 16),
            "lib_win": 6,
            "fasc_win": 7,
            "hitler_zone": 4,
            "powers": {
                "default": {
                    1: GamePhase.INVESTIGATION,
                    2: GamePhase.PUBLIC_INQUEST,
                    3: GamePhase.SPECIAL_ELECTION,
                    4: GamePhase.EXECUTION,
                    5: GamePhase.EXECUTION,
                    6: GamePhase.EXECUTION # + Veto implicito
                }
            },
            "roles": {
                # Formula usata: Fascisti totali (incluso Hitler) = floor((Giocatori - 1) / 2)
                11: {Role.LIBERAL: 6, Role.HITLER: 1, Role.FASCIST: 4},
                12: {Role.LIBERAL: 7, Role.HITLER: 1, Role.FASCIST: 4},
                13: {Role.LIBERAL: 7, Role.HITLER: 1, Role.FASCIST: 5},
                14: {Role.LIBERAL: 8, Role.HITLER: 1, Role.FASCIST: 5},
                15: {Role.LIBERAL: 8, Role.HITLER: 1, Role.FASCIST: 6}
            }
        },
        "distopia": { # 16-20 Players
            "range": range(16, 21),
            "lib_win": 6,
            "fasc_win": 8,
            "hitler_zone": 5,
            "powers": {
                "default": {
                    1: GamePhase.INVESTIGATION,
                    2: GamePhase.PUBLIC_INQUEST,
                    3: GamePhase.MARTIAL_LAW,
                    4: GamePhase.EXECUTION,
                    5: GamePhase.EXECUTION,
                    6: GamePhase.PURGE, # Double Execution
                    7: GamePhase.EXECUTION # + Veto implicito
                }
            },
            "roles": {
                16: {Role.LIBERAL: 9, Role.HITLER: 1, Role.FASCIST: 6},
                17: {Role.LIBERAL: 9, Role.HITLER: 1, Role.FASCIST: 7},
                18: {Role.LIBERAL: 10, Role.HITLER: 1, Role.FASCIST: 7},
                19: {Role.LIBERAL: 10, Role.HITLER: 1, Role.FASCIST: 8},
                20: {Role.LIBERAL: 11, Role.HITLER: 1, Role.FASCIST: 8}
            }
        }
    }

    def get_config(self):
        num_players = len(self.players)
        for mode, config in self.GAME_CONFIG.items():
            if num_players in config["range"]:
                # Handle powers
                powers_config = config["powers"]
                if num_players in powers_config:
                    powers = powers_config[num_players]
                else:
                    powers = powers_config.get("default", {})
                
                # Handle nested roles dicts
                roles = config.get("roles", {}).get(num_players, {})
                
                return {
                    "mode": mode,
                    "lib_win": config["lib_win"],
                    "fasc_win": config["fasc_win"],
                    "hitler_zone": config["hitler_zone"],
                    "powers": powers,
                    "roles_dist": roles
                }
        # Fallback (shouldn't happen if ranges cover everything)
        return self.GAME_CONFIG["classica"]

    def check_executive_power(self):
        config = self.get_config()
        fascist_count = self.policies['Fascist']
        power = config["powers"].get(fascist_count)
        
        # Veto Power logic
        # In Classica: Unlocks at 5 (passive)
        # In Intima: Not explicitly mentioned, assume standard? Or maybe none?
        # In Massa: Unlocks at 6 (passive)
        # In Distopia: Unlocks at 7 (passive)
        
        veto_threshold = config["fasc_win"] - 1
        if fascist_count == veto_threshold:
            self.veto_unlocked = True
            
        if power:
            self.phase = power
            # Setup for specific powers
            if power == GamePhase.POLICY_PEEK:
                if len(self.deck) < 3:
                     # Regenerate if needed before peeking
                     self.deck = ["Liberal"] * 6 + ["Fascist"] * 11
                     self.discard_pile = []
                     random.shuffle(self.deck)
                self.peeked_policies = self.deck[:3]
            elif power == GamePhase.PURGE:
                self.purge_remaining = 2
        else:
            self.advance_turn()

    def check_win_conditions(self):
        config = self.get_config()
        if self.policies['Liberal'] >= config["lib_win"]:
            self.winner = "Liberal"
            self.phase = GamePhase.GAME_OVER
            self.db.set_room_state(self.room_id, "LOBBY")
            return True
        if self.policies['Fascist'] >= config["fasc_win"]:
            self.winner = "Fascist"
            self.phase = GamePhase.GAME_OVER
            self.db.set_room_state(self.room_id, "LOBBY")
            return True
        return False

    def handle_investigate_player(self, player_id, target_id):
        if self.phase != GamePhase.INVESTIGATION or player_id != self.president_candidate: return
        if target_id == player_id: return # Can't investigate self
        
        # In DB, roles are stored.
        target_role = self.roles.get(target_id)
        party = "Liberal" if target_role == Role.LIBERAL else "Fascist" # Hitler is Fascist party
        
        self.investigated_player = {'id': target_id, 'party': party}
        # We stay in this phase until they click "Continue" or similar? 
        # Actually, let's just show it and wait for them to click "End Investigation" or "Continue"
        # For now, let's assume the UI shows the result and they click a button to proceed.
        # But wait, we need a way to transition OUT of this phase.
        # Let's add an 'acknowledge' action or just auto-advance?
        # Better: The action sets the result, and we return the UI. 
        # Then we need another action to 'end_power' or 'advance_turn'.
        # Let's make 'investigate_player' do the investigation, and we need a 'confirm_investigation' to move on.
        # Or simpler: 'investigate_player' sets the state, and we rely on 'end_turn' or similar.
        # Let's add 'end_executive_action' generic handler?
        # Logic continues in next block
        pass 

    def handle_investigation_confirm(self, player_id):
        if self.phase != GamePhase.INVESTIGATION or player_id != self.president_candidate: return
        self.investigated_player = None
        self.advance_turn()

    def handle_policy_peek_done(self, player_id):
        if self.phase != GamePhase.POLICY_PEEK or player_id != self.president_candidate: return
        self.peeked_policies = []
        self.advance_turn()

    def handle_public_inquest(self, player_id, target_id):
        if self.phase != GamePhase.PUBLIC_INQUEST or player_id != self.president_candidate: return
        if target_id == player_id: return
        
        target_role = self.roles.get(target_id)
        party = "Liberal" if target_role == Role.LIBERAL else "Fascist"
        
        self.public_investigation = {'id': target_id, 'party': party}
        # We need a confirm step for this too, or just auto-advance?
        # Let's use a confirm step to ensure everyone sees it.
        
    def handle_public_inquest_confirm(self, player_id):
        if self.phase != GamePhase.PUBLIC_INQUEST or player_id != self.president_candidate: return
        self.public_investigation = None
        self.advance_turn()

    def handle_martial_law(self, player_id, next_president_id, next_chancellor_id):
        if self.phase != GamePhase.MARTIAL_LAW or player_id != self.president_candidate: return
        if next_president_id == next_chancellor_id: return # Cannot be same person
        if next_president_id in self.dead_players or next_chancellor_id in self.dead_players: return
        
        self.president_candidate = next_president_id
        self.chancellor_candidate = next_chancellor_id
        self.phase = GamePhase.VOTE
        self.votes = {}
        # Note: We do NOT advance the turn index here, effectively jumping.
        # But we should update current_president_index to match the new president so next turn follows correctly?
        # "Nomina immediatamente il prossimo Presidente... E il prossimo Cancelliere."
        # It's a forced nomination.
        try:
            self.current_president_index = self.turn_order.index(next_president_id)
        except ValueError:
            pass

    def handle_purge(self, player_id, target_id):
        if self.phase != GamePhase.PURGE or player_id != self.president_candidate: return
        if target_id == player_id: return
        if target_id in self.dead_players: return

        print(f"DEBUG: Purging player {target_id}. Remaining: {self.purge_remaining}")
        self.dead_players.append(target_id)
        
        # Check if Hitler
        if self.roles[target_id] == Role.HITLER:
            self.winner = "Liberal"
            self.phase = GamePhase.GAME_OVER
            self.db.set_room_state(self.room_id, "LOBBY")
            return

        self.purge_remaining -= 1
        
        if self.purge_remaining <= 0:
            self.advance_turn()
        else:
            # Stay in PURGE phase for second kill
            pass

    def handle_execution(self, player_id, target_id):
        if self.phase != GamePhase.EXECUTION or player_id != self.president_candidate: return
        if target_id == player_id: return
        
        print(f"DEBUG: Executing player {target_id}. Current dead_players: {self.dead_players}")
        self.dead_players.append(target_id)
        print(f"DEBUG: Player {target_id} added to dead_players. New list: {self.dead_players}")
        
        # Check if Hitler
        if self.roles[target_id] == Role.HITLER:
            self.winner = "Liberal"
            self.phase = GamePhase.GAME_OVER
            self.db.set_room_state(self.room_id, "LOBBY")
            return
            
        self.advance_turn()

    def handle_special_election(self, player_id, target_id):
        if self.phase != GamePhase.SPECIAL_ELECTION or player_id != self.president_candidate: return
        if target_id == player_id: return
        if target_id in self.dead_players: return
        
        self.special_election_next = target_id
        self.advance_turn()

    def advance_turn(self):
        print(f"DEBUG: advance_turn called. Current index: {self.current_president_index}, Turn Order: {self.turn_order}, Dead: {self.dead_players}")
        if self.special_election_next:
            print(f"DEBUG: Special election next: {self.special_election_next}")
            self.president_candidate = self.special_election_next
            self.special_election_next = None
            # Do NOT advance current_president_index
        else:
            self.current_president_index = (self.current_president_index + 1) % len(self.turn_order)
            print(f"DEBUG: Next index (pre-skip): {self.current_president_index}, Player: {self.turn_order[self.current_president_index]}")
            
            # Skip dead players
            loop_count = 0
            while self.turn_order[self.current_president_index] in self.dead_players:
                print(f"DEBUG: Skipping dead player {self.turn_order[self.current_president_index]}")
                self.current_president_index = (self.current_president_index + 1) % len(self.turn_order)
                loop_count += 1
                if loop_count > len(self.turn_order):
                    print("DEBUG: All players appear to be dead? Breaking loop.")
                    break
            
            self.president_candidate = self.turn_order[self.current_president_index]
            print(f"DEBUG: New President Candidate: {self.president_candidate}")
            
        self.chancellor_candidate = None
        self.chancellor = None
        self.phase = GamePhase.NOMINATION
        self.votes = {}
        self.investigated_player = None # Clear previous investigation


    def chaos_policy(self):
        if not self.deck:
            self.deck.extend(self.discard_pile)
            self.discard_pile = []
            random.shuffle(self.deck)
            
        policy = self.deck.pop(0)
        self.policies[policy] += 1
        self.election_tracker = 0
        self.last_enacted = f"{policy} (Chaos)"
        
        # Check wins
        if self.policies['Liberal'] >= 5:
            self.winner = "Liberal"
            self.phase = GamePhase.GAME_OVER
            self.db.set_room_state(self.room_id, "LOBBY")
            return
        if self.policies['Fascist'] >= 6:
            self.winner = "Fascist"
            self.phase = GamePhase.GAME_OVER
            self.db.set_room_state(self.room_id, "LOBBY")
            return
            
        self.advance_turn()



    def get_web_view(self, player_id):
        from flask import render_template
        role = self.roles.get(player_id, "Unknown")
        team_info = self.get_team_info(player_id)
        
        # Determine visible data based on phase and role
        visible_policies = []
        if self.phase == GamePhase.LEGISLATIVE_PRESIDENT and player_id == self.president_candidate:
            visible_policies = self.drawn_policies
        elif self.phase == GamePhase.LEGISLATIVE_CHANCELLOR and player_id == self.chancellor:
            visible_policies = self.drawn_policies
            
        # Pre-process vote results for display
        vote_results = []
        for pid, vote in self.votes.items():
            nickname = next((p['nickname'] for p in self.players if p['id'] == pid), "Unknown")
            vote_results.append({'nickname': nickname, 'vote': vote})

        return render_template('sh_game.html',
                               room_id=self.room_id,
                               role=role.value if hasattr(role, 'value') else role,
                               phase=self.phase.value,
                               policies=self.policies,
                               president=self.president_candidate,
                               chancellor=self.chancellor,
                               chancellor_candidate=self.chancellor_candidate,
                               tracker=self.election_tracker,
                               team_info=team_info,
                               players=self.players,
                               votes=self.votes,
                               vote_results=vote_results,
                               visible_policies=visible_policies,
                               winner=self.winner,
                               player_id=player_id,
                               investigated_player=self.investigated_player,
                               peeked_policies=self.peeked_policies,
                               dead_players=self.dead_players,
                               veto_unlocked=self.veto_unlocked,
                               last_president_id=self.last_president_id,
                               last_chancellor_id=self.last_chancellor_id,
                               public_investigation=self.public_investigation,
                               purge_remaining=self.purge_remaining,
                               game_config=self.get_config(),
                               go_server_url=os.getenv('GO_SERVER_URL'))

    def get_json_state(self):
        return {
            "phase": self.phase,
            "policies": self.policies,
            "president": self.president_candidate,
            "chancellor_candidate": self.chancellor_candidate,
            "chancellor": self.chancellor,
            "tracker": self.election_tracker,
            "last_vote": self.votes,
            "winner": self.winner
        }
    
    def get_team_info(self, player_id):
        player_role = self.roles.get(player_id)
        if not player_role:
            return {"role": "Unknown", "team_members": []}
        
        team_members = []
        
        if player_role == Role.FASCIST:
            for pid, role in self.roles.items():
                if pid != player_id and role in [Role.FASCIST, Role.HITLER]:
                    nickname = next((p['nickname'] for p in self.players if p['id'] == pid), "Unknown")
                    team_members.append({"id": pid, "nickname": nickname, "role": role.value})
        
        elif player_role == Role.HITLER and self.hitler_knows_team:
            for pid, role in self.roles.items():
                if pid != player_id and role == Role.FASCIST:
                    nickname = next((p['nickname'] for p in self.players if p['id'] == pid), "Unknown")
                    team_members.append({"id": pid, "nickname": nickname, "role": role.value})
        
        return {
            "role": player_role.value,
            "team_members": team_members,
            "hitler_knows_team": self.hitler_knows_team
        }
