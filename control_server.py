import os
import json
import subprocess
import threading
import time
import sys
import platform
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

# --- Configuration and Process Management ---
CONFIG_FILE = 'config.json'
IS_RASPBERRY_PI = platform.system() == 'Linux'

# Real process variables
recorder_process = None

# Dummy process variables (for local testing)
dummy_recorder_thread = None
dummy_recorder_stop_event = threading.Event()

process_lock = threading.Lock()
# Store the last known config in a global variable for convenience
current_config = {}

def load_initial_config():
    """Load config at startup to get paths for script and log file."""
    try:
        script_dir = os.path.dirname(__file__)
        config_path = os.path.join(script_dir, CONFIG_FILE)
        with open(config_path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Provide sensible defaults if config is missing or corrupt
        return {
            "thunder_recorder_script": "Scripts/DFRobot_AS3935_Thunders_Rec.py",
            "log_file": "thunder_recorder.log",
            "recording_directory": "/tmp/thunder_recordings" # Default for safety
        }

current_config = load_initial_config()
RECORDER_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), current_config.get("thunder_recorder_script"))
LOG_FILE = os.path.join(os.path.dirname(__file__), current_config.get("log_file"))


def load_config():
    """Loads the configuration from config.json."""
    global current_config
    try:
        script_dir = os.path.dirname(__file__)
        config_path = os.path.join(script_dir, CONFIG_FILE)
        with open(config_path, 'r') as f:
            current_config = json.load(f) # Update global current_config
            return current_config
    except (FileNotFoundError, json.JSONDecodeError):
        # If config file is missing or invalid, return last known good config or empty dict
        print(f"Warning: {CONFIG_FILE} not found or invalid, returning current in-memory config.")
        return current_config if current_config else {}

def save_config(config_data):
    """Saves the configuration to config.json."""
    global current_config
    try:
        script_dir = os.path.dirname(__file__)
        config_path = os.path.join(script_dir, CONFIG_FILE)
        with open(config_path, 'w') as f:
            json.dump(config_data, f, indent=4)
        current_config = config_data # Update global current_config
        return True
    except IOError as e:
        print(f"Error saving config: {e}")
        return False

def dummy_recorder_loop(log_file, stop_event):
    """Simulates the recorder script for local testing."""
    with open(log_file, 'a') as f:
        f.write(f"{time.asctime()} - INFO - Dummy recorder started for local testing.\n")
    
    event_counter = 0
    while not stop_event.is_set():
        time.sleep(10) # Wait for 10 seconds
        if stop_event.is_set():
            break
        
        event_counter += 1
        with open(log_file, 'a') as f:
            if event_counter % 5 == 0: # Simulate a lightning event every 50 seconds
                 f.write(f"{time.asctime()} - INFO - Lightning occurs!\n")
                 f.write(f"{time.asctime()} - INFO - Distance: 15km\n")
                 f.write(f"{time.asctime()} - INFO - Intensity: 12345 \n")
                 f.write(f"{time.asctime()} - INFO - Recording started: thunder_..._simulated.wav\n")
            elif event_counter % 2 == 0: # Simulate a disturber every 20 seconds
                 f.write(f"{time.asctime()} - WARNING - Disturber discovered!\n")
            else:
                 f.write(f"{time.asctime()} - INFO - Still listening...\n")

    with open(log_file, 'a') as f:
        f.write(f"{time.asctime()} - INFO - Dummy recorder stopped.\n")

def is_recorder_running():
    """Checks if the recorder subprocess is currently running."""
    if IS_RASPBERRY_PI:
        global recorder_process
        if recorder_process is not None:
            return recorder_process.poll() is None
    else:
        global dummy_recorder_thread
        return dummy_recorder_thread is not None and dummy_recorder_thread.is_alive()
    return False

def start_recorder():
    """Starts the thunder recording script (or a dummy for local testing)."""
    global recorder_process, dummy_recorder_thread, dummy_recorder_stop_event
    with process_lock:
        if is_recorder_running():
            return False # Already running

        log_dir = os.path.dirname(LOG_FILE)
        os.makedirs(log_dir, exist_ok=True)
        
        if IS_RASPBERRY_PI:
            try:
                recorder_process = subprocess.Popen(
                    ['python3', RECORDER_SCRIPT_PATH],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )
                threading.Thread(target=read_recorder_output, args=(recorder_process, LOG_FILE), daemon=True).start()
                print(f"Recorder script started with PID: {recorder_process.pid}")
                return True
            except Exception as e:
                print(f"Error starting recorder: {e}")
                return False
        else:
            # Local testing mode
            print("Starting dummy recorder for local testing...")
            dummy_recorder_stop_event.clear()
            dummy_recorder_thread = threading.Thread(target=dummy_recorder_loop, args=(LOG_FILE, dummy_recorder_stop_event), daemon=True)
            dummy_recorder_thread.start()
            return True

