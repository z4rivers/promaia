"""
PC digital fingerprint scanner — automated profile data extraction.

Analyzes local git repos, file structure, and installed apps to infer
profile data. Results are stored in profile with source='inferred'.

This formalizes the manual scan that was proved in Phase 2 (populating 39 fields).
Safe to run multiple times — results are upserted via ON CONFLICT.

Usage:
    from promaia.brain.channels.pc_scan import run_pc_scan
    result = run_pc_scan(db=some_db)
"""
import json
import logging
import os
import platform
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SUBPROCESS_TIMEOUT = 30  # seconds
MAX_REPOS = 10
CONFIDENCE_INFERRED = 0.6


def run_pc_scan(
    home_dir: Optional[str] = None,
    db=None,
) -> Dict[str, Any]:
    """Run the PC digital fingerprint scan.

    Analyzes local git repos, file structure, and installed apps to extract
    profile-relevant data. Each section is independent — partial results are
    returned if any section fails.

    Args:
        home_dir: Override home directory (default: os.path.expanduser('~')).
        db: database instance. If None, imports and creates one.

    Returns:
        dict with {fields_updated, repos_scanned, apps_found, insights}
    """
    if home_dir is None:
        home_dir = os.path.expanduser("~")

    if db is None:
        from promaia.storage.db_factory import get_db
        db = get_db()

    result = {
        "fields_updated": 0,
        "repos_scanned": 0,
        "apps_found": 0,
        "insights": [],
    }

    # --- Section 1: Git analysis ---
    try:
        git_result = _scan_git_repos(home_dir, db)
        result["repos_scanned"] = git_result["repos_scanned"]
        result["fields_updated"] += git_result["fields_updated"]
        result["insights"].extend(git_result["insights"])
    except Exception as e:
        logger.error(f"PC scan git analysis failed: {e}", exc_info=True)
        result["insights"].append(f"Git analysis failed: {e}")

    # --- Section 2: File structure analysis ---
    try:
        file_result = _scan_file_structure(home_dir, db)
        result["fields_updated"] += file_result["fields_updated"]
        result["insights"].extend(file_result["insights"])
    except Exception as e:
        logger.error(f"PC scan file structure analysis failed: {e}", exc_info=True)
        result["insights"].append(f"File structure analysis failed: {e}")

    # --- Section 3: Installed apps detection ---
    try:
        apps_result = _scan_installed_apps(db)
        result["apps_found"] = apps_result["apps_found"]
        result["fields_updated"] += apps_result["fields_updated"]
        result["insights"].extend(apps_result["insights"])
    except Exception as e:
        logger.error(f"PC scan installed apps detection failed: {e}", exc_info=True)
        result["insights"].append(f"Installed apps detection failed: {e}")

    logger.info(
        f"PC scan complete: {result['repos_scanned']} repos, "
        f"{result['apps_found']} apps, {result['fields_updated']} fields updated"
    )
    return result


# ---------------------------------------------------------------------------
# Section 1: Git analysis
# ---------------------------------------------------------------------------

