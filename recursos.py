"""
Caminhos de recursos do aplicativo (bancos de perguntas, ícone, sons).

Módulo puro — sem tkinter, serial, pygame ou qualquer outra dependência de
interface. Sabe apenas onde está a "pasta da aplicação":

- rodando do código-fonte: a pasta do projeto (onde ficam os JSONs);
- rodando como executável (PyInstaller): a pasta do `.exe`, que é onde o
  usuário coloca os bancos de perguntas personalizados.

Sobre `sys._MEIPASS`: ele **não** é consultado. O `.spec` do projeto hoje usa
`datas=[]`, ou seja, nenhum arquivo é empacotado dentro do executável — logo
não existe nada para procurar na pasta temporária do PyInstaller. Quando os
JSONs (ou os sons) forem empacotados de verdade, `caminho_recurso` ganha uma
busca em `_MEIPASS` **somente para os recursos empacotados**, mantendo a pasta
do `.exe` como lugar dos arquivos do usuário.
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