def read_recorder_output(proc, log_file_path):
    """Reads output from the recorder subprocess and writes it to the log file."""
    with open(log_file_path, 'a') as f:
        for line in proc.stdout:
            f.write(line)
            sys.stdout.write(line)
    proc.stdout.close()
    print(f"Recorder process (PID: {proc.pid}) output stream closed.")


def stop_recorder():
    """Stops the thunder recording script (or the dummy)."""
    global recorder_process, dummy_recorder_thread, dummy_recorder_stop_event
    with process_lock:
        if not is_recorder_running():
            return False # Not running

        if IS_RASPBERRY_PI:
            try:
                print(f"Attempting to terminate recorder process (PID: {recorder_process.pid})...")
                recorder_process.terminate()
                recorder_process.wait(timeout=10)
                print(f"Recorder process (PID: {recorder_process.pid}) stopped.")
            except subprocess.TimeoutExpired:
                print(f"Recorder process (PID: {recorder_process.pid}) did not terminate gracefully, killing...")
                recorder_process.kill()
                recorder_process.wait()
            except Exception as e:
                print(f"Error stopping recorder: {e}")
            finally:
                recorder_process = None
        else:
            # Local testing mode
            print("Stopping dummy recorder...")
            dummy_recorder_stop_event.set()
            dummy_recorder_thread.join(timeout=5)
            dummy_recorder_thread = None
        return True

# --- Flask Routes ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/config', methods=['GET', 'POST'])
def handle_config():
    if request.method == 'GET':
        return jsonify(load_config())
    elif request.method == 'POST':
        if save_config(request.json):
            global RECORDER_SCRIPT_PATH, LOG_FILE
            current_config = load_config()
            RECORDER_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), current_config.get("thunder_recorder_script"))
            LOG_FILE = os.path.join(os.path.dirname(__file__), current_config.get("log_file"))
            return jsonify({"status": "success", "message": "Configuration updated."}), 200
        return jsonify({"status": "error", "message": "Failed to save configuration."}), 500

@app.route('/api/status')
def get_status():
    running = is_recorder_running()
    pid = None
    if running:
        if IS_RASPBERRY_PI:
            pid = recorder_process.pid if recorder_process else None
        else:
            pid = "N/A (Simulated)"
            
    status = {
        "running": running,
        "pid": pid,
        "config": load_config()
    }
    return jsonify(status)

@app.route('/api/start_recorder', methods=['POST'])
def api_start_recorder():
    if start_recorder():
        return jsonify({"status": "success", "message": "Recorder started."}), 200
    return jsonify({"status": "error", "message": "Failed to start recorder or already running."}), 400

@app.route('/api/stop_recorder', methods=['POST'])
def api_stop_recorder():
    if stop_recorder():
        return jsonify({"status": "success", "message": "Recorder stopped."}), 200
    return jsonify({"status": "error", "message": "Failed to stop recorder or not running."}), 400

@app.route('/api/restart_recorder', methods=['POST'])
def api_restart_recorder():
    load_config() 
    if is_recorder_running():
        stop_recorder()
        time.sleep(1) 
    if start_recorder():
        return jsonify({"status": "success", "message": "Recorder restarted."}), 200
    return jsonify({"status": "error", "message": "Failed to restart recorder."}), 400

@app.route('/api/git_sync', methods=['POST'])
def api_git_sync():
    """Executes 'git pull' to update the repository."""
    try:
        # Best to run this in the directory of the script
        git_dir = os.path.dirname(__file__)
        
        # Check if it's a git repository
        if not os.path.isdir(os.path.join(git_dir, '.git')):
            return jsonify({"status": "error", "message": "Not a Git repository."}), 400

        git_process = subprocess.Popen(
            ['git', 'pull'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=git_dir # Run the command in the script's directory
        )
        stdout, _ = git_process.communicate()
        
        if git_process.returncode == 0:
            return jsonify({"status": "success", "message": "Repository updated successfully.", "output": stdout}), 200
        else:
            return jsonify({"status": "error", "message": "Git pull failed.", "output": stdout}), 500
            
    except FileNotFoundError:
        return jsonify({"status": "error", "message": "'git' command not found. Is Git installed and in the system's PATH?"}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": f"An error occurred: {str(e)}"}), 500

@app.route('/api/logs')
def get_logs():
    try:
        with open(LOG_FILE, 'r') as f:
            lines = f.readlines()
            return jsonify({"logs": lines[-100:]}), 200
    except FileNotFoundError:
        return jsonify({"logs": ["Log file not found."]})
    except Exception as e:
        return jsonify({"logs": [f"Error reading log file: {e}"]})

if __name__ == '__main__':
    if not os.path.exists('templates'):
        os.makedirs('templates')
    app.run(host='0.0.0.0', port=5000, debug=True)