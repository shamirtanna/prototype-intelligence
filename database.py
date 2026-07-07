
import sqlite3
import json
import re
from datetime import datetime

DB_FILE = "history.db"

def init_db():
    """Create the history table if it doesn't exist."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT,
            timestamp TEXT,
            strategy_snippet TEXT,
            built_count INTEGER,
            missed_count INTEGER,
            total_effort TEXT,
            full_result TEXT
        )
    """)
    conn.commit()
    conn.close()

def extract_project_name(strategy, codebase):
    """Try to auto-detect project name from inputs."""
    
    # Try codebase first: look for <title>, package name, app name
    title_match = re.search(r'<title>(.*?)</title>', codebase)
    if title_match:
        return title_match.group(1).strip()
    
    # Look for "name" in package.json style
    name_match = re.search(r'"name"\s*:\s*"([^"]+)"', codebase)
    if name_match:
        return name_match.group(1).strip()
    
    # Look for app = Flask('name') or similar
    flask_match = re.search(r"Flask\(['\"]([^'\"]+)['\"]\)", codebase)
    if flask_match and flask_match.group(1) != "__name__":
        return flask_match.group(1).strip()
    
    # Try strategy: use first meaningful line
    if strategy:
        lines = strategy.strip().split('\n')
        for line in lines:
            clean = line.strip().strip('#').strip('*').strip()
            if clean and len(clean) > 3 and len(clean) < 60:
                return clean
    
    return "Untitled Project"

def save_analysis(project_name, strategy, result):
    """Save a completed analysis to the database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    built_count = result.get("assessment", {}).get("built_count", 0)
    missed_count = result.get("assessment", {}).get("missed_count", 0)
    
    # Get total effort from first stage
    stages = result.get("plan_to_build", {}).get("stages", [])
    total_effort = stages[0].get("effort", "unknown") if stages else "unknown"
    
    # Save a snippet of strategy for display
    strategy_snippet = strategy[:100] + "..." if len(strategy) > 100 else strategy
    
    cursor.execute("""
        INSERT INTO analyses (project_name, timestamp, strategy_snippet, built_count, missed_count, total_effort, full_result)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        project_name,
        datetime.now().isoformat(),
        strategy_snippet,
        built_count,
        missed_count,
        total_effort,
        json.dumps(result)
    ))
    conn.commit()
    conn.close()

def get_history(project_name=None):
    """Get all past analyses, optionally filtered by project."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    if project_name:
        cursor.execute("""
            SELECT id, project_name, timestamp, built_count, missed_count, total_effort
            FROM analyses WHERE project_name = ? ORDER BY timestamp DESC
        """, (project_name,))
    else:
        cursor.execute("""
            SELECT id, project_name, timestamp, built_count, missed_count, total_effort
            FROM analyses ORDER BY timestamp DESC
        """)
    
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {
            "id": row[0],
            "project_name": row[1],
            "timestamp": row[2],
            "built_count": row[3],
            "missed_count": row[4],
            "total_effort": row[5]
        }
        for row in rows
    ]

def get_projects():
    """Get list of unique project names."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT project_name FROM analyses ORDER BY project_name")
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]

def get_analysis(analysis_id):
    """Get a single full analysis by ID."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT full_result FROM analyses WHERE id = ?", (analysis_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return json.loads(row[0])
    return None

def get_progress(project_name):
    """Compare latest two analyses for a project — show progress."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT built_count, missed_count, total_effort, timestamp
        FROM analyses WHERE project_name = ? ORDER BY timestamp DESC LIMIT 2
    """, (project_name,))
    rows = cursor.fetchall()
    conn.close()
    
    if len(rows) < 2:
        return None
    
    current = rows[0]
    previous = rows[1]
    
    return {
        "built_change": current[0] - previous[0],
        "missed_change": current[1] - previous[1],
        "current_effort": current[2],
        "previous_effort": previous[2],
        "current_date": current[3],
        "previous_date": previous[3]
    }

# Initialize database when this file is imported
init_db()

