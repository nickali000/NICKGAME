package main

import (
	"encoding/json"
)

// Hub maintains the set of active clients and broadcasts messages to the
// clients.
type Hub struct {
	// Registered clients.
	clients map[*Client]bool

	// Inbound messages from the clients.
	broadcast chan []byte

	// Register requests from the clients.
	register chan *Client

	// Unregister requests from clients.
	unregister chan *Client

	// Active rooms
	rooms map[string]*Room
}

type Room struct {
	ID      string
	Clients map[*Client]bool
}

func newHub() *Hub {
	return &Hub{
		broadcast:  make(chan []byte),
		register:   make(chan *Client),
		unregister: make(chan *Client),
		clients:    make(map[*Client]bool),
		rooms:      make(map[string]*Room),
	}
}

func (h *Hub) run() {
	for {
		select {
		case client := <-h.register:
			h.clients[client] = true
			// If client has a room ID, add to room
			if client.roomID != "" {
				h.addToRoom(client, client.roomID)
			}

		case client := <-h.unregister:
			if _, ok := h.clients[client]; ok {
				delete(h.clients, client)
				close(client.send)
				if client.roomID != "" {
					h.removeFromRoom(client, client.roomID)
				}
			}

		case message := <-h.broadcast:
			// Broadcast to all clients (global) - mostly for debugging or global announcements
			for client := range h.clients {
				select {
				case client.send <- message:
				default:
					close(client.send)
					delete(h.clients, client)
				}
			}
		}
	}
}

func (h *Hub) addToRoom(client *Client, roomID string) {
	if _, ok := h.rooms[roomID]; !ok {
		h.rooms[roomID] = &Room{
			ID:      roomID,
			Clients: make(map[*Client]bool),
		}
	}
	h.rooms[roomID].Clients[client] = true
}

func (h *Hub) removeFromRoom(client *Client, roomID string) {
	if room, ok := h.rooms[roomID]; ok {
		delete(room.Clients, client)
		if len(room.Clients) == 0 {
			delete(h.rooms, roomID)
		}
	}
}

// BroadcastToRoom sends a message to all clients in a specific room
func (h *Hub) BroadcastToRoom(roomID string, message []byte) {
	if room, ok := h.rooms[roomID]; ok {
		// Parse message to check if we have separate HTML/JSON payloads
		// For now, assume message is the raw JSON from Python

		var payload map[string]interface{}
		if err := json.Unmarshal(message, &payload); err == nil {
			// Check if we have "html" and "json" keys
			htmlContent, hasHtml := payload["html"]
			jsonContent, hasJson := payload["json"]

			if hasHtml || hasJson {
				// Hybrid broadcasting
				for client := range room.Clients {
					if client.isDisplayCpp && hasJson {
						// Send JSON to C++ display
						jsonBytes, _ := json.Marshal(jsonContent)
						client.send <- jsonBytes
					} else if !client.isDisplayCpp && hasHtml {
						// Send HTML to mobile/web
						// We might want to wrap it in a structure or send raw string
						// Let's send a JSON with "html" field to be safe for the JS client
						msg := map[string]interface{}{"type": "view_update", "html": htmlContent}
						msgBytes, _ := json.Marshal(msg)
						client.send <- msgBytes
					}
				}
				return
			}
		}

		// Fallback: send original message to everyone
		for client := range room.Clients {
			select {
			case client.send <- message:
			default:
				close(client.send)
				delete(room.Clients, client)
			}
		}
	}
}

// BroadcastToRoomExcept sends message to all clients in room except the specified one
func (h *Hub) BroadcastToRoomExcept(roomID string, except *Client, message []byte) {
	if room, ok := h.rooms[roomID]; ok {
		for client := range room.Clients {
			if client == except {
				continue // Skip the sender
			}
			select {
			case client.send <- message:
			default:
				close(client.send)
				delete(room.Clients, client)
			}
		}
	}
}

// BroadcastToAll sends a message to all connected clients
func (h *Hub) BroadcastToAll(message []byte) {
	for client := range h.clients {
		select {
		case client.send <- message:
		default:
			close(client.send)
			delete(h.clients, client)
		}
	}
}
