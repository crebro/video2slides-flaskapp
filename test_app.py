import socketio
import requests
import time

sio = socketio.Client()

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
    url = "http://127.0.0.1:5000/"
    # Using a short video for testing
    video_url = "https://www.youtube.com/watch?v=25Ofw-xc_Hk" # Rick Astley - Never Gonna Give You Up (classic)
    params = {
        'video_path': video_url,
        'interval': 1,
        'threshold': 0.9
    }
    response = requests.get(url, params=params)
    print(f"Response: {response.json()}")

def test_websocket():
    print("Testing WebSocket connection...")
    try:
        sio.connect('http://127.0.0.1:5000')
        print("Connected to WebSocket")
        
        video_url = "https://www.youtube.com/watch?v=aqz-KE-bpKQ"
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
