import os
import json
import subprocess
import threading
import time
import sys
import platform
from flask import Flask, request, jsonify, render_template, send_from_directory
from datetime import datetime
import collections
from scipy.io import wavfile # Import wavfile to read duration

# Custom module imports
import database
import waveform

app = Flask(__name__)

# --- Configuration and Global State ---
CONFIG_FILE = 'config.json'
IS_RASPBERRY_PI = platform.system() == 'Linux'

# System State
SYSTEM_STATE = "IDLE" # Possible states: IDLE, LISTENING, RECORDING, PROCESSING, ERROR
recorder_thread = None
stop_event = threading.Event()
state_lock = threading.Lock()

# In-memory log caches
log_lock = threading.Lock()
server_log_cache = collections.deque(maxlen=200)
capture_log_cache = collections.deque(maxlen=500) # Larger cache for potentially verbose capture logs

# --- Logging Setup ---

class StreamToLogger:
    """
    A file-like object that redirects a stream (like stdout or stderr)
    to both the original stream and a thread-safe in-memory deque.
    """
    def __init__(self, original_stream, log_deque, lock):
        self.original_stream = original_stream
        self.log_deque = log_deque
        self.lock = lock

    def write(self, buf):
        # Write to the original stream
        self.original_stream.write(buf)
        self.original_stream.flush()
        # Append to our in-memory cache
        with self.lock:
            self.log_deque.append(buf)

    def flush(self):
        self.original_stream.flush()

# Redirect stdout and stderr to the server log cache
sys.stdout = StreamToLogger(sys.stdout, server_log_cache, log_lock)
sys.stderr = StreamToLogger(sys.stderr, server_log_cache, log_lock)


# --- Helper Functions ---

def set_system_state(new_state):
    """Thread-safe function to update the system state."""
    global SYSTEM_STATE
    with state_lock:
        SYSTEM_STATE = new_state
    print(f"System state changed to: {SYSTEM_STATE}")

def load_config():
    """Loads the configuration from config.json."""
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        print(f"Warning: {CONFIG_FILE} not found or invalid.", file=sys.stderr)
        return {}

