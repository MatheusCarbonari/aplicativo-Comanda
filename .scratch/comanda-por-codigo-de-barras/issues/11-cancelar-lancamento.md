# 11: Cancelar integralmente um Lançamento

**What to build:** permitir que qualquer Garçom invalide integralmente um Lançamento de Atendimento aberto, informando um motivo obrigatório e preservando todo o histórico da ação.

**Blocked by:** 08 — Registrar lançamentos adicionais e calcular o total; 09 — Criar idempotência reutilizável para operações mutáveis.

**Status:** ready-for-agent

- [ ] O cancelamento aceita os motivos aprovados e exige descrição quando o motivo é “outro”.
- [ ] Qualquer Usuário operacional `GARCOM` pode cancelar um Lançamento, mesmo quando outro Garçom o registrou.
- [ ] Usuário `CAIXA`, Atendimento encerrado, Lançamento inexistente ou já cancelado são rejeitados sem alterar dados.
- [ ] O Lançamento original permanece imutável e o cancelamento registra responsável e instante UTC do backend.
- [ ] Não existe cancelamento parcial de quantidade; a correção exige um novo Lançamento.
- [ ] A operação reutiliza o mecanismo geral de idempotência do ticket 09.
- [ ] Testes cobrem motivos, autorização, autoria cruzada, imutabilidade, idempotência e rollback.

