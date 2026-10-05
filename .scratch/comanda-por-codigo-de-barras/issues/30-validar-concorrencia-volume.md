# 30: Validar concorrência e volume esperados

**What to build:** uma verificação reproduzível de que o protótipo continua correto e responsivo com o volume e a concorrência previstos para a demonstração.

**Blocked by:** 18 — Resolver a corrida entre Lançamento e Fechamento; 20 — Atualizar telas abertas periodicamente.

**Status:** ready-for-agent

- [ ] O cenário usa pelo menos dez mil lançamentos persistidos.
- [ ] O cenário representa até dez dispositivos realizando leituras e escritas concorrentes.
- [ ] São exercitados registro de Lançamento, consulta e Fechamento sem violar as invariantes do Atendimento.
- [ ] Contenção do SQLite é registrada e tratada sem corrupção ou perda silenciosa de operações confirmadas.
- [ ] Operações normais na rede local simulada são comparadas com a meta prática de aproximadamente um segundo.
- [ ] O resultado documenta ambiente, método e medições sem transformar a meta em SLA formal.
- [ ] O teste pode ser executado separadamente da suíte rápida e falha quando encontra duplicidade de Atendimento ou total incorreto.

