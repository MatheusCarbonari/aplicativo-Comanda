# 11: Cancelar integralmente um Lançamento

**What to build:** permitir que qualquer Garçom invalide integralmente um Lançamento de Atendimento aberto, informando um motivo obrigatório e preservando todo o histórico da ação.

**Blocked by:** 08 — Registrar lançamentos adicionais e calcular o total; 09 — Criar idempotência reutilizável para operações mutáveis.

**Status:** resolved

- [x] O cancelamento aceita os motivos aprovados e exige descrição quando o motivo é “outro”.
- [x] Qualquer Usuário operacional `GARCOM` pode cancelar um Lançamento, mesmo quando outro Garçom o registrou.
- [x] Usuário `CAIXA`, Atendimento encerrado, Lançamento inexistente ou já cancelado são rejeitados sem alterar dados.
- [x] O Lançamento original permanece imutável e o cancelamento registra responsável e instante UTC do backend.
- [x] Não existe cancelamento parcial de quantidade; a correção exige um novo Lançamento.
- [x] A operação reutiliza o mecanismo geral de idempotência do ticket 09.
- [x] Testes cobrem motivos, autorização, autoria cruzada, imutabilidade, idempotência e rollback.

## Answer

O cancelamento foi modelado como `CancelamentoLancamento`, ligado por
`OneToOneField` protegido ao Lançamento original. Assim, o registro de consumo não
é alterado nem apagado, e o banco garante no máximo um cancelamento com motivo,
descrição, autor e horário próprios. O caso de uso aceita somente Garçom e
Atendimento aberto, exige descrição para `OUTRO` e reutiliza a identidade
persistente `CANCELAR_LANCAMENTO` no mecanismo idempotente do ticket 09.

Os totais agora usam a consulta centralizada de Lançamentos válidos e ignoram os
cancelados, inclusive nos lançamentos adicionais e na interface. A disputa entre
cancelamentos distintos converge pela constraint de unicidade; somente a violação
exata da coluna do Lançamento é traduzida para “já cancelado”, enquanto outros
`IntegrityError` continuam propagando.

Contenção SQLite `BUSY`/`LOCKED` recebe no máximo duas tentativas da operação
idempotente completa. Cada falha reverte cancelamento e registro de idempotência
antes do retry; contenção persistente vira indisponibilidade temporária e HTTP 503.
Testes cobrem motivos, permissões, autoria cruzada, imutabilidade, total,
idempotência, rollback, constraint, concorrência com conexões separadas e ausência
de estado parcial.

