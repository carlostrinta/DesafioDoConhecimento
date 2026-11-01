# Roteiro da Release 2.10.0 — Editor de perguntas

> **Status:** tag anotada `v2.10.0-editor-ui` criada em `main` (commit do
> versionamento 2.10.0). **Sem push** até aprovação do Carlos.
>
> **Escopo desta release:** editor de perguntas acessível pela tela de seleção
> de tema, com persistência real, listagem de pastas candidatas e correções de
> usabilidade. O build do `.exe` e o teste em PC sem Python são as etapas
> pendentes — é o que este roteiro cobre.

---

## 1. Pré-requisitos do build

- Windows 10/11 x64.
- **Python 3.12.15** (versão de referência do projeto).
- Git com a tag `v2.10.0-editor-ui` (ou `main` no mesmo commit).
- Pasta de trabalho limpa: `git status --short` sem saída.
- Acesso à internet para instalar dependências (apenas no build).

```powershell
git checkout main
git status --short
python -c "import versao; print(versao.VERSAO)"   # deve imprimir 2.10.0
```

### Ambiente isolado

```powershell
py -3.12 -m venv .venv-build
.venv-build\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller
```

Anote as versões usadas no build (principalmente PyInstaller):

```powershell
python --version
pyinstaller --version
pip freeze > build-requirements.txt
```

### Testes antes do build

```powershell
python -m pytest -q
$env:DESAFIO_GOLDEN_UI="1"; python -m pytest -q; Remove-Item Env:\DESAFIO_GOLDEN_UI
```

Esperado: **722 passed, 1 skipped** sem golden e **723 passed** com golden.
Não seguir para o build se houver falha.

---

## 2. Build com PyInstaller

O `.spec` versionado já lê `versao.py` e `versao_info.txt`; não editar a versão
em dois lugares.

```powershell
pyinstaller --clean --noconfirm "Desafio do Conhecimento.spec"
```

Saída esperada:

```
dist\Desafio do Conhecimento.exe
```

### Conferir os metadados gravados no `.exe`

```powershell
(Get-Item "dist\Desafio do Conhecimento.exe").VersionInfo |
  Format-List FileVersion, ProductVersion, CompanyName, ProductName, LegalCopyright
```

Deve mostrar:

- `FileVersion` / `ProductVersion`: **2.10.0**
- `CompanyName`: **Carlos Santos**
- `ProductName`: **Desafio do Conhecimento**

### Conferir o hash

```powershell
Get-FileHash "dist\Desafio do Conhecimento.exe" -Algorithm SHA256
```

Guardar o SHA256 para publicar junto com o `.zip` e conferir depois da
extração.

### Observações do `.spec`

- `datas=[]`: **nada** é embutido no `.exe`. Bancos, `config.exemplo.json`,
  `sons/` e documentação precisam estar ao lado do executável.
- O ícone `desafio.ico` é embutido.
- Não usar `--onefile` fora do `.spec`; o layout de recursos depende da pasta
  da aplicação (`recursos.py`).

---

## 3. Conteúdo do `.zip`

Montar uma pasta de release com esta estrutura:

```
Desafio do Conhecimento 2.10.0\
  Desafio do Conhecimento.exe
  README.md
  LICENSE
  LICENCA_PERGUNTAS.md
  config.exemplo.json
  conhecimentos_gerais.json
  eletrotecnica.json
  radiologia.json
  sons\
    README.md
    LICENCAS.md
    (opcional: arquivos .ogg/.wav aprovados)
  docs\
    PLANO_EDITOR_PERGUNTAS.md
    ligacao_v2.svg
  ROTEIRO_SERIAL_HARDWARE.md        (opcional, para usuários de Arduino)
  firmware\                          (opcional, para usuários de Arduino)
```

### Obrigatórios

- `Desafio do Conhecimento.exe` (build desta tag).
- `README.md`, `LICENSE`, `LICENCA_PERGUNTAS.md`.
- `config.exemplo.json` — o usuário copia para `config.json` se quiser mudar
  algo.
- `conhecimentos_gerais.json`, `eletrotecnica.json`, `radiologia.json` — bancos
  distribuídos (abrem no editor em somente leitura).
