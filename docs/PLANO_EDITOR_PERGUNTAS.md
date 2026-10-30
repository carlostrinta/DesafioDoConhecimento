# Plano do editor de perguntas

> **Status:** documento de planejamento. Nenhum código do editor foi criado
> nesta etapa. Este arquivo existe para decidir escopo, formato e riscos antes
> da implementação.
>
> **Público:** Carlos (decisões de produto) e quem for implementar.
>
> **Premissa:** o jogo continua funcionando sem o editor. O editor é uma
> ferramenta interna/acessória, não um requisito para jogar.

---

## Contexto atual

- Os bancos são arquivos `.json` lidos por `perguntas.py`.
- Cada pergunta hoje é um objeto com `pergunta`, `alternativas`, `correta`,
  `categoria` e `explicacao`.
- O carregador já valida o banco inteiro e é a única fonte de verdade sobre o
  que é uma pergunta válida.
- A partida salva (`persistencia.py`) guarda um hash do banco em uso. Mudar o
  arquivo invalida a partida antiga.
- A interface é Tk/tkinter desenhada em Canvas, com layout pensado para
  1366×768 e telas maiores.
- Os bancos distribuídos são CC BY 4.0, autor Carlos Santos
  (`LICENCA_PERGUNTAS.md`).

O editor deve reaproveitar essas peças, não criar um segundo modelo de
pergunta nem um segundo validador.

---

## 1. Escopo da v1

### Incluído (recomendado)

| Recurso | Decisão |
| --- | --- |
| Criar pergunta | sim |
| Editar pergunta | sim |
| Excluir pergunta | sim, com confirmação e desfazer |
| Duplicar pergunta | sim, com sufixo “(cópia)” e sem copiar o ID |
| Criar banco novo | sim, a partir de um banco vazio ou de um modelo |
| Reordenar perguntas | sim, por botões e/ou `Alt+↑`/`Alt+↓` |
| Busca | sim, por texto da pergunta, alternativa, categoria e explicação |
| Filtro por categoria | sim, combo com “Todas” + categorias do banco |
| Validação em tempo real | sim, por campo, ao sair do campo e ao salvar |
| Importar/exportar CSV | **opcional na v1**, ver abaixo |
| Metadados do banco | ler e preservar; editar em tela “Propriedades” |
| Undo/redo | sim, dentro da sessão do editor |
| Salvamento seguro | sim, obrigatório (ver seção 5) |

### Fora do escopo da v1

- Editor de imagens/áudio ou anexos.
- Sincronização em nuvem, multiusuário ou edição concorrente.
- Versionamento histórico completo (além do `.bak`).
- Geração automática de perguntas por IA.
- Tradução automática.
- Edição de bancos durante uma rodada em andamento (ver seção 2).
- Importação de DOCX/PDF/planilhas além de CSV.

### CSV: recomendação

**Recomendação:** deixar CSV para a etapa de polimento ou para a v1.1, não
para o núcleo da v1.

Motivos:

- CSV é ótimo para revisão em Excel/LibreOffice e para receber lotes de
  terceiros, mas é frágil com vírgulas, aspas, acentos e alternativas com
  quebra de linha.
- O JSON já é o formato canônico e o validador é o mesmo. CSV adiciona um
  segundo caminho de entrada com regras próprias.
- Se entrar, deve ser **importação para o modelo** (nunca edição direta do
  CSV) e **exportação a partir do modelo**, com relatório de erros por linha.

Se Carlos quiser CSV na v1, o contrato mínimo é:

- UTF-8 com BOM na exportação (`utf-8-sig`) para abrir bem no Excel;
- cabeçalho obrigatório: `pergunta,alternativa_1,alternativa_2,alternativa_3,
  alternativa_4,correta,categoria,explicacao`;
- `correta` como número 1–4 (ou 0–3, decidir e documentar);
- aspas duplas, vírgulas e quebras de linha escapadas pelo módulo `csv`;
- importação **tudo ou nada**: se qualquer linha falhar, não grava nada e
  mostra “linha X, campo Y: motivo”;
- duplicatas detectadas após normalização, com opção de ignorar ou importar.

