# BunkMarte

BunkMarte is a Python + Flet attendance tracker built for college schedules.  
It helps you mark classes quickly, track attendance percentage by subject, and review/edit full class history from a mobile-friendly interface.

## Features

- **Daily timetable view** with tap-to-mark attendance
- **Multiple attendance statuses** (Present, Absent, Bunk, Mass Bunk, Proxy/Freebie, Cancelled, Exam Day, Holiday)
- **Subject-wise attendance summary** with percentage and progress bars
- **Full history view** per subject, including unmarked scheduled sessions for backfilling
- **Class swap support** for day-specific timetable overrides
- **SQLite persistence** for offline local data storage
- **Dark UI theme** optimized for mobile usage

## Tech Stack

- **Python 3.12+**
- **Flet** (UI framework)
- **SQLite** (local database)

## Project Structure

```text
BunkMarte-Python-/
├── main.py                     # Main Flet application
├── requirements.txt            # Python dependencies
├── bunkmarte.db                # SQLite database (generated/updated at runtime)
└── .github/workflows/
    └── build-apk.yml           # GitHub Actions workflow for Android APK build
```

## Getting Started

### 1) Clone and enter the project

```bash
git clone https://github.com/rathambhagat/BunkMarte-Python-.git
cd BunkMarte-Python-
```

### 2) Create and activate a virtual environment (recommended)

```bash
python -m venv .venv
source .venv/bin/activate      # Linux/macOS
# .venv\Scripts\activate       # Windows PowerShell
```

### 3) Install dependencies

```bash
pip install -r requirements.txt
```

### 4) Run the app

```bash
python main.py
```

## How Data Storage Works

- Attendance and swap data are stored in a SQLite database named `bunkmarte.db`.
- On desktop/local runs, the DB is created in the project directory.
- On packaged Android runs, storage uses Flet’s app data directory (`FLET_APP_STORAGE_DATA`).

## Building Android APK

The repository includes a GitHub Actions workflow (`.github/workflows/build-apk.yml`) that:

1. Sets up Python 3.12
2. Installs Flet CLI
3. Builds APK using:

```bash
yes | flet build apk --project "BunkMarte" --module-name main.py --split-per-abi
```

4. Uploads the generated APK as a workflow artifact.

## Notes

- The weekly timetable and attendance rules are currently defined in `main.py`.
- If you change subject names or schedule blocks, run the app again to continue tracking with the updated configuration.

## License

No license file is currently provided in this repository.
