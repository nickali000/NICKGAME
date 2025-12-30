package main

import (
	"flag"
	"log"
	"net/http"
	"os"
)

var addr = flag.String("addr", ":8080", "http service address")

func getEnv(key, fallback string) string {
	if value, ok := os.LookupEnv(key); ok {
		return value
	}
	return fallback
}

func main() {
	flag.Parse()
	hub := newHub()
	go hub.run()

	http.HandleFunc("/ws", func(w http.ResponseWriter, r *http.Request) {
		serveWs(hub, w, r)
	})

	// Proxy all other requests to Python server
	// Proxy removed to ensure strict separation: Python serves HTML, Go serves WS.
	// http.HandleFunc("/", ...)

	log.Printf("Server started on %s", *addr)
	log.Printf("Using Python Server URL: %s", getEnv("PYTHON_SERVER_URL", "http://localhost:5001"))
	err := http.ListenAndServe(*addr, nil)
	if err != nil {
		log.Fatal("ListenAndServe: ", err)
	}
}
