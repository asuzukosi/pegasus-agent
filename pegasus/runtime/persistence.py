from pegasus.config.config import Config
from pegasus.session.session import Session
from pegasus.config.loader import get_config_dir
import os
from datetime import datetime
from typing import Any
import json

class SessionSnapshot:
    session_id: str
    created_at: datetime
    updated_at: datetime
    turn_count: int
    messages: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "turn_count": self.turn_count,
            "messages": self.messages,
        }
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'SessionSnapshot':
        return SessionSnapshot(
            session_id=data["session_id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            turn_count=data["turn_count"],
            messages=data["messages"],
        )

class PersistenceManager:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._data_dir = get_config_dir()
        self._session_dir = self._data_dir / "sessions"
        self._session_dir.mkdir(parents=True, exist_ok=True)
        self._checkpoint_dir = self._data_dir / "checkpoints"
        self._checkpoint_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self._session_dir, 0o700)
        os.chmod(self._checkpoint_dir, 0o700)


    def save(self, snapshot: SessionSnapshot) -> None:
        session_file = self._session_dir / f"{snapshot.session_id}.json"
        with open(session_file, "w") as f:
            json.dump(snapshot.to_dict(), f, indent=4)
        os.chmod(session_file, 0o600)

    def load(self, session_id: str) -> SessionSnapshot | None:
        session_file = self._session_dir / f"{session_id}.json"
        if not session_file.exists():
            return None
        with open(session_file, "r") as f:
            data = json.load(f)
            return SessionSnapshot.from_dict(data)

    def list_sessions(self) -> list[SessionSnapshot]:
        session_files = list(self._session_dir.glob("*.json"))
        sessions = []
        for session_file in session_files:
            with open(session_file, "r") as f:
                data = json.load(f)
                sessions.append({
                    "session_id": data["session_id"],
                    "created_at": datetime.fromisoformat(data["created_at"]),
                    "updated_at": datetime.fromisoformat(data["updated_at"]),
                    "turn_count": data["turn_count"],
                })
        sessions = sorted(sessions, key=lambda x: x["updated_at"], reverse=True)
        return sessions
                

    def save_checkpoint(self, snapshot: SessionSnapshot, ) -> None:
        timestamp = datetime.now().isoformat()
        checkpoint_file = self._checkpoint_dir / f"{snapshot.session_id}_{timestamp}.json"
        with open(checkpoint_file, "w") as f:
            json.dump(snapshot.to_dict(), f, indent=4)
        os.chmod(checkpoint_file, 0o600)

    def load_checkpoint(self, session_id: str, timestamp: str) -> SessionSnapshot | None:
        checkpoint_file = self._checkpoint_dir / f"{session_id}_{timestamp}.json"
        if not checkpoint_file.exists():
            return None
        with open(checkpoint_file, "r") as f:
            data = json.load(f)
            return SessionSnapshot.from_dict(data)