- `sons/README.md` e `sons/LICENCAS.md` — mesmo sem áudio, mantêm a pasta e as
  licenças.
- `docs/PLANO_EDITOR_PERGUNTAS.md` — decisões nº 7 e nº 12 do editor.

### Opcionais

- `firmware/` e `ROTEIRO_SERIAL_HARDWARE.md` — só se a release for divulgada
  para quem usa Arduino.
- `docs/ligacao_v2.svg` — diagrama dos 10 botões.
- Arquivos de áudio aprovados em `sons/`.

### Nunca incluir

- `config.json` (configuração pessoal do Carlos).
- `logs/`, `estado_partida.json`, `estado_partida.invalida-*.json`.
- `.bak`, `.lock`, `.tmp`.
- `tests/`, `.pytest_cache/`, `.coverage`, `__pycache__/`, `.venv*/`.
- `build/`, `dist/` além do `.exe`, `.spec`, `requirements*.txt`,
  `versao_info.txt` (metadados de build, não de uso).

### Gerar o `.zip`

```powershell
New-Item -ItemType Directory -Force release | Out-Null
Compress-Archive -Path "release\Desafio do Conhecimento 2.10.0\*" `
  -DestinationPath "release\Desafio-do-Conhecimento-2.10.0-win64.zip" -Force
