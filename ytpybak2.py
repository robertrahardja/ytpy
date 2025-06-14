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

def get_transcript(video_id, languages=['en']):
    """
    Retrieve the transcript for a YouTube video.
    """
    import time
    
    try:
        # First, list all available transcripts
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        print("Available transcripts:")
        for transcript in transcript_list:
            print(f"  - {transcript.language} ({transcript.language_code}) - Generated: {transcript.is_generated}")
        
        # Try to get transcript in preferred languages
        transcript = None
        for lang in languages:
            try:
                transcript = transcript_list.find_transcript([lang])
                print(f"Found transcript in language: {lang}")
                break
            except Exception as e:
                print(f"No transcript found for language '{lang}': {e}")
                continue
        
        # If no transcript found in preferred languages, try generated English
        if transcript is None:
            try:
                transcript = transcript_list.find_generated_transcript(['en'])
                print("Using generated English transcript")
            except Exception as e:
                print(f"No generated English transcript found: {e}")
        
        # If still no transcript, try any available transcript
        if transcript is None:
            try:
                # Get the first available transcript
                available_transcripts = list(transcript_list)
                if available_transcripts:
                    transcript = available_transcripts[0]
                    print(f"Using first available transcript: {transcript.language}")
                else:
                    print("No transcripts available for this video")
                    return None
            except Exception as e:
                print(f"Error getting any transcript: {e}")
                return None
        
        # Try to fetch with retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"Fetching transcript (attempt {attempt + 1}/{max_retries})...")
                transcript_data = transcript.fetch()
                print(f"Successfully fetched {len(transcript_data)} transcript entries")
                return transcript_data
            except Exception as e:
                print(f"Attempt {attempt + 1} failed: {e}")
                if "no element found" in str(e):
                    print("This appears to be an XML parsing error - YouTube may be returning an error page")
                    if attempt < max_retries - 1:
                        print(f"Waiting 2 seconds before retry...")
                        time.sleep(2)
                else:
                    break
        
        # If all attempts failed, try alternative approach
        print("All fetch attempts failed. Trying alternative method...")
        try:
            # Try to get raw transcript data
            from youtube_transcript_api._api import YouTubeTranscriptApi as RawApi
            transcript_data = RawApi.get_transcript(video_id, languages=languages)
            print(f"Alternative method successful: {len(transcript_data)} entries")
            return transcript_data
        except Exception as e:
            print(f"Alternative method also failed: {e}")
        
        return None
        
    except Exception as e:
        print(f"Error retrieving transcript: {e}")
        # Additional debugging info
        print(f"Video ID: {video_id}")
        print("This could mean:")
        print("  1. The video doesn't have transcripts/captions")
        print("  2. The video is private or restricted")
        print("  3. The video ID is invalid")
        print("  4. YouTube has rate-limited the requests")
        print("  5. YouTube changed their API response format")
        
        # Suggest alternatives
        print("\nAlternatives to try:")
        print("  1. Wait a few minutes and try again (rate limiting)")
        print("  2. Use yt-dlp: yt-dlp --write-subs --write-auto-subs --sub-lang en --skip-download [URL]")
        print("  3. Try a different video to test if the issue is video-specific")
        
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
    parser.add_argument('-l', '--languages', nargs='+', default=['en'], 
                        help='Preferred languages (default: en)')
    parser.add_argument('--no-clipboard', action='store_true', 
                        help='Do not copy to clipboard')
    parser.add_argument('--debug', action='store_true',
                        help='Enable debug output')
    
    args = parser.parse_args()
    
    # Extract video ID
    video_id = extract_video_id(args.url)
    if not video_id:
        print("Error: Invalid YouTube URL")
        print(f"URL provided: {args.url}")
        sys.exit(1)
    
    if args.debug:
        print(f"Extracted video ID: {video_id}")
        print(f"Original URL: {args.url}")
    
    # Get transcript
    print(f"Downloading transcript for video ID: {video_id}")
    transcript = get_transcript(video_id, args.languages)
    
    if transcript:
        print(f"Successfully retrieved transcript with {len(transcript)} entries")
        save_transcript(transcript, 
                       output_file=args.output, 
                       copy_to_clipboard=not args.no_clipboard)
    else:
        print("Failed to download transcript")
        sys.exit(1)

if __name__ == '__main__':
    main()
