from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class ERColumn(BaseModel):
    name: str
    data_type: str
    markers: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)

    @property
    def nullable(self) -> bool:
        return "not_null" not in self.markers


class ERTable(BaseModel):
    name: str
    kind: Literal["table", "view"] = "table"
    subject_area: str
    columns: list[ERColumn] = Field(default_factory=list)


class ERRelationship(BaseModel):
    source_table: str
    source_column: str
    target_table: str
    target_column: str
    cardinality: str = "many-to-one"
    label: str = ""
    attributes: dict[str, Any] = Field(default_factory=dict)


class ERModel(BaseModel):
    name: str
    dialect: str = "sqlite"
    direction: Literal["LR", "TB"] = "LR"
    tables: list[ERTable] = Field(default_factory=list)
    relationships: list[ERRelationship] = Field(default_factory=list)

