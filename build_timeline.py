# build_timeline.py

import pandas as pd
from pathlib import Path
import argparse

def build_event_timeline(year: int, event: str):
    """
    Processes raw lap data to create a detailed, chronological event timeline
    and a race_info file for sync features.
    """
    print(f"--- Building Timeline for {year} {event} ---")
    event_name_safe = event.replace(' ', '_')
    
    # Paths
    event_folder = Path(f"raw_data/{year}_{event_name_safe}")
    laps_file = event_folder / "laps.pkl"
    results_file = event_folder / "results.pkl"
    out_dir = Path("processed_data")
    out_dir.mkdir(parents=True, exist_ok=True)
    timeline_out_file = out_dir / f"{year}_{event_name_safe}_timeline.parquet"
    race_info_out_file = out_dir / f"{year}_{event_name_safe}_race_info.pkl"

    # Load data
    try:
        laps_df = pd.read_pickle(laps_file)
        results_df = pd.read_pickle(results_file).rename(columns={"Abbreviation": "Driver"})
    except FileNotFoundError as e:
        print(f"❌ Error: Could not load raw data file: {e.filename}"); exit(1)

    # --- NEW: Create and save a race_info file with leader lap start times ---
    print("Creating race_info file for syncing...")
    # Find the first driver to start each lap (our de facto leader for that lap)
    leader_laps = laps_df.loc[laps_df.groupby('LapNumber')['LapStartTime'].idxmin()]
    lap_start_times = leader_laps[['LapNumber', 'LapStartTime']].set_index('LapNumber')
    
    race_info = {
        'lap_start_times': lap_start_times['LapStartTime'].to_dict()
    }
    pd.to_pickle(race_info, race_info_out_file)
    print(f"✅ Saved race_info file to {race_info_out_file}")
    # --- End of new section ---
    
    # The rest of the timeline building is the same as before...
    # (Omitted for brevity, no changes to this logic)
    laps_df['IsPersonalBestS1'] = laps_df['Sector1Time'] == laps_df.groupby('Driver')['Sector1Time'].cummin()
    laps_df['IsPersonalBestS2'] = laps_df['Sector2Time'] == laps_df.groupby('Driver')['Sector2Time'].cummin()
    laps_df['IsPersonalBestS3'] = laps_df['Sector3Time'] == laps_df.groupby('Driver')['Sector3Time'].cummin()
    laps_to_process = laps_df[[ "Driver", "LapNumber", "Position", "Compound", "TyreLife", "LapTime", "Sector1SessionTime", "Sector2SessionTime", "Sector3SessionTime", "Sector1Time", "Sector2Time", "Sector3Time", "PitInTime", "PitOutTime", "IsPersonalBestS1", "IsPersonalBestS2", "IsPersonalBestS3" ]].copy()
    status_df = results_df[['Driver', 'Status']].rename(columns={'Status': 'FinalStatus'}); laps = laps_to_process.merge(status_df, on='Driver', how='left')
    all_events = []
    for row in laps.itertuples():
        lap_data = { "Driver": row.Driver, "LapNumber": row.LapNumber, "Position": row.Position, "Compound": row.Compound, "TyreLife": row.TyreLife, "LapTime": row.LapTime, "Sector1Time": row.Sector1Time, "Sector2Time": row.Sector2Time, "Sector3Time": row.Sector3Time, "FinalStatus": row.FinalStatus, "IsPersonalBestS1": row.IsPersonalBestS1, "IsPersonalBestS2": row.IsPersonalBestS2, "IsPersonalBestS3": row.IsPersonalBestS3 }
        if pd.notna(row.Sector1SessionTime): all_events.append({"Time": row.Sector1SessionTime, "EventType": "Sector1", **lap_data})
        if pd.notna(row.Sector2SessionTime): all_events.append({"Time": row.Sector2SessionTime, "EventType": "Sector2", **lap_data})
        if pd.notna(row.Sector3SessionTime): all_events.append({"Time": row.Sector3SessionTime, "EventType": "Lap", **lap_data})
        if pd.notna(row.PitInTime): all_events.append({"Time": row.PitInTime, "EventType": "PitIn", **lap_data})
        if pd.notna(row.PitOutTime): all_events.append({"Time": row.PitOutTime, "EventType": "PitOut", **lap_data})
    if not all_events: print("❌ No events found."); return
    timeline_df = pd.DataFrame(all_events).sort_values(by="Time").reset_index(drop=True)
    print("Calculating gaps and intervals...")
    sector_groups = timeline_df.groupby(['LapNumber', 'EventType'])
    leader_time_per_sector = sector_groups['Time'].transform('min')
    timeline_df['GapToLeader'] = timeline_df['Time'] - leader_time_per_sector
    timeline_df['Interval'] = sector_groups['Time'].diff().fillna(pd.NaT)
    timeline_df.to_parquet(timeline_out_file)
    print(f"✅ Saved timeline to {timeline_out_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build a timeline file from raw F1 data.")
    parser.add_argument("year", type=int, help="The year of the race.")
    parser.add_argument("event", type=str, help="The name of the event (e.g., 'Dutch Grand Prix').")
    args = parser.parse_args()
    build_event_timeline(args.year, args.event)