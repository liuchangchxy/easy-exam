from dataclasses import dataclass


@dataclass(frozen=True)
class EvidenceItem:
    title: str
    url: str | None = None
    summary: str | None = None

    def to_dict(self) -> dict:
        return {"title": self.title, "url": self.url, "summary": self.summary}
