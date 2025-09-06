#!/usr/bin/env python3
# replay.py

import sys
import time
import pandas as pd
from pathlib import Path
import traceback
import fastf1
import datetime
import subprocess
import re
import tty
import termios
import select
import os

# === CONFIG & STYLING (omitted for brevity, no changes) ===
DEFAULT_PLAYBACK_SPEED = 1.0; OVERTAKE_ARROW_DURATION = pd.Timedelta(seconds=4)
FRAME_RATE = 20.0; FRAME_DURATION = 1.0 / FRAME_RATE
COL_WIDTHS = { "POS": 6, "DRIVER": 7, "TEAM": 13, "STATUS": 9, "PITS": 5, "TYRE": 8, "INTERVAL": 9, "GAP": 9, "S1": 9, "S2": 9, "S3": 9, "PREV_LAP": 9 }
PROGRESS_BAR_WIDTH = 40; RETIREMENT_THRESHOLD = pd.Timedelta(seconds=120)
FG_WHITE = "\033[38;5;15m"; FG_BLACK = "\033[38;5;0m"; RESET = "\033[0m"; DIM = "\033[2m"; BOLD = "\033[1m"; CLEAR_SCREEN = "\033[2J\033[H"
SECTOR_PURPLE = "\033[38;5;93m"; SECTOR_GREEN = "\033[38;5;40m"; SECTOR_YELLOW = "\033[38;5;226m"; DRS_COLOR = "\033[38;5;201m" 
POS_GAIN_COLOR = SECTOR_GREEN; POS_LOSS_COLOR = SECTOR_PURPLE
FLAG_GREEN_BG = "\033[48;5;22m"; FLAG_YELLOW_BG = "\033[48;5;226m"; FLAG_RED_BG = "\033[48;5;196m"
TEAM_STYLES = { "Mercedes": ("\033[48;5;36m", FG_BLACK), "Red Bull Racing": ("\033[48;5;21m", FG_WHITE), "Ferrari": ("\033[48;5;196m", FG_WHITE), "McLaren": ("\033[48;5;208m", FG_BLACK), "Aston Martin": ("\033[48;5;28m", FG_WHITE), "Alpine": ("\033[48;5;33m", FG_WHITE), "RB": ("\033[48;5;69m", FG_WHITE), "Williams": ("\033[48;5;27m", FG_WHITE), "Kick Sauber": ("\033[48;5;40m", FG_BLACK), "Stake F1 Team Kick Sauber": ("\033[48;5;40m", FG_BLACK), "Haas F1 Team": ("\033[48;5;242m", FG_WHITE), "Racing Bulls": ("\033[48;5;69m", FG_WHITE) }
TYRE_COLORS = { "S": "\033[38;5;196m", "M": "\033[38;5;226m", "H": "\033[38;5;255m", "I": "\033[38;5;40m", "W": "\033[38;5;33m" }
SHORT_TEAM_NAMES = { "Red Bull Racing": "Red Bull", "Stake F1 Team Kick Sauber": "Sauber", "Kick Sauber": "Sauber", "Haas F1 Team": "Haas", "Racing Bulls": "Racing Bulls" }
SHORT_TYRE_NAMES = { "SOFT": "S", "MEDIUM": "M", "HARD": "H", "INTERMEDIATE": "I", "WET": "W", }
TRACK_STATUS_MAP = { '1': (FLAG_GREEN_BG, FG_BLACK, "TRACK CLEAR"), '2': (FLAG_YELLOW_BG, FG_BLACK, "YELLOW FLAG"), '4': (FLAG_YELLOW_BG, FG_BLACK, "SAFETY CAR"), '5': (FLAG_RED_BG, FG_WHITE, "RED FLAG"), '6': (FLAG_YELLOW_BG, FG_BLACK, "VSC DEPLOYED"), '7': (FLAG_GREEN_BG, FG_BLACK, "VSC ENDING"), }