**Alternativa descartada:** editar CSV como se fosse o banco. Isso quebraria
a validação única e a gravação atômica.

---

## 2. Onde o editor vive

### Recomendação: tela dentro do aplicativo, atalho `F3`

- Um único processo, um único tema visual, um único caminho de configuração.
- O editor compartilha o banco carregado, o validador e a pasta de perguntas.
- `F3` abre/fecha o editor; `Esc` fecha sem salvar (com aviso se houver
  alterações).
- A tela é modal em relação ao jogo: enquanto o editor está aberto, a partida
  não avança e os atalhos de jogo são suspensos.
- Ao fechar o editor, o jogo recarrega o banco se o arquivo mudou.

### Alternativa: janela separada

Prós: isolamento de foco, possibilidade de editar enquanto o jogo roda em
outra tela. Contras: duas instâncias mexendo no mesmo arquivo, sincronização
de tema/configuração, risco de editar o banco em uso no meio de uma rodada.
**Não recomendado para a v1.** Se um dia houver janela separada, ela deve ser
um segundo processo com trava de arquivo e sem acesso ao estado da partida.

### Comportamento durante a partida

**Recomendação:** bloquear a abertura do editor quando houver rodada em
andamento.

- “Rodada em andamento” = fase diferente de `AGUARDANDO` **ou** pergunta
  carregada com tempo correndo **ou** partida salva sendo retomada.
- Se o operador tentar `F3`, mostrar: “Termine ou reinicie a rodada antes de
  editar as perguntas.”
- Partida apenas aberta, sem rodada ativa: permitir editar **outro** banco;
  editar o banco em uso exige confirmação e invalida a partida salva (seção 6).
- Nunca salvar por baixo do banco que a partida está usando sem aviso.

**Alternativa:** permitir edição e recarregar o banco no fim da rodada. É mais
fluido, mas cria a pergunta “o que acontece se a pergunta atual for excluída?”
e aumenta muito o risco. Deixar para uma versão futura, se houver demanda.

---

## 3. Formato do banco

### Formato atual (compatibilidade obrigatória)

```json
[
  {
    "pergunta": "Qual é a capital do Brasil?",
    "alternativas": ["Brasília", "Rio de Janeiro", "São Paulo"],
    "correta": 0,
    "categoria": "Geografia",
    "explicacao": "Brasília foi inaugurada em 1960."
  }
]
```

O leitor atual aceita uma **lista** de objetos. Qualquer mudança precisa
continuar lendo essa forma sem migração manual.

### Recomendação: aceitar lista e envelope, salvar envelope novo

Ler duas formas:

1. **Legado:** lista de perguntas (formato atual).
2. **Novo:** objeto com metadados e a lista:

```json
{
  "versao_formato": 1,
  "tema": "Conhecimentos gerais",
  "autor": "Carlos Santos",
  "licenca": "CC BY 4.0",
  "perguntas": [
    {
      "pergunta": "Qual é a capital do Brasil?",
      "alternativas": ["Brasília", "Rio de Janeiro", "São Paulo"],
      "correta": 0,
      "categoria": "Geografia",
      "explicacao": "Brasília foi inaugurada em 1960."
    }
  ]
}
```

Regras:

- `versao_formato` é inteiro; ausência = formato legado (lista).
- `perguntas` é obrigatório no envelope; lista vazia é permitida para banco
  novo.
- `tema`, `autor` e `licenca` são **opcionais**. O editor mostra, mas não
  exige, na v1.
- Campos desconhecidos do envelope e das perguntas são **preservados** ao
  salvar (para não destruir extensões futuras).
- `id` de pergunta é opcional e interno do editor; se ausente, o editor gera
  um na memória, mas **não precisa gravar** na v1. Gravar IDs facilita
  duplicar/reordenar; se gravar, usar string curta e não reutilizar após
  exclusão.
- A ordem da lista é a ordem do baralho. Reordenar muda o JSON.

### Migração

1. Abrir lista legada -> normalizar em memória para `Banco(perguntas,
   metadados)`.
2. Salvar só quando o usuário mandar; nesse momento gravar o envelope novo
   com `versao_formato: 1`.