def _scan_git_repos(home_dir: str, db) -> Dict[str, Any]:
    """Scan ~/dev/ for git repos and extract commit patterns."""
    dev_dir = os.path.join(home_dir, "dev")
    result = {"repos_scanned": 0, "fields_updated": 0, "insights": []}

    if not os.path.isdir(dev_dir):
        result["insights"].append(f"No dev directory found at {dev_dir}")
        return result

    # Find git repos (top-level dirs in ~/dev/ with .git)
    repos: List[Dict[str, Any]] = []
    try:
        for entry in sorted(os.listdir(dev_dir)):
            repo_path = os.path.join(dev_dir, entry)
            if os.path.isdir(os.path.join(repo_path, ".git")):
                repos.append({"name": entry, "path": repo_path})
                if len(repos) >= MAX_REPOS:
                    break
    except OSError as e:
        logger.warning(f"Could not list {dev_dir}: {e}")
        return result

    if not repos:
        result["insights"].append("No git repositories found in ~/dev/")
        return result

    # Aggregate commit data across all repos
    all_hours: List[int] = []
    all_days: List[int] = []  # 0=Mon, 6=Sun
    burst_gaps: List[float] = []
    repo_names: List[str] = []
    total_commits = 0

    for repo in repos:
        commits = _get_git_commits(repo["path"])
        if commits:
            repo_names.append(repo["name"])
            result["repos_scanned"] += 1
            total_commits += len(commits)

            for commit in commits:
                ts = commit.get("timestamp")
                if ts:
                    all_hours.append(ts.hour)
                    all_days.append(ts.weekday())

            # Detect burst patterns (gaps between commits in hours)
            sorted_commits = sorted(commits, key=lambda c: c.get("timestamp", datetime.min.replace(tzinfo=timezone.utc)))
            for i in range(1, len(sorted_commits)):
                prev_ts = sorted_commits[i - 1].get("timestamp")
                curr_ts = sorted_commits[i].get("timestamp")
                if prev_ts and curr_ts:
                    gap_hours = (curr_ts - prev_ts).total_seconds() / 3600
                    if gap_hours > 0:
                        burst_gaps.append(gap_hours)

    # --- Derive chronotype ---
    if all_hours:
        hour_counts = Counter(all_hours)
        peak_hours = [h for h, _ in hour_counts.most_common(4)]
        peak_hours.sort()

        if any(h >= 22 or h <= 3 for h in peak_hours):
            chronotype = "night_owl"
        elif any(h <= 7 for h in peak_hours):
            chronotype = "early_bird"
        else:
            chronotype = "standard"

        _upsert_profile(db, "energy_patterns", "chronotype", chronotype, CONFIDENCE_INFERRED)
        result["fields_updated"] += 1
        result["insights"].append(f"Chronotype: {chronotype} (peak hours: {peak_hours})")

        # Peak focus hours
        peak_str = ", ".join(f"{h}:00" for h in peak_hours)
        _upsert_profile(db, "energy_patterns", "peak_focus_hours", peak_str, CONFIDENCE_INFERRED)
        result["fields_updated"] += 1

    # --- Derive sprint duration ---
    if burst_gaps:
        # "Sprint" = cluster of commits with <4h gaps
        sprint_lengths: List[int] = []
        current_sprint = 1
        for gap in burst_gaps:
            if gap < 4:
                current_sprint += 1
            else:
                if current_sprint > 1:
                    sprint_lengths.append(current_sprint)
                current_sprint = 1
        if current_sprint > 1:
            sprint_lengths.append(current_sprint)

        if sprint_lengths:
            avg_sprint = sum(sprint_lengths) / len(sprint_lengths)
            sprint_desc = f"{avg_sprint:.1f} commits per sprint (avg)"
            _upsert_profile(db, "work_patterns", "sprint_duration", sprint_desc, CONFIDENCE_INFERRED)
            result["fields_updated"] += 1
            result["insights"].append(f"Sprint pattern: {sprint_desc}")

    # --- Active projects ---
    if repo_names:
        _upsert_profile(db, "context", "active_projects", repo_names, CONFIDENCE_INFERRED)
        result["fields_updated"] += 1
        result["insights"].append(f"Active projects: {', '.join(repo_names)}")

    # --- Day-of-week patterns ---
    if all_days:
        day_counts = Counter(all_days)
        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        most_active_days = [day_names[d] for d, _ in day_counts.most_common(3)]
        _upsert_profile(db, "work_patterns", "most_active_days", most_active_days, CONFIDENCE_INFERRED)
        result["fields_updated"] += 1

    return result


