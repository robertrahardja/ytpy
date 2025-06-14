#!/usr/bin/env python3
"""
YouTube Transcript Batch Downloader
This script downloads transcripts from multiple YouTube videos or playlists
and saves them to text files in a specified folder.
"""
import argparse
import re
import sys
import os
import pyperclip
import requests
import json
from urllib.parse import urlparse, parse_qs
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter

def extract_video_id(url):
    """
    Extract the video ID from a YouTube URL.
    Supports various YouTube URL formats.
    """
    parsed_url = urlparse(url)
    
    # Handle different YouTube URL formats
    if parsed_url.hostname in ('www.youtube.com', 'youtube.com'):
        if parsed_url.path == '/watch':
            # Format: https://www.youtube.com/watch?v=VIDEO_ID
            return parse_qs(parsed_url.query).get('v', [None])[0]
        elif parsed_url.path.startswith(('/embed/', '/v/')):
            # Format: https://www.youtube.com/embed/VIDEO_ID
            # Format: https://www.youtube.com/v/VIDEO_ID
            return parsed_url.path.split('/')[2]
    elif parsed_url.hostname == 'youtu.be':
        # Format: https://youtu.be/VIDEO_ID
        return parsed_url.path[1:]
    
    return None

def extract_playlist_id(url):
    """
    Extract the playlist ID from a YouTube URL.
    """
    parsed_url = urlparse(url)
    
    if parsed_url.hostname in ('www.youtube.com', 'youtube.com'):
        if parsed_url.path == '/playlist' or 'playlist' in parsed_url.path:
            # Format: https://www.youtube.com/playlist?list=PLAYLIST_ID
            return parse_qs(parsed_url.query).get('list', [None])[0]
        elif '/watch' in parsed_url.path and 'list' in parse_qs(parsed_url.query):
            # Format: https://www.youtube.com/watch?v=VIDEO_ID&list=PLAYLIST_ID
            return parse_qs(parsed_url.query).get('list', [None])[0]
    
    return None

def get_playlist_videos(playlist_id, api_key=None):
    """
    Get all video IDs from a YouTube playlist.
    If API key is not provided, will use a scraping approach.
    """
    if api_key:
        return get_playlist_videos_api(playlist_id, api_key)
    else:
        return get_playlist_videos_scrape(playlist_id)

def get_playlist_videos_scrape(playlist_id):
    """
    Get video IDs from a playlist using web scraping approach.
    This is a fallback method if no API key is provided.
    """
    try:
        # Create initial URL for the playlist
        initial_url = f"https://www.youtube.com/playlist?list={playlist_id}"
        response = requests.get(initial_url)
        
        if response.status_code != 200:
            print(f"Failed to fetch playlist. Status code: {response.status_code}")
            return []
        
        # Extract video IDs from the response using regex
        # This is a simple approach and might break if YouTube changes their page structure
        video_ids = re.findall(r'"videoId":"([^"]+)"', response.text)
        
        # Remove duplicates while preserving order
        unique_ids = []
        for vid in video_ids:
            if vid not in unique_ids:
                unique_ids.append(vid)
        
        print(f"Found {len(unique_ids)} videos in playlist")
        return unique_ids
    
    except Exception as e:
        print(f"Error scraping playlist: {e}")
        return []

def get_playlist_videos_api(playlist_id, api_key):
    """
    Get all video IDs from a YouTube playlist using the YouTube Data API.
    """
    video_ids = []
    next_page_token = None
    
    try:
        while True:
            # Build the API request URL
            url = f"https://www.googleapis.com/youtube/v3/playlistItems?part=contentDetails&maxResults=50&playlistId={playlist_id}&key={api_key}"
            if next_page_token:
                url += f"&pageToken={next_page_token}"
            
            # Make the request
            response = requests.get(url)
            if response.status_code != 200:
                print(f"API request failed: {response.status_code}")
                break
            
            data = response.json()
            
            # Extract video IDs
            for item in data.get('items', []):
                video_id = item.get('contentDetails', {}).get('videoId')
                if video_id:
                    video_ids.append(video_id)
            
            # Check if there are more pages
            next_page_token = data.get('nextPageToken')
            if not next_page_token:
                break
        
        print(f"Found {len(video_ids)} videos in playlist")
        return video_ids
    
    except Exception as e:
        print(f"Error retrieving playlist: {e}")
        return []

