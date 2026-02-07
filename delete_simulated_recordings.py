import database
import os
import json

def delete_simulated_recordings():
    script_dir = os.path.dirname(__file__)
    config_path = os.path.join(script_dir, 'config.json')
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading config.json: {e}", file=os.stderr)
        return

    db_path = os.path.join(script_dir, config.get('database_file', 'db/recordings.db'))

    # Delete recordings that match the pattern from manual additions
    database.delete_recordings_by_path_pattern(db_path, f"{config.get('recording_directory', '/tmp/thunder_recordings')}/manual_%")
    
    # Delete recordings that match the pattern from server-side simulations
    # control_server.py in simulation mode also uses the recording_directory in config
    database.delete_recordings_by_path_pattern(db_path, f"{config.get('recording_directory', '/tmp/thunder_recordings')}/thunder_%")


if __name__ == "__main__":
    delete_simulated_recordings()
