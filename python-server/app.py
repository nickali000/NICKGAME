from flask import Flask, request, jsonify, render_template, redirect
from games.secret_hitler import SecretHitlerGame
from games.dodgeball import DodgeballGame
from games.spia import SpiaGame
from games.parola_segreta import ParolaSegretaGame
from db_manager import DBManager
import uuid
import os

app = Flask(__name__)

# Database Manager
db = DBManager()

# Debug: Print GO_SERVER_URL
print(f"DEBUG: GO_SERVER_URL is set to: {os.getenv('GO_SERVER_URL')}")

# In-memory storage for active game instances
active_games = {}

def get_or_restore_game(room_id):
    if room_id in active_games:
        return active_games[room_id]
    
    # Try to restore from DB
    room = db.get_room(room_id)
    if room and room['game_type'] and room['state'] == 'PLAYING':
        print(f"DEBUG: Restoring game {room_id} from DB")
        if room['game_type'] == "secret_hitler":
            game = SecretHitlerGame(room_id, db)
        elif room['game_type'] == "dodgeball":
            game = DodgeballGame(room_id, db)
        elif room['game_type'] == "spia":
            game = SpiaGame(room_id, db)
        else:
            return None
            
        # Load players
        players = db.get_players(room_id)
        for p in players:
            game.add_player(p['id'], p['nickname'])
            
        active_games[room_id] = game
        return game
    return None

# ... (omitted)





@app.route('/')
def index():
    return render_template('index.html', go_server_url=os.getenv('GO_SERVER_URL'))

@app.route('/lobby')
def lobby():
    room_id = request.args.get('room_id')
    user_id = request.args.get('user_id')
    
    print(f"DEBUG: Lobby requested for room_id={room_id}, user_id={user_id}")
    
    room = db.get_room(room_id)
    print(f"DEBUG: DB returned room: {room}")
    
    if not room:
        return "Room not found", 404
        
    # Check if game is already playing
    # Check if game is already playing
    if room['state'] == 'PLAYING':
        # Self-healing: Check if game is actually over (e.g. from previous crash/bug)
        is_game_over = False
        if room.get('game_type') == 'secret_hitler':
            sh_state = db.get_secret_hitler_state(room_id)
            if sh_state and sh_state.get('winner'):
                is_game_over = True
        
        if is_game_over:
            print(f"DEBUG: Room {room_id} state is PLAYING but game is over. Resetting to LOBBY.")
            db.set_room_state(room_id, 'LOBBY')
            room['state'] = 'LOBBY' # Update local variable so we render lobby below
        else:
            return render_template('redirect.html', url=f"/game/{room_id}?user_id={user_id}")
        
    players = db.get_players(room_id)
    is_admin = (room['admin_id'] == user_id)
    
    # Get game info if selected
    game_type = room.get('game_type')
    game_name = None
    if game_type:
        games = db.get_available_games()
        game_name = next((g['name'] for g in games if g['id'] == game_type), game_type)

    return render_template('lobby.html', 
                           room_id=room_id, 
                           players=players, 
                           user_id=user_id,
                           is_admin=is_admin,
                           admin_id=room['admin_id'],
                           game_type=game_type,
                           game_name=game_name)

@app.route('/api/rooms', methods=['GET'])
def get_rooms():
    rooms_data = db.get_all_rooms()
    games = db.get_available_games()
    games_map = {g['id']: g['name'] for g in games}
    
    rooms_list = []
    for r in rooms_data:
        game_id = r['game_type']
        game_name = games_map.get(game_id, game_id) if game_id else "None"
        
        rooms_list.append({
            "id": r['id'],
            "game": game_name,
            "players": r['player_count']
        })
    return jsonify({"rooms": rooms_list})

@app.route('/api/games', methods=['GET'])
def get_games():
    games = db.get_available_games()
    games_list = []
    for g in games:
        games_list.append({
            "id": g['id'],
            "name": g['name'],
            "min_players": g['min_players'],
            "max_players": g['max_players'],
            "description": g['description']
        })
    return jsonify({"games": games_list})

@app.route('/api/room/create', methods=['POST'])
def create_room():
    data = request.json
    user_id = data.get('user_id')
    nickname = data.get('nickname', 'Admin')  # Get nickname from request
    room_id = generate_room_id()
    
    db.create_room(room_id, user_id)
    # Add creator as first player
    db.add_player(room_id, user_id, nickname)
    
    return jsonify({"status": "ok", "room_id": room_id})

@app.route('/api/room/set_game', methods=['POST'])
def set_game():
    data = request.json
    print(f"DEBUG: set_game called with data: {data}")
    room_id = data.get('room_id')
    game_type = data.get('game_type')
    
    room = db.get_room(room_id)
    print(f"DEBUG: set_game found room: {room}")
    if not room:
        print(f"DEBUG: Room {room_id} not found in DB")
        return jsonify({"status": "error", "message": "Room not found"}), 404
        
    db.set_game(room_id, game_type)
    
    # Get game name for response
    games = db.get_available_games()
    game_name = next((g['name'] for g in games if g['id'] == game_type), game_type)
    
    # Initialize Game Object
    if game_type == "secret_hitler":
        active_games[room_id] = SecretHitlerGame(room_id, db)
    elif game_type == "dodgeball":
        active_games[room_id] = DodgeballGame(room_id, db)
    elif game_type == "spia":
        active_games[room_id] = SpiaGame(room_id, db)
    elif game_type == "parola_segreta":
        active_games[room_id] = ParolaSegretaGame(room_id, db)
    else:
        return jsonify({"status": "error", "message": "Unknown game type"}), 400
    
    # Load existing players into game object
    players = db.get_players(room_id)
    for p in players:
        active_games[room_id].add_player(p['id'], p['nickname'])
    
    print(f"Game {game_type} set for room {room_id} with {len(players)} players")
        
    return jsonify({"status": "game_set", "game": game_name, "game_type": game_type})