# === MENU & ORCHESTRATION (omitted for brevity, no changes) ===
def get_race_schedule(year):
    print(f"Fetching {year} race schedule..."); schedule = fastf1.get_event_schedule(year)
    return schedule[schedule['EventDate'].dt.tz_localize(None) < datetime.datetime.now()]
def check_race_status(year, event_name):
    event_name_safe = event_name.replace(' ', '_'); raw_path = Path(f"raw_data/{year}_{event_name_safe}"); processed_path = Path(f"processed_data/{year}_{event_name_safe}_timeline.parquet")
    if processed_path.exists(): return f"{SECTOR_GREEN}Processed{RESET}"
    if raw_path.exists() and (raw_path / "laps.pkl").exists(): return f"{SECTOR_YELLOW}Raw Data{RESET}"
    return f"{DIM}Not Downloaded{RESET}"
def display_menu(races_with_status):
    print(f"\n{BOLD}Select a race to replay:{RESET}")
    for i, race in enumerate(races_with_status):
        print(f" {i+1:2d}) Round {race['RoundNumber']:<2} - {race['EventName']:<25} | Status: {race['Status']}")
    print("\n Enter 'q' to quit.")
def run_script(script_name, year, event_name):
    command = [sys.executable, script_name, str(year), event_name]
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None: break
            if output: print(output.strip())
        return process.poll() == 0
    except Exception as e:
        print(f"❌ An error occurred while running {script_name}: {e}"); return False
def get_user_input():
    if not select.select([sys.stdin], [], [], 0)[0]: return None
    char = sys.stdin.read(1)
    if char == '\x1b':
        seq = sys.stdin.read(2)
        if seq == '[A': return 'up'
        if seq == '[B': return 'down'
        if seq == '[C': return 'right'
        if seq == '[D': return 'left'
    return char

# === REPLAY ENGINE ===
  # In replay.py, replace the whole draw_leaderboard function with this:

