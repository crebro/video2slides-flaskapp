import socketio
import requests
import time
from dotenv import load_dotenv
import os
load_dotenv()

sio = socketio.Client()
PORT=8000

@sio.on('status')
def on_status(data):
    print(f"Status from server: {data}")

@sio.on('processing_complete')
def on_complete(data):
    print(f"Processing complete! Data: {data}")
    sio.disconnect()

@sio.on('processing_error')
def on_error(data):
    print(f"Error from server: {data}")
    sio.disconnect()

def test_rest_endpoint():
    print("Testing / endpoint...")
    url = f"http://127.0.0.1:{PORT}/compile"
    # Using a short video for testing
    video_url = "https://www.youtube.com/watch?v=V14oJZK9QbA"
    body = {
        'video_path': video_url,
        'interval': 1,
        'threshold': 0.9
    }
    headers = {
        'X-Compile-Request-Header': os.getenv('X_COMPILE_REQUEST_HEADER')
    }
    response = requests.post(url, json=body, headers=headers)
    print(f"Response: {response.text}")

def test_websocket():
    print("Testing WebSocket connection...")
    try:
        sio.connect(f'http://127.0.0.1:{PORT}')
        print("Connected to WebSocket")
        
        video_url = "https://www.youtube.com/watch?v=V14oJZK9QbA"
        sio.emit('compute_task', {
            'video_path': video_url,
            'interval': 60,
            'threshold': 0.9
        })
        print("Emitted compute_task")
        
        # Wait for completion or timeout
        timeout = 300 # 5 minutes
        start_time = time.time()
        while sio.connected and time.time() - start_time < timeout:
            time.sleep(1)
            
        if sio.connected:
            print("Timed out waiting for processing")
            sio.disconnect()
            
    except Exception as e:
        print(f"WebSocket error: {e}")

if __name__ == "__main__":
    # Note: The server must be running for this to work.
    # We will try to test just the registration first.
    test_rest_endpoint()
    # test_websocket() # Uncomment to test websocket fully