def get_video_title(video_id, api_key=None):
    """
    Get the title of a YouTube video.
    If API key is provided, use the API, otherwise use web scraping.
    """
    if api_key:
        try:
            url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet&id={video_id}&key={api_key}"
            response = requests.get(url)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('items'):
                    return data['items'][0]['snippet']['title']
        except Exception as e:
            print(f"Error getting video title via API: {e}")
    
    # Fallback to basic scraping
    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
        response = requests.get(url)
        
        if response.status_code == 200:
            # Extract title using regex
            title_match = re.search(r'<title>(.*?) - YouTube</title>', response.text)
            if title_match:
                return title_match.group(1)
    except Exception as e:
        print(f"Error getting video title: {e}")
    
    return video_id  # Return video ID as fallback

def get_transcript(video_id, languages=['en']):
    """
    Retrieve the transcript for a YouTube video.
    """
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        # Try to get transcript in preferred languages
        transcript = None
        for lang in languages:
            try:
                transcript = transcript_list.find_transcript([lang])
                break
            except:
                continue
        
        # If no transcript found in preferred languages, get any available transcript
        if transcript is None:
            try:
                transcript = transcript_list.find_generated_transcript(['en'])
            except:
                # Try to get any available transcript
                available_transcripts = list(transcript_list)
                if available_transcripts:
                    transcript = available_transcripts[0]
        
        if transcript:
            return transcript.fetch()
        return None
    except Exception as e:
        print(f"Error retrieving transcript for video {video_id}: {e}")
        return None

def format_transcript(transcript, include_title=None, include_video_id=None):
    """
    Format a transcript into plain text.
    """
    formatter = TextFormatter()
    text_formatted = formatter.format_transcript(transcript)
    
    # Add title and video ID as header if provided
    header = ""
    if include_title:
        header += f"Title: {include_title}\n"
    if include_video_id:
        header += f"Video ID: {include_video_id}\n"
    if header:
        header += f"URL: https://www.youtube.com/watch?v={include_video_id}\n\n"
    
    return header + text_formatted + "\n\n"

def ensure_directory_exists(directory):
    """
    Create directory if it doesn't exist.
    """
    if not os.path.exists(directory):
        os.makedirs(directory)
        print(f"Created directory: {directory}")

def save_transcript(transcript, output_dir=None, output_file=None, copy_to_clipboard=False, 
                    include_title=None, include_video_id=None):
    """
    Save the transcript to a text file and/or clipboard.
    """
    if not transcript:
        return False
    
    text_formatted = format_transcript(transcript, include_title, include_video_id)
    
    # Copy to clipboard if requested
    if copy_to_clipboard:
        try:
            pyperclip.copy(text_formatted)
            print("Transcript copied to clipboard!")
        except Exception as e:
            print(f"Error copying to clipboard: {e}")
    
    # Save to file if output file is specified
    if output_file:
        try:
            # Create directory if it doesn't exist
            if output_dir:
                ensure_directory_exists(output_dir)
                full_path = os.path.join(output_dir, output_file)
            else:
                full_path = output_file
                
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(text_formatted)
            print(f"Transcript saved to: {full_path}")
        except Exception as e:
            print(f"Error saving transcript: {e}")
    
    return True

