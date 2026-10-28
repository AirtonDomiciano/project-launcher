# MOAH Project Launcher

App desktop local para achar projetos no SSD e abri-los no Cursor. Não há login, servidor ou serviço externo.

A interface usa **Python 3 e PyQt6**, que já vêm no Debian 13 (`python3-pyqt6`). O catálogo, a descoberta, a persistência XDG e a execução do Cursor ficam em Python puro, sem Qt. A janela só chama essas ações. Uma integração futura com o MOAH pode reutilizar `listProjects`, `searchProjects`, `openProject` e `openGroup`.

O Cursor é iniciado com a lista `["/usr/bin/cursor", "-n", caminho]`, sem shell.

## Executar

```bash
python3 -m moah_launcher
```

Na primeira execução, se `/media/projetos` estiver acessível, as pastas existentes entre Aluai, IMEX, Agents, Aulas, MOAH e Projetos são gravadas como origem. Nenhuma outra pasta da raiz é varrida até ser adicionada em **Pastas**.

Atalhos: setas movem a seleção, Enter ou clique abre, estrela ou Ctrl+D favorita, Ctrl+F volta para a busca.

## Testes

```bash
make test
```

Os testes cobrem descoberta, persistência, argumentos passados ao Cursor e a janela numa plataforma Qt offscreen. Eles não abrem o Cursor de verdade.

## Pacote Debian

```bash
make deb
sudo apt install ./dist/moah-project-launcher_0.1.0_all.deb
```

O pacote depende de `python3` e `python3-pyqt6`. Os dados do app ficam fora das pastas dos projetos:

- configuração: `$XDG_CONFIG_HOME/moah-project-launcher/settings.json` (ou `~/.config/moah-project-launcher/`)
- catálogo, favoritos, recentes e grupos: `$XDG_DATA_HOME/moah-project-launcher/` (ou `~/.local/share/moah-project-launcher/`)

## Ações

```python
from moah_launcher.actions import LauncherActions

acoes = LauncherActions()
acoes.invoke("searchProjects", {"query": "aluai"})
acoes.invoke("openProject", {"projectId": "prj_..."})
acoes.invoke("openGroup", {"groupId": "grp_..."})
```

O id de um projeto é um hash do caminho absoluto, sem resolver links simbólicos. O id de um grupo é criado uma vez e permanece quando o grupo é renomeado.
