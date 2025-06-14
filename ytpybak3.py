#!/usr/bin/env python3
"""
YouTube Transcript Downloader using yt-dlp
This script downloads the transcript of a YouTube video using yt-dlp as a fallback.
"""
import argparse
import os
import sys
import subprocess
import json
import tempfile
import pyperclip
from pathlib import Path

def extract_video_id(url):
    """Extract video ID from YouTube URL"""
    from urllib.parse import urlparse, parse_qs
    
    parsed_url = urlparse(url)
    
    if parsed_url.hostname in ('www.youtube.com', 'youtube.com'):
        if parsed_url.path == '/watch':
            return parse_qs(parsed_url.query).get('v', [None])[0]
        elif parsed_url.path.startswith(('/embed/', '/v/')):
            return parsed_url.path.split('/')[2]
    elif parsed_url.hostname == 'youtu.be':
        return parsed_url.path[1:]
    
    return None

def get_transcript_with_ytdlp(url, temp_dir):
    """
    Get transcript using yt-dlp
    """
    try:
        # Check if yt-dlp is installed
        result = subprocess.run(['yt-dlp', '--version'], 
                              capture_output=True, text=True)
        if result.returncode != 0:
            print("Error: yt-dlp is not installed.")
            print("Install with: pip install yt-dlp")
            return None
        
        print(f"Using yt-dlp version: {result.stdout.strip()}")
        
        # Download subtitles only - prioritize auto-generated since manual subs might not exist
        cmd = [
            'yt-dlp',
            '--write-auto-subs',  # Focus on auto-generated subs
            '--sub-lang', 'en',
            '--sub-format', 'vtt',
            '--skip-download',
            '--output', f'{temp_dir}/%(title)s.%(ext)s',
            url
        ]
        
        print("Downloading auto-generated subtitles with yt-dlp...")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"yt-dlp error: {result.stderr}")
            # Try with both manual and auto subs as fallback
            print("Trying with both manual and auto-generated subtitles...")
            cmd[1] = '--write-subs'
            cmd.insert(2, '--write-auto-subs')
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"yt-dlp fallback also failed: {result.stderr}")
                return None
        
        # Find the downloaded subtitle file
        vtt_files = list(Path(temp_dir).glob('*.vtt'))
        if not vtt_files:
            print("No subtitle files found")
            # List all files in temp dir for debugging
            all_files = list(Path(temp_dir).glob('*'))
            print(f"Files in temp directory: {[f.name for f in all_files]}")
            return None
        
        vtt_file = vtt_files[0]
        print(f"Found subtitle file: {vtt_file.name}")
        
        # Parse VTT file
        transcript_text = parse_vtt_file(vtt_file)
        return transcript_text
        
    except Exception as e:
        print(f"Error with yt-dlp: {e}")
        return None

def parse_vtt_file(vtt_file):
    """
    Parse VTT subtitle file and extract text
    """
    try:
        with open(vtt_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines = content.split('\n')
        transcript_lines = []
        
        skip_next = False
        for line in lines:
            line = line.strip()
            
            # Skip WebVTT header and timing lines
            if line.startswith('WEBVTT') or '-->' in line or line.isdigit():
                continue
            
            # Skip empty lines
            if not line:
                continue
            
            # Add non-empty text lines
            transcript_lines.append(line)
        
        # Join all lines and clean up
        transcript = ' '.join(transcript_lines)
        
        # Clean up common VTT artifacts
        transcript = transcript.replace('&amp;', '&')
        transcript = transcript.replace('&lt;', '<')
        transcript = transcript.replace('&gt;', '>')
        transcript = transcript.replace('&quot;', '"')
        
        return transcript
        
    except Exception as e:
        print(f"Error parsing VTT file: {e}")
        return None

def save_transcript(transcript, output_file=None, copy_to_clipboard=True):
    """
    Save the transcript to a text file and/or clipboard.
    """
    if not transcript:
        print("No transcript to save")
        return
    
    # Copy to clipboard if requested
    if copy_to_clipboard:
        try:
            pyperclip.copy(transcript)
            print("Transcript copied to clipboard!")
        except Exception as e:
            print(f"Error copying to clipboard: {e}")
    
    # Save to file if output file is specified
    if output_file:
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(transcript)
            print(f"Transcript saved to: {output_file}")
        except Exception as e:
            print(f"Error saving transcript: {e}")

def main():
    parser = argparse.ArgumentParser(description='Download YouTube video transcript using yt-dlp')
    parser.add_argument('url', help='YouTube video URL')
    parser.add_argument('-o', '--output', help='Output file name (if not provided, only copies to clipboard)')
    parser.add_argument('--no-clipboard', action='store_true', 
                        help='Do not copy to clipboard')
    
    args = parser.parse_args()
    
    # Extract video ID for verification
    video_id = extract_video_id(args.url)
    if not video_id:
        print("Error: Invalid YouTube URL")
        sys.exit(1)
    
    print(f"Processing video ID: {video_id}")
    
    # Create temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"Using temporary directory: {temp_dir}")
        
        # Get transcript
        transcript = get_transcript_with_ytdlp(args.url, temp_dir)
        
        if transcript:
            print(f"Successfully retrieved transcript ({len(transcript)} characters)")
            save_transcript(transcript, 
                           output_file=args.output, 
                           copy_to_clipboard=not args.no_clipboard)
        else:
            print("Failed to download transcript")
            print("\nTroubleshooting:")
            print("1. Make sure the video has captions/subtitles")
            print("2. Check if the video is publicly accessible")
            print("3. Install/update yt-dlp: pip install -U yt-dlp")
            sys.exit(1)

if __name__ == '__main__':
    main()
