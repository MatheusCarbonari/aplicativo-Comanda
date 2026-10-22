# 28: Verificar durabilidade diante de encerramento abrupto

**What to build:** uma verificação automatizada em nível de processo que demonstre que operações confirmadas sobrevivem à interrupção do servidor e operações não confirmadas não deixam efeitos parciais.

**Blocked by:** 11 — Cancelar integralmente um Lançamento; 16 — Fechar um Atendimento confirmado.

**Status:** resolved

- [x] O teste executa a aplicação contra SQLite persistente real, não banco somente em memória.
- [x] Interrupção antes do commit não preserva Atendimento, Lançamento, cancelamento ou Fechamento parcial.
- [x] Interrupção depois do commit preserva integralmente a operação após reiniciar o processo.
- [x] Um cliente que perdeu a resposta pode reenviar a mesma chave e recuperar o resultado confirmado sem duplicação.
- [x] Atendimentos abertos continuam abertos e comandas liberadas permanecem disponíveis após reinício.
- [x] A verificação é determinística o suficiente para execução repetida e documenta limitações da simulação de queda de energia.

## Answer

Implementada uma verificação multiprocesso com protocolo JSON determinístico e
bancos SQLite persistentes isolados. O processo auxiliar executa os quatro casos
de uso públicos dentro de uma transação externa, sinaliza antes ou depois do
commit efetivo e é encerrado abruptamente pelo processo pai. Novos processos
reabrem o banco para comprovar rollback, durabilidade, revisões, disponibilidade
da Comanda física e replay idempotente sem duplicação. A documentação registra a
execução, WAL/FULL e os limites frente a uma queda física de energia. O auxiliar
fica na borda `testes_suporte`; stdout é drenado por uma thread, stderr vai para
arquivo isolado e toda espera do pai possui timeout com encerramento e coleta do
filho. O próprio mutador observa e valida WAL/FULL antes de operar.

