#!/usr/bin/env python3
"""
YouTube Transcript Batch Downloader using yt-dlp
This script downloads transcripts from multiple YouTube videos or playlists
using yt-dlp, which handles both manual subtitles and auto-generated captions.
"""
import argparse
import re
import sys
import os
import json
import subprocess
import pyperclip
from pathlib import Path
from urllib.parse import urlparse, parse_qs

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

def check_ytdlp_installed():
    """
    Check if yt-dlp is installed and accessible.
    """
    try:
        result = subprocess.run(['yt-dlp', '--version'], 
                              capture_output=True, text=True, check=True)
        print(f"Using yt-dlp version: {result.stdout.strip()}")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: yt-dlp is not installed or not found in PATH.")
        print("Install it with: pip install yt-dlp")
        return False

def get_video_info(url, languages=['en']):
    """
    Get video information and available subtitles using yt-dlp.
    """
    try:
        # Get video info with available subtitles
        cmd = [
            'yt-dlp',
            '--dump-json',
            '--no-download',
            '--write-auto-sub',
            '--write-sub',
            '--sub-langs', ','.join(languages + ['en', 'en-US', 'en-GB']),
            url
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        # Parse each line as JSON (for playlists, yt-dlp outputs multiple JSON objects)
        videos_info = []
        for line in result.stdout.strip().split('\n'):
            if line.strip():
                try:
                    video_info = json.loads(line)
                    videos_info.append(video_info)
                except json.JSONDecodeError:
                    continue
        
        return videos_info
    
    except subprocess.CalledProcessError as e:
        print(f"Error getting video info: {e}")
        print(f"stderr: {e.stderr}")
        return []

def download_subtitles(url, output_dir, languages=['en'], prefer_auto=False):
    """
    Download subtitles for a video or playlist using yt-dlp.
    
    Args:
        url: YouTube URL
        output_dir: Directory to save subtitles
        languages: List of preferred languages
        prefer_auto: Whether to prefer auto-generated subtitles over manual ones
                    (False = prefer manual, download auto if manual not available)
    """
    try:
        # Ensure output directory exists
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # Build subtitle language list with proper priority
        sub_langs = []
        
        if prefer_auto:
            # Prefer auto-generated first, then manual as fallback
            for lang in languages:
                sub_langs.append(f"{lang}-auto")  # Auto-generated version first
                sub_langs.append(lang)           # Manual version as fallback
            # Add English variants
            sub_langs.extend(['en-auto', 'en', 'en-US', 'en-GB'])
        else:
            # Prefer manual first, then auto-generated as fallback
            for lang in languages:
                sub_langs.append(lang)           # Manual version first
                sub_langs.append(f"{lang}-auto") # Auto-generated as fallback
            # Add English variants
            sub_langs.extend(['en', 'en-US', 'en-GB', 'en-auto'])
        
        # Remove duplicates while preserving order
        sub_langs = list(dict.fromkeys(sub_langs))
        
        cmd = [
            'yt-dlp',
            '--write-sub',      # Download manual subtitles
            '--write-auto-sub', # Download auto-generated subtitles
            '--skip-download',  # Only download subtitles, not video
            '--sub-langs', ','.join(sub_langs),
            '--sub-format', 'vtt/srt/best',
            '--output', f"{output_dir}/%(title)s.%(ext)s",
            '--restrict-filenames',  # Use only ASCII characters in filenames
            url
        ]
        
        print(f"Language priority: {' > '.join(sub_langs[:6])}{'...' if len(sub_langs) > 6 else ''}")
        print(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("Subtitle download completed successfully")
            return True
        else:
            print(f"Subtitle download failed: {result.stderr}")
            return False
    
    except Exception as e:
        print(f"Error downloading subtitles: {e}")
        return False

def convert_subtitles_to_text(subtitle_dir, output_format='txt', add_paragraphs=True):
    """
    Convert downloaded subtitle files (VTT/SRT) to plain text.
    
    Args:
        subtitle_dir: Directory containing subtitle files
        output_format: Output format ('txt')
        add_paragraphs: Whether to add paragraph breaks for better readability
    """
    subtitle_files = []
    
    # Find all subtitle files in the directory
    for ext in ['*.vtt', '*.srt']:
        subtitle_files.extend(Path(subtitle_dir).glob(ext))
    
    converted_files = []
    
    for sub_file in subtitle_files:
        try:
            # Read subtitle file
            with open(sub_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Convert to plain text
            plain_text = extract_text_from_subtitles(content, str(sub_file))
            
            if plain_text:
                # Add better paragraph formatting if requested
                if add_paragraphs:
                    plain_text = add_paragraph_breaks(plain_text)
                
                # Create output filename
                output_file = sub_file.with_suffix(f'.{output_format}')
                
                # Write plain text
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(plain_text)
                
                print(f"Converted: {sub_file.name} -> {output_file.name}")
                converted_files.append(output_file)
                
                # Remove original subtitle file
                sub_file.unlink()
        
        except Exception as e:
            print(f"Error converting {sub_file}: {e}")
    
    return converted_files

def add_paragraph_breaks(text):
    """
    Add paragraph breaks to improve readability of transcript text.
    """
    lines = text.split('\n')
    formatted_lines = []
    
    for i, line in enumerate(lines):
        formatted_lines.append(line)
        
        # Add extra line break after sentences that end with punctuation
        # and before lines that start with capital letters (likely new thoughts)
        if i < len(lines) - 1:
            current_ends_sentence = line.rstrip().endswith(('.', '!', '?'))
            next_starts_capital = lines[i + 1].strip() and lines[i + 1].strip()[0].isupper()
            
            # Add paragraph break if current line ends a sentence and next starts with capital
            if current_ends_sentence and next_starts_capital:
                # But don't add if the next line is very short (likely a continuation)
                if len(lines[i + 1].strip()) > 10:
                    formatted_lines.append('')  # Add blank line
    
    return '\n'.join(formatted_lines)

def extract_text_from_subtitles(content, filename):
    """
    Extract plain text from subtitle content (VTT or SRT format).
    Preserves natural sentence breaks and paragraphs.
    """
    lines = content.split('\n')
    text_lines = []
    
    # Determine if it's VTT or SRT
    is_vtt = filename.endswith('.vtt') or 'WEBVTT' in content
    
    if is_vtt:
        # Process VTT format
        in_cue = False
        current_cue_lines = []
        
        for line in lines:
            line = line.strip()
            
            # Skip VTT header and metadata
            if line.startswith('WEBVTT') or line.startswith('NOTE') or line.startswith('STYLE'):
                continue
            
            # Skip timestamp lines
            if '-->' in line:
                # Save previous cue if exists
                if current_cue_lines:
                    cue_text = ' '.join(current_cue_lines)
                    if cue_text:
                        text_lines.append(cue_text)
                    current_cue_lines = []
                in_cue = True
                continue
            
            # Empty line indicates end of cue
            if not line:
                if current_cue_lines:
                    cue_text = ' '.join(current_cue_lines)
                    if cue_text:
                        text_lines.append(cue_text)
                    current_cue_lines = []
                in_cue = False
                continue
            
            # Extract text content (skip cue settings)
            if in_cue and not line.startswith('<') and not line.endswith('>'):
                # Remove VTT formatting tags
                clean_line = re.sub(r'<[^>]+>', '', line)
                clean_line = re.sub(r'&[a-zA-Z]+;', '', clean_line)  # Remove HTML entities
                if clean_line.strip():
                    current_cue_lines.append(clean_line.strip())
        
        # Don't forget the last cue
        if current_cue_lines:
            cue_text = ' '.join(current_cue_lines)
            if cue_text:
                text_lines.append(cue_text)
    
    else:
        # Process SRT format
        current_subtitle_lines = []
        
        for line in lines:
            line = line.strip()
            
            # Skip sequence numbers
            if line.isdigit():
                continue
            
            # Skip timestamp lines
            if '-->' in line:
                continue
            
            # Empty line indicates end of subtitle block
            if not line:
                if current_subtitle_lines:
                    subtitle_text = ' '.join(current_subtitle_lines)
                    if subtitle_text:
                        text_lines.append(subtitle_text)
                    current_subtitle_lines = []
                continue
            
            # This should be subtitle text
            # Remove SRT formatting tags
            clean_line = re.sub(r'<[^>]+>', '', line)
            clean_line = re.sub(r'\{[^}]+\}', '', clean_line)  # Remove formatting
            if clean_line.strip():
                current_subtitle_lines.append(clean_line.strip())
        
        # Don't forget the last subtitle
        if current_subtitle_lines:
            subtitle_text = ' '.join(current_subtitle_lines)
            if subtitle_text:
                text_lines.append(subtitle_text)
    
    # Join with line breaks to preserve natural flow
    full_text = '\n'.join(text_lines)
    
    # Clean up excessive whitespace but preserve line breaks
    full_text = re.sub(r'[ \t]+', ' ', full_text)  # Normalize spaces and tabs
    full_text = re.sub(r'\n\s*\n\s*\n+', '\n\n', full_text)  # Limit to max 2 consecutive newlines
    full_text = full_text.strip()
    
    return full_text

def list_available_subtitles(url):
    """
    List all available subtitles for a video without downloading.
    """
    try:
        cmd = [
            'yt-dlp',
            '--list-subs',
            '--no-download',
            url
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print("Available subtitles:")
        print(result.stdout)
        return True
    
    except subprocess.CalledProcessError as e:
        print(f"Error listing subtitles: {e}")
        return False

def process_url(url, output_dir, languages=['en'], list_only=False, 
                prefer_auto=False, copy_to_clipboard=False, add_paragraphs=True):
    """
    Process a single URL (video or playlist) and download transcripts.
    """
    if list_only:
        print(f"Listing available subtitles for: {url}")
        return list_available_subtitles(url)
    
    print(f"Processing URL: {url}")
    
    # Determine if it's a playlist or single video
    playlist_id = extract_playlist_id(url)
    
    if playlist_id:
        print(f"Processing playlist: {playlist_id}")
        output_subdir = Path(output_dir) / f"playlist_{playlist_id}"
    else:
        video_id = extract_video_id(url)
        if video_id:
            print(f"Processing video: {video_id}")
            output_subdir = Path(output_dir) / f"video_{video_id}"
        else:
            print(f"Processing URL with auto-generated folder name")
            output_subdir = Path(output_dir) / "downloads"
    
    # Download subtitles
    success = download_subtitles(url, str(output_subdir), languages, prefer_auto)
    
    if success:
        # Convert subtitles to plain text
        converted_files = convert_subtitles_to_text(str(output_subdir), 'txt', add_paragraphs)
        
        # Copy last file to clipboard if requested
        if copy_to_clipboard and converted_files:
            try:
                with open(converted_files[-1], 'r', encoding='utf-8') as f:
                    content = f.read()
                pyperclip.copy(content)
                print(f"Copied {converted_files[-1].name} to clipboard")
            except Exception as e:
                print(f"Error copying to clipboard: {e}")
        
        print(f"Successfully processed. Files saved to: {output_subdir}")
        return len(converted_files)
    
    return 0

def read_urls_from_file(file_path):
    """
    Read URLs from a text file (one URL per line).
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        print(f"Read {len(urls)} URLs from {file_path}")
        return urls
    except Exception as e:
        print(f"Error reading URLs from file: {e}")
        return []

def main():
    parser = argparse.ArgumentParser(
        description='Download transcripts from YouTube videos or playlists using yt-dlp',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "https://www.youtube.com/watch?v=VIDEO_ID"
  %(prog)s "https://www.youtube.com/playlist?list=PLAYLIST_ID" --prefer-auto
  %(prog)s -f urls.txt --languages en es fr
  %(prog)s --list-subs "https://www.youtube.com/watch?v=VIDEO_ID"
        """
    )
    
    parser.add_argument('urls', nargs='*', 
                        help='YouTube video or playlist URLs (space separated)')
    parser.add_argument('-f', '--file', 
                        help='Text file with YouTube URLs (one per line)')
    parser.add_argument('-o', '--output-dir', default='~/YoutubeTranscripts',
                        help='Output directory (default: ~/YoutubeTranscripts)')
    parser.add_argument('-l', '--languages', nargs='+', default=['en'],
                        help='Preferred languages (default: en)')
    parser.add_argument('-c', '--clipboard', action='store_true',
                        help='Copy the last transcript to clipboard')
    parser.add_argument('--list-subs', action='store_true',
                        help='List available subtitles without downloading')
    parser.add_argument('--no-paragraphs', action='store_true',
                        help='Disable automatic paragraph formatting')
    parser.add_argument('--prefer-auto', action='store_true',
                        help='Prefer auto-generated subtitles over manual (default: prefer manual)')
    
    args = parser.parse_args()
    
    # Check if yt-dlp is installed
    if not check_ytdlp_installed():
        sys.exit(1)
    
    # Collect all URLs
    urls = args.urls or []
    if args.file:
        file_urls = read_urls_from_file(args.file)
        urls.extend(file_urls)
    
    if not urls:
        print("Error: No YouTube URLs provided. Use command line arguments or a file.")
        parser.print_help()
        sys.exit(1)
    
    # Create output directory
    if not args.list_subs:
        # Expand user path (~)
        output_dir = Path(args.output_dir).expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)
        args.output_dir = str(output_dir)  # Update args with expanded path
        print(f"Output directory: {output_dir.absolute()}")
    
    # Process each URL
    total_successful = 0
    for i, url in enumerate(urls):
        print(f"\n{'='*60}")
        print(f"Processing URL {i+1}/{len(urls)}")
        print(f"{'='*60}")
        
        copy_to_clipboard = args.clipboard and (i == len(urls) - 1)
        successful = process_url(
            url, 
            args.output_dir, 
            args.languages,
            args.list_subs,
            args.prefer_auto,  # Now defaults to False (prefer manual)
            copy_to_clipboard,
            not args.no_paragraphs  # Add paragraphs unless disabled
        )
        
        if isinstance(successful, int):
            total_successful += successful
    
    if not args.list_subs:
        print(f"\n{'='*60}")
        print(f"Summary: Successfully downloaded {total_successful} transcripts from {len(urls)} URLs")
        print(f"Files saved to: {Path(args.output_dir).absolute()}")

if __name__ == '__main__':
    main()
