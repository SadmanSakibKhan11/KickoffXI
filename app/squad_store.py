"""
Squad Store — Firestore Access for User Saved Squads
=====================================================
Manages user-owned squads in Cloud Firestore under subcollections:
    users/{uid}/saved_squads/{squadId}

Document Schema:
    name: string
    formation: string
    created_at: ISO-8601 UTC string
    updated_at: ISO-8601 UTC string
    players: list of 18 dicts:
        - player_key: string ("<nationality-slug>:<name-slug>")
        - role: "starter" | "bench"
        - slot: string (slot index "0".."10" or "GK"|"DEF"|"MID"|"ATT")

Security & Structural Isolation:
- Squads are only ever accessed under users/{uid}/saved_squads/{squadId}.
- Attempting to access another user's squad yields a 404 (not found).
- Squad IDs are validated against ^[A-Za-z0-9_-]{1,64}$.
- Soft cap: maximum 50 saved squads per user.
- Interface pattern allowing in-memory substitution for unit tests.
"""

import re
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from app.firebase_client import get_firestore_client

SQUAD_ID_REGEX = re.compile(r'^[A-Za-z0-9_-]{1,64}$')
MAX_SQUADS_PER_USER = 50


def is_valid_squad_id(squad_id: str) -> bool:
    """Validate squad ID format to prevent invalid Firestore document paths."""
    if not squad_id or not isinstance(squad_id, str):
        return False
    return bool(SQUAD_ID_REGEX.match(squad_id))


class SquadStoreError(Exception):
    """Base exception for squad store errors."""
    pass


class SquadLimitReachedError(SquadStoreError):
    """Raised when a user attempts to exceed the maximum allowed squads."""
    pass


