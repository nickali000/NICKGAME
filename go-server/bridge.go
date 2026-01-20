package main

import (
	"bytes"
	"encoding/json"
	"io/ioutil"
	"log"
	"net/http"
)

var pythonServerURL = getEnv("PYTHON_SERVER_URL", "http://localhost:5001") + "/api"

func callPythonAPI(endpoint string, data map[string]interface{}) (map[string]interface{}, error) {
	jsonData, err := json.Marshal(data)
	if err != nil {
		return nil, err
	}

	url := pythonServerURL + endpoint
	log.Printf("DEBUG: calling Python API: %s with data %s", url, string(jsonData))

	resp, err := http.Post(url, "application/json", bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	body, err := ioutil.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}

	var result map[string]interface{}
	if err := json.Unmarshal(body, &result); err != nil {
		log.Printf("ERROR: Failed to unmarshal response from %s. Body: %s", url, string(body))
		return nil, err
	}

	return result, nil
}
