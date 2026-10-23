# 30: Validar concorrência e volume esperados

**What to build:** uma verificação reproduzível de que o protótipo continua correto e responsivo com o volume e a concorrência previstos para a demonstração.

**Blocked by:** 18 — Resolver a corrida entre Lançamento e Fechamento; 20 — Atualizar telas abertas periodicamente.

**Status:** resolved

- [x] O cenário usa pelo menos dez mil lançamentos persistidos.
- [x] O cenário representa até dez dispositivos realizando leituras e escritas concorrentes.
- [x] São exercitados registro de Lançamento, consulta e Fechamento sem violar as invariantes do Atendimento.
- [x] Contenção do SQLite é registrada e tratada sem corrupção ou perda silenciosa de operações confirmadas.
- [x] Operações normais na rede local simulada são comparadas com a meta prática de aproximadamente um segundo.
- [x] O resultado documenta ambiente, método e medições sem transformar a meta em SLA formal.
- [x] O teste pode ser executado separadamente da suíte rápida e falha quando encontra duplicidade de Atendimento ou total incorreto.

## Answer

Adicionado o comando `validar_volume_concorrencia`, executado em processo e banco
SQLite temporários com migrations reais, WAL e `synchronous=FULL`. A preparação
em massa usa ORM; dez dispositivos simulados com conexões próprias exercitam os
casos de uso públicos de registro, consulta e Fechamento. O relatório JSON separado dos logs
operacionais registra ambiente, seed, volume, resultados, contenções/retries e
estatísticas de tempo monotônico. O verificador falha explicitamente diante de
Atendimento aberto duplicado, Total incorreto, perda de confirmação, violação de
Fechamento, idempotência, disponibilidade da Comanda ou integridade SQLite.

