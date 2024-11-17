from __future__ import annotations

import argparse
import os
import re
from typing import Any

import isodate2  # type: ignore
from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from youtube_transcript_api import YouTubeTranscriptApi  # type: ignore


def get_video_id(url: str) -> str | None:
    """Extract video ID from URL"""
    pattern = r"(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})"
    match = re.search(pattern, url)
    return match.group(1) if match else None


def get_comments(youtube, video_id: str) -> list[dict]:
    """Fetch comments from a YouTube video"""
    comments = []

    try:
        # Fetch top-level comments
        request = youtube.commentThreads().list(
            part="snippet,replies",
            videoId=video_id,
            textFormat="plainText",
            maxResults=100,  # Adjust based on needs
        )

        while request:
            response = request.execute()
            for item in response["items"]:
                # Top-level comment
                top_level_comment = item["snippet"]["topLevelComment"]["snippet"]["textDisplay"]
                comments.append(top_level_comment)

                # Check if there are replies in the thread
                if "replies" in item:
                    for reply in item["replies"]["comments"]:
                        reply_text = reply["snippet"]["textDisplay"]
                        # Add incremental spacing and a dash for replies
                        comments.append("    - " + reply_text)

            # Prepare the next page of comments, if available
            if "nextPageToken" in response:
                request = youtube.commentThreads().list_next(previous_request=request, previous_response=response)
            else:
                request = None

    except HttpError as e:
        print(f"Failed to fetch comments: {e}")

    return comments


def fetch_yt_data(url: str, options: Any) -> dict[str, Any] | None:
    """Main function to fetch video metadata and comments"""
    # Load environment variables from .env file
    load_dotenv(os.path.expanduser("~/.parllama/.env"))
    load_dotenv(os.path.expanduser("~/.config/fabric/.env"))

    # Get YouTube API key from environment variable
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        # print(
        #     "Error: YOUTUBE_API_KEY not found in ~/.parllama/.env or ~/.config/fabric/.env"
        # )
        return None

    # Extract video ID from URL
    video_id = get_video_id(url)
    if not video_id:
        # print("Invalid YouTube URL")
        return None

    try:
        # Initialize the YouTube API client
        youtube = build("youtube", "v3", developerKey=api_key)

        # Get video details
        video_response = youtube.videos().list(id=video_id, part="contentDetails,snippet").execute()

        # Extract video duration and convert to minutes
        duration_iso = video_response["items"][0]["contentDetails"]["duration"]  # type: ignore
        duration_seconds = isodate2.parse_duration(duration_iso).total_seconds()
        duration_minutes = round(duration_seconds / 60)
        # Set up metadata
        metadata: dict[str, Any] = {
            "id": video_response["items"][0]["id"],  # type: ignore
            "title": video_response["items"][0]["snippet"]["title"],  # type: ignore
            "channel": video_response["items"][0]["snippet"]["channelTitle"],  # type: ignore
            "published_at": video_response["items"][0]["snippet"]["publishedAt"],  # type: ignore
        }

        # Get video transcript
        try:
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=[options.lang])
            transcript_text = " ".join([item["text"] for item in transcript_list])
            transcript_text = transcript_text.replace("\n", " ")
        except Exception as e:
            transcript_text = f"Transcript not available in the selected language ({options.lang}). ({e})"

        # Get comments if the flag is set
        comments = []
        if options.comments:
            comments = get_comments(youtube, video_id)

        output = {
            "transcript": transcript_text,
            "duration": duration_minutes,
            "comments": comments,
            "metadata": metadata,
        }
        return output
    except HttpError:
        return None
        # print(
        #     f"Error: Failed to access YouTube API. Please check your YOUTUBE_API_KEY and ensure it is valid: {e}"
        # )


def main() -> None:
    """Main Function for standalone run"""
    parser = argparse.ArgumentParser(
        description="yt (video meta) extracts metadata about a video, such as the transcript, the video's duration, and now comments. By Daniel Miessler."
    )
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument("--duration", action="store_true", help="Output only the duration")
    parser.add_argument("--transcript", action="store_true", help="Output only the transcript")
    parser.add_argument("--comments", action="store_true", help="Output the comments on the video")
    parser.add_argument("--metadata", action="store_true", help="Output the video metadata")
    parser.add_argument("--lang", default="en", help="Language for the transcript (default: English)")

    args = parser.parse_args()

    if args.url is None:
        print("Error: No URL provided.")
        return

    fetch_yt_data(args.url, args)


if __name__ == "__main__":
    main()
