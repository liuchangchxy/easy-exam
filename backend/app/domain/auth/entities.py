from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    id: str
    username: str
    is_active: bool = True

    def to_dict(self) -> dict:
        return {"id": self.id, "username": self.username, "is_active": self.is_active}
