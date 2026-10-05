# 17: Rejeitar Fechamento com revisão desatualizada

**What to build:** impedir que o Caixa confirme um total antigo quando o Atendimento mudou depois da apresentação do resumo.

**Blocked by:** 16 — Fechar um Atendimento confirmado.

**Status:** ready-for-agent

- [ ] O resumo usado na confirmação contém uma revisão verificável do Atendimento.
- [ ] Qualquer mudança relevante no conteúdo invalida a revisão anteriormente apresentada.
- [ ] Confirmar com revisão antiga não encerra o Atendimento.
- [ ] A resposta apresenta ou permite carregar imediatamente o resumo atualizado e exige nova confirmação.
- [ ] Repetir a confirmação com a revisão atual encerra o Atendimento uma única vez.
- [ ] Testes de integração cobrem Lançamento e cancelamento ocorridos entre visualização e confirmação.

