# 16: Fechar um Atendimento confirmado

**What to build:** permitir que o Caixa confira o resumo atual e confirme de forma explícita e irreversível o Fechamento de um Atendimento aberto.

**Blocked by:** 09 — Criar idempotência reutilizável para operações mutáveis; 13 — Consultar a Comanda como Caixa.

**Status:** resolved

- [x] Somente Usuário operacional `CAIXA` pode confirmar o Fechamento.
- [x] O sistema exibe conteúdo e total antes de solicitar a confirmação explícita.
- [x] O Fechamento registra instante UTC e Caixa responsável, encerra o Atendimento e libera imediatamente a Comanda física.
- [x] Atendimento com total zero pode ser fechado explicitamente.
- [x] Depois do commit, novas mutações no Atendimento são rejeitadas e não existe reabertura no protótipo.
- [x] A operação reutiliza o mecanismo geral de idempotência do ticket 09.
- [x] Testes cobrem autorização, confirmação, total zero, liberação da Comanda física, idempotência e irreversibilidade.

## Answer

O Atendimento agora registra `fechado_por`, protegido contra exclusão, e
`fechado_em`. O Caixa acessa uma página GET de conferência com resumo, histórico,
Total e aviso de irreversibilidade; somente o POST desse formulário executa o
Fechamento.

O caso de uso usa a operação idempotente estável `FECHAR_ATENDIMENTO` e atualiza
condicionalmente apenas um Atendimento ainda `ABERTO`. Estado, autoria, instante e
resultado idempotente são confirmados ou revertidos juntos. Um replay da mesma
chave recupera o resultado original, enquanto uma chave nova encontra o estado
`ENCERRADO` e é rejeitada.

Ao sair de `ABERTO`, o Atendimento deixa de participar da restrição de unicidade
parcial existente, tornando a Comanda imediatamente disponível para um novo
Atendimento. O histórico anterior permanece intacto e não foi criado fluxo de
reabertura.