class BaseSquadStore:
    """Abstract interface for saved squad storage."""

    def list_squads(self, uid: str) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def get_squad_raw(self, uid: str, squad_id: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def create_squad(
        self,
        uid: str,
        name: str,
        formation: str,
        players: List[Dict[str, Any]],
        squad_id: Optional[str] = None,
    ) -> str:
        raise NotImplementedError

    def update_squad(
        self,
        uid: str,
        squad_id: str,
        name: str,
        formation: str,
        players: List[Dict[str, Any]]
    ) -> bool:
        raise NotImplementedError

    def delete_squad(self, uid: str, squad_id: str) -> bool:
        raise NotImplementedError

    def duplicate_squad(
        self,
        uid: str,
        squad_id: str,
        new_name: Optional[str] = None
    ) -> Optional[str]:
        raise NotImplementedError


class FirestoreSquadStore(BaseSquadStore):
    """Production implementation using Google Cloud Firestore."""

    def __init__(self, db=None):
        self._db = db

    @property
    def db(self):
        if self._db is None:
            self._db = get_firestore_client()
        return self._db

    def _squads_col(self, uid: str):
        return self.db.collection('users').document(uid).collection('saved_squads')

    def list_squads(self, uid: str) -> List[Dict[str, Any]]:
        col_ref = self._squads_col(uid)
        docs = col_ref.stream()

        squads = []
        for doc in docs:
            data = doc.to_dict() or {}
            players = data.get('players', [])
            starters = [p for p in players if p.get('role') == 'starter']
            bench = [p for p in players if p.get('role') == 'bench']

            squads.append({
                'id': doc.id,
                'name': data.get('name', ''),
                'formation': data.get('formation', ''),
                'created_at': data.get('created_at', ''),
                'updated_at': data.get('updated_at', ''),
                'starter_count': len(starters),
                'bench_count': len(bench),
                'total_count': len(players),
            })

        # Sort by updated_at descending
        squads.sort(key=lambda s: s['updated_at'] or '', reverse=True)
        return squads

    def get_squad_raw(self, uid: str, squad_id: str) -> Optional[Dict[str, Any]]:
        if not is_valid_squad_id(squad_id):
            return None

        doc_ref = self._squads_col(uid).document(squad_id)
        snap = doc_ref.get()
        if not snap.exists:
            return None

        data = snap.to_dict() or {}
        data['id'] = doc_ref.id
        return data

    def create_squad(
        self,
        uid: str,
        name: str,
        formation: str,
        players: List[Dict[str, Any]],
        squad_id: Optional[str] = None,
    ) -> str:
        col_ref = self._squads_col(uid)

        # Check limit
        existing_count = len(list(col_ref.select([]).stream()))
        if existing_count >= MAX_SQUADS_PER_USER:
            raise SquadLimitReachedError(
                f"Squad limit of {MAX_SQUADS_PER_USER} reached. Please delete an older squad."
            )

        sid = squad_id or uuid.uuid4().hex[:12]
        if not is_valid_squad_id(sid):
            raise SquadStoreError(f"Invalid squad ID: '{sid}'")

        now_iso = datetime.now(timezone.utc).isoformat()
        squad_doc = {
            'name': name.strip(),
            'formation': formation.strip(),
            'created_at': now_iso,
            'updated_at': now_iso,
            'players': players
        }

        col_ref.document(sid).set(squad_doc)
        return sid

    def update_squad(
        self,
        uid: str,
        squad_id: str,
        name: str,
        formation: str,
        players: List[Dict[str, Any]]
    ) -> bool:
        if not is_valid_squad_id(squad_id):
            return False

        doc_ref = self._squads_col(uid).document(squad_id)
        snap = doc_ref.get()
        if not snap.exists:
            return False

        now_iso = datetime.now(timezone.utc).isoformat()
        doc_ref.update({
            'name': name.strip(),
            'formation': formation.strip(),
            'updated_at': now_iso,
            'players': players
        })
        return True

    def delete_squad(self, uid: str, squad_id: str) -> bool:
        if not is_valid_squad_id(squad_id):
            return False

        doc_ref = self._squads_col(uid).document(squad_id)
        snap = doc_ref.get()
        if not snap.exists:
            return False

        doc_ref.delete()
        return True

    def duplicate_squad(
        self,
        uid: str,
        squad_id: str,
        new_name: Optional[str] = None
    ) -> Optional[str]:
        raw = self.get_squad_raw(uid, squad_id)
        if not raw:
            return None

        target_name = (new_name or '').strip() or f"{raw['name']} (Copy)"
        return self.create_squad(
            uid=uid,
            name=target_name,
            formation=raw['formation'],
            players=raw.get('players', [])
        )


class InMemorySquadStore(BaseSquadStore):
    """In-memory squad store for fast, isolated offline unit tests."""

    def __init__(self):
        # uid -> { squad_id -> squad_doc }
        self.squads: Dict[str, Dict[str, Dict[str, Any]]] = {}

    def _user_squads(self, uid: str) -> Dict[str, Dict[str, Any]]:
        return self.squads.setdefault(uid, {})

    def list_squads(self, uid: str) -> List[Dict[str, Any]]:
        user_squads = self._user_squads(uid)
        result = []
        for sid, data in user_squads.items():
            players = data.get('players', [])
            starters = [p for p in players if p.get('role') == 'starter']
            bench = [p for p in players if p.get('role') == 'bench']
            result.append({
                'id': sid,
                'name': data.get('name', ''),
                'formation': data.get('formation', ''),
                'created_at': data.get('created_at', ''),
                'updated_at': data.get('updated_at', ''),
                'starter_count': len(starters),
                'bench_count': len(bench),
                'total_count': len(players),
            })
        result.sort(key=lambda s: s['updated_at'] or '', reverse=True)
        return result

    def get_squad_raw(self, uid: str, squad_id: str) -> Optional[Dict[str, Any]]:
        if not is_valid_squad_id(squad_id):
            return None
        user_squads = self._user_squads(uid)
        doc = user_squads.get(squad_id)
        if not doc:
            return None
        copy = dict(doc)
        copy['id'] = squad_id
        return copy

    def create_squad(
        self,
        uid: str,
        name: str,
        formation: str,
        players: List[Dict[str, Any]],
        squad_id: Optional[str] = None,
    ) -> str:
        user_squads = self._user_squads(uid)
        if len(user_squads) >= MAX_SQUADS_PER_USER:
            raise SquadLimitReachedError(
                f"Squad limit of {MAX_SQUADS_PER_USER} reached. Please delete an older squad."
            )

        sid = squad_id or uuid.uuid4().hex[:12]
        if not is_valid_squad_id(sid):
            raise SquadStoreError(f"Invalid squad ID: '{sid}'")

        now_iso = datetime.now(timezone.utc).isoformat()
        user_squads[sid] = {
            'name': name.strip(),
            'formation': formation.strip(),
            'created_at': now_iso,
            'updated_at': now_iso,
            'players': list(players)
        }
        return sid

    def update_squad(
        self,
        uid: str,
        squad_id: str,
        name: str,
        formation: str,
        players: List[Dict[str, Any]]
    ) -> bool:
        if not is_valid_squad_id(squad_id):
            return False
        user_squads = self._user_squads(uid)
        if squad_id not in user_squads:
            return False

        now_iso = datetime.now(timezone.utc).isoformat()
        doc = user_squads[squad_id]
        doc['name'] = name.strip()
        doc['formation'] = formation.strip()
        doc['updated_at'] = now_iso
        doc['players'] = list(players)
        return True

    def delete_squad(self, uid: str, squad_id: str) -> bool:
        if not is_valid_squad_id(squad_id):
            return False
        user_squads = self._user_squads(uid)
        if squad_id in user_squads:
            del user_squads[squad_id]
            return True
        return False

    def duplicate_squad(
        self,
        uid: str,
        squad_id: str,
        new_name: Optional[str] = None
    ) -> Optional[str]:
        raw = self.get_squad_raw(uid, squad_id)
        if not raw:
            return None
        target_name = (new_name or '').strip() or f"{raw['name']} (Copy)"
        return self.create_squad(
            uid=uid,
            name=target_name,
            formation=raw['formation'],
            players=raw.get('players', [])
        )


_current_squad_store: Optional[BaseSquadStore] = None


def get_squad_store() -> BaseSquadStore:
    global _current_squad_store
    if _current_squad_store is None:
        _current_squad_store = FirestoreSquadStore()
    return _current_squad_store


def set_squad_store(store: BaseSquadStore) -> None:
    global _current_squad_store
    _current_squad_store = store

