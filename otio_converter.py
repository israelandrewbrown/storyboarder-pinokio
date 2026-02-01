import json
import sys
import opentimelineio as otio

def storyboarder_to_otio(storyboarder_data):
    """
    Converts a Storyboarder JSON object into an OpenTimelineIO Timeline object.
    """
    # Use a default FPS if not found in the data
    fps = storyboarder_data.get("fps", 24) 
    boards = storyboarder_data.get("boards", [])

    # Create a new OTIO Timeline
    timeline = otio.schema.Timeline(name="Storyboarder Project")
    
    # Create tracks
    video_track = otio.schema.Track(name="Video Track")
    audio_track = otio.schema.Track(name="Audio Track")
    timeline.tracks.append(video_track)
    timeline.tracks.append(audio_track)

    for board in boards:
        # 1. Calculate duration as RationalTime
        # Use board's duration, or defaultBoardTiming if board.duration is missing
        duration_seconds = board.get("duration", storyboarder_data.get("defaultBoardTiming", 1.0))
        duration = otio.opentime.RationalTime(duration_seconds, fps)

        # 2. Create a MediaReference for the video clip (board image)
        media_ref = otio.schema.ExternalReference(
            target_url=board.get("url", f"board-{board.get('uid', 'unknown')}.png"),
            available_range=otio.opentime.TimeRange(duration=duration)
        )

        # 3. Create the Video Clip
        video_clip = otio.schema.Clip(
            name=f"Board {board.get('uid', 'unknown')}",
            media_reference=media_ref,
            source_range=otio.opentime.TimeRange(duration=duration)
        )

        # 4. Add Storyboarder metadata to the video clip
        video_clip.metadata["storyboarder"] = {
            "uid": board.get("uid"),
            "dialogue": board.get("dialogue"),
            "newShot": board.get("newShot"),
            "duration_seconds": duration_seconds
            # Add other relevant board data here
        }

        # 5. Add the video clip to the video track
        video_track.append(video_clip)

        # 6. Create Audio Clips for each track
        audio_tracks = board.get("audio", [])
        if isinstance(audio_tracks, dict): # Handle old single-track format
            audio_tracks = [audio_tracks]

        for track_data in audio_tracks:
            if track_data and track_data.get("filename"):
                audio_duration_seconds = track_data.get("duration", duration_seconds)
                audio_duration = otio.opentime.RationalTime(audio_duration_seconds, fps)

                audio_media_ref = otio.schema.ExternalReference(
                    target_url=track_data["filename"],
                    available_range=otio.opentime.TimeRange(duration=audio_duration)
                )

                audio_clip = otio.schema.Clip(
                    name=f"Audio {track_data['filename']}",
                    media_reference=audio_media_ref,
                    source_range=otio.opentime.TimeRange(duration=audio_duration)
                )
                audio_clip.metadata["storyboarder"] = {
                    "filename": track_data["filename"],
                    "duration": audio_duration_seconds
                }
                audio_track.append(audio_clip)

    return timeline

def otio_to_storyboarder(otio_json_string):
    """
    Converts an OTIO JSON string into a Storyboarder JSON object.
    """
    timeline = otio.adapters.read_from_string(otio_json_string, "otio_json")
    
    storyboarder_data = {
        "version": "2.0", # Assuming current version
        "boards": [],
        "defaultBoardTiming": 1.0, # Placeholder, could be derived from common clip duration
        "fps": 24 # Placeholder, could be derived from RationalTime rate
    }

    # Find the video track and the audio track
    video_track = None
    audio_clips = []
    
    for t in timeline.tracks:
        if t.name == "Video Track":
            video_track = t
        elif t.name == "Audio Track":
            # Collect all audio clips from the audio track
            for item in t:
                if isinstance(item, otio.schema.Clip):
                    audio_clips.append(item)

    if not video_track:
        return storyboarder_data

    # Try to infer FPS from the first video clip's source range
    if len(video_track) and isinstance(video_track[0], otio.schema.Clip):
        try:
            storyboarder_data["fps"] = video_track[0].source_range.duration.rate
        except AttributeError:
            pass # Keep default 24 fps

    for video_clip in video_track:
        if not isinstance(video_clip, otio.schema.Clip):
            continue

        # Extract duration
        duration_seconds = video_clip.source_range.duration.value
        
        # Extract metadata
        metadata = video_clip.metadata.get("storyboarder", {})

        # Extract media reference URL (for the board image)
        url = video_clip.media_reference.target_url if video_clip.media_reference else f"board-{metadata.get('uid', 'unknown')}.png"

        board = {
            "uid": metadata.get("uid", "new-uid"),
            "url": url,
            "duration": duration_seconds,
            "dialogue": metadata.get("dialogue", ""),
            "newShot": metadata.get("newShot", True),
            "audio": []
        }

        # Find corresponding audio clips (simple approach: all audio clips are assigned to all boards)
        # A more complex approach would be to use TimeRange to determine which audio clips overlap with the video clip
        # For simplicity in this initial implementation, we'll assign all audio clips to the first board
        # and rely on the user to manage audio per board in Storyboarder.
        if not storyboarder_data["boards"]: # Only assign to the first board for now
            for audio_clip in audio_clips:
                audio_metadata = audio_clip.metadata.get("storyboarder", {})
                board["audio"].append({
                    "filename": audio_clip.media_reference.target_url,
                    "duration": audio_metadata.get("duration", audio_clip.source_range.duration.value)
                })

        storyboarder_data["boards"].append(board)

    return storyboarder_data

def main():
    # The first argument is the command: 'export' or 'import'
    if len(sys.argv) < 2:
        print("Usage: python3 otio_converter.py <command>", file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]
    
    # Read the input JSON from stdin
    try:
        input_data = sys.stdin.read()
        if not input_data:
            raise ValueError("No input data received from stdin.")
    except Exception as e:
        print(f"Error reading from stdin: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        if command == "export":
            storyboarder_data = json.loads(input_data)
            otio_timeline = storyboarder_to_otio(storyboarder_data)
            output_json = otio.adapters.write_to_string(otio_timeline, "otio_json")
            print(output_json)
        
        elif command == "import":
            # input_data is the OTIO JSON string
            storyboarder_data = otio_to_storyboarder(input_data)
            output_json = json.dumps(storyboarder_data, indent=2)
            print(output_json)

        else:
            print(f"Unknown command: {command}", file=sys.stderr)
            sys.exit(1)

    except Exception as e:
        print(f"Conversion error for command '{command}': {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
