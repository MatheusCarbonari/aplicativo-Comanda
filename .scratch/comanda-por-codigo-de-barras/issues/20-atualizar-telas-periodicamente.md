# 20: Atualizar telas abertas periodicamente

**What to build:** manter as visões abertas de Garçom e Caixa próximas do estado atual por atualização imediata após ações locais e consulta automática periódica ao backend.

**Blocked by:** 08 — Registrar lançamentos adicionais e calcular o total; 13 — Consultar a Comanda como Caixa; 16 — Fechar um Atendimento confirmado.

**Status:** ready-for-agent

- [ ] Uma operação local concluída atualiza a tela imediatamente com o resultado confirmado pelo backend.
- [ ] Telas abertas consultam o estado aproximadamente a cada dois segundos.
- [ ] Mudanças feitas por outro dispositivo aparecem sem exigir recarregamento manual completo.
- [ ] A atualização não cria Atendimento nem repete operações mutáveis.
- [ ] A solução não exige WebSocket.
- [ ] Testes de interface com tempo controlado cobrem atualização externa, ausência de mudança e encerramento do ciclo ao sair da tela.

