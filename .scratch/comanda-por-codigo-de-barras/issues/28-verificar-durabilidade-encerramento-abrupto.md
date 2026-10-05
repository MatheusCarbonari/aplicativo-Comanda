# 28: Verificar durabilidade diante de encerramento abrupto

**What to build:** uma verificação automatizada em nível de processo que demonstre que operações confirmadas sobrevivem à interrupção do servidor e operações não confirmadas não deixam efeitos parciais.

**Blocked by:** 11 — Cancelar integralmente um Lançamento; 16 — Fechar um Atendimento confirmado.

**Status:** ready-for-agent

- [ ] O teste executa a aplicação contra SQLite persistente real, não banco somente em memória.
- [ ] Interrupção antes do commit não preserva Atendimento, Lançamento, cancelamento ou Fechamento parcial.
- [ ] Interrupção depois do commit preserva integralmente a operação após reiniciar o processo.
- [ ] Um cliente que perdeu a resposta pode reenviar a mesma chave e recuperar o resultado confirmado sem duplicação.
- [ ] Atendimentos abertos continuam abertos e comandas liberadas permanecem disponíveis após reinício.
- [ ] A verificação é determinística o suficiente para execução repetida e documenta limitações da simulação de queda de energia.

