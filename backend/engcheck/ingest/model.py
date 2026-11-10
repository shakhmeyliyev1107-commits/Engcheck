"""Parserlarning umumiy natija modeli."""
from dataclasses import dataclass, field


@dataclass
class Cell:
    text: str
    location: str


@dataclass
class Table:
    rows: list[list[Cell]]


@dataclass
class TextItem:
    text: str
    location: str
    attrs: dict[str, str] | None = None


@dataclass
class Page:
    number: int
    text: str = ""
    tables: list[Table] = field(default_factory=list)
    items: list[TextItem] = field(default_factory=list)


@dataclass
class ParsedDocument:
    pages: list[Page]
