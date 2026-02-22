from skimage.metrics import structural_similarity as compare_ssim
import os
import subprocess
import img2pdf
import re
import cv2
import random
from datetime import timedelta
import shutil
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from youtube_transcript_api import YouTubeTranscriptApi
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

def extract_youtube_id(url):
    """
    Extract the YouTube video ID from a URL.
    """
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'(?:embed\/|v\/|shorts\/)([0-9A-Za-z_-]{11})',
        r'(?:youtu\.be\/)([0-9A-Za-z_-]{11})'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def get_subtitles(video_id):
    """
    Extract subtitles from a YouTube video link using yt-dlp.
    Returns the path to the subtitle file (.srt) if successful, else None.
    """

    ytt_api = YouTubeTranscriptApi()
    fetched_transcript = ytt_api.fetch(video_id)

    return fetched_transcript

def images_to_pdf(input_folder, output_pdf):
    """
    Convert all images in a folder to a single PDF file using img2pdf.
    """
    image_files = []
    for f in os.listdir(input_folder):
        if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff')):
            image_files.append(os.path.join(input_folder, f))
    
    image_files.sort(key=lambda x: [int(c) if c.isdigit() else c for c in re.split('([0-9]+)', x)])
    
    if not image_files:
        print("No images found in the directory")
        return
    
    with open(output_pdf, "wb") as f:
        f.write(img2pdf.convert(image_files))
    
    print(f"Successfully created {output_pdf} with {len(image_files)} images")

def compare_frames(frame1, frame2):
    """
    Compare two frames and return their similarity score (0-1).
    """
    if frame1.shape != frame2.shape:
        return 0.0
    
    gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
    
    (score, _) = compare_ssim(gray1, gray2, full=True)
    return score

def extract_frames_task(video_path, socket_id=None, interval_seconds=10, similarity_threshold=0.95):
    """
    Background task to extract frames and generate PDF.
    """
    video_id = extract_youtube_id(video_path)
    if not video_id:
        video_id = "unknown_video_" + str(random.randint(1000, 9999))
    
    output_dir = os.path.join(app.static_folder, video_id)
    os.makedirs(output_dir, exist_ok=True)
    
    video_full_path = os.path.join(output_dir, f'{video_id}.mp4')
    
    # Download video if it doesn't exist
    if not os.path.exists(video_full_path):
        print(f"Downloading video {video_id}...")
        cmd = [
            'yt-dlp', '-f', 'bestvideo[ext=mp4]',
            '--merge-output-format', 'mp4',
            '--output', video_full_path,
            video_path
        ]
        subprocess.run(cmd, stderr=subprocess.DEVNULL)
    
    if not os.path.exists(video_full_path):
        print("Failed to download video.")
        if socket_id:
            socketio.emit('processing_error', {'message': 'Failed to download video'}, room=socket_id)
        return

    # Temporary directory for extracted frames
    temp_dir = os.path.join(output_dir, "temp_frames")
    os.makedirs(temp_dir, exist_ok=True)
    
    # Get video duration
    try:
        cmd = [
            'ffprobe', '-v', 'error', '-show_entries', 
            'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', 
            video_full_path
        ]
        duration = float(subprocess.check_output(cmd).decode('utf-8').strip())
    except Exception as e:
        print(f"Error getting duration: {e}")
        duration = 0
    
    print(f"Video duration: {timedelta(seconds=duration)}")
    
    # Extract frames at intervals using FFmpeg
    frame_pattern = os.path.join(temp_dir, "frame_%04d.png")
    cmd = [
        'ffmpeg', '-y', '-i', video_full_path, '-vf', 
        f'fps=1/{interval_seconds}', '-vsync', 'vfr', 
        frame_pattern
    ]
    subprocess.run(cmd, stderr=subprocess.DEVNULL)
    
    frame_files = sorted([f for f in os.listdir(temp_dir) if f.startswith('frame_')])
    
    unique_frame_count = 0
    last_unique_frame = None
    unique_frame_timestamps = []
    
    for i, frame_file in enumerate(frame_files, 1):
        frame_path = os.path.join(temp_dir, frame_file)
        current_frame = cv2.imread(frame_path, cv2.IMREAD_COLOR)
        
        if current_frame is None:
            continue

        # this is technically not true, but this allows us to process the subtitles easily
        timestamp = (i - 1) * interval_seconds
        
        if last_unique_frame is None:
            unique_frame_count += 1
            output_path = os.path.join(output_dir, f"frame_{unique_frame_count}.png")
            cv2.imwrite(output_path, current_frame)
            last_unique_frame = current_frame.copy()
            unique_frame_timestamps.append(timestamp)
        else:
            similarity = compare_frames(current_frame, last_unique_frame)
            if similarity < similarity_threshold:
                unique_frame_count += 1
                output_path = os.path.join(output_dir, f"frame_{unique_frame_count}.png")
                cv2.imwrite(output_path, current_frame)
                last_unique_frame = current_frame.copy()
                unique_frame_timestamps.append(timestamp)
    
    shutil.rmtree(temp_dir)
    images_to_pdf(output_dir, os.path.join(output_dir, "output.pdf"))

    # Group subtitles by unique frame timestamps
    print(unique_frame_timestamps)
    subtitle_groups = []
    try:
        subtitles = get_subtitles(video_id)
        
        for idx, ts in enumerate(unique_frame_timestamps):
            next_ts = unique_frame_timestamps[idx + 1] if idx + 1 < len(unique_frame_timestamps) else float('inf')
            
            group = {
                "frame_index": idx + 1,
                "timestamp": ts,
                "subtitles": []
            }
            
            for sub in subtitles:
                if ts <= sub.start < next_ts:
                    group['subtitles'].append(sub.text)
            
            subtitle_groups.append(group)
            
        # Save to JSON file
        json_path = os.path.join(output_dir, "subtitle_groups.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(subtitle_groups, f, indent=4, ensure_ascii=False)
            print(f"Successfully written to JSON file")
            
    except Exception as e:
        print(f"Error processing subtitles: {e}")

    print(f"Finished processing {video_id}. Found {unique_frame_count} unique frames.")
    
    if socket_id:
        socketio.emit('processing_complete', {
            'video_id': video_id,
            'pdf_path': f'/static/{video_id}/output.pdf',
            'video_path': f'/static/{video_id}/{video_id}.mp4',
            'frames_count': unique_frame_count
        }, room=socket_id)

@app.route("/")
def compute():
    video_path = request.args.get('video_path')
    interval = int(request.args.get('interval', 10))
    threshold = float(request.args.get('threshold', 0.95))
    
    if not video_path:
        return jsonify({'error': 'video_path is required'}), 400
    
    # Start background task
    socketio.start_background_task(extract_frames_task, video_path, None, interval, threshold)
    
    return jsonify({'message': 'process begun'})

@socketio.on('compute_task')
def handle_compute_task(data):
    video_path = data.get('video_path')
    interval = int(data.get('interval', 10))
    threshold = float(data.get('threshold', 0.95))
    
    if not video_path:
        emit('processing_error', {'message': 'video_path is required'})
        return
    
    # Start background task with client identifier
    socketio.start_background_task(extract_frames_task, video_path, request.sid, interval, threshold)
    emit('status', {'message': 'Processing started'})

if __name__ == "__main__":
    socketio.run(app, debug=True, port=5000)

