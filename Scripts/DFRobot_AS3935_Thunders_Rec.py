

import sys
sys.path.append('../')
import time
from DFRobot_AS3935_Lib import DFRobot_AS3935
import RPi.GPIO as GPIO
from datetime import datetime
import subprocess
import os
import json
import logging

# --- Configuration Loading ---
CONFIG_FILE = 'config.json'
config = {}

try:
    # Adjust path if running from a subdirectory
    script_dir = os.path.dirname(__file__)
    config_path = os.path.join(script_dir, '..', CONFIG_FILE) # Assuming config.json is in parent dir
    with open(config_path, 'r') as f:
        config = json.load(f)
except FileNotFoundError:
    print(f"Error: {CONFIG_FILE} not found. Please create it with default parameters.")
    sys.exit(1)
except json.JSONDecodeError:
    print(f"Error: Could not decode JSON from {CONFIG_FILE}. Check file format.")
    sys.exit(1)

# --- Logging Setup ---
LOG_FILE = config.get("log_file", "thunder_recorder.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout) # Also log to console for immediate feedback
    ]
)
logger = logging.getLogger(__name__)

# Log startup message
logger.info("Thunder Recording Script starting up...")

# Now replace the hardcoded values with config values
AS3935_I2C_ADDR = config.get("AS3935_I2C_ADDR", 3)
AS3935_CAPACITANCE = config.get("AS3935_CAPACITANCE", 96)
IRQ_PIN = config.get("IRQ_PIN", 7)

DEVICE = config.get("DEVICE", "plughw:3,0")
RECORDING_LENGTH = config.get("RECORDING_LENGTH", 60)
recording_directory = config.get("recording_directory", "/tmp/thunder_recordings")

# Ensure recording directory exists
os.makedirs(recording_directory, exist_ok=True)

# Variables for lightning detection - still global but initialized later
lightning_distance = 0
lightning_intensity = 0

recording_process = None
recording_start_time = None


GPIO.setmode(GPIO.BOARD)

sensor = DFRobot_AS3935(AS3935_I2C_ADDR, bus = 1)
if (sensor.reset()):
  logger.info("init sensor sucess.")
else:
  logger.error("init sensor fail")
  while True:
    pass
#Configure sensor
sensor.power_up()

#set indoors or outdoors models
sensor.set_indoors()
#sensor.set_outdoors()

#disturber detection
sensor.disturber_en()
#sensor.disturber_dis()

sensor.set_irq_output_source(0)
time.sleep(0.5)
#set capacitance
sensor.set_tuning_caps(AS3935_CAPACITANCE)

# Connect the IRQ and GND pin to the oscilloscope.
# uncomment the following sentences to fine tune the antenna for better performance.
# This will dispaly the antenna's resonance frequency/16 on IRQ pin (The resonance frequency will be divided by 16 on this pin)
# Tuning AS3935_CAPACITANCE to make the frequency within 500/16 kHz plus 3.5% to 500/16 kHz minus 3.5%
#
# sensor.setLco_fdiv(0)
# sensor.setIrq_output_source(3)

#Set the noise level,use a default value greater than 7
sensor.set_noise_floor_lv1(config.get("noise_floor_lv1", 2))

#used to modify WDTH,alues should only be between 0x00 and 0x0F (0 and 7)
sensor.set_watchdog_threshold(config.get("watchdog_threshold", 2))

#used to modify SREJ (spike rejection),values should only be between 0x00 and 0x0F (0 and 7)
sensor.set_spike_rejection(config.get("spike_rejection", 2))

#view all register data
#sensor.print_all_regs()


# Function to start audio recording
def start_recording():
    global recording_process, recording_start_time, lightning_distance, lightning_intensity
    
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    filename = f"thunder_{timestamp}_intensity{lightning_intensity}_distance{lightning_distance}.wav"
    filepath = os.path.join(recording_directory, filename)
    
    logger.info(f"Recording started: {filename}")
    
    # Start recording using arecord
    recording_process = subprocess.Popen(['arecord', '-D', DEVICE, '-r', 'S24_3LE', '-c4', filepath])
    recording_start_time = time.time()

# Function to stop audio recording
def stop_recording():
    global recording_process
    if recording_process is not None:
        logger.info("Stopping recording...")
        recording_process.terminate()
        recording_process = None


try:
    while True:
        # If we're recording, check if the recording timer needs to be reset or stopped
        if recording_process and (time.time() - recording_start_time > RECORDING_LENGTH):
            stop_recording()
        
        time.sleep(0.1)  # A small delay to prevent high CPU usage

except KeyboardInterrupt:
    logger.info("Exiting...")
    if recording_process:
        stop_recording()




def callback_handle(channel):
  global sensor, recording_start_time, lightning_distance, lightning_intensity
 
  time.sleep(0.005)
  intSrc = sensor.get_interrupt_src()
  if intSrc == 1:
    lightning_distKm = sensor.get_lightning_distKm()
    logger.info('Lightning occurs!')
    logger.info('Distance: %dkm'%lightning_distKm)
    lightning_energy_val = sensor.get_strike_energy_raw()
    logger.info('Intensity: %d '%lightning_energy_val)

    lightning_distance = sensor.get_lightning_distKm()
    lightning_intensity = sensor.get_strike_energy_raw()

    

    
  elif intSrc == 2:
    logger.warning('Disturber discovered!')

    if recording_process is None:
        # Start a new recording
        start_recording()
    else:
        # Reset the recording timer if already recording
        recording_start_time = time.time()

  elif intSrc == 3:
    logger.warning('Noise level too high!')
  else:
    pass
#Set to input mode
GPIO.setup(IRQ_PIN, GPIO.IN)
#Set the interrupt pin, the interrupt function, rising along the trigger
GPIO.add_event_detect(IRQ_PIN, GPIO.RISING, callback=callback_handle)
logger.info("start lightning detect.")

while True:
  time.sleep(1.0)





