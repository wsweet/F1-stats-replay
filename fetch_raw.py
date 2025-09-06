# fetch_raw.py

import fastf1
from pathlib import Path
import argparse

def fetch_raw_data(year: int, event: str):
    """
    Downloads and caches raw F1 data for a specific event.

    Args:
        year (int): The year of the event.
        event (str): The name of the event (e.g., "Dutch Grand Prix").
    """
    print(f"--- Fetching Raw Data for {year} {event} ---")
    fastf1.Cache.enable_cache("f1_cache")

    event_name_safe = event.replace(' ', '_')
    event_folder = Path(f"raw_data/{year}_{event_name_safe}")
    event_folder.mkdir(parents=True, exist_ok=True)
    print(f"📁 Saving raw data to {event_folder}/")

    try:
        session = fastf1.get_session(year, event, 'R')
        session.load(laps=True, telemetry=False, weather=True, messages=True) # Ensure weather and messages are loaded
    except Exception as e:
        print(f"❌ Could not load session for {year} {event}. Error: {e}")
        return

    session.laps.to_pickle(event_folder / "laps.pkl")
    session.results.to_pickle(event_folder / "results.pkl")
    print(f"✅ Saved laps and results.")

    # --- NEW: Save Track Status, Weather, and Race Control Data ---
    if hasattr(session, 'track_status') and session.track_status is not None:
        session.track_status.to_pickle(event_folder / "track_status.pkl")
        print("✅ Saved track status.")
    
    if hasattr(session, 'weather_data') and session.weather_data is not None:
        session.weather_data.to_pickle(event_folder / "weather_data.pkl")
        print("✅ Saved weather data.")
        
    if hasattr(session, 'race_control_messages') and session.race_control_messages is not None:
        session.race_control_messages.to_pickle(event_folder / "race_control.pkl")
        print("✅ Saved race control messages.")
    
    print(f"--- Fetch complete for {year} {event} ---")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch raw data for an F1 event.")
    parser.add_argument("year", type=int, help="The year of the race.")
    parser.add_argument("event", type=str, help="The name of the event (e.g., 'Dutch Grand Prix').")
    args = parser.parse_args()

    fetch_raw_data(args.year, args.event)