# Licenças dos sons

Preencha uma linha para **cada arquivo de áudio** colocado nesta pasta. O
projeto não inclui áudio por padrão; esta tabela existe para manter a
distribuição do `.exe` legal e rastreável.

| Arquivo | Evento | Autor | Fonte (URL) | Licença | Data | Observações |
| --- | --- | --- | --- | --- | --- | --- |
| _exemplo:_ `nova_pergunta.ogg` | nova pergunta | _Nome_ | _https://..._ | CC0 1.0 | 2026-10-28 | Convertido para mono/OGG. |

## Regras rápidas

- Use apenas arquivos com licença que permita redistribuição e uso comercial,
  salvo decisão explícita em contrário do responsável pelo evento.
- CC0 é a opção mais simples: não exige atribuição, mas manter a fonte ajuda a
  auditar o pacote.
- Licenças com atribuição (CC BY, por exemplo) exigem crédito visível na
  documentação ou nos créditos do aplicativo.
- Não use áudio de marca, jogo comercial, filme ou vídeo sem autorização.
- Se um arquivo for substituído, registre a troca em vez de apagar a linha
  antiga.
- O fallback sintetizado do código é gerado pelo próprio projeto e não precisa
  desta tabela.

## Checklist antes de distribuir

- [ ] Todos os arquivos de `sons/` aparecem na tabela.
- [ ] A licença permite redistribuir junto com o `.exe`.
- [ ] Atribuições obrigatórias estão no README/créditos.
- [ ] Os nomes batem com `sons/README.md` e `audio.ARQUIVOS_SOM`.
- [ ] Arquivos de botão têm menos de 1 segundo.
- [ ] WAV/OGG abrem sem erro no teste do aplicativo.
