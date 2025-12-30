package main

import (
	"bytes"
	"encoding/json"
	"io/ioutil"
	"net/http"
)

var pythonServerURL = getEnv("PYTHON_SERVER_URL", "http://localhost:5001") + "/api"

func callPythonAPI(endpoint string, data map[string]interface{}) (map[string]interface{}, error) {
	jsonData, err := json.Marshal(data)
	if err != nil {
		return nil, err
	}

	resp, err := http.Post(pythonServerURL+endpoint, "application/json", bytes.NewBuffer(jsonData))
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
		return nil, err
	}

	return result, nil
}
