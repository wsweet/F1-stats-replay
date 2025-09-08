import sys
import fastf1
import pandas as pd
from pathlib import Path

def fetch_data(year, event):
    """
    Fetches raw F1 session data and saves it to a structured directory.
    """
    session = fastf1.get_session(year, event, 'R')
    try:
        session.load(telemetry=True, weather=True, messages=True)
    except Exception as e:
        print(f"❌ Error loading session data: {e}")
        return False

    event_name_safe = event.replace(' ', '_')
    output_dir = Path(f"raw_data/{year}_{event_name_safe}")
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Save key session data to pickle files
        laps = session.laps
        results = session.results
        session_info = session.session_info
        
        # --- FIX FOR INCONSISTENT DATA TYPES ---
        # The race_control_messages Time column can be inconsistent.
        # Ensure it is a consistent Timedelta before saving.
        race_control_messages = session.race_control_messages.copy()
        if not race_control_messages.empty:
            race_control_messages['Time'] = race_control_messages['Time'] - race_control_messages['Time'].iloc[0]
        # End of fix
        
        weather_data = session.weather_data
        track_status = session.track_status

        laps.to_pickle(output_dir / "laps.pkl")
        results.to_pickle(output_dir / "results.pkl")
        session_info.to_pickle(output_dir / "session_info.pkl")
        race_control_messages.to_pickle(output_dir / "race_control.pkl")
        weather_data.to_pickle(output_dir / "weather_data.pkl")
        track_status.to_pickle(output_dir / "track_status.pkl")
        
        print(f"✅ Raw data for {year} {event} saved successfully.")
        return True
    except Exception as e:
        print(f"❌ Error saving data: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python fetch_raw.py <year> <event_name>")
        sys.exit(1)

    YEAR = int(sys.argv[1])
    EVENT = sys.argv[2]
    
    # Enable cache for fastf1
    fastf1.Cache.enable_cache('f1_cache')
    
    fetch_data(YEAR, EVENT)