def draw_leaderboard(year, event_name, driver_state, sorted_drivers, driver_teams, race_laps, total_laps, current_race_time, best_times, status_info, playback_info):
    """Draws the entire screen based on the current state."""
    leader = sorted_drivers[0]; leader_state = driver_state[leader]
    screen_content = []; screen_content.append(CLEAR_SCREEN)
    is_paused, playback_speed = playback_info
    
    # --- 1. Draw Header ---
    pause_str = f"| {BOLD}{SECTOR_YELLOW}[PAUSED]{RESET} " if is_paused else ""
    speed_str = f"| Speed: {playback_speed:.2f}x"
    header_time = "RACE STARTING" if current_race_time is None else f"Time: {format_timedelta(current_race_time)}"
    title_line = f"{BOLD}{year} {event_name} | Lap {race_laps}/{total_laps} | {header_time}{RESET} {pause_str}{speed_str}"
    screen_content.append(title_line)

    track_status_code, drs_allowed, is_wet = status_info
    bg_color, fg_color, status_text = TRACK_STATUS_MAP.get(track_status_code, (None, None, "UNKNOWN"))
    
    status_line_parts = []
    if bg_color: status_line_parts.append(f"{bg_color}{fg_color} {status_text} {RESET}")
    
    drs_status_text = f"{SECTOR_GREEN}DRS ENABLED{RESET}" if drs_allowed else f"{DIM}DRS DISABLED{RESET}"
    status_line_parts.append(drs_status_text)
    
    if is_wet: status_line_parts.append(f"{BOLD}{TYRE_COLORS['W']}WET TRACK{RESET}")
    screen_content.append(" | ".join(status_line_parts))

    completed_laps = max(0, race_laps - 1);
    if leader_state['Status'] != 'On Track': progress_percent = 1.0
    else: progress_percent = (completed_laps / total_laps if total_laps > 0 else 0)
    filled_width = int(progress_percent * PROGRESS_BAR_WIDTH); bar = '█' * filled_width + '░' * (PROGRESS_BAR_WIDTH - filled_width); progress_line = f"Progress: [{bar}] {progress_percent:.1%}"
    screen_content.append(progress_line)
    
    header_line = ( f"{'':<{COL_WIDTHS['POS']}}" f"{'DRIVER':<{COL_WIDTHS['DRIVER']}}" f"{'TEAM':<{COL_WIDTHS['TEAM']}}" f"{'STATUS':<{COL_WIDTHS['STATUS']}}" f"{'PITS':<{COL_WIDTHS['PITS']}}" f"{'TYRE':<{COL_WIDTHS['TYRE']}}" f"{'INTERVAL':<{COL_WIDTHS['INTERVAL']}}" f"{'GAP':<{COL_WIDTHS['GAP']}}" f"{'S1':<{COL_WIDTHS['S1']}}" f"{'S2':<{COL_WIDTHS['S2']}}" f"{'S3':<{COL_WIDTHS['S3']}}" f"{'PREV LAP':<{COL_WIDTHS['PREV_LAP']}}" )
    screen_content.append(header_line); screen_content.append("-" * len(header_line))

    # --- 2. Draw Driver Lines (REFACTORED FOR CLARITY) ---
    for i, drv in enumerate(sorted_drivers):
        state = driver_state[drv]
        parts = []

        # Each column is now built and padded independently
        pos_num_str = 'NC' if state['Status'] != 'On Track' else f"{int(state['Position']):>2}"
        arrow = state['PositionChangeSymbol'] if current_race_time is not None and current_race_time < state['PositionChangeExpiry'] else ''
        pos_str = f"{pos_num_str} {arrow}"
        parts.append(get_padded_str(pos_str, COL_WIDTHS['POS']))
        
        parts.append(f"{drv}".ljust(COL_WIDTHS['DRIVER']))
        
        team_name = driver_teams.get(drv, "Unknown")
        display_team = SHORT_TEAM_NAMES.get(team_name, team_name)
        bg, fg = TEAM_STYLES.get(team_name, ("", ""))
        padding = " " * (COL_WIDTHS['TEAM'] - len(display_team))
        parts.append(f"{bg}{fg}{display_team}{padding}{RESET}")
        
        display_status = state['DisplayStatus']
        if state['Status'] != 'On Track': display_status = state['Status']
        parts.append(get_padded_str(f"{BOLD}{display_status}{RESET}", COL_WIDTHS['STATUS']))
        
        if state['Status'] == 'On Track' and display_status != 'GRID':
            pit_stops = state['PitStops']
            pits_str = f"[{pit_stops}]" if pit_stops > 0 else ""
            parts.append(pits_str.ljust(COL_WIDTHS['PITS']))
            
            compound = str(state['Compound']).upper()
            display_compound = SHORT_TYRE_NAMES.get(compound, "?")
            tyre_color = TYRE_COLORS.get(display_compound, "")
            tyre_life = int(state['TyreLife']) if pd.notna(state['TyreLife']) else 0
            tyre_text = f"{display_compound:<2} [{tyre_life:>2}]"
            parts.append(get_padded_str(f"{tyre_color}{tyre_text}{RESET}", COL_WIDTHS['TYRE']))
            
            if state['LastEventLap'] < 2:
                blank_width = sum(COL_WIDTHS[k] for k in ['INTERVAL', 'GAP', 'S1', 'S2', 'S3', 'PREV_LAP'])
                parts.append(" " * blank_width)
            else:
                interval_td = state['Interval']
                interval_str = format_timedelta(interval_td)
                drs_is_active = drs_allowed and pd.notna(interval_td) and interval_td.total_seconds() < 1.0
                if drs_is_active: interval_str = f"{DRS_COLOR}{interval_str}{RESET}"
                parts.append(get_padded_str(interval_str, COL_WIDTHS['INTERVAL']))
                
                gap_str = format_gap(state['GapToLeader'], leader_state.get('S3', pd.NaT), i == 0)
                parts.append(gap_str.ljust(COL_WIDTHS['GAP']))
                
                best_s1, best_s2, best_s3 = best_times
                s1_color = SECTOR_PURPLE if state['S1'] == best_s1 and pd.notna(state['S1']) else SECTOR_GREEN if state['IsPersonalBestS1'] else SECTOR_YELLOW
                s2_color = SECTOR_PURPLE if state['S2'] == best_s2 and pd.notna(state['S2']) else SECTOR_GREEN if state['IsPersonalBestS2'] else SECTOR_YELLOW
                s3_color = SECTOR_PURPLE if state['S3'] == best_s3 and pd.notna(state['S3']) else SECTOR_GREEN if state['IsPersonalBestS3'] else SECTOR_YELLOW
                
                s1_str, s2_str, s3_str = "", "", ""
                event_type = state['LastEventType']
                if event_type == 'Sector1':
                    s1_str = format_timedelta(state['S1'], color=s1_color, bold=True)
                    s2_str = format_timedelta(state['Prev_S2'], dim=True)
                    s3_str = format_timedelta(state['Prev_S3'], dim=True)
                elif event_type == 'Sector2':
                    s1_str = format_timedelta(state['S1'], color=s1_color)
                    s2_str = format_timedelta(state['S2'], color=s2_color, bold=True)
                    s3_str = format_timedelta(state['Prev_S3'], dim=True)
                elif event_type == 'Lap':
                    s1_str = format_timedelta(state['S1'], color=s1_color)
                    s2_str = format_timedelta(state['S2'], color=s2_color)
                    s3_str = format_timedelta(state['S3'], color=s3_color, bold=True)

                parts.append(get_padded_str(s1_str, COL_WIDTHS['S1']))
                parts.append(get_padded_str(s2_str, COL_WIDTHS['S2']))
                parts.append(get_padded_str(s3_str, COL_WIDTHS['S3']))
                
                prev_lap_str = format_timedelta(state['PreviousLapTime'])
                parts.append(get_padded_str(prev_lap_str, COL_WIDTHS['PREV_LAP']))
        else:
            if display_status == "GRID":
                parts.append(''.ljust(COL_WIDTHS['PITS']))
                compound = str(state.get('Compound', '?')).upper()
                display_compound = SHORT_TYRE_NAMES.get(compound, "?")
                tyre_color = TYRE_COLORS.get(display_compound, "")
                tyre_life = int(state.get('TyreLife', 0))
                tyre_text = f"{display_compound:<2} [{tyre_life:>2}]"
                parts.append(get_padded_str(f"{tyre_color}{tyre_text}{RESET}", COL_WIDTHS['TYRE']))

            blank_width = sum(COL_WIDTHS[k] for k in ['INTERVAL', 'GAP', 'S1', 'S2', 'S3', 'PREV_LAP'])
            if display_status != "GRID":
                blank_width += COL_WIDTHS['PITS'] + COL_WIDTHS['TYRE']
            parts.append(" " * blank_width)

        screen_content.append("".join(parts))
    
    # Footer
    screen_content.append("-" * len(header_line))
    controls_str = "P/Space: Pause | ↑/↓: Speed | ←/→: Skip Lap | 1: 1x | N: Sync Next Lap | Q: Quit"
    screen_content.append(controls_str)
    
    sys.stdout.write("\n".join(screen_content)); sys.stdout.flush()

