package main

import (
	"encoding/json"
	"log"
)

type Message struct {
	Type string `json:"type"`
	// Common fields
	RoomID string `json:"room_id,omitempty"`
	UserID string `json:"user_id,omitempty"`
	Device string `json:"device,omitempty"`

	// For specific actions
	GameType string      `json:"game_type,omitempty"`
	Action   interface{} `json:"action,omitempty"`
	Nickname string      `json:"nickname,omitempty"`
}

func handleMessage(client *Client, message []byte) {
	log.Printf("Received message: %s", string(message))
	var msg Message
	if err := json.Unmarshal(message, &msg); err != nil {
		log.Printf("Error unmarshalling message: %v", err)
		return
	}

	switch msg.Type {
	case "handshake":
		client.userID = msg.UserID
		if msg.RoomID != "" {
			client.roomID = msg.RoomID
			client.hub.addToRoom(client, msg.RoomID)
		}
		if msg.Device == "display_client" {
			client.isDisplayCpp = true
		}

	case "create_room":
		resp, err := callPythonAPI("/room/create", map[string]interface{}{
			"user_id":  client.userID,
			"nickname": msg.Nickname,
		})
		if err != nil {
			log.Printf("Error creating room: %v", err)
			return
		}

		roomID := resp["room_id"].(string)
		client.roomID = roomID
		client.hub.addToRoom(client, roomID)

		// Send response back to client
		sendJSON(client, map[string]interface{}{
			"type":    "room_created",
			"room_id": roomID,
		})

		// Broadcast global update
		client.hub.BroadcastToAll([]byte(`{"type": "rooms_updated"}`))

	case "join_room":
		resp, err := callPythonAPI("/room/"+msg.RoomID+"/join", map[string]interface{}{
			"user_id":  client.userID,
			"nickname": msg.Nickname,
		})
		if err != nil {
			log.Printf("Error joining room: %v", err)
			return
		}

		log.Printf("DEBUG: Python join response: %v", resp)

		if resp["status"] == "joined" {
			client.roomID = msg.RoomID
			client.hub.addToRoom(client, msg.RoomID)

			log.Printf("DEBUG: Sending room_joined to client %s", client.userID)
			// Notify client
			sendJSON(client, map[string]interface{}{
				"type":     "room_joined",
				"room_id":  msg.RoomID,
				"is_admin": resp["is_admin"],
			})

			// Broadcast to OTHER room members that a new player joined (not to self)
			playerJoinedMsg, _ := json.Marshal(map[string]interface{}{
				"type":     "player_joined",
				"nickname": msg.Nickname,
			})
			client.hub.BroadcastToRoomExcept(msg.RoomID, client, playerJoinedMsg)

			// Broadcast global update (player count changed)
			client.hub.BroadcastToAll([]byte(`{"type": "rooms_updated"}`))
		} else {
			log.Printf("DEBUG: Join failed, status: %v", resp["status"])
		}

	case "select_game":
		targetRoomID := client.roomID
		if targetRoomID == "" {
			targetRoomID = msg.RoomID
		}

		resp, err := callPythonAPI("/room/set_game", map[string]interface{}{
			"room_id":   targetRoomID,
			"game_type": msg.GameType,
		})
		if err != nil {
			log.Printf("Error setting game: %v", err)
			sendJSON(client, map[string]interface{}{
				"type":    "error",
				"message": "Failed to set game: " + err.Error(),
			})
			return
		}
		if resp["status"] == "game_set" {
			// Broadcast update to room
			client.hub.BroadcastToRoom(targetRoomID, []byte(`{"type": "game_selected", "game_type": "`+msg.GameType+`", "game_name": "`+resp["game"].(string)+`"}`))

			// Broadcast global update (game type changed)
			client.hub.BroadcastToAll([]byte(`{"type": "rooms_updated"}`))
		}

	case "start_game":
		resp, err := callPythonAPI("/game/start", map[string]interface{}{
			"room_id": client.roomID,
		})
		if err != nil {
			log.Printf("Error starting game: %v", err)
			sendJSON(client, map[string]interface{}{
				"type":    "error",
				"message": "Failed to start game: " + err.Error(),
			})
			return
		}

		if resp["status"] == "started" {
			// Get redirect URL from response
			redirectURL := resp["redirect"].(string)

			// Broadcast game_started with redirect URL to all players
			broadcastMsg, _ := json.Marshal(map[string]interface{}{
				"type":     "game_started",
				"redirect": redirectURL,
			})
			client.hub.BroadcastToRoom(client.roomID, broadcastMsg)
		}

	case "action":
		log.Printf("DEBUG: Handling action. Client roomID='%s', userID='%s', Msg roomID='%s'", client.roomID, client.userID, msg.RoomID)

		// Fallback: use message roomID if client roomID is empty
		targetRoomID := client.roomID
		if targetRoomID == "" {
			targetRoomID = msg.RoomID
		}

		resp, err := callPythonAPI("/action", map[string]interface{}{
			"room_id": targetRoomID,
			"user_id": client.userID,
			"action":  msg.Action,
		})
		if err != nil {
			log.Printf("Error handling action: %v", err)
			return
		}

		// Resp should contain "html" and "json"
		// We replace the HTML with a simple signal to force reload,
		// because sending one player's HTML to everyone is wrong and wasteful.
		// The client will see "view_update" and reload.
		resp["html"] = "RELOAD"

		respBytes, _ := json.Marshal(resp)
		client.hub.BroadcastToRoom(targetRoomID, respBytes)

	case "leave_room":
		// Check if user is admin
		isAdmin := msg.UserID != "" // We'll verify on backend

		if isAdmin {
			// Admin leaving - delete room
			_, err := callPythonAPI("/room/"+client.roomID+"/delete", map[string]interface{}{
				"user_id": client.userID,
			})
			if err != nil {
				log.Printf("Error deleting room: %v", err)
			}

			// Broadcast to all room members to leave
			client.hub.BroadcastToRoom(client.roomID, []byte(`{"type": "room_deleted"}`))

			// Broadcast global update
			client.hub.BroadcastToAll([]byte(`{"type": "rooms_updated"}`))
		}
	}
}

func sendJSON(client *Client, data map[string]interface{}) {
	bytes, _ := json.Marshal(data)
	client.send <- bytes
}
