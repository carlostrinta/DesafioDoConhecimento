"""
Caminhos de recursos do aplicativo (bancos de perguntas, ícone, sons).

Módulo puro — sem tkinter, serial, pygame ou qualquer outra dependência de
interface. Sabe apenas onde está a "pasta da aplicação":

- rodando do código-fonte: a pasta do projeto (onde ficam os JSONs);
- rodando como executável (PyInstaller): a pasta do `.exe`, que é onde o
  usuário coloca os bancos de perguntas personalizados.

Sobre `sys._MEIPASS`: ele **não** é consultado. O `.spec` do projeto hoje usa
`datas=[]`, ou seja, nenhum arquivo é empacotado dentro do executável — logo
não existe nada para procurar na pasta temporária do PyInstaller. Os JSONs,
`config.json` e a pasta `sons/` são arquivos **do usuário**, sempre ao lado do
`.exe`; não devem entrar em `datas`. Se algum recurso interno for empacotado no
futuro, `caminho_recurso` pode ganhar uma busca em `_MEIPASS` **somente para
esse recurso**, mantendo a pasta do `.exe` como lugar dos arquivos externos.
"""

from __future__ import annotations

import os
import sys


def obter_diretorio_base() -> str:
    """Pasta onde ficam os recursos do jogo."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def caminho_recurso(nome: str) -> str:
    """Caminho absoluto de um recurso dentro da pasta da aplicação."""
    return os.path.join(obter_diretorio_base(), nome)