def run_replay(year, event_name, playback_speed):
    event_name_safe = event_name.replace(" ", "_"); BASE_PATH = Path(__file__).parent
    DATA_FILE = BASE_PATH / f"processed_data/{year}_{event_name_safe}_timeline.parquet"; RAW_DATA_FOLDER = BASE_PATH / f"raw_data/{year}_{event_name_safe}"
    try:
        timeline_df = pd.read_parquet(DATA_FILE)
        if not timeline_df.empty: first_event_time = timeline_df['Time'].iloc[0]; timeline_df['Time'] = timeline_df['Time'] - first_event_time
        results_df = pd.read_pickle(RAW_DATA_FOLDER / "results.pkl"); laps_df = pd.read_pickle(RAW_DATA_FOLDER / "laps.pkl")
        drivers = results_df['Abbreviation'].tolist(); driver_teams = dict(zip(results_df['Abbreviation'], results_df['TeamName']))
        
        # --- NEW: Load all status data, with fallbacks ---
        try: track_status_df = pd.read_pickle(RAW_DATA_FOLDER / "track_status.pkl")
        except FileNotFoundError: track_status_df = pd.DataFrame()
        try: weather_df = pd.read_pickle(RAW_DATA_FOLDER / "weather_data.pkl")
        except FileNotFoundError: weather_df = pd.DataFrame()
        try: race_control_df = pd.read_pickle(RAW_DATA_FOLDER / "race_control.pkl")
        except FileNotFoundError: race_control_df = pd.DataFrame()

    except FileNotFoundError as e:
        print(f"❌ Error: Could not load data file: {e.filename}"); return
    
    # --- NEW: Pre-process Race Control messages to create a DRS timeline ---
    drs_status_df = pd.DataFrame()
    if not race_control_df.empty:
        drs_messages = race_control_df[race_control_df['Message'].str.contains("DRS", na=False)]
        if not drs_messages.empty:
            drs_timeline = [{'Time': pd.Timedelta(seconds=0), 'DRS_Status': False}] # Start with DRS disabled
            for row in drs_messages.itertuples():
                drs_timeline.append({'Time': row.Time, 'DRS_Status': "ENABLED" in row.Message.upper()})
            drs_status_df = pd.DataFrame(drs_timeline)

    # (State Init is unchanged, omitted for brevity)
    lap1_laps = laps_df.loc[laps_df['LapNumber'] == 1]; starting_compounds = dict(zip(lap1_laps['Driver'], lap1_laps['Compound']))
    driver_state = {}; starting_grid = results_df.sort_values(by='GridPosition')
    for i, driver_row in starting_grid.iterrows():
        drv = driver_row['Abbreviation']
        driver_state[drv] = { "Position": driver_row['GridPosition'], "PreviousPosition": driver_row['GridPosition'], "LapNumber": 0, "Compound": starting_compounds.get(drv, "?"), "TyreLife": 1, "GapToLeader": pd.NaT, "Interval": pd.NaT, "Status": "On Track", "DisplayStatus": "GRID", "LastEventType": "", "LastEventLap": 0, "PitStops": 0, "S1": pd.NaT, "S2": pd.NaT, "S3": pd.NaT, "Prev_S2": pd.NaT, "Prev_S3": pd.NaT, "PreviousLapTime": pd.NaT, "LastUpdateTime": pd.Timedelta(seconds=-1), 'IsPersonalBestS1': False, 'IsPersonalBestS2': False, 'IsPersonalBestS3': False, 'PositionChangeSymbol': '', 'PositionChangeExpiry': pd.Timedelta(seconds=-1) }
    
    try:
        event_index, timeline_events = 0, timeline_df.to_dict('records')
        total_events, total_laps = len(timeline_events), int(timeline_df['LapNumber'].max())
        if total_events == 0: print("❌ Timeline file contains no events."); return
        best_s1_so_far, best_s2_so_far, best_s3_so_far = pd.Timedelta.max, pd.Timedelta.max, pd.Timedelta.max
        draw_leaderboard(year, event_name, driver_state, drivers, driver_teams, 0, total_laps, None, (None, None, None), ('1', False, False), (False, playback_speed))
        time.sleep(5)
        
        current_race_time = timeline_events[0]['Time']; is_paused = False; last_frame_time = time.monotonic()
        
        while event_index < total_events:
            # (Input handling and time advancement omitted for brevity)
            key = get_user_input();
            if key:
                if key.lower() == 'q': print("\nQuitting replay."); break
                if key.lower() == 'p' or key == ' ': is_paused = not is_paused
                if key.lower() == 'f' or key == 'up': playback_speed *= 2
                if key.lower() == 'r' or key == 'down': playback_speed = max(0.25, playback_speed / 2)
                if key == '1': playback_speed = 1.0
                if key == 'right': current_race_time += pd.Timedelta(seconds=10)
                if key == 'left': current_race_time = max(timeline_events[0]['Time'], current_race_time - pd.Timedelta(seconds=10)); event_index = 0
            real_time_now = time.monotonic(); real_time_delta = real_time_now - last_frame_time; last_frame_time = real_time_now
            if not is_paused:
                race_time_delta = pd.Timedelta(seconds=real_time_delta * playback_speed); current_race_time += race_time_delta
                while event_index < total_events and timeline_events[event_index]['Time'] <= current_race_time:
                    # (Event processing logic unchanged)
                    event = timeline_events[event_index]; drv = event['Driver']; state = driver_state[drv]; new_pos = event['Position']
                    if new_pos != state['PreviousPosition'] and state['LastEventLap'] > 1:
                        if new_pos < state['PreviousPosition']: state['PositionChangeSymbol'] = f"{POS_GAIN_COLOR}▲{RESET}"
                        else: state['PositionChangeSymbol'] = f"{POS_LOSS_COLOR}▼{RESET}"
                        state['PositionChangeExpiry'] = event['Time'] + OVERTAKE_ARROW_DURATION
                    state['PreviousPosition'] = new_pos;
                    if event['EventType'] == 'PitIn': state['DisplayStatus'] = 'IN PIT'
                    elif event['EventType'] == 'PitOut': state['DisplayStatus'] = 'OUT'; state['PitStops'] += 1
                    elif event['EventType'] == 'Sector1' and (state['DisplayStatus'] == 'OUT' or state['DisplayStatus'] == 'GRID'): state['DisplayStatus'] = ''
                    if event['LapNumber'] > state['LastEventLap']: state['Prev_S2'], state['Prev_S3'] = state['S2'], state['S3']; state['S1'], state['S2'], state['S3'] = pd.NaT, pd.NaT, pd.NaT
                    state.update({ "Position": new_pos, "LapNumber": event['LapNumber'], "Compound": event['Compound'], "TyreLife": event['TyreLife'], "GapToLeader": event['GapToLeader'], "Interval": event['Interval'], "LastEventType": event['EventType'], "LastEventLap": event['LapNumber'], "LastUpdateTime": event['Time'], 'IsPersonalBestS1': event['IsPersonalBestS1'], 'IsPersonalBestS2': event['IsPersonalBestS2'], 'IsPersonalBestS3': event['IsPersonalBestS3'] })
                    if event['EventType'] == 'Sector1':
                        state['S1'] = event['Sector1Time'];
                        if pd.notna(state['S1']) and state['S1'] < best_s1_so_far: best_s1_so_far = state['S1']
                    elif event['EventType'] == 'Sector2':
                        state['S2'] = event['Sector2Time']
                        if pd.notna(state['S2']) and state['S2'] < best_s2_so_far: best_s2_so_far = state['S2']
                    elif event['EventType'] == 'Lap':
                        state['S3'], state['PreviousLapTime'] = event['Sector3Time'], event['LapTime']
                        if pd.notna(state['S3']) and state['S3'] < best_s3_so_far: best_s3_so_far = state['S3']
                    event_index += 1
                for drv in drivers:
                    state = driver_state[drv]
                    if state['Status'] == 'On Track':
                        if state['LastEventLap'] >= total_laps and state['LastEventType'] == 'Lap': state['Status'] = results_df.loc[results_df['Abbreviation'] == drv, 'Status'].iloc[0]; state['DisplayStatus'] = state['Status']
                        elif (current_race_time - state['LastUpdateTime']) > RETIREMENT_THRESHOLD: state['Status'], state['DisplayStatus'] = 'DNF', 'DNF'
            
            sorted_drivers = sorted(drivers, key=lambda d: (0 if driver_state[d]['Status'] == 'On Track' else 1, driver_state[d]['Position']))
            race_laps = int(driver_state[sorted_drivers[0]]['LapNumber'])
            
            # --- NEW: Get current status from all sources ---
            current_track_status_code = '1'
            if not track_status_df.empty:
                current_statuses = track_status_df[track_status_df['Time'] <= (current_race_time + first_event_time)]
                if not current_statuses.empty: current_track_status_code = str(current_statuses.iloc[-1]['Status'])
            is_wet = False
            if not weather_df.empty:
                current_weather = weather_df[weather_df['Time'] <= (current_race_time + first_event_time)]
                if not current_weather.empty: is_wet = current_weather.iloc[-1]['Rainfall'] == True
            
            drs_allowed = False
            if not drs_status_df.empty:
                drs_events = drs_status_df[drs_status_df['Time'] <= (current_race_time + first_event_time)]
                if not drs_events.empty: drs_allowed = drs_events.iloc[-1]['DRS_Status']

            status_info = (current_track_status_code, drs_allowed, is_wet)
            best_times = (best_s1_so_far, best_s2_so_far, best_s3_so_far)
            playback_info = (is_paused, playback_speed)
            
            draw_leaderboard(year, event_name, driver_state, sorted_drivers, driver_teams, race_laps, total_laps, current_race_time - timeline_events[0]['Time'], best_times, status_info, playback_info)
            
            if is_paused: time.sleep(FRAME_DURATION)
            else:
                processing_time = time.monotonic() - real_time_now
                sleep_for = FRAME_DURATION - processing_time
                if sleep_for > 0: time.sleep(sleep_for)
    except Exception as e:
        print(f"\n--- A CRITICAL ERROR OCCURRED ---"); traceback.print_exc()