def save_config(data):
    """Saves the provided dictionary to config.json."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(data, f, indent=4)
        return True
    except IOError as e:
        print(f"Error saving configuration to {CONFIG_FILE}: {e}", file=sys.stderr)
        return False

# --- Main Recorder Lifecycle ---

def recorder_lifecycle(config, stop_event_flag):
    """
    The main background thread that manages the detection, recording,
    and processing lifecycle.
    """
    db_path = config.get("database_file", "db/recordings.db")
    
    while not stop_event_flag.is_set():
        # --- 1. LISTENING State ---
        set_system_state("LISTENING")
        lightning_data = None
        
        # Clear capture log before starting
        with log_lock:
            capture_log_cache.clear()

        if IS_RASPBERRY_PI:
            script_path = os.path.join(os.path.dirname(__file__), config.get("thunder_recorder_script"))
            try:
                # Use line-buffering (bufsize=1) and text mode
                detector_process = subprocess.Popen(
                    ['python3', '-u', script_path], # -u for unbuffered output
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, # Redirect stderr to stdout
                    text=True,
                    bufsize=1 
                )
                
                # Stream output line by line
                for line in iter(detector_process.stdout.readline, ''):
                    if stop_event_flag.is_set():
                        detector_process.terminate() # Stop the script if stop is signaled
                        break
                    
                    # Log to both capture log and main server log
                    with log_lock:
                        capture_log_cache.append(line)
                    print(f"[Detector] {line.strip()}") # Also log to main server log for context

                    # Check for the specific JSON output indicating detection
                    try:
                        # The script should ONLY output JSON upon successful detection
                        potential_json = json.loads(line)
                        if potential_json.get("event") == "lightning":
                            lightning_data = potential_json
                            break # Exit the loop to proceed with recording
                    except json.JSONDecodeError:
                        continue # Not a JSON line, just a regular log, so continue listening
                
                detector_process.stdout.close()
                return_code = detector_process.wait()

                if return_code != 0 and not lightning_data:
                    print(f"Detector script exited with non-zero code: {return_code}", file=sys.stderr)

            except Exception as e:
                print(f"Error running detector script: {e}", file=sys.stderr)
        else:
            # --- SIMULATION for local testing ---
            print("SIMULATION: Simulating lightning detection...")
            with log_lock:
                capture_log_cache.append("SIMULATOR: Listening for thunder...\n")
            time.sleep(15) # Wait for 15 seconds to simulate listening
            if stop_event_flag.is_set(): break
            # Fake a lightning event
            lightning_data = {"event": "lightning", "distance_km": 10, "intensity": 5000}
            sim_log = f"SIMULATOR: Detected lightning! Data: {json.dumps(lightning_data)}\n"
            print(f"SIMULATION: {lightning_data}")
            with log_lock:
                capture_log_cache.append(sim_log)

        # --- 2. RECORDING State ---
        if lightning_data and lightning_data.get("event") == "lightning":
            set_system_state("RECORDING")
            
            # Create unique filenames
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            wav_filename = f"thunder_{ts}.wav"
            waveform_filename = f"thunder_{ts}.png"

            # Define paths from config
            recording_dir = config.get("recording_directory", "recordings")
            waveform_dir = config.get("waveform_directory", "static/waveforms")
            
            # Create absolute paths
            wav_filepath = os.path.join(recording_dir, wav_filename)
            waveform_filepath = os.path.join(waveform_dir, waveform_filename)

            # Ensure directories exist
            os.makedirs(recording_dir, exist_ok=True)
            os.makedirs(waveform_dir, exist_ok=True)

            recording_duration = config.get("RECORDING_LENGTH", 15)
            actual_wav_duration = 0.0 # Initialize actual duration

            if IS_RASPBERRY_PI:
                try:
                    device = config.get("DEVICE", "plughw:1,0")
                    # Note: arecord format might need to be configurable
                    arecord_cmd = ['arecord', '-D', device, '-f', 'cd', '-d', str(recording_duration), wav_filepath]
                    print(f"Executing: {' '.join(arecord_cmd)}")
                    subprocess.run(arecord_cmd, check=True)
                    # Get actual duration after recording
                    if os.path.exists(wav_filepath):
                        samplerate, data = wavfile.read(wav_filepath)
                        actual_wav_duration = len(data) / samplerate

                except Exception as e:
                    print(f"Error during recording: {e}", file=sys.stderr)
                    set_system_state("ERROR")
                    time.sleep(5)
                    continue # Skip to next listening cycle
            else:
                print(f"SIMULATION: Faking recording for {recording_duration}s to {wav_filepath}")
                time.sleep(2) # Simulate recording time
                # Create a dummy empty wav file for the simulation
                with open(wav_filepath, 'w') as f: f.write("dummy")
                actual_wav_duration = recording_duration # In simulation, assume recorded length is config length


            # --- 3. PROCESSING State ---
            set_system_state("PROCESSING")
            print("Generating waveform...")
            
            # Generate waveform (this will fail in simulation if scipy can't read the dummy file)
            # We'll add a check in the waveform generator to handle this
            waveform.generate_waveform_image(wav_filepath, waveform_filepath)

            print("Adding record to database...")
            db_metadata = {
                'wav_filepath': wav_filepath,
                'waveform_image_path': os.path.join('waveforms', waveform_filename), # Store relative path for web
                'distance_km': lightning_data.get("distance_km"),
                'intensity': lightning_data.get("intensity"),
                'duration_seconds': actual_wav_duration # Add duration
            }
            database.add_recording(db_path, db_metadata)
        
        if stop_event_flag.is_set():
            break
            
    set_system_state("IDLE")
    print("Recorder lifecycle thread has stopped.")

# --- Control Functions ---

def start_recorder():
    global recorder_thread, stop_event
    with state_lock:
        if recorder_thread and recorder_thread.is_alive():
            return False # Already running
        
        config = load_config()
        stop_event.clear()
        recorder_thread = threading.Thread(target=recorder_lifecycle, args=(config, stop_event), daemon=True)
        recorder_thread.start()
        return True

def stop_recorder():
    global recorder_thread, stop_event
    with state_lock:
        if not recorder_thread or not recorder_thread.is_alive():
            return False # Not running
            
        print("Signaling recorder thread to stop...")
        stop_event.set()
        # The thread will stop on its own time, we don't block here with join()
        # to keep the UI responsive.
        return True

# --- Flask Routes ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

@app.route('/waveforms/<path:filename>')
def send_waveform_image(filename):
    # This serves images from the 'static/waveforms' directory
    return send_from_directory(os.path.join('static', 'waveforms'), filename)

@app.route('/api/config', methods=['GET', 'POST'])
def handle_config():
    if request.method == 'GET':
        return jsonify(load_config())
    elif request.method == 'POST':
        if save_config(request.json):
            return jsonify({"status": "success", "message": "Configuration updated."}), 200
        return jsonify({"status": "error", "message": "Failed to save configuration."}), 500

@app.route('/api/status')
def get_status():
    status = {
        "system_state": SYSTEM_STATE,
        "is_running": recorder_thread.is_alive() if recorder_thread else False
    }
    return jsonify(status)
    
@app.route('/api/recordings')
def get_recordings():
    config = load_config()
    db_path = config.get("database_file", "db/recordings.db")
    all_recordings = database.get_all_recordings(db_path)
    return jsonify(all_recordings)

@app.route('/api/server_logs')
def get_server_logs():
    with log_lock:
        # Create a snapshot of the current logs
        logs = list(server_log_cache)
    return jsonify({"logs": logs})

@app.route('/api/capture_logs')
def get_capture_logs():
    with log_lock:
        # Create a snapshot of the current logs
        logs = list(capture_log_cache)
    return jsonify({"logs": logs})

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

# Git sync endpoint remains the same
@app.route('/api/git_sync', methods=['POST'])
def api_git_sync():
    try:
        git_dir = os.path.dirname(__file__)
        if not os.path.isdir(os.path.join(git_dir, '.git')):
            return jsonify({"status": "error", "message": "Not a Git repository."}), 400
        git_process = subprocess.Popen(['git', 'pull'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=git_dir)
        stdout, _ = git_process.communicate()
        if git_process.returncode == 0:
            return jsonify({"status": "success", "message": "Repository updated successfully.", "output": stdout}), 200
        else:
            return jsonify({"status": "error", "message": "Git pull failed.", "output": stdout}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": f"An error occurred: {str(e)}"}), 500

if __name__ == '__main__':
    # Initialize DB on startup
    app_config = load_config()
    db_path = app_config.get("database_file", "db/recordings.db")
    database.init_db(db_path)
    
    app.run(host='0.0.0.0', port=5001, debug=True)