Get-FileHash "release\Desafio-do-Conhecimento-2.10.0-win64.zip" -Algorithm SHA256
```

Conferir o `.zip` em uma pasta vazia: extrair e rodar o `.exe` de lá.

---

## 4. Checklist em PC sem Python

Executar em um PC Windows 10/11 **sem Python instalado** e, de preferência,
sem Arduino conectado. Marcar cada item.

### Instalação e abertura

- [ ] Confirmar que `python` e `py` não existem no PATH (`where python` falha).
- [ ] Extrair o `.zip` em uma pasta gravável (ex.: `C:\Testes\Desafio`).
- [ ] Abrir `Desafio do Conhecimento.exe` com duplo clique.
- [ ] Não aparece console preto; a janela do jogo abre.
- [ ] `F1` (Sobre) mostra **2.10.0** e o autor Carlos Santos.
- [ ] Fechar e abrir de novo: a janela abre sem erro.

### Jogo básico (teclado)

- [ ] Primeira abertura pede o tema; a lista mostra os três bancos embutidos.
- [ ] Escolher um tema e jogar uma rodada completa com 2 equipes.
- [ ] Testar `A`/`B`, `R`, `1`/`2`, `N`; placar e tempos funcionam.
- [ ] Testar 3 e 4 equipes (se configurado) e `Ctrl+R` para reiniciar.
- [ ] `F11` alterna tela cheia; `Esc` sai da tela cheia.
- [ ] Som liga/desliga com `S`; sem `sons/`, o jogo abre sem travar.

### Editor — abrir pelo seletor

- [ ] `Ctrl+T` abre o seletor de tema.
- [ ] Durante o jogo, `F3` **não** abre o editor.
- [ ] No seletor, `E` edita o tema selecionado e `Ctrl+N` cria banco novo.
- [ ] Cada tema tem o botão **Editar**; o rodapé tem **Criar**.

### Editar banco do usuário

- [ ] Editar uma pergunta, alterar o texto e clicar **Salvar** (ou `Ctrl+S`).
- [ ] O título perde o `*`; nenhuma mensagem de erro aparece.
- [ ] Fechar o editor, reabrir o seletor e confirmar que o banco continua lá.
- [ ] Jogar e confirmar que o texto alterado aparece na pergunta.

### Criar banco novo

- [ ] Clicar **Criar**, informar nome e autor.
- [ ] Preencher a pergunta em branco, alternativas, correta e categoria.
- [ ] Salvar; confirmar o arquivo em
      `Documents\Desafio do Conhecimento\perguntas`.
- [ ] Reabrir o seletor: o banco novo aparece e pode ser jogado.

### Banco distribuído (somente leitura)

- [ ] Editar `conhecimentos_gerais.json`, `eletrotecnica.json` ou
      `radiologia.json`.
- [ ] O editor mostra cadeado e **Salvar como cópia** em destaque.
- [ ] Salvar como cópia; o arquivo novo aparece em `Documents\...\perguntas`.
- [ ] O banco distribuído original **não** foi alterado.
- [ ] O seletor lista original e cópia, indicando as pastas de origem.

### Conflito, exclusão e fechamento

- [ ] Criar/copiar com um nome que já existe: aparece confirmação.
- [ ] Cancelar a confirmação **não** sobrescreve o arquivo existente.
- [ ] Confirmar sobrescreve e cria `.bak` ao lado do arquivo.
- [ ] Excluir uma pergunta e salvar; reabrir e confirmar que ela sumiu.
- [ ] Excluir e fechar sem salvar: aparece Salvar/Descartar/Cancelar.
- [ ] Cancelar mantém o editor aberto e o arquivo intacto.

### Permissão e log

- [ ] Copiar a pasta da release para `C:\Program Files\Desafio` (ou marcar a
      pasta como somente leitura) e tentar salvar por cima.
- [ ] O erro de permissão aparece na tela e **não** derruba o jogo.
- [ ] Salvar como cópia funciona em `Documents\...\perguntas`.
- [ ] Abrir `logs\desafio.log` ao lado do `.exe` e confirmar o `WARNING`
      `desafio.editor_modelo` com o caminho e o motivo.
- [ ] Nenhum traceback inesperado no log após os testes acima.

### Dados do usuário e limpeza

- [ ] Fechar o jogo; confirmar que `config.json`, `logs/` e bancos do usuário
      ficam na pasta da aplicação/`Documents`, não dentro do `.zip`.
- [ ] Apagar a pasta de teste; os bancos em `Documents` permanecem (aviso ao
      usuário).
- [ ] Reextrair o `.zip` em outra pasta e abrir de novo: funciona sem Python.

### Hardware (opcional, só se for divulgar)

- [ ] Arduino Uno com firmware v2, 2 a 4 equipes e 10 botões.
- [ ] Mega 2560 com firmware v2.
- [ ] Clone CH340 com firmware v2 (e v1 em 2 equipes, se ainda suportado).
- [ ] Sem Arduino: o jogo cai para teclado sem travar.

### SmartScreen / antivírus

- [ ] Registrar se o Windows mostra aviso de SmartScreen (`.exe` sem
      assinatura). Se aparecer, documentar no release (“Mais informações →
      Executar assim mesmo”) ou assinar o binário em uma release futura.

---

## 5. Publicação (somente após o aceite)

1. Confirmar que o checklist acima foi concluído no PC sem Python.
2. Anexar o `.zip` e o SHA256 à release do GitHub `v2.10.0`.
3. Usar o texto da tag `v2.10.0-editor-ui` como base das notas, deixando claro
   o que foi validado no `.exe` e o que não foi.
4. Push (somente depois da autorização do Carlos):

```powershell
git push DesafioDoConhecimento main
git push DesafioDoConhecimento v2.10.0-editor-ui
```

5. Não refazer o build depois do push sem criar uma nova tag; o `.exe`
   publicado precisa corresponder ao commit e ao SHA256 divulgados.

---

## 6. Rollback

- Manter o `.zip` da versão anterior (2.8.1) disponível.
- Se o `.exe` 2.10.0 falhar no PC sem Python, não apagar a tag: publicar uma
  nota e preparar 2.10.1.
- Bancos do usuário ficam em `Documents\Desafio do Conhecimento\perguntas` e
  `%APPDATA%\DesafioDoConhecimento\perguntas`; o `.bak` de cada banco é a
  primeira cópia de segurança.
- Partidas salvas incompatíveis são renomeadas para
  `estado_partida.invalida-AAAA-MM-DD.json`, nunca apagadas.

---

## 7. Critérios de aceite da release

- [ ] Testes verdes em 3.12.15 e 3.15.1, com e sem golden.
- [ ] `.exe` 2.10.0 com metadados corretos e SHA256 registrado.
- [ ] Checklist da seção 4 concluído em PC sem Python.
- [ ] Editor abre só pelo seletor; criar/editar/excluir/copiar persistem e
      reaparecem no seletor.
- [ ] Bancos distribuídos continuam somente leitura.
- [ ] Erros de permissão/conflito/somente leitura aparecem na tela e no log.
- [ ] Nenhum dado pessoal (`config.json`, `logs/`, partidas) dentro do `.zip`.