3. Antes de sobrescrever, criar `.bak` (seção 5).
4. O leitor antigo do jogo precisa passar a aceitar o envelope **antes** de o
   editor gravar o primeiro banco novo. Essa é uma dependência de ordem:
   primeiro adaptar `perguntas.py` para ler as duas formas, depois liberar o
   editor.
5. Bancos existentes continuam válidos e não são reescritos em massa.

**Alternativa descartada:** manter sempre a lista e usar um arquivo lateral
(`banco.meta.json`). Evita migração, mas duplica o estado e complica copiar o
banco para outra máquina.

**Alternativa descartada:** exigir `versao_formato` já na v1. Quebraria todos
os bancos atuais.

---

## 4. Validador único e mensagens

### Regra de ouro

**Não criar um segundo validador.** O editor chama o mesmo código que o
carregador usa. O ideal é extrair de `perguntas.py` uma função pura:

```python
def validar_pergunta(dados: dict, indice: int | None = None) -> list[ErroCampo]:
    ...
```

com `ErroCampo(campo, mensagem, severidade)` e uma versão de banco:

```python
def validar_banco(perguntas: list[dict], metadados: dict | None = None) -> list[ErroCampo]:
    ...
```

O carregador e o editor chamam `validar_banco`; a UI só apresenta o resultado.
Se hoje o carregador levanta exceção na primeira falha, ele passa a acumular
erros por campo (ou mantém a exceção e o editor usa a função que acumula).

### Mensagens em português, por campo

Exemplos de contrato (não copiar texto sem revisar):

| Campo | Situação | Mensagem |
| --- | --- | --- |
| `pergunta` | vazio | “Escreva o enunciado da pergunta.” |
| `pergunta` | curto demais | “O enunciado precisa ter pelo menos 5 caracteres.” |
| `pergunta` | longo demais | “O enunciado passa do limite de 500 caracteres.” |
| `alternativas` | menos de 2 | “Informe pelo menos 2 alternativas.” |
| `alternativas` | mais de 4 | “Informe no máximo 4 alternativas.” |
| `alternativas[i]` | vazio | “A alternativa {i+1} está vazia.” |
| `alternativas` | repetida | “As alternativas {i+1} e {j+1} são iguais.” |
| `correta` | fora da faixa | “Marque uma alternativa correta válida.” |
| `correta` | ausente | “Marque qual alternativa é a correta.” |
| `categoria` | vazia | “Informe a categoria.” |
| `explicacao` | longa demais | “A explicação passa do limite de 1.000 caracteres.” |
| banco | duplicata | “A pergunta {i+1} repete a pergunta {j+1}.” |
| banco | vazio | “O banco precisa ter pelo menos 1 pergunta.” |

### Limites recomendados

| Item | Limite | Justificativa |
| --- | ---: | --- |
| enunciado | 5–500 caracteres | cabe na tela sem rolagem excessiva |
| cada alternativa | 1–300 caracteres | legível no placar e no botão |
| explicação | 0–1.000 caracteres | espaço para contexto sem virar texto livre |
| categoria | 1–80 caracteres | filtro e agrupamento |
| alternativas | 2–4 | regra atual do jogo |
| `correta` | inteiro `0..len(alternativas)-1` | formato atual |
| perguntas por banco | mínimo 1; máximo prático 5.000 | acima disso a UI precisa de virtualização |

Normalização para comparar duplicatas: `strip`, colapsar espaços, comparar
sem diferenciar maiúsculas/minúsculas e sem acentos (opcional; decidir com
Carlos). A duplicata **não** deve ser bloqueada silenciosamente: mostrar
aviso e deixar o usuário decidir.

### O que o editor não deve fazer

- Corrigir automaticamente o índice `correta` quando uma alternativa é
  removida. Melhor invalidar e pedir confirmação.
- Remover espaços internos ou reescrever o texto do usuário.
- Aceitar HTML ou markdown sem uma decisão explícita de renderização.

---

## 5. Salvamento seguro

### Gravação atômica

1. Serializar o banco em memória para JSON UTF-8.
2. Gravar em `banco.json.tmp` na **mesma pasta** do destino.
3. `flush()` + `os.fsync()` (quando disponível).
4. Se o destino existe, copiar/renomear o original para `banco.json.bak`
   **antes** do `os.replace`.
