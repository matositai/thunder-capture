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
            intensity INTEGER,
            duration_seconds REAL
        )
    ''')
    # Add duration_seconds column if it doesn't exist (for existing databases)
    cursor.execute('''
        PRAGMA table_info(recordings);
    ''')
    columns = [col[1] for col in cursor.fetchall()]
    if 'duration_seconds' not in columns:
        cursor.execute('''
            ALTER TABLE recordings ADD COLUMN duration_seconds REAL;
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
            'INSERT INTO recordings (wav_filepath, waveform_image_path, distance_km, intensity, duration_seconds) VALUES (?, ?, ?, ?, ?)',
            (
                metadata.get('wav_filepath'),
                metadata.get('waveform_image_path'),
                metadata.get('distance_km'),
                metadata.get('intensity'),
                metadata.get('duration_seconds')
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
    cursor.execute('SELECT id, timestamp, wav_filepath, waveform_image_path, distance_km, intensity, duration_seconds FROM recordings ORDER BY timestamp DESC')
    recordings = cursor.fetchall()
    conn.close()
    # Convert list of Row objects to list of dicts for JSON serialization
    return [dict(row) for row in recordings]

def delete_recordings_by_path_pattern(db_path, pattern):
    """Deletes recordings from the database where wav_filepath matches the given pattern."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM recordings WHERE wav_filepath LIKE ?', (pattern,))
    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()
    print(f"Deleted {deleted_count} recordings matching pattern: {pattern}")
    return deleted_count

