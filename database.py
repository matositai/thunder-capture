import sqlite3
import os

def get_db_connection(db_path):
    """Creates a database connection."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row # This allows accessing columns by name
    return conn

def init_db(db_path):
    """Initializes the database and creates the recordings table if it doesn't exist."""
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)
        
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recordings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            wav_filepath TEXT NOT NULL UNIQUE,
            waveform_image_path TEXT,
            distance_km INTEGER,
            intensity INTEGER
        )
    ''')
    conn.commit()
    conn.close()
    print(f"Database initialized at {db_path}")

def add_recording(db_path, metadata):
    """Adds a new recording's metadata to the database."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute(
            'INSERT INTO recordings (wav_filepath, waveform_image_path, distance_km, intensity) VALUES (?, ?, ?, ?)',
            (
                metadata.get('wav_filepath'),
                metadata.get('waveform_image_path'),
                metadata.get('distance_km'),
                metadata.get('intensity')
            )
        )
        conn.commit()
        last_id = cursor.lastrowid
        return last_id
    except sqlite3.IntegrityError:
        print(f"Error: A recording for {metadata.get('wav_filepath')} already exists.")
        return None
    finally:
        conn.close()

def get_all_recordings(db_path):
    """Retrieves all recordings from the database."""
    if not os.path.exists(db_path):
        return []
        
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT id, timestamp, wav_filepath, waveform_image_path, distance_km, intensity FROM recordings ORDER BY timestamp DESC')
    recordings = cursor.fetchall()
    conn.close()
    # Convert list of Row objects to list of dicts for JSON serialization
    return [dict(row) for row in recordings]