def process_url(url, output_dir, languages, api_key, copy_to_clipboard=False):
    """
    Process a single URL (either video or playlist).
    """
    # Check if it's a playlist or single video
    playlist_id = extract_playlist_id(url)
    
    if playlist_id:
        print(f"Processing playlist ID: {playlist_id}")
        # Create a subfolder for the playlist
        playlist_dir = os.path.join(output_dir, f"playlist_{playlist_id}")
        ensure_directory_exists(playlist_dir)
        
        video_ids = get_playlist_videos(playlist_id, api_key)
        
        if not video_ids:
            print("No videos found in playlist or failed to retrieve playlist")
            return 0
            
        # Process each video in the playlist
        successful_transcripts = 0
        for i, video_id in enumerate(video_ids):
            print(f"Processing video {i+1}/{len(video_ids)}: {video_id}")
            title = get_video_title(video_id, api_key)
            
            transcript = get_transcript(video_id, languages)
            
            if transcript:
                # Create a safe filename from title
                safe_title = re.sub(r'[\\/*?:"<>|]', "_", title)
                filename = f"{safe_title}_{video_id}.txt"
                
                save_transcript(transcript, 
                               output_dir=playlist_dir,
                               output_file=filename, 
                               copy_to_clipboard=copy_to_clipboard and (i == len(video_ids)-1),
                               include_title=title,
                               include_video_id=video_id)
                successful_transcripts += 1
            else:
                print(f"No transcript available for video: {video_id}")
        
        print(f"Successfully downloaded {successful_transcripts} out of {len(video_ids)} transcripts")
        return successful_transcripts
        
    else:
        # Handle single video
        video_id = extract_video_id(url)
        if not video_id:
            print(f"Error: Invalid YouTube URL: {url}")
            return 0
        
        print(f"Processing video ID: {video_id}")
        title = get_video_title(video_id, api_key)
        
        transcript = get_transcript(video_id, languages)
        
        if transcript:
            # Create a safe filename from title
            safe_title = re.sub(r'[\\/*?:"<>|]', "_", title)
            filename = f"{safe_title}_{video_id}.txt"
            
            save_transcript(transcript, 
                           output_dir=output_dir,
                           output_file=filename, 
                           copy_to_clipboard=copy_to_clipboard,
                           include_title=title,
                           include_video_id=video_id)
            return 1
        else:
            print(f"Failed to download transcript for {video_id}")
            return 0

def read_urls_from_file(file_path):
    """
    Read URLs from a text file (one URL per line).
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip()]
        print(f"Read {len(urls)} URLs from {file_path}")
        return urls
    except Exception as e:
        print(f"Error reading URLs from file: {e}")
        return []

def main():
    parser = argparse.ArgumentParser(description='Download transcripts from multiple YouTube videos or playlists')
    parser.add_argument('urls', nargs='*', help='YouTube video or playlist URLs (space separated)')
    parser.add_argument('-f', '--file', help='Text file with YouTube URLs (one per line)')
    parser.add_argument('-o', '--output-dir', default='youtube_transcripts', 
                        help='Output directory (default: youtube_transcripts)')
    parser.add_argument('-l', '--languages', nargs='+', default=['en'], 
                        help='Preferred languages (default: en)')
    parser.add_argument('-c', '--clipboard', action='store_true', 
                        help='Copy the last transcript to clipboard')
    parser.add_argument('--api-key', help='YouTube Data API key (for better title and playlist handling)')
    
    args = parser.parse_args()
    
    # Collect all URLs from command line arguments and/or file
    urls = args.urls
    if args.file:
        file_urls = read_urls_from_file(args.file)
        urls.extend(file_urls)
    
    if not urls:
        print("Error: No YouTube URLs provided. Use command line arguments or a file.")
        parser.print_help()
        sys.exit(1)
    
    # Create the output directory
    ensure_directory_exists(args.output_dir)
    
    # Process each URL
    total_successful = 0
    for i, url in enumerate(urls):
        print(f"\nProcessing URL {i+1}/{len(urls)}: {url}")
        # Only copy the last transcript to clipboard if requested
        copy_to_clipboard = args.clipboard and (i == len(urls) - 1)
        successful = process_url(url, args.output_dir, args.languages, args.api_key, copy_to_clipboard)
        total_successful += successful
    
    print(f"\nSummary: Successfully downloaded {total_successful} transcripts from {len(urls)} URLs")
    print(f"Transcripts saved to directory: {os.path.abspath(args.output_dir)}")

if __name__ == '__main__':
    main()
