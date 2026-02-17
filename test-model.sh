#!/bin/bash

# TEST OPENWEBUI API CONNECTIVITY
# Replace YOUR_API_KEY with your actual key from https://chat.oss.net.bd

# ============================================================================
# TEST 1: Basic connectivity (no auth needed)
# ============================================================================
echo "Test 1: Can reach OpenWebUI?"
curl -I https://local-ai-url
# Expected: HTTP/1.1 200 OK or 301 Redirect

echo ""
echo "============================================================================"
echo ""

# ============================================================================
# TEST 2: Check API authentication (replace with YOUR API KEY)
# ============================================================================
API_KEY="******"  # ← CHANGE THIS TO YOUR KEY

echo "Test 2: API Key Authentication"
echo "Testing with key: ${API_KEY:0:10}..."
curl -X GET https://<local-ai>/api/models \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json"
# Expected: JSON list of available models

echo ""
echo "============================================================================"
echo ""

# ============================================================================
# TEST 3: Simple chat completion
# ============================================================================
echo "Test 3: Chat Completion (Simple Test)"
curl -X POST https://<local-ai>/api/chat/completions \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama2",
    "messages": [{"role": "user", "content": "Hello, what is 2+2?"}],
    "stream": false
  }' | python -m json.tool
# Expected: JSON response with "content" field containing answer

echo ""
echo "============================================================================"
echo ""

# ============================================================================
# TEST 4: MinIO-specific query (like the anomaly detector uses)
# ============================================================================
echo "Test 4: MinIO Anomaly Context (What Detector Uses)"
curl -X POST https://<local-ai>/api/chat/completions \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama2",
    "messages": [
      {
        "role": "user",
        "content": "Analyze this MinIO storage anomaly briefly (1-2 sentences max):\n\nMetric: minio_gateway_requests_total\nCurrent value: 450.00\nExpected value: 105.00\nChange: +329%\n\nProvide a brief technical explanation."
      }
    ],
    "stream": false,
    "temperature": 0.7
  }' | python -m json.tool
# Expected: JSON response with insight about what could cause request spike

echo ""
echo "============================================================================"
echo ""

# ============================================================================
# TEST 5: Test from inside Docker container
# ============================================================================
echo "Test 5: Test from Inside Docker Container"
echo "Running: docker exec minio-anomaly-detector curl ..."
docker exec minio-anomaly-detector curl -X POST https://<local-ai>/api/chat/completions \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama2",
    "messages": [{"role": "user", "content": "test"}],
    "stream": false
  }' | python -m json.tool
# Expected: JSON response from inside the container

echo ""
echo "============================================================================"
echo "TESTS COMPLETE"
echo "============================================================================"
