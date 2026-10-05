# 21: Tratar perda e recuperação de comunicação

**What to build:** informar claramente quando o backend está indisponível, preservar o último contexto visível e impedir que a interface simule sucesso durante a falha.

**Blocked by:** 05 — Expor e verificar a saúde do backend; 20 — Atualizar telas abertas periodicamente.

**Status:** ready-for-agent

- [ ] A interface apresenta “Sem comunicação com o servidor” ao detectar indisponibilidade.
- [ ] Dados já carregados continuam visíveis e são marcados como possivelmente desatualizados.
- [ ] Ações mutáveis ficam desabilitadas ou falham claramente, sem confirmação otimista enganosa.
- [ ] Nenhum Lançamento é mantido somente no navegador para sincronização posterior.
- [ ] A recuperação é detectada automaticamente, atualiza os dados, remove o aviso e reabilita as ações permitidas.
- [ ] Testes de interface cobrem perda antes da operação, perda após envio sem resposta e recuperação posterior.

