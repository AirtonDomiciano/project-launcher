"""Textos mostrados ao usuário. Ficam num só lugar para a interface e os testes."""

PROJECT_NOT_FOUND = "Projeto não encontrado"
GROUP_NOT_FOUND = "Grupo não encontrado"
GROUP_EMPTY = "Grupo sem projetos"
NO_SOURCE_FOLDERS = "Nenhuma pasta de origem selecionada."
GROUP_NEEDS_NAME = "O grupo precisa de um nome."
GROUP_NEEDS_PROJECT = "Escolha ao menos um projeto."
MANUAL_ONLY = (
    "Só um projeto adicionado manualmente pode ser removido daqui. "
    "Os demais saem do catálogo quando deixam de ser encontrados."
)
FILESYSTEM_ROOT_REJECTED = "A raiz do sistema de arquivos não pode ser uma pasta de origem."


def ssd_unavailable(path: str) -> str:
    return f"SSD indisponível: {path} não está acessível."


def folder_unavailable(path: str) -> str:
    return f"Pasta indisponível: {path}"


def cursor_missing(path: str) -> str:
    return f"Cursor não encontrado: {path}"


def symlink_skipped(path: str) -> str:
    return f"Link simbólico ignorado: {path}"


def no_permission(path: str) -> str:
    return f"Sem permissão para ler: {path}"


def cursor_failed(error: str) -> str:
    return f"Não foi possível iniciar o Cursor: {error}"


def partial_group(failed: int, total: int) -> str:
    return f"{failed} de {total} projetos não foram abertos"


def unreadable_file(name: str) -> str:
    return f"Arquivo de dados ilegível e preservado: {name}"
