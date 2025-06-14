
#!/usr/bin/env python3
"""
YouTube Transcript Downloader
This script downloads the transcript of a YouTube video and saves it to a text file and/or clipboard.
"""
import argparse
import re
import sys
import pyperclip
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

def get_transcript(video_id, languages=['id']):
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
            transcript = transcript_list.find_generated_transcript(['id'])
        
        return transcript.fetch()
    except Exception as e:
        print(f"Error retrieving transcript: {e}")
        return None

def save_transcript(transcript, output_file=None, copy_to_clipboard=True):
    """
    Save the transcript to a text file and/or clipboard.
    """
    formatter = TextFormatter()
    text_formatted = formatter.format_transcript(transcript)
    
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
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(text_formatted)
            print(f"Transcript saved to: {output_file}")
        except Exception as e:
            print(f"Error saving transcript: {e}")

def main():
    parser = argparse.ArgumentParser(description='Download YouTube video transcript')
    parser.add_argument('url', help='YouTube video URL')
    parser.add_argument('-o', '--output', help='Output file name (if not provided, only copies to clipboard)')
    parser.add_argument('-l', '--languages', nargs='+', default=['id'], 
                        help='Preferred languages (default: en)')
    parser.add_argument('--no-clipboard', action='store_true', 
                        help='Do not copy to clipboard')
    
    args = parser.parse_args()
    
    # Extract video ID
    video_id = extract_video_id(args.url)
    if not video_id:
        print("Error: Invalid YouTube URL")
        sys.exit(1)
    
    # Get transcript
    print(f"Downloading transcript for video ID: {video_id}")
    transcript = get_transcript(video_id, args.languages)
    
    if transcript:
        save_transcript(transcript, 
                       output_file=args.output, 
                       copy_to_clipboard=not args.no_clipboard)
    else:
        print("Failed to download transcript")
        sys.exit(1)

if __name__ == '__main__':
    main()
