import sys
import os
import time
import json
import logging
import threading
import argparse # Import argparse

# This script is now a one-shot detector. It initializes the sensor,
# waits for a lightning event, prints the event data as JSON to stdout,
# and then exits. It will also exit after a timeout if no event is detected.

# Since this script is in a subdirectory, we need to adjust the path to find the library and config
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
try:
    from DFRobot_AS3935_Lib import DFRobot_AS3935
    import RPi.GPIO as GPIO
except (ImportError, RuntimeError):
    print("Error: This script is intended to be run on a Raspberry Pi with RPi.GPIO library installed.")
    # In a non-pi environment, we can define dummy classes to allow for syntax checking.
    class DFRobot_AS3935:
        def __init__(self, addr, bus): pass
        def reset(self): return True
        def power_up(self): pass
        def set_indoors(self): pass
        def set_outdoors(self): pass # Added set_outdoors for completeness
        def disturber_en(self): pass
        def set_irq_output_source(self, val): pass
        def set_tuning_caps(self, val): pass
        def set_noise_floor_lv1(self, val): pass
        def set_watchdog_threshold(self, val): pass
        def set_spike_rejection(self, val): pass
        def get_interrupt_src(self): return 0
        def get_lightning_distKm(self): return 0
        def get_strike_energy_raw(self): return 0
    class GPIO:
        BOARD = 1
        IN = 1
        RISING = 1
        def setmode(self, mode): pass
        def setup(self, pin, mode): pass
        def add_event_detect(self, pin, edge, callback): pass
        def cleanup(self): pass


# --- Configuration Loading ---
CONFIG_FILE = 'config.json'
config = {}
try:
    script_dir = os.path.dirname(__file__)
    # config.json is in the parent directory of this script's directory (Scripts/)
    config_path = os.path.join(script_dir, '..', CONFIG_FILE)
    with open(config_path, 'r') as f:
        config = json.load(f)
except Exception as e:
    print(f"FATAL: Could not load {CONFIG_FILE}. Error: {e}", file=sys.stderr)
    sys.exit(1)

# --- Argument Parsing ---
parser = argparse.ArgumentParser(description="One-shot lightning detector script for AS3935.")
parser.add_argument('--indoor', action='store_true', help='Configure AS3935 for indoor operation.')
args = parser.parse_args()


# --- Logging Setup ---
LOG_FILE = os.path.join(os.path.dirname(__file__), '..', config.get("log_file", "thunder_recorder.log"))
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [Detector] - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# --- Script Parameters ---
AS3935_I2C_ADDR = config.get("AS3935_I2C_ADDR", 3)
AS3935_CAPACITANCE = config.get("AS3935_CAPACITANCE", 96)
IRQ_PIN = config.get("IRQ_PIN", 7)
WAIT_TIMEOUT = 600 # Timeout in seconds (e.g., 10 minutes)

# Use a threading event to signal exit
exit_event = threading.Event()
sensor = None # Define sensor globally to be accessible in callback

def main_exit():
    """Cleanup GPIO and signal exit."""
    GPIO.cleanup()
    exit_event.set()

def callback_handle(channel):
  """
  This function is called by the GPIO interrupt.
  It checks the interrupt source and, if it's lightning,
  prints JSON data to stdout and signals the main thread to exit.
  """
  global sensor
  time.sleep(0.005) # Debounce
  
  try:
    intSrc = sensor.get_interrupt_src()
  except Exception as e:
    logger.error(f"Error getting interrupt source from sensor: {e}")
    return

  if intSrc == 1: # Lightning detected
    distance_km = sensor.get_lightning_distKm()
    intensity = sensor.get_strike_energy_raw()
    
    event_data = {
        "event": "lightning",
        "distance_km": distance_km,
        "intensity": intensity
    }
    # Print JSON to stdout for the parent process (the control_server)
    print(json.dumps(event_data), flush=True)
    
    logger.info(f"Lightning detected! Distance: {distance_km}km, Intensity: {intensity}")
    main_exit() # Signal to exit successfully
    
  elif intSrc == 2: # Disturber
    logger.warning('Disturber discovered!')
    
  elif intSrc == 3: # Noise
    logger.warning('Noise level too high!')

def main():
    global sensor
    
    logger.info("Starting one-shot lightning detector...")
    
    try:
        GPIO.setmode(GPIO.BOARD)
        
        # Initialize Sensor
        sensor = DFRobot_AS3935(AS3935_I2C_ADDR, bus=1)
        if not sensor.reset():
            logger.error("Sensor init failed. Exiting.")
            sys.exit(1)
            
        sensor.power_up()
        
        # Configure for indoor/outdoor based on argument
        if args.indoor:
            sensor.set_indoors()
            logger.info("AS3935 configured for indoor operation.")
        else:
            sensor.set_outdoors()
            logger.info("AS3935 configured for outdoor operation.")
            
        sensor.disturber_en()
        sensor.set_irq_output_source(0)
        time.sleep(0.5)
        sensor.set_tuning_caps(AS3935_CAPACITANCE)
        
        # Set sensitivity parameters from config
        sensor.set_noise_floor_lv1(config.get("noise_floor_lv1", 2))
        sensor.set_watchdog_threshold(config.get("watchdog_threshold", 2))
        sensor.set_spike_rejection(config.get("spike_rejection", 2))
        
        # Setup GPIO interrupt
        GPIO.setup(IRQ_PIN, GPIO.IN)
        GPIO.add_event_detect(IRQ_PIN, GPIO.RISING, callback=callback_handle)
        
        logger.info(f"Listening for lightning... Timeout in {WAIT_TIMEOUT} seconds.")
        
        # Wait for the event from the callback, with a timeout
        event_is_set = exit_event.wait(timeout=WAIT_TIMEOUT)
        
        if not event_is_set:
            logger.info("Timeout reached. No lightning detected.")
        
    except Exception as e:
        # Check for dummy GPIO class to avoid raising error on non-pi systems
        if type(GPIO).__name__ == 'GPIO':
             logger.error(f"An unexpected error occurred: {e}")
    finally:
        if type(GPIO).__name__ == 'GPIO':
            GPIO.cleanup()
        logger.info("Detector script finished.")
        sys.exit(0)

if __name__ == '__main__':
    main()