5. `os.replace(tmp, destino)` — no Windows, substitui de forma atômica na
   mesma unidade.
6. Em caso de erro, apagar o `.tmp` e manter o original intacto.

Nunca escrever direto no arquivo aberto pelo jogo. Nunca usar
`open(destino, "w")` sem o passo temporário.

### Backup

- `.bak` único, sobrescrito a cada salvamento (simples e previsível).
- Opcional: `.bak.1`, `.bak.2` se Carlos quiser histórico. Na v1, um `.bak`
  basta.
- Se o `.bak` não puder ser criado, **abortar** o salvamento e avisar. Não
  sobrescrever sem rede de segurança.

### Codificação e conteúdo

- UTF-8 sem BOM no JSON (`encoding="utf-8"`, `ensure_ascii=False`).
- `indent=2`, quebra de linha `\n`, chave final com newline.
- Preservar a ordem das chaves conhecidas e dos campos desconhecidos.
- Não gravar `NaN`/`Infinity` (não há números livres no formato).

### Pasta sem permissão

Cenários: `.exe` em `C:\Program Files`, pasta somente leitura, pendrive
protegido.

**Recomendação:** tentar salvar; se `PermissionError`/`OSError`, oferecer
“Salvar como…” em uma pasta gravável:

1. pasta do usuário (`Documents\Desafio do Conhecimento\perguntas`) ou
2. pasta configurada em `perguntas.pasta`, se gravável, ou
3. `%APPDATA%\DesafioDoConhecimento\perguntas`.

Mostrar o caminho escolhido e lembrar que o jogo precisa apontar para ele.
Nunca “resolver” gravando em `C:\Temp` silenciosamente.

### Arquivo aberto em outra instância

**Recomendação:** trava advisory no arquivo de destino (ou em
`banco.json.lock`), mantida enquanto o editor estiver com o banco aberto.

- No Windows, `msvcrt.locking` ou abrir com `O_EXCL` para o `.lock`; no
  POSIX, `fcntl.flock`.
- Se a trava falhar, abrir em **somente leitura** e avisar: “Este banco está
  aberto em outra instância. Feche o outro editor ou use ‘Salvar como’.”
- Trava obsoleta (processo morto): permitir remoção manual explícita
  (“Remover trava”) em vez de apagar automaticamente.
- A trava não substitui a gravação atômica: as duas proteções são
  complementares.

**Alternativa:** detectar por data de modificação antes de gravar e pedir
confirmação. É mais simples, mas tem corrida entre a checagem e a escrita.
Usar como segunda linha de defesa, não como única.

---

## 6. Interação com a persistência da partida

O hash do banco em uso é parte do contrato de retomada. Editar o banco muda o
hash.

### Cenários e decisões

| Cenário | Recomendação |
| --- | --- |
| Nenhuma partida salva | salvar normalmente |
| Partida salva de **outro** banco | salvar normalmente; não mexer na partida |
| Partida salva do **mesmo** banco, sem rodada ativa | avisar: “A partida salva será invalidada.”; salvar só após confirmação |
| Rodada em andamento | bloquear a edição (seção 2) |
| Usuário cancela o aviso | não salvar; manter alterações em memória |
| Usuário confirma | salvar; apagar/invalidar a partida salva de forma explícita |

### O que “invalidar” significa

Recomendação: **não apagar o arquivo de partida silenciosamente**. Marcar como
incompatível e, na próxima abertura, mostrar “A partida salva foi feita com
uma versão anterior do banco e não pode ser retomada.” Oferecer:

- “Começar nova partida” (padrão); ou
- “Guardar cópia” (renomear para `estado_partida.invalida-AAAA-MM-DD.json`).

Isso evita perda de dados e deixa claro por que a retomada não aparece. O
hashes já existentes em `persistencia.py` devem ser reutilizados; não criar
um segundo algoritmo.

### Ordem de implementação

1. Adaptar o leitor para o envelope (seção 3).
2. Fazer o editor calcular o mesmo hash do jogo.
3. Só então ligar o botão “Salvar” na UI.

