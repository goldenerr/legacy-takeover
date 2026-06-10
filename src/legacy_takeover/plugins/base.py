"""Plugin Abstract Base Class and Pydantic data models."""

from abc import ABC, abstractmethod
from enum import Enum, IntEnum
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────────────────────


class ModuleType(str, Enum):
    PACKAGE = "package"
    MODULE = "module"
    FILE = "file"
    CLASS = "class"
    FUNCTION = "function"
    SERVICE = "service"
    CONTROLLER = "controller"
    MIDDLEWARE = "middleware"
    CONFIG = "config"
    UNKNOWN = "unknown"


class DependencyType(str, Enum):
    IMPORT = "import"
    CALL = "call"
    INHERITANCE = "inheritance"
    HTTP_CLIENT = "http_client"
    GRPC_CLIENT = "grpc_client"
    MESSAGE_QUEUE = "message_queue"
    DATABASE = "database"
    FILE_READ = "file_read"
    UNKNOWN = "unknown"


class RiskCategory(str, Enum):
    SECURITY = "security"
    TECH_DEBT = "tech_debt"
    SINGLE_POINT = "single_point_of_failure"
    BUS_FACTOR = "bus_factor"
    LICENSE = "license_compliance"
    PERFORMANCE = "performance"


class RiskSeverity(IntEnum):
    INFO = 2
    LOW = 4
    MEDIUM = 6
    HIGH = 8
    CRITICAL = 10


# ── Data Models ────────────────────────────────────────────────────────────────


class Module(BaseModel):
    name: str
    path: str
    type: ModuleType = ModuleType.UNKNOWN
    parent: str | None = None
    children: list["Module"] = Field(default_factory=list)
    description: str = ""
    lines_of_code: int = 0
    metadata: dict = Field(default_factory=dict)


class ModuleGraph(BaseModel):
    language: str
    root: Module
    modules: list[Module] = Field(default_factory=list)
    summary: str = ""


class Dependency(BaseModel):
    from_module: str
    to_module: str
    type: DependencyType = DependencyType.UNKNOWN
    detail: str = ""


class DependencyTree(BaseModel):
    language: str
    nodes: list[str] = Field(default_factory=list)
    edges: list[Dependency] = Field(default_factory=list)
    external_deps: list[str] = Field(default_factory=list)
    summary: str = ""


class Column(BaseModel):
    name: str
    type: str
    nullable: bool = True
    primary_key: bool = False
    foreign_key: str | None = None
    default: str | None = None


class Table(BaseModel):
    name: str
    columns: list[Column] = Field(default_factory=list)
    description: str = ""
    row_estimate: int = 0


class ERDiagram(BaseModel):
    language: str
    tables: list[Table] = Field(default_factory=list)
    orm_framework: str = "unknown"
    summary: str = ""


class Risk(BaseModel):
    id: str
    category: RiskCategory
    severity: RiskSeverity
    confidence: float = Field(ge=0.0, le=1.0)
    title: str
    description: str
    file: str = ""
    line: int = 0
    evidence: str = ""
    recommendation: str = ""

    @property
    def risk_score(self) -> float:
        return self.severity.value * self.confidence


# ── Abstract Base Class ───────────────────────────────────────────────────────


class LanguageAnalyzer(ABC):
    name: ClassVar[str]
    file_patterns: ClassVar[list[str]]

    def __init__(self, repo_path: Path, depth: str = "standard"):
        self.repo_path = repo_path
        self.depth = depth

    @abstractmethod
    def detect(self) -> float: ...

    @abstractmethod
    def extract_structure(self) -> ModuleGraph: ...

    @abstractmethod
    def extract_dependencies(self) -> DependencyTree: ...

    @abstractmethod
    def extract_db_schema(self) -> ERDiagram: ...

    @abstractmethod
    def assess_risks(self) -> list[Risk]: ...
