package main

import (
	"flag"
	"log"
	"net/http"
	"net/http/httputil"
	"net/url"
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

	pythonServerUrl := getEnv("PYTHON_SERVER_URL", "http://localhost:5001")
	target, err := url.Parse(pythonServerUrl)
	if err != nil {
		log.Fatal("Error parsing Python Server URL:", err)
	}
	proxy := httputil.NewSingleHostReverseProxy(target)

	http.HandleFunc("/ws", func(w http.ResponseWriter, r *http.Request) {
		serveWs(hub, w, r)
	})

	// Proxy all other requests to Python server
	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		proxy.ServeHTTP(w, r)
	})

	log.Printf("Server started on %s", *addr)
	log.Printf("Using Python Server URL: %s", pythonServerUrl)
	err = http.ListenAndServe(*addr, nil)
	if err != nil {
		log.Fatal("ListenAndServe: ", err)
	}
}
