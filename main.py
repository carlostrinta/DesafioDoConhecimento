"""
Ponto de entrada do Duelo de Conhecimento.

Aqui fica só a montagem: logging, janela raiz, aplicação e loop do Tk. A lógica
(`jogo.py`), a interface (`desafio.py`, `ui_componentes.py`, `ui_selecao.py`),
a serial e o áudio vivem nos módulos próprios.

`--debug` mostra o log detalhado também no console; sem ele, o log vai apenas
para `logs/desafio.log` (veja `logging_conf.py`).

`DESAFIO_AUTO_FECHAR=1` agenda `fechar()` após 1 s; é o gancho usado pelo
teste de regressão que executa este arquivo como subprocesso.
"""

import argparse
import logging
import os
import tkinter as tk

import logging_conf


def iniciar(app_cls=None, debug=False):
    """Configura o log, monta a raiz, instancia a aplicação e roda o loop."""
    logger = logging_conf.configurar(debug=debug)
    logging_conf.instalar_excepthook()
    logger.info("Iniciando aplicação (debug=%s)", debug)

    # Import tardio: o config.json só é lido depois de o log estar pronto.
    if app_cls is None:
        from desafio import DueloDeConhecimento

        app_cls = DueloDeConhecimento

    root = tk.Tk()
    root.report_callback_exception = (
        lambda *exc_info: logging_conf.tratar_excecao_tk(*exc_info, parent=root)
    )

    app = app_cls(root)
    if os.environ.get("DESAFIO_AUTO_FECHAR"):
        root.after(1000, app.fechar)

    try:
        root.mainloop()
    finally:
        logger.info("Encerrando aplicação")
        logging.shutdown()

    return app


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Desafio do Conhecimento",
        epilog="Sem --debug, o log vai apenas para logs/desafio.log.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="mostra o log detalhado (DEBUG) também no console",
    )
    args = parser.parse_args(argv)

    return iniciar(debug=args.debug)


if __name__ == "__main__":
    main()
