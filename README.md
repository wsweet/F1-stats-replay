# F1 Stats Replay CLI

A command-line tool written in Python for "replaying" F1 race data. This project fetches and processes raw data from the FastF1 API to provide a real-time, terminal-based view of a race.

## Features

* Live updating leaderboard with position changes.
* Real-time lap, sector, and gap data.
* Visual representation of tyre compounds and pit stops.
* Support for multiple playback speeds and manual time skipping.

## Installation

1.  Ensure you have Python 3.8+ installed.
2.  Clone this repository to your local machine:
    ```bash
    git clone [https://github.com/YOUR-GITHUB-USERNAME/f1-stats-replay.git](https://github.com/YOUR-GITHUB-USERNAME/f1-stats-replay.git)
    cd f1-stats-replay
    ```
3.  Create and activate a Python virtual environment:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```
4.  Install the required packages:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

1.  To run the main program, simply execute the `replay.py` script from the project root:
    ```bash
    python3 replay.py
    ```
2.  The program will display a menu of recent F1 races. Select one to automatically fetch data, build the timeline, and start the replay.

## Data Source

This project uses the `FastF1` library to access data from the official F1® API. Data is cached locally to speed up subsequent replays of the same event.
