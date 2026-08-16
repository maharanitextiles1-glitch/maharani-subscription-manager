
# Maharani Social Media Subscription Manager

Working local web app using Flask + SQLite.

## Features
- Persistent SQLite database
- Add subscription
- Edit subscription
- Delete subscription
- Mark paid / unpaid
- Cancel / reactivate
- Automatic Active / Due Soon / Overdue status
- Dashboard monthly/yearly/annual totals
- Notifications
- Payment history
- Search and filters
- Renewal calendar
- Responsive UI

## Run on Mac / Windows / Linux

1. Install Python 3.10+
2. Open Terminal / Command Prompt in this folder
3. Create a virtual environment (recommended):

### macOS / Linux
python3 -m venv .venv
source .venv/bin/activate

### Windows
python -m venv .venv
.venv\Scripts\activate

4. Install:
pip install -r requirements.txt

5. Run:
python app.py

6. Open:
http://127.0.0.1:5000

The SQLite database (`subscriptions.db`) is created automatically on first run.

## Important
This is a functional internal-use version. Before putting it on the public internet, add authentication, HTTPS, CSRF protection, backups and production deployment configuration.
