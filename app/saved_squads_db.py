"""
Saved Squads — SQLite Data Access Layer
=========================================
Lightweight persistence for user-created squads using raw sqlite3.
No ORM — matches the project's minimal-dependency style.

Tables:
    saved_squads         — Squad metadata (name, formation, timestamps, user ownership)
    saved_squad_players  — Player references per squad (starter/bench, slot)

All queries use parameterized placeholders for SQL injection safety.
All operations are scoped to a user_id for ownership enforcement.
"""

import sqlite3
import os
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def get_db_path(app):
    """Resolve the saved squads database path from app config."""
    return app.config.get('SAVED_SQUADS_DB')


def get_db(db_path):
    """
    Open a SQLite connection with foreign key enforcement enabled.

    Returns:
        sqlite3.Connection with row_factory set to sqlite3.Row
        for dict-like access.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def init_db(db_path):
    """
    Create the saved_squads and saved_squad_players tables if they
    don't already exist. Safe to call on every app startup.

    Also runs a safe migration to add user_id column if missing.
    """
    # Ensure the directory exists
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

    conn = get_db(db_path)
    try:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS saved_squads (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                formation   TEXT NOT NULL,
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS saved_squad_players (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                squad_id    INTEGER NOT NULL REFERENCES saved_squads(id) ON DELETE CASCADE,
                player_id   INTEGER NOT NULL,
                role        TEXT NOT NULL,
                slot        TEXT NOT NULL
            );
        ''')
        conn.commit()

        # Migration: add user_id column if it doesn't exist yet
        columns = [row['name'] for row in conn.execute('PRAGMA table_info(saved_squads)').fetchall()]
        if 'user_id' not in columns:
            conn.execute('ALTER TABLE saved_squads ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE CASCADE')
            conn.commit()
            logger.info("[OK] Migrated saved_squads: added user_id column")

        logger.info(f"[OK] Saved squads database initialized at {db_path}")
    except Exception as e:
        logger.error(f"[ERROR] Failed to initialize saved squads database: {e}")
        raise
    finally:
        conn.close()


def _now_iso():
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


# ════════════════════════════════════════════════════════════════
# LIST ALL SQUADS (scoped to user)
# ════════════════════════════════════════════════════════════════

def list_squads(db_path, user_id):
    """
    Return all saved squads for a specific user with metadata and player counts.

    Returns:
        List of dicts: [{id, name, formation, starter_count, bench_count,
                         total_count, created_at, updated_at}, ...]
    """
    conn = get_db(db_path)
    try:
        rows = conn.execute('''
            SELECT
                s.id, s.name, s.formation, s.created_at, s.updated_at,
                COALESCE(SUM(CASE WHEN sp.role = 'starter' THEN 1 ELSE 0 END), 0) AS starter_count,
                COALESCE(SUM(CASE WHEN sp.role = 'bench' THEN 1 ELSE 0 END), 0) AS bench_count,
                COUNT(sp.id) AS total_count
            FROM saved_squads s
            LEFT JOIN saved_squad_players sp ON sp.squad_id = s.id
            WHERE s.user_id = ?
            GROUP BY s.id
            ORDER BY s.updated_at DESC
        ''', (user_id,)).fetchall()

        return [{
            'id': r['id'],
            'name': r['name'],
            'formation': r['formation'],
            'starter_count': r['starter_count'],
            'bench_count': r['bench_count'],
            'total_count': r['total_count'],
            'created_at': r['created_at'],
            'updated_at': r['updated_at'],
        } for r in rows]
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════════
# GET SINGLE SQUAD (raw, without player resolution)
# ════════════════════════════════════════════════════════════════

def get_squad_raw(db_path, squad_id, user_id):
    """
    Retrieve a single saved squad and its player references.
    Enforces ownership via user_id — returns None if squad
    doesn't belong to the requesting user.

    Does NOT resolve player data — that's done in the route layer
    where the data_loader is available.

    Returns:
        Dict with squad metadata + 'players' list, or None if not found.
    """
    conn = get_db(db_path)
    try:
        squad = conn.execute(
            'SELECT * FROM saved_squads WHERE id = ? AND user_id = ?', (squad_id, user_id)
        ).fetchone()

        if not squad:
            return None

        players = conn.execute(
            'SELECT * FROM saved_squad_players WHERE squad_id = ? ORDER BY role, slot',
            (squad_id,)
        ).fetchall()

        return {
            'id': squad['id'],
            'name': squad['name'],
            'formation': squad['formation'],
            'created_at': squad['created_at'],
            'updated_at': squad['updated_at'],
            'players': [{
                'player_id': p['player_id'],
                'role': p['role'],
                'slot': p['slot'],
            } for p in players],
        }
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════════
# CREATE SQUAD
# ════════════════════════════════════════════════════════════════

def create_squad(db_path, name, formation, starters, bench_players, user_id):
    """
    Insert a new saved squad with its player references.

    Args:
        name:          Squad name (str).
        formation:     Formation name (str, e.g. '4-3-3').
        starters:      List of dicts: [{player_id, slot}, ...]
                       where slot is the slot_index as string.
        bench_players: List of dicts: [{player_id, slot}, ...]
                       where slot is the bench category (GK/DEF/MID/ATT).
        user_id:       ID of the owning user.

    Returns:
        The new squad's ID.
    """
    now = _now_iso()
    conn = get_db(db_path)
    try:
        cursor = conn.execute(
            'INSERT INTO saved_squads (name, formation, created_at, updated_at, user_id) VALUES (?, ?, ?, ?, ?)',
            (name, formation, now, now, user_id)
        )
        squad_id = cursor.lastrowid

        # Insert starter references
        for s in starters:
            conn.execute(
                'INSERT INTO saved_squad_players (squad_id, player_id, role, slot) VALUES (?, ?, ?, ?)',
                (squad_id, s['player_id'], 'starter', str(s['slot']))
            )

        # Insert bench references
        for b in bench_players:
            conn.execute(
                'INSERT INTO saved_squad_players (squad_id, player_id, role, slot) VALUES (?, ?, ?, ?)',
                (squad_id, b['player_id'], 'bench', str(b['slot']))
            )

        conn.commit()
        logger.info(f"[OK] Created saved squad '{name}' (ID: {squad_id}) for user {user_id}")
        return squad_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════════
# UPDATE SQUAD
# ════════════════════════════════════════════════════════════════

def update_squad(db_path, squad_id, name, formation, starters, bench_players, user_id):
    """
    Replace an existing saved squad's metadata and player references.
    Enforces ownership via user_id.
    Uses delete-then-insert within a transaction for clean replacement.

    Returns:
        True if the squad existed and was updated, False if not found/not owned.
    """
    conn = get_db(db_path)
    try:
        # Verify squad exists and belongs to user
        existing = conn.execute(
            'SELECT id FROM saved_squads WHERE id = ? AND user_id = ?', (squad_id, user_id)
        ).fetchone()
        if not existing:
            return False

        now = _now_iso()

        # Update squad metadata
        conn.execute(
            'UPDATE saved_squads SET name = ?, formation = ?, updated_at = ? WHERE id = ?',
            (name, formation, now, squad_id)
        )

        # Delete old player associations
        conn.execute(
            'DELETE FROM saved_squad_players WHERE squad_id = ?', (squad_id,)
        )

        # Insert new starter references
        for s in starters:
            conn.execute(
                'INSERT INTO saved_squad_players (squad_id, player_id, role, slot) VALUES (?, ?, ?, ?)',
                (squad_id, s['player_id'], 'starter', str(s['slot']))
            )

        # Insert new bench references
        for b in bench_players:
            conn.execute(
                'INSERT INTO saved_squad_players (squad_id, player_id, role, slot) VALUES (?, ?, ?, ?)',
                (squad_id, b['player_id'], 'bench', str(b['slot']))
            )

        conn.commit()
        logger.info(f"[OK] Updated saved squad ID {squad_id} ('{name}')")
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════════
# DELETE SQUAD
# ════════════════════════════════════════════════════════════════

def delete_squad(db_path, squad_id, user_id):
    """
    Delete a saved squad and its player associations (via CASCADE).
    Enforces ownership via user_id.

    Returns:
        True if the squad existed and was deleted, False if not found/not owned.
    """
    conn = get_db(db_path)
    try:
        # Verify existence and ownership
        existing = conn.execute(
            'SELECT id FROM saved_squads WHERE id = ? AND user_id = ?', (squad_id, user_id)
        ).fetchone()
        if not existing:
            return False

        conn.execute('DELETE FROM saved_squads WHERE id = ?', (squad_id,))
        conn.commit()
        logger.info(f"[OK] Deleted saved squad ID {squad_id}")
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════════
# DUPLICATE SQUAD
# ════════════════════════════════════════════════════════════════

def duplicate_squad(db_path, squad_id, user_id, new_name=None):
    """
    Create a copy of an existing saved squad under a new name.
    Enforces ownership of the source squad via user_id.

    Args:
        squad_id: ID of the squad to duplicate.
        user_id:  ID of the owning user.
        new_name: Name for the copy. If None, appends ' (Copy)' to original.

    Returns:
        The new squad's ID, or None if the source squad was not found.
    """
    source = get_squad_raw(db_path, squad_id, user_id)
    if not source:
        return None

    copy_name = new_name if new_name else f"{source['name']} (Copy)"

    starters = [p for p in source['players'] if p['role'] == 'starter']
    bench_players = [p for p in source['players'] if p['role'] == 'bench']

    return create_squad(db_path, copy_name, source['formation'], starters, bench_players, user_id)