Se o editor salvar antes de o jogo saber ler o novo formato, a próxima
abertura falha. Esse é o maior risco de integração da etapa.

---

## 7. UI e interação

### Layout recomendado

```
┌──────────────────────────────────────────────────────────────┐
│ Editor de perguntas — banco.json            [Salvar] [Fechar]│
├───────────────────────────┬──────────────────────────────────┤
│ Busca: [___________]      │  Pergunta                        │
│ Categoria: [Todas ▼]      │  [______________________________]│
│                           │                                  │
│ ┌───────────────────────┐ │  Alternativas                    │
│ │ 1. Capital do Brasil? │ │  ( ) [________________________]  │
│ │ 2. Maior planeta?     │ │  ( ) [________________________]  │
│ │ 3. ...                │ │  ( ) [________________________]  │
│ └───────────────────────┘ │  ( ) [________________________]  │
│ [Nova] [Duplicar] [Excluir]│                                  │
│ [↑] [↓]                   │  Categoria: [__________]         │
│                           │  Explicação: [________________]  │
│                           │  [________________________________]│
│                           │  ⚠ mensagem do validador         │
└───────────────────────────┴──────────────────────────────────┘
```

- Lista à esquerda (40%), formulário à direita (60%).
- Rodapé/coluna de status com contagem: “12 perguntas · 3 categorias”.
- Mensagens de erro **ao lado do campo**, em vermelho, e um resumo no rodapé.
- Botão “Salvar” desabilitado enquanto houver erro bloqueante.
- Indicador de alterações não salvas no título: `banco.json *`.

### Navegação por teclado

| Atalho | Ação |
| --- | --- |
| `F3` | abre/fecha o editor |
| `Ctrl+N` | nova pergunta |
| `Ctrl+D` | duplicar selecionada |
| `Delete` | excluir selecionada (com confirmação) |
| `Ctrl+S` | salvar |
| `Ctrl+Z` / `Ctrl+Y` | desfazer / refazer |
| `Ctrl+F` | foco na busca |
| `Alt+↑` / `Alt+↓` | mover pergunta na lista |
| `Tab` / `Shift+Tab` | próximo/anterior campo |
| `Esc` | cancelar edição do campo ou fechar (com aviso) |

A lista deve funcionar com setas, `Home`/`End`, `PageUp`/`PageDown` e
`Enter` para editar. Evitar depender de mouse.

### Tamanhos de tela

- **1366×768:** layout de duas colunas; formulário com rolagem vertical;
  botões em uma linha; fonte mínima 11 px.
- **1920×1080:** mesmas proporções, mais espaço para a lista e a explicação.
- **Janela pequena (ex.: 1024×600):** colapsar para uma coluna (lista em cima,
  formulário embaixo) ou permitir rolagem; nunca cortar o botão Salvar.
- Testar com escala de UI do Windows em 100%, 125% e 150%.

### Desfazer/refazer

- Pilha de comandos com limite (ex.: 100 operações), por sessão de edição.
- Operações: criar, editar campo, excluir, duplicar, reordenar, alterar
  metadados.
- Salvar **não** limpa a pilha; apenas marca o ponto “salvo”.
- Fechar com alterações não salvas: “Salvar”, “Descartar”, “Cancelar”.

### Alterações não salvas

- Aviso ao fechar o editor, trocar de banco, abrir outro tema ou sair do app.
- Se o usuário descartar, restaurar o estado do último salvamento (não
  recarregar do disco sem perguntar).
- Nunca fechar a janela principal com o editor sujo sem confirmação.

---

## 8. Testes

### Lógica pura, sem tkinter

Separar em módulos testáveis:

- `editor_modelo.py` (ou equivalente): banco em memória, CRUD, reordenação,
  busca/filtro, undo/redo, normalização, hash.
- Reutilizar `perguntas.validar_banco`.
- `editor_persistencia.py`: leitura das duas formas, serialização, gravação
  atômica, `.bak`, trava, permissão.

Testes headless (rodam em qualquer CI):