# === MAIN EXECUTION BLOCK (omitted for brevity, no changes) ===
if __name__ == "__main__":
    original_terminal_settings = termios.tcgetattr(sys.stdin)
    try:
        tty.setcbreak(sys.stdin.fileno())
        YEAR_TO_CHECK = 2025
        fastf1.Cache.enable_cache('f1_cache')
        schedule = get_race_schedule(YEAR_TO_CHECK)
        races = []
        for race in schedule.itertuples():
            if "Testing" in race.EventName: continue
            status = check_race_status(YEAR_TO_CHECK, race.EventName)
            races.append({'RoundNumber': race.RoundNumber, 'EventName': race.EventName, 'Status': status})
        while True:
            display_menu(races)
            choice = input(f"{BOLD}> {RESET}")
            if choice.lower() == 'q': break
            try:
                choice_idx = int(choice) - 1
                if not 0 <= choice_idx < len(races): print("Invalid choice."); continue
                selected_race = races[choice_idx]
                year = YEAR_TO_CHECK; event = selected_race['EventName']
                raw_status = check_race_status(year, event)
                if "Not Downloaded" in raw_status:
                    print("\nFetching raw data...");
                    if not run_script('fetch_raw.py', year, event): continue
                    print("\nBuilding timeline...")
                    if not run_script('build_timeline.py', year, event): continue
                elif "Raw Data" in raw_status:
                    print("\nBuilding timeline from existing raw data...")
                    if not run_script('build_timeline.py', year, event): continue
                run_replay(year, event, DEFAULT_PLAYBACK_SPEED)
                break
            except ValueError: print("Invalid input.")
            except KeyboardInterrupt: print("\nExiting."); break
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, original_terminal_settings)