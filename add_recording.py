import os
import json
import argparse
from datetime import datetime

# Assume these are in the same directory or adjust path
import waveform
import database

def load_config():
    """Loads the configuration from config.json."""
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        print(f"Error: {config_path} not found or invalid.", file=os.stderr)
        return {}

def add_single_recording(wav_file_path, distance_km=None, intensity=None):
    config = load_config()
    if not config:
        print("Failed to load configuration. Cannot add recording.", file=os.stderr)
        return

    db_path = os.path.join(os.path.dirname(__file__), config.get("database_file", "db/recordings.db"))
    recording_dir = os.path.join(os.path.dirname(__file__), config.get("recording_directory", "recordings"))
    waveform_dir_full_path = os.path.join(os.path.dirname(__file__), config.get("waveform_directory", "static/waveforms"))
    
    os.makedirs(recording_dir, exist_ok=True)
    os.makedirs(waveform_dir_full_path, exist_ok=True)

    # Copy the wav file to the recording directory
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_wav_filename = f"manual_{ts}_{os.path.basename(wav_file_path)}"
    destination_wav_path = os.path.join(recording_dir, new_wav_filename)
    
    try:
        import shutil
        shutil.copy(wav_file_path, destination_wav_path)
        print(f"Copied {wav_file_path} to {destination_wav_path}")
    except FileNotFoundError:
        print(f"Error: Source WAV file not found at {wav_file_path}", file=os.stderr)
        return
    except Exception as e:
        print(f"Error copying WAV file: {e}", file=os.stderr)
        return

    waveform_filename = f"manual_{ts}_{os.path.splitext(os.path.basename(wav_file_path))[0]}.png"
    waveform_filepath_full = os.path.join(waveform_dir_full_path, waveform_filename)
    
    print(f"Generating waveform for {destination_wav_path}...")
    if waveform.generate_waveform_image(destination_wav_path, waveform_filepath_full):
        print(f"Waveform generated at {waveform_filepath_full}")

        # Store relative path for web access
        waveform_image_path_relative = os.path.join('waveforms', waveform_filename) 

        db_metadata = {
            'wav_filepath': destination_wav_path,
            'waveform_image_path': waveform_image_path_relative,
            'distance_km': distance_km,
            'intensity': intensity,
            'timestamp': datetime.now().isoformat()
        }
        database.add_recording(db_path, db_metadata)
        print("Recording added to database.")
    else:
        print(f"Failed to generate waveform for {destination_wav_path}", file=os.stderr)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Add a WAV file recording and its waveform to the Thunder Capture database.")
    parser.add_argument("wav_file", help="Path to the WAV file to add.")
    parser.add_argument("--distance", type=float, help="Optional: Distance in km of the lightning strike.")
    parser.add_argument("--intensity", type=int, help="Optional: Intensity of the lightning strike.")
    
    args = parser.parse_args()

    add_single_recording(args.wav_file, args.distance, args.intensity)