- criar/editar/excluir/duplicar/reordenar;
- busca e filtro por categoria;
- validação por campo com mensagens em português;
- duplicatas normalizadas;
- leitura de lista legada e de envelope;
- round-trip JSON (salvar e reler = mesmo modelo);
- campos desconhecidos preservados;
- gravação atômica: simular falha no meio e garantir original intacto;
- `.bak` criado antes de sobrescrever;
- pasta sem permissão (mock de `PermissionError`) -> “Salvar como…”;
- trava de outra instância (mock) -> somente leitura;
- hash muda ao editar e invalida a partida salva;
- CSV (se aprovado): escaping, BOM, erro por linha, tudo ou nada.

### Testes Tk reais

- Abrir `F3`, criar pergunta, salvar e reabrir.
- Navegação por teclado e foco.
- Layout em 1366×768 e 1920×1080 (medidas, não golden de pixels).
- Aviso de alterações não salvas.
- Bloqueio durante rodada.
- Em ambiente headless, `pytest.skip` com mensagem clara.

### Golden

- Usar golden **somente para casos novos** do editor (ex.: estado vazio,
  formulário com erro, lista filtrada).
- Não regravar goldens existentes do jogo por causa do editor.
- Golden opt-in, como já é feito (`DESAFIO_GOLDEN_UI=1`).

### Cobertura

- Medir `perguntas.py` e os novos módulos do editor.
- Não deixar a cobertura de `protocolo.py`/`jogo.py` cair por causa de
  refatorações laterais.
- Meta sugerida: 90%+ nos módulos puros do editor; UI Tk coberta por smoke.

---

## 9. Licença dos bancos criados no editor

- **Padrão recomendado:** CC BY 4.0, com campo `autor` preenchido.
- O editor deve mostrar um aviso curto: “Ao salvar, você declara que tem
  direito sobre estas perguntas e as licencia em CC BY 4.0, salvo indicação
  em contrário.”
- `autor` é opcional tecnicamente, mas o editor pede na primeira gravação de
  um banco novo. Sem autor, gravar `"autor": ""` e avisar.
- `licenca` é texto livre; o padrão é `"CC BY 4.0"`. Se o usuário escolher
  outra, o editor não deve fingir que é CC BY.
- Bancos existentes mantêm a licença que já têm; o editor não reescreve
  `licenca` sem ação do usuário.
- `LICENCA_PERGUNTAS.md` deve ser atualizado para dizer que vale também para
  bancos criados/exportados pelo editor, com o autor indicado no arquivo.
- Exportação CSV (se houver) não carrega metadados de licença; incluir um
  cabeçalho/rodapé ou um arquivo `LEIA-ME` ao lado.

**Alternativa:** exigir autor e licença para salvar. Mais burocrático; pode
atrapalhar uso pessoal. Recomendação: exigir autor só em banco novo e avisar
sobre a licença, sem bloquear.

---

## 10. Fatiamento em etapas pequenas

Cada etapa deve terminar com testes verdes e um commit próprio. A ordem
respeita as dependências (modelo -> persistência -> UI -> integração).

### Etapa E1 — Modelo e validação (sem UI)

- `Banco` em memória, CRUD, duplicar, reordenar, busca/filtro.
- Leitura da lista legada e do envelope.
- Reuso de `perguntas.validar_banco`; mensagens por campo.
- **Aceite:** testes headless cobrindo todas as operações; nenhum import de
  tkinter; `perguntas.py` continua aceitando os bancos atuais.
- **Risco:** baixo. O maior cuidado é não alterar o comportamento do leitor.

### Etapa E2 — Salvamento seguro

- Serialização UTF-8, `.tmp` + `os.replace`, `.bak`, tratamento de permissão,
  trava advisory.
- **Aceite:** testes de falha simulada, backup, pasta sem permissão e trava;
  round-trip; original intacto em erro.
- **Risco:** médio (perda de dados). Fazer revisão dedicada e testar em
  Windows real.

### Etapa E3 — UI de lista

- Tela `F3`, lista, busca, filtro, seleção, reordenar, contagem.
- **Aceite:** smoke Tk em 1366×768; navegação por teclado; busca/filtro;
  estado vazio; nenhuma edição ainda.
- **Risco:** baixo/médio (layout e foco).

