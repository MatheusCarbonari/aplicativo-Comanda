# 26: Restaurar backup e verificar integridade

**What to build:** um procedimento administrativo seguro que substitua o banco por uma cópia escolhida somente quando novas operações estiverem impedidas e a integridade puder ser confirmada.

**Blocked by:** 23 — Criar backup SQLite seguro.

**Status:** ready-for-agent

- [ ] A restauração não aparece na interface operacional e exige uma escolha explícita do backup.
- [ ] O procedimento recusa executar enquanto a aplicação aceita novas operações ou o banco está em condição insegura.
- [ ] O backup escolhido é validado antes de substituir o banco operacional.
- [ ] Após a substituição, uma verificação de integridade é obrigatória antes de liberar novamente o acesso.
- [ ] Falhas preservam ou permitem recuperar o banco anterior e produzem orientação compreensível ao operador.
- [ ] O procedimento e a necessidade de reiniciar a aplicação são documentados.
- [ ] Testes com SQLite real cobrem restauração válida, cópia corrompida e falha intermediária.