def _get_git_commits(repo_path: str) -> List[Dict[str, Any]]:
    """Extract recent commits from a git repo."""
    try:
        proc = subprocess.run(
            ["git", "log", "--format=%H|%ai|%s", "-n", "100"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT,
        )
        if proc.returncode != 0:
            return []

        commits = []
        for line in proc.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("|", 2)
            if len(parts) < 3:
                continue
            hash_val, date_str, subject = parts
            try:
                # Parse git date format: "2026-03-05 10:30:00 -0800"
                ts = datetime.strptime(date_str.strip()[:19], "%Y-%m-%d %H:%M:%S")
                ts = ts.replace(tzinfo=timezone.utc)
            except ValueError:
                ts = None
            commits.append({"hash": hash_val, "timestamp": ts, "subject": subject})
        return commits

    except (subprocess.TimeoutExpired, OSError) as e:
        logger.warning(f"Git log failed for {repo_path}: {e}")
        return []


# ---------------------------------------------------------------------------
# Section 2: File structure analysis
# ---------------------------------------------------------------------------

def _scan_file_structure(home_dir: str, db) -> Dict[str, Any]:
    """Scan ~/dev/ directory structure and config files for tech stack signals."""
    dev_dir = os.path.join(home_dir, "dev")
    result = {"fields_updated": 0, "insights": []}

    tech_stack: List[str] = []

    if os.path.isdir(dev_dir):
        # Scan for language/framework indicators
        for entry in os.listdir(dev_dir):
            project_dir = os.path.join(dev_dir, entry)
            if not os.path.isdir(project_dir):
                continue

            if os.path.exists(os.path.join(project_dir, "package.json")):
                if "JavaScript/Node.js" not in tech_stack:
                    tech_stack.append("JavaScript/Node.js")
            if os.path.exists(os.path.join(project_dir, "requirements.txt")) or \
               os.path.exists(os.path.join(project_dir, "pyproject.toml")):
                if "Python" not in tech_stack:
                    tech_stack.append("Python")
            if os.path.exists(os.path.join(project_dir, "Cargo.toml")):
                if "Rust" not in tech_stack:
                    tech_stack.append("Rust")
            if os.path.exists(os.path.join(project_dir, "go.mod")):
                if "Go" not in tech_stack:
                    tech_stack.append("Go")
            if os.path.exists(os.path.join(project_dir, "tsconfig.json")):
                if "TypeScript" not in tech_stack:
                    tech_stack.append("TypeScript")

    if tech_stack:
        _upsert_profile(db, "context", "tech_stack", tech_stack, CONFIDENCE_INFERRED)
        result["fields_updated"] += 1
        result["insights"].append(f"Tech stack detected: {', '.join(tech_stack)}")

    # OS / device detection
    os_info = f"{platform.system()} {platform.release()}"
    _upsert_profile(db, "context", "devices", [os_info], CONFIDENCE_INFERRED)
    result["fields_updated"] += 1
    result["insights"].append(f"Device: {os_info}")

    # Shell preference
    shell = os.environ.get("SHELL") or os.environ.get("COMSPEC", "unknown")
    _upsert_profile(db, "context", "shell_preference", shell, CONFIDENCE_INFERRED)
    result["fields_updated"] += 1

    return result


# ---------------------------------------------------------------------------
# Section 3: Installed apps detection (Windows-specific)
# ---------------------------------------------------------------------------

def _scan_installed_apps(db) -> Dict[str, Any]:
    """Detect installed applications and store interesting ones as memories."""
    result = {"apps_found": 0, "fields_updated": 0, "insights": []}

    if platform.system() != "Windows":
        result["insights"].append("App detection only supported on Windows")
        return result

    apps = _get_installed_apps_windows()
    result["apps_found"] = len(apps)

    if not apps:
        result["insights"].append("No installed apps detected")
        return result

    # Categorize apps
    categories = _categorize_apps(apps)

    # Store interesting categories as memories
    for category, app_list in categories.items():
        if app_list:
            summary = f"Installed {category} software: {', '.join(app_list[:10])}"
            try:
                db.execute(
                    """
                    INSERT INTO memories (content, domain, source, source_id)
                    VALUES (%s, 'personal', 'pc_scan', 'pc_scan_apps')
                    ON CONFLICT DO NOTHING
                    """,
                    (summary,),
                )
            except Exception as e:
                logger.warning(f"Could not store app memory for {category}: {e}")

    # Store dev tools in profile
    if categories.get("dev_tools"):
        _upsert_profile(db, "context", "dev_tools", categories["dev_tools"], CONFIDENCE_INFERRED)
        result["fields_updated"] += 1
        result["insights"].append(f"Dev tools: {', '.join(categories['dev_tools'][:5])}")

    if categories.get("creative"):
        _upsert_profile(db, "context", "creative_tools", categories["creative"], CONFIDENCE_INFERRED)
        result["fields_updated"] += 1
        result["insights"].append(f"Creative tools: {', '.join(categories['creative'][:5])}")

    return result


def _get_installed_apps_windows() -> List[str]:
    """Get list of installed Windows applications via registry query."""
    apps: List[str] = []
    reg_paths = [
        r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        r"HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
    ]

    for reg_path in reg_paths:
        try:
            proc = subprocess.run(
                ["reg", "query", reg_path, "/s", "/v", "DisplayName"],
                capture_output=True,
                text=True,
                timeout=SUBPROCESS_TIMEOUT,
            )
            if proc.returncode == 0:
                for line in proc.stdout.split("\n"):
                    if "DisplayName" in line and "REG_SZ" in line:
                        # Extract the value after REG_SZ
                        parts = line.split("REG_SZ", 1)
                        if len(parts) == 2:
                            name = parts[1].strip()
                            if name and name not in apps:
                                apps.append(name)
        except (subprocess.TimeoutExpired, OSError) as e:
            logger.warning(f"Registry query failed for {reg_path}: {e}")

    return apps


def _categorize_apps(apps: List[str]) -> Dict[str, List[str]]:
    """Categorize installed apps into meaningful groups."""
    categories: Dict[str, List[str]] = {
        "dev_tools": [],
        "productivity": [],
        "creative": [],
        "communication": [],
        "browsers": [],
    }

    dev_keywords = [
        "visual studio", "vs code", "vscode", "python", "node", "git",
        "docker", "postman", "jetbrains", "intellij", "pycharm", "sublime",
        "cursor", "wsl", "powershell", "windows terminal", "figma",
    ]
    creative_keywords = [
        "adobe", "photoshop", "illustrator", "blender", "gimp", "inkscape",
        "figma", "canva", "davinci", "obs", "audacity",
    ]
    productivity_keywords = [
        "notion", "obsidian", "evernote", "todoist", "trello", "slack",
        "microsoft office", "excel", "word", "powerpoint", "onenote",
        "bitwarden", "1password", "lastpass",
    ]
    communication_keywords = [
        "slack", "discord", "zoom", "teams", "signal", "telegram", "whatsapp",
    ]
    browser_keywords = [
        "chrome", "firefox", "edge", "brave", "opera", "vivaldi", "arc",
    ]

    for app in apps:
        app_lower = app.lower()
        if any(kw in app_lower for kw in dev_keywords):
            categories["dev_tools"].append(app)
        if any(kw in app_lower for kw in creative_keywords):
            categories["creative"].append(app)
        if any(kw in app_lower for kw in productivity_keywords):
            categories["productivity"].append(app)
        if any(kw in app_lower for kw in communication_keywords):
            categories["communication"].append(app)
        if any(kw in app_lower for kw in browser_keywords):
            categories["browsers"].append(app)

    return categories


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _upsert_profile(
    db,
    category: str,
    field: str,
    value: Any,
    confidence: float = CONFIDENCE_INFERRED,
    source: str = "inferred",
) -> None:
    """Upsert a single profile field in profile."""
    value_json = json.dumps(value)
    try:
        db.execute(
            """
            INSERT INTO profile (category, field, value, confidence, source, updated_at)
            VALUES (%s, %s, %s, %s, %s, datetime('now'))
            ON CONFLICT (category, field) DO UPDATE SET
                value = EXCLUDED.value,
                confidence = EXCLUDED.confidence,
                source = EXCLUDED.source,
                updated_at = datetime('now')
            """,
            (category, field, value_json, confidence, source),
        )
    except Exception as e:
        logger.error(f"Profile upsert failed for {category}.{field}: {e}")

    # Generate embedding for semantic search
    try:
        from promaia.storage.vector_db import VectorDBManager
        embed_text = f"{category} {field}: {value_json}"
        vector_mgr = VectorDBManager()
        embedding = vector_mgr.generate_embedding(embed_text)
        embedding_array = json.dumps(embedding)

        page_id = f"profile:{category}:{field}"
        db.execute(
                    "DELETE FROM content_embeddings WHERE page_id = %s AND chunk_id IS NULL",
                    (page_id,),
                )
        db.execute(
                    """INSERT INTO content_embeddings (page_id, content, embedding, database_name, created_at, updated_at)
                       VALUES (%s, %s, %s, 'brain_profile', datetime('now'), datetime('now'))""",
                    (page_id, embed_text, embedding_array),
                )
    except Exception as e:
        logger.warning(f"Profile embedding failed for {category}.{field}: {e}")