### Etapa E4 — UI de edição

- Formulário, validação em tempo real, alternativas dinâmicas, explicação,
  undo/redo, alterações não salvas.
- **Aceite:** criar/editar/excluir/duplicar pela UI; erros por campo; golden
  novo do formulário; `Esc`/fechar com aviso.
- **Risco:** médio (complexidade de estado e foco).

### Etapa E5 — Integração com o jogo

- Abrir pelo `F3`, bloquear durante rodada, recarregar banco ao fechar,
  invalidar partida salva com aviso, criar banco novo na pasta configurada.
- **Aceite:** partida em andamento bloqueia; hash muda; aviso de invalidação;
  fluxo completo salvar -> jogar -> retomar.
- **Risco:** alto (persistência e hash). Fazer por último, com testes de
  integração e validação manual.

### Etapa E6 — Polimento

- CSV (se aprovado), atalhos finais, acessibilidade, mensagens, documentação,
  empacotamento no `.exe` (se o editor for distribuído).
- **Aceite:** revisão de textos, teste em 125%/150% de escala, manual do
  usuário, nenhuma regressão nos goldens antigos.
- **Risco:** baixo, mas com tendência a crescer; manter o escopo.

### Ordem se Carlos quiser CSV antes

CSV entra como E2.5, **depois** do modelo e antes da UI de edição. Se entrar
depois da UI, vira um segundo caminho de dados e aumenta o retrabalho.

---

## Perguntas abertas para o Carlos

1. O editor deve poder editar os **bancos distribuídos** (`conhecimentos_gerais`,
   `eletrotecnica`, `radiologia`) ou só cópias do usuário? Se puder, a pasta do
   `.exe` protegida vira o caso comum.
2. Onde os bancos novos devem ser salvos por padrão: pasta do jogo, pasta
   configurada em `perguntas.pasta`, `Documents` ou `%APPDATA%`?
3. `versao_formato`, `autor`, `licenca` e `tema` devem ser **obrigatórios** em
   algum momento ou ficam opcionais para sempre?
4. CSV entra na v1 ou fica para depois? Se entra, `correta` é 1–4 ou 0–3?
5. Quais são os limites reais de texto que você aceita (enunciado,
   alternativas, explicação, categoria)? Os valores sugeridos servem?
6. Duplicatas devem ser **bloqueadas** ou apenas avisadas?
7. O editor pode abrir com uma partida apenas **aberta** (sem rodada) para
   editar outro banco? E para editar o banco em uso, basta confirmar?
8. Ao invalidar a partida salva, o padrão é **apagar**, **renomear** ou
   **manter e ignorar**?
9. O editor precisa de **ID** persistente por pergunta? Isso ajuda duplicar e
   reordenar, mas muda o JSON.
10. Undo/redo deve sobreviver ao salvamento ou ser só da sessão?
11. O editor deve ter **autosave**? Recomendação: não na v1; só aviso de
    alterações não salvas.
12. O editor precisa rodar no **.exe** distribuído ou pode ser uma ferramenta
    separada (`python editor.py`) para uso interno?
13. A licença dos bancos criados no editor é sempre CC BY 4.0 ou o usuário
    pode escolher outra? O campo `autor` é obrigatório?
14. Haverá edição em **rede/pasta compartilhada**? Se sim, a trava advisory
    precisa de um teste específico e talvez de um bloqueio mais forte.
15. O layout deve seguir o tema escuro atual ou ter tema claro para impressão?

---

## Critérios de aceite do plano

- [ ] Carlos confirmou o escopo da v1 e o que fica fora.
- [ ] Formato do banco decidido (lista + envelope) e leitor adaptado antes do
      editor.
- [ ] Validador único definido, com mensagens e limites aprovados.
- [ ] Política de salvamento (atômico, `.bak`, trava e permissão) aprovada.
- [ ] Comportamento durante partida e invalidação da partida salva aprovados.
- [ ] Layout e atalhos validados em 1366×768 e 1920×1080.
- [ ] Etapas E1–E6 com critérios de aceite e riscos revisados.
- [ ] Perguntas abertas acima respondidas ou explicitamente adiadas.