@app.route('/api/game/start', methods=['POST'])
def start_game():
    data = request.json
    room_id = data.get('room_id')
    
    print(f"Start game request for room {room_id}")
    print(f"Active games: {list(active_games.keys())}")
    
    if room_id not in active_games:
        # Try to restore if in DB but not in memory (e.g. server restart)
        room = db.get_room(room_id)
        if room and room['game_type']:
             if room['game_type'] == "secret_hitler":
                active_games[room_id] = SecretHitlerGame(room_id, db)
             elif room['game_type'] == "dodgeball":
                active_games[room_id] = DodgeballGame(room_id, db)
             elif room['game_type'] == "spia":
                active_games[room_id] = SpiaGame(room_id, db)
             elif room['game_type'] == "parola_segreta":
                active_games[room_id] = ParolaSegretaGame(room_id, db)
            
             # Need to load players into game object
             if room_id in active_games:
                players = db.get_players(room_id)
                for p in players:
                    active_games[room_id].add_player(p['id'], p['nickname'])
                print(f"Restored game {room['game_type']} from DB with {len(players)} players")
        else:
            print(f"No game type set for room {room_id}")
            return jsonify({"status": "error", "message": "No game selected. Please select a game first."}), 400
        
    game = active_games[room_id]
    print(f"Game has {len(game.players)} players")
    success = game.start_game()
    
    if success:
        print(f"Game started successfully for room {room_id}")
        # Update room state in DB
        db.set_room_state(room_id, "PLAYING")
        return jsonify({"status": "started", "redirect": f"/game/{room_id}"})
    else:
        print(f"Game start failed for room {room_id}")
        return jsonify({"status": "error", "message": "Could not start game"}), 400

@app.route('/game/<room_id>')
def game_view(room_id):
    user_id = request.args.get('user_id')
    
    if not user_id:
        return "User ID required", 400
    
    game = get_or_restore_game(room_id)
    if not game:
        # If no game is active, redirect to lobby
        return redirect(f"/lobby?room_id={room_id}&user_id={user_id}")
    return game.get_web_view(user_id)

@app.route('/api/action', methods=['POST'])
def handle_action():
    data = request.json
    room_id = data.get('room_id')
    user_id = data.get('user_id')
    action = data.get('action')
    
    print(f"DEBUG: app.py handle_action called for room {room_id}, user {user_id}, action {action}")
    game = get_or_restore_game(room_id)
    if not game:
        print(f"DEBUG: Room {room_id} not found or no game active")
        return jsonify({"status": "error", "message": "No game active"}), 400
    response_data = game.handle_action(user_id, action)
    print(f"DEBUG: app.py handle_action response: {response_data}")
    return jsonify(response_data)

@app.route('/api/room/<room_id>/join', methods=['POST'])
def join_room(room_id):
    data = request.json
    user_id = data.get('user_id')
    nickname = data.get('nickname')
    
    room = db.get_room(room_id)
    if not room:
        return jsonify({"status": "error", "message": "Room not found"}), 404
    
    db.add_player(room_id, user_id, nickname)
        
    # If game is active, add to game as well
    game = get_or_restore_game(room_id)
    if game:
        game.add_player(user_id, nickname)
        
    return jsonify({"status": "joined", "is_admin": room['admin_id'] == user_id})

@app.route('/api/room/<room_id>/delete', methods=['POST'])
def delete_room(room_id):
    data = request.json
    user_id = data.get('user_id')
    
    room = db.get_room(room_id)
    if not room:
        return jsonify({"status": "error", "message": "Room not found"}), 404
    
    # Check if user is admin
    if room['admin_id'] != user_id:
        return jsonify({"status": "error", "message": "Only admin can delete room"}), 403
    
    # Delete from game instances
    if room_id in active_games:
        del active_games[room_id]
    
    # Delete from database
    db.delete_room(room_id)
    
    return jsonify({"status": "deleted"})

@app.route('/api/game/reset', methods=['POST'])
def reset_game():
    data = request.json
    room_id = data.get('room_id')
    
    print(f"DEBUG: Resetting game for room {room_id}")
    
    # 1. Delete game state from DB
    db.delete_secret_hitler_state(room_id)
    
    # 2. Set room state to LOBBY
    db.set_room_state(room_id, "LOBBY")
    
    # 3. Remove from active_games memory
    if room_id in active_games:
        del active_games[room_id]
        
    return jsonify({"status": "reset"})

@app.route('/api/game/<room_id>/status', methods=['GET'])
def get_game_status(room_id):
    # Check if game is active in memory
    game = get_or_restore_game(room_id)
    
    if game:
        # If game is active (Spia, SecretHitler, etc.)
        state = getattr(game, 'state', 'PLAYING')
        winner = getattr(game, 'winner', None)
        
        response = {
            "status": "active",
            "state": state,
            "winner": winner
        }
        print(f"DEBUG /api/game/{room_id}/status: Returning {response}")
        return jsonify(response)
    else:
        # If no game active, check DB room state
        room = db.get_room(room_id)
        if room:
            return jsonify({
                "status": "room_found",
                "state": room['state'] # Likely 'LOBBY'
            })
        else:
            return jsonify({"status": "error", "message": "Room not found"}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=False)
