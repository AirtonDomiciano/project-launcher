APP_DIR_NAME = "moah-project-launcher"
DEFAULT_PROJECTS_ROOT = "/media/projetos"
DEFAULT_CURSOR_BIN = "/usr/bin/cursor"
SUGGESTED_ROOT_NAMES = ("Aluai", "IMEX", "Agents", "Aulas", "MOAH", "Projetos")
MARKER_NAMES = (".git", "package.json", "pyproject.toml", "Cargo.toml", "go.mod")
IGNORED_DIRS = frozenset(
    {"node_modules", ".git", "dist", "build", ".next", ".venv", "vendor"}
)
MAX_RECENTS = 30
SCHEMA_VERSION = 1
