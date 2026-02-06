import RPi.GPIO as GPIO
import time
import subprocess
import os

# Pin where the AS3935 lightning sensor is connected
THUNDER_PIN = 17  # Change this to the correct GPIO pin you're using

# Audio Recording Settings
DEVICE = "plughw:1,0"  # Adjust based on your input device, use 'arecord -l' to find it
RECORDING_LENGTH = 60  # Seconds

recording_process = None
recording_start_time = None

# Function to start audio recording
def start_recording():
    global recording_process, recording_start_time
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    filename = f"thunder_{timestamp}.wav"
    print(f"Recording started: {filename}")
    
    # Start recording using arecord
    recording_process = subprocess.Popen(['arecord', '-D', DEVICE, '-f', 'cd', filename])
    recording_start_time = time.time()

# Function to stop audio recording
def stop_recording():
    global recording_process
    if recording_process is not None:
        print("Stopping recording...")
        recording_process.terminate()
        recording_process = None

# Function to handle the thunder detection
def handle_thunder_detected(channel):
    global recording_start_time
    
    print("Thunder detected!")
    
    if recording_process is None:
        # Start a new recording
        start_recording()
    else:
        # Reset the recording timer if already recording
        recording_start_time = time.time()

# GPIO Setup
GPIO.setmode(GPIO.BCM)
GPIO.setup(THUNDER_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

# Attach the thunder detection handler to the GPIO pin
GPIO.add_event_detect(THUNDER_PIN, GPIO.RISING, callback=handle_thunder_detected)

print("Listening for thunder...")

try:
    while True:
        # If we're recording, check if the recording timer needs to be reset or stopped
        if recording_process and (time.time() - recording_start_time > RECORDING_LENGTH):
            stop_recording()
        
        time.sleep(0.1)  # A small delay to prevent high CPU usage

except KeyboardInterrupt:
    print("Exiting...")
    if recording_process:
        stop_recording()
finally:
    GPIO.cleanup()
