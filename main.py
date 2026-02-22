#!/usr/bin/env python3
from skimage.metrics import structural_similarity as compare_ssim
import os
import subprocess
import img2pdf
import re
import cv2
import random
from datetime import timedelta
import shutil

def generate_random_string(length=8):
    """
    Generate a random string of fixed length.
    
    Args:
        length (int): Length of the random string
    
    Returns:
        str: Random string
    """
    letters = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    return ''.join(random.choice(letters) for i in range(length))

def images_to_pdf(input_folder, output_pdf):
    """
    Convert all images in a folder to a single PDF file using img2pdf.
    Preserves original image quality and is very fast.
    
    Args:
        input_folder (str): Path to folder containing images
        output_pdf (str): Path for output PDF file
    """
    # Get all image files sorted numerically
    image_files = []
    for f in os.listdir(input_folder):
        if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff')):
            image_files.append(os.path.join(input_folder, f))
    
    # Sort files numerically (so frame_1.png comes before frame_10.png)
    image_files.sort(key=lambda x: [int(c) if c.isdigit() else c for c in re.split('([0-9]+)', x)])
    
    if not image_files:
        print("No images found in the directory")
        return
    
    # Convert to PDF
    with open(output_pdf, "wb") as f:
        f.write(img2pdf.convert(image_files))
    
    print(f"Successfully created {output_pdf} with {len(image_files)} images")


def extract_frames(video_path, output_dir, interval_seconds=10, similarity_threshold=0.95):
    """
    Extract frames from video at regular intervals and save unique frames.
    
    Args:
        video_path (str): Path to input video file
        output_dir (str): Directory to save unique frames
        interval_seconds (int): Interval in seconds between frame captures
        similarity_threshold (float): Threshold for considering frames similar (0-1)
    """

    ## video path is a youtube link
    ## use youtube-dlp to download the video
    ## yt-dlp -f "bestvideo[ext=mp4]" --merge-output-format mp4 "https://www.youtube.com/watch?v=Qc87CsxM2kU&t=1779s"
    ## specify the output directory

    video_full_path = os.path.join(output_dir, f'{generate_random_string()}.mp4')
    cmd = [
        'yt-dlp', '-f', 'bestvideo[ext=mp4]',
        '--merge-output-format', 'mp4',
        '--output', video_full_path,
        video_path
    ]
    subprocess.run(cmd, stderr=subprocess.DEVNULL)
    video_path = video_full_path
    print(f"Video downloaded to {video_path}")

    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Temporary directory for extracted frames
    temp_dir = os.path.join(output_dir, "temp_frames")
    os.makedirs(temp_dir, exist_ok=True)
    
    # Get video duration using ffprobe
    cmd = [
        'ffprobe', '-v', 'error', '-show_entries', 
        'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', 
        video_path
    ]
    duration = float(subprocess.check_output(cmd).decode('utf-8').strip())
    
    print(f"Video duration: {timedelta(seconds=duration)}")
    
    # Calculate number of frames to extract
    num_frames = int(duration // interval_seconds)
    print(f"Extracting {num_frames} frames at {interval_seconds} second intervals")
    
    # Extract frames at intervals using FFmpeg
    frame_pattern = os.path.join(temp_dir, "frame_%04d.png")
    cmd = [
        'ffmpeg', '-i', video_path, '-vf', 
        f'fps=1/{interval_seconds}', '-vsync', 'vfr', 
        frame_pattern
    ]
    subprocess.run(cmd, stderr=subprocess.DEVNULL)
    
    # Get all extracted frames
    frame_files = sorted([f for f in os.listdir(temp_dir) if f.startswith('frame_')])
    
    # Compare frames and save unique ones
    unique_frame_count = 1
    last_unique_frame = None
    
    for i, frame_file in enumerate(frame_files, 1):
        frame_path = os.path.join(temp_dir, frame_file)
        current_frame = cv2.imread(frame_path, cv2.IMREAD_COLOR)
        
        if current_frame is None:
            continue
            
        if last_unique_frame is None:
            # First frame is always unique
            output_path = os.path.join(output_dir, f"frame_{unique_frame_count+1:04d}.png")
            cv2.imwrite(output_path, current_frame)
            last_unique_frame = current_frame.copy()
            unique_frame_count += 1
            print(f"Frame {i} - First unique frame saved")
        else:
            # Compare only with last unique frame
            similarity = compare_frames(current_frame, last_unique_frame)
            if similarity < similarity_threshold:
                output_path = os.path.join(output_dir, f"frame_{unique_frame_count+1:04d}.png")
                cv2.imwrite(output_path, current_frame)
                last_unique_frame = current_frame.copy()
                unique_frame_count += 1
                print(f"Frame {i} - Unique ({similarity*100:.1f}% similar to last)")
            else:
                print(f"Frame {i} - Similar to last ({similarity*100:.1f}%), skipped") 
    
    # Clean up temporary directory
    shutil.rmtree(temp_dir)

    images_to_pdf(output_dir, os.path.join(output_dir, "output.pdf"))
    subprocess.run(['rm', os.path.join(output_dir, "*.png")], stderr=subprocess.DEVNULL)
    
    print(f"\nFinished processing. Found {unique_frame_count} unique frames out of {len(frame_files)} sampled frames.")

def compare_frames(frame1, frame2):
    """
    Compare two frames and return their similarity score (0-1).
    
    Args:
        frame1: First frame (numpy array)
        frame2: Second frame (numpy array)
    
    Returns:
        float: Similarity score (0-1)
    """
    if frame1.shape != frame2.shape:
        return 0.0
    
    # Convert to grayscale
    gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
    
    # Compute Structural Similarity Index
    (score, _) = compare_ssim(gray1, gray2, full=True)
    return score

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Extract unique frames from video at regular intervals")
    parser.add_argument("video_path", help="Path to input video file")
    parser.add_argument("output_dir", help="Directory to save unique frames")
    parser.add_argument("--interval", type=int, default=1, 
                       help="Interval in seconds between frame captures (default: 10)")
    parser.add_argument("--threshold", type=float, default=0.95,
                       help="Similarity threshold for considering frames the same (default: 0.95)")
    
    args = parser.parse_args()
    
    extract_frames(
        args.video_path,
        args.output_dir,
        interval_seconds=args.interval,
        similarity_threshold=args.threshold
    )