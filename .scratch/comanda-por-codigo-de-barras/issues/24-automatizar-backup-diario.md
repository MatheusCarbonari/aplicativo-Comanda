# 24: Automatizar backup diário

**What to build:** executar automaticamente o backup seguro uma vez por dia no ambiente principal Windows e conservar somente as sete cópias diárias mais recentes.

**Blocked by:** 23 — Criar backup SQLite seguro.

**Status:** ready-for-agent

- [ ] A automação reutiliza o comando seguro de backup, sem duplicar sua lógica.
- [ ] Existe uma forma documentada e automatizável de agendamento diário no Windows.
- [ ] O mecanismo permanece adaptável a agendamento equivalente em Linux sem alterar regras de domínio.
- [ ] Após sucesso, somente as sete cópias diárias mais recentes são mantidas segundo ordem determinística.
- [ ] Uma falha de backup não elimina previamente uma cópia válida necessária à retenção.
- [ ] Execuções repetidas ou sobrepostas são tratadas com segurança e deixam resultado observável em logs.
- [ ] Testes cobrem acionamento, retenção, ordenação e falha durante uma execução agendada.

