# Project Context: thunderCapture

This document summarizes the `thunderCapture` project and the modifications made during this Gemini CLI session.

## Project Overview
`thunderCapture` is a Raspberry Pi-based system designed to detect lightning strikes using an AS3935 sensor, record associated audio events, generate visual waveforms, and log all relevant metadata into a SQLite database. It features a Flask web server for control and monitoring, offering a web-based user interface to manage the system and view captured events.

## Key Files and Their Roles
*   **`control_server.py`**: The core Flask web application. It orchestrates the lightning detection lifecycle, manages system state, handles API requests, and serves the web interface.
*   **`config.json`**: The central configuration file for the application, storing parameters for hardware, recording, sensor tuning, and file paths.
*   **`database.py`**: Manages interactions with the SQLite database (`recordings.db`), handling schema initialization and CRUD operations for recording data.
*   **`waveform.py`**: Contains the logic for generating waveform images from recorded audio files.
*   **`Scripts/DFRobot_AS3935_Thunders_Rec.py`**: The script responsible for interacting with the AS3935 sensor to detect lightning and report events.
*   **`templates/index.html`**: The web-based user interface, providing controls, status display, captured event listings, logs, and configuration management.

## Changes Made During This Session

### 1. Backend (`control_server.py`)
*   **Implemented `/api/logs` Endpoint**: A new API endpoint (`/api/logs`) was added to `control_server.py`. This endpoint provides access to real-time system logs.
*   **In-memory Log Cache**: A `collections.deque` was integrated with a custom `StreamToLogger` class to capture `stdout` and `stderr` output in a thread-safe, in-memory buffer. This allows the `/api/logs` endpoint to serve recent system activity.

### 2. Frontend (`templates/index.html`)
*   **Title Update**: The page title was changed to "Thunder Capture".
*   **Dark Theme Implementation**: The entire user interface was updated with a "thunder dark theme" for improved aesthetics and readability.
*   **Tabbed Navigation**: The UI was reorganized into three main tabs: "Events", "Logs", and "Configuration", providing a cleaner and more organized user experience.
*   **Redesigned Captured Events Table**: The "Captured Events" display was revamped. Each event now occupies two rows (a "two-stripe" layout):
    *   The first row displays metadata (Timestamp, Distance, Intensity).
    *   The second row shows the corresponding waveform image, spanning the full width of the table for better visibility.
*   **JavaScript Adaptations**: The existing JavaScript logic for fetching status, recordings, and config was updated to work seamlessly with the new tabbed structure and table design. The `fetchLogs` function now populates the new "Logs" tab.

## How to Run the Project

1.  **Navigate to the project directory**:
    ```bash
    cd thunderCapture
    ```
2.  **Install Python Dependencies (if not already installed)**:
    ```bash
    pip install Flask
    ```
    (Ensure other potential dependencies like `scipy` or `numpy` for `waveform.py` are also met if you encounter errors.)
3.  **Start the Flask Server**:
    ```bash
    python3 control_server.py
    ```
4.  **Access the Web Interface**: Open your web browser and navigate to `http://localhost:5001`.

## Version Control
It is highly recommended to commit these changes to your version control system (e.g., Git) to track modifications and maintain project history.
