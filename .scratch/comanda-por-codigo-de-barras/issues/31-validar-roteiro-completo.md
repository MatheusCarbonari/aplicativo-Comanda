# 31: Validar o roteiro completo de demonstração

**What to build:** comprovar o fluxo integrado do protótipo do primeiro Lançamento ao Fechamento, incluindo operação administrativa e uso representativo em celular e computador.

**Blocked by:** 14 — Usar leitor de código de barras como teclado; 15 — Gerar a folha de códigos de barras; 19 — Apresentar o resumo final do Atendimento; 21 — Tratar perda e recuperação de comunicação; 24 — Automatizar backup diário; 25 — Garantir backup antes de migrações; 26 — Restaurar backup e verificar integridade; 27 — Reinicializar dados de desenvolvimento com segurança; 28 — Verificar durabilidade diante de encerramento abrupto; 29 — Documentar execução única e acesso pela rede local; 30 — Validar concorrência e volume esperados.

**Status:** ready-for-agent

- [ ] O roteiro automatizado cobre seleção de Garçom, primeiro Lançamento, lançamentos adicionais, outro Garçom e cancelamento.
- [ ] O fluxo de Caixa cobre consulta por teclado, consolidação, mudança posterior à conferência, nova confirmação, Fechamento e resumo final.
- [ ] A Comanda física volta a ficar disponível e pode iniciar novo Atendimento sem misturar históricos.
- [ ] O roteiro cobre perda e recuperação de comunicação sem sucesso fictício ou armazenamento offline.
- [ ] A execução é validada em dimensões representativas de celular e desktop nos navegadores suportados disponíveis ao teste.
- [ ] Backup, restauração, reinício e idempotência são exercitados conforme o roteiro de aceite do projeto.
- [ ] A validação manual com leitor físico possui passos e resultado esperado registrados.
- [ ] Falhas encontradas são corrigidas nos tickets responsáveis ou registradas como novos tickets coesos; este ticket não vira um pacote amplo de implementação.

