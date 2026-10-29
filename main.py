"""
Ponto de entrada do Duelo de Conhecimento.

Aqui fica só a montagem: logging, janela raiz, aplicação e loop do Tk. A lógica
(`jogo.py`), a interface (`desafio.py`, `ui_componentes.py`, `ui_selecao.py`),
a serial e o áudio vivem nos módulos próprios.

`--debug` mostra o log detalhado também no console; sem ele, o log vai apenas
para `logs/desafio.log` (veja `logging_conf.py`).

`DESAFIO_AUTO_FECHAR=1` agenda `fechar()` após 1 s; é o gancho usado pelo
teste de regressão que executa este arquivo como subprocesso. Com
`DESAFIO_AUTO_INICIAR=1`, o app pula o seletor de tema, inicia o banco padrão
e o fechamento espera a contagem de largada chegar em AGUARDANDO — assim o
smoke percorre o caminho real do overlay, não só a abertura da janela.
"""

import argparse
import logging
import os
import tkinter as tk

import logging_conf


def _fechar_apos_contagem(root, app):
    """
    Espera a primeira pergunta passar por CONTAGEM -> AGUARDANDO e fecha.

    Usado só no smoke (`DESAFIO_AUTO_INICIAR=1`). O limite de 15 s evita que
    uma falha na contagem deixe o subprocesso preso para sempre.
    """
    estado = {"iniciou": False, "tentativas": 0}

    def verificar():
        estado["tentativas"] += 1
        jogo = getattr(app, "jogo", None)
        pergunta = getattr(getattr(jogo, "estado", None), "pergunta_atual", None)
        if pergunta is not None:
            estado["iniciou"] = True

        if estado["iniciou"] and jogo is not None and not jogo.contagem_ativa:
            app._smoke_contagem_ok = True
            # Deixa o "JÁ!" aparecer e o job de 500 ms escondê-lo.
            root.after(700, app.fechar)
            return
        if estado["tentativas"] >= 150:
            app.fechar()
            return
        root.after(100, verificar)

    root.after(300, verificar)


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
    auto_iniciar = bool(
        os.environ.get("DESAFIO_AUTO_FECHAR")
        and os.environ.get("DESAFIO_AUTO_INICIAR")
    )
    if os.environ.get("DESAFIO_AUTO_FECHAR"):
        if auto_iniciar:
            _fechar_apos_contagem(root, app)
        else:
            root.after(1000, app.fechar)

    try:
        root.mainloop()
    finally:
        logger.info("Encerrando aplicação")
        logging.shutdown()

    if auto_iniciar and not getattr(app, "_smoke_contagem_ok", False):
        raise SystemExit(
            "Smoke da contagem de largada nao chegou em AGUARDANDO"
        )

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
