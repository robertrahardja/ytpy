#!/usr/bin/env python3
"""
YouTube Transcript Downloader
This script downloads transcripts from YouTube videos or entire playlists
and saves them to a text file and/or clipboard.
"""
import argparse
import re
import sys
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

def format_transcript(transcript, include_video_id=None):
    """
    Format a transcript into plain text.
    """
    formatter = TextFormatter()
    text_formatted = formatter.format_transcript(transcript)
    
    # Add video ID as header if provided
    if include_video_id:
        header = f"=== TRANSCRIPT FOR VIDEO: {include_video_id} ===\n\n"
        return header + text_formatted + "\n\n"
    
    return text_formatted

def save_transcript(transcript, output_file=None, copy_to_clipboard=True, include_video_id=None):
    """
    Save the transcript to a text file and/or clipboard.
    """
    if not transcript:
        return False
    
    text_formatted = format_transcript(transcript, include_video_id)
    
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
            with open(output_file, 'a', encoding='utf-8') as f:
                f.write(text_formatted)
            print(f"Transcript appended to: {output_file}")
        except Exception as e:
            print(f"Error saving transcript: {e}")
    
    return True

def main():
    parser = argparse.ArgumentParser(description='Download YouTube video or playlist transcripts')
    parser.add_argument('url', help='YouTube video or playlist URL')
    parser.add_argument('-o', '--output', help='Output file name (if not provided, only copies to clipboard)')
    parser.add_argument('-l', '--languages', nargs='+', default=['en'], 
                        help='Preferred languages (default: en)')
    parser.add_argument('--no-clipboard', action='store_true', 
                        help='Do not copy to clipboard')
    parser.add_argument('--api-key', help='YouTube Data API key (for better playlist handling)')
    parser.add_argument('--separate-files', action='store_true',
                        help='Save each transcript to a separate file')
    
    args = parser.parse_args()
    
    # Check if it's a playlist or single video
    playlist_id = extract_playlist_id(args.url)
    
    if playlist_id:
        print(f"Detected playlist ID: {playlist_id}")
        video_ids = get_playlist_videos(playlist_id, args.api_key)
        
        if not video_ids:
            print("No videos found in playlist or failed to retrieve playlist")
            sys.exit(1)
            
        # Clear the output file if it exists (to avoid appending to existing content)
        if args.output and not args.separate_files:
            try:
                with open(args.output, 'w', encoding='utf-8') as f:
                    f.write(f"=== TRANSCRIPTS FOR PLAYLIST: {playlist_id} ===\n\n")
                print(f"Created output file: {args.output}")
            except Exception as e:
                print(f"Error creating output file: {e}")
                sys.exit(1)
        
        # Process each video in the playlist
        successful_transcripts = 0
        for i, video_id in enumerate(video_ids):
            print(f"Processing video {i+1}/{len(video_ids)}: {video_id}")
            
            transcript = get_transcript(video_id, args.languages)
            
            if transcript:
                if args.separate_files and args.output:
                    # Save to separate files
                    video_output = f"{args.output.rsplit('.', 1)[0]}_{video_id}.{args.output.rsplit('.', 1)[1] if '.' in args.output else 'txt'}"
                    save_transcript(transcript, 
                                   output_file=video_output, 
                                   copy_to_clipboard=(i == len(video_ids)-1) and not args.no_clipboard)
                else:
                    # Append to single file
                    save_transcript(transcript, 
                                   output_file=args.output, 
                                   copy_to_clipboard=(i == len(video_ids)-1) and not args.no_clipboard,
                                   include_video_id=video_id)
                successful_transcripts += 1
            else:
                print(f"No transcript available for video: {video_id}")
        
        print(f"Successfully downloaded {successful_transcripts} out of {len(video_ids)} transcripts")
        
    else:
        # Handle single video
        video_id = extract_video_id(args.url)
        if not video_id:
            print("Error: Invalid YouTube URL")
            sys.exit(1)
        
        print(f"Downloading transcript for video ID: {video_id}")
        transcript = get_transcript(video_id, args.languages)
        
        if transcript:
            # For single videos, create a new file rather than append
            if args.output:
                try:
                    with open(args.output, 'w', encoding='utf-8') as f:
                        pass
                    print(f"Created output file: {args.output}")
                except Exception as e:
                    print(f"Error creating output file: {e}")
                    sys.exit(1)
                    
            save_transcript(transcript, 
                           output_file=args.output, 
                           copy_to_clipboard=not args.no_clipboard)
        else:
            print("Failed to download transcript")
            sys.exit(1)

if __name__ == '__main__':
    main()
