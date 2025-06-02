#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

echo "Maison Trüvra Development Environment Setup & Launch"
echo "=================================================="

# --- Configuration ---
FLASK_BACKEND_PORT=5001
FRONTEND_STATIC_SERVER_PORT=8000
VENV_NAME="venv"
PROJECT_ROOT_DIR=$(pwd) # Assumes script is run from project root

# --- Helper Functions ---
check_command_exists() {
    command -v "$1" >/dev/null 2>&1 || { echo >&2 "Error: Command '$1' is not installed. Please install it and try again."; exit 1; }
}

# --- Pre-flight Checks ---
echo "Checking for necessary tools..."
check_command_exists python3
check_command_exists pip
check_command_exists npm
check_command_exists flask # Check if flask CLI is available (usually after venv activation)

# --- Backend Setup & Launch ---
echo ""
echo "Setting up and launching Backend..."

# Create and activate virtual environment if it doesn't exist or is not activated
if [ ! -d "$VENV_NAME" ]; then
    echo "Creating Python virtual environment '$VENV_NAME'..."
    python3 -m venv "$VENV_NAME"
else
    echo "Virtual environment '$VENV_NAME' already exists."
fi

echo "Activating virtual environment..."
source "$VENV_NAME/bin/activate"

echo "Installing/Updating Python dependencies from requirements.txt..."
pip install -r requirements.txt

# Database setup
# Check if the instance folder and database file exist.
# This is a simple check; for robust migration status, more complex checks are needed.
INSTANCE_DIR="${PROJECT_ROOT_DIR}/instance"
DB_FILE_DEV="${INSTANCE_DIR}/dev_maison_truvra_orm.sqlite3" # As per your DevelopmentConfig

if [ ! -d "$INSTANCE_DIR" ] || [ ! -f "$DB_FILE_DEV" ]; then
    echo "Instance directory or database file not found. Running initial database setup..."
    if [ ! -d "${PROJECT_ROOT_DIR}/migrations" ]; then
        echo "Running: flask db init"
        flask db init
    fi
    echo "Running: flask db migrate -m 'Automated initial migration'"
    flask db migrate -m "Automated initial migration"
    echo "Running: flask db upgrade"
    flask db upgrade
    echo "Running: flask seed-db"
    flask seed-db
else
    echo "Database appears to be set up. Running migrations if any..."
    flask db upgrade # Ensures DB is up-to-date with latest migrations
fi

echo "Starting Flask backend server in the background on port $FLASK_BACKEND_PORT..."
# Ensure .env file exists
if [ ! -f ".env" ]; then
    echo "WARNING: .env file not found. Backend might not start correctly or use default configurations."
    echo "Please create a .env file with necessary configurations (see previous instructions)."
    # Optionally, you could create a default .env here if certain basic values are always needed.
fi

# Run backend.run as a module from the project root
(python -m backend.run &)
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"
# Give backend a moment to start
sleep 3

# --- Frontend Setup & Launch ---
echo ""
echo "Setting up and launching Frontend..."
cd "${PROJECT_ROOT_DIR}/website"

if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies (npm install)..."
    npm install
else
    echo "Frontend dependencies (node_modules) already exist."
fi

echo "Building frontend static files (npm run build)..."
npm run build

echo "Starting static file server for frontend (website/dist) in the background on port $FRONTEND_STATIC_SERVER_PORT..."
cd "${PROJECT_ROOT_DIR}/website/dist"

# Option 1: Python's HTTP server (simple, usually available)
(python3 -m http.server $FRONTEND_STATIC_SERVER_PORT &)
FRONTEND_PID_PY=$!
echo "Frontend (Python http.server) PID: $FRONTEND_PID_PY"

# Option 2: live-server (if installed and preferred for auto-reloading HTML/CSS changes)
# Uncomment the next lines and comment out Python server lines if you prefer live-server
# check_command_exists live-server
# (live-server --port=$FRONTEND_STATIC_SERVER_PORT --no-browser &) # --no-browser to prevent auto-opening
# FRONTEND_PID_LS=$!
# echo "Frontend (live-server) PID: $FRONTEND_PID_LS"

cd "$PROJECT_ROOT_DIR" # Return to project root

echo ""
echo "--------------------------------------------------"
echo "Maison Trüvra Development Environment is LIVE!"
echo ""
echo "Backend API running at: http://localhost:$FLASK_BACKEND_PORT"
echo "Frontend (Public & Admin) running at: http://localhost:$FRONTEND_STATIC_SERVER_PORT"
echo "   - Public site: http://localhost:$FRONTEND_STATIC_SERVER_PORT/ (or /fr/, /en/)"
echo "   - Admin Panel: http://localhost:$FRONTEND_STATIC_SERVER_PORT/admin/admin_login.html"
echo ""
echo "To STOP the servers:"
echo " - Backend: kill $BACKEND_PID"
if [ ! -z "$FRONTEND_PID_PY" ]; then
    echo " - Frontend (Python http.server): kill $FRONTEND_PID_PY"
fi
# if [ ! -z "$FRONTEND_PID_LS" ]; then
#     echo " - Frontend (live-server): kill $FRONTEND_PID_LS"
# fi
echo "   (You might need to find PIDs manually if the script is interrupted: pgrep -f backend.run, pgrep -f http.server)"
echo "--------------------------------------------------"

# Keep the script running to keep background processes alive if not detached,
# or simply to display the message. For a truly backgrounded setup, you'd use `nohup`
# or a process manager like `pm2` or `supervisor`.
# For simple local dev, this script running and then manually killing is often fine.
# The processes launched with `&` will continue running if the script exits,
# but this `wait` will keep the script itself alive until you Ctrl+C it, which
# might also terminate child processes depending on your shell.
wait
