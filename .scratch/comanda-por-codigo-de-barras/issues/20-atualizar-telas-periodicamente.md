# 20: Atualizar telas abertas periodicamente

**What to build:** manter as visões abertas de Garçom e Caixa próximas do estado atual por atualização imediata após ações locais e consulta automática periódica ao backend.

**Blocked by:** 08 — Registrar lançamentos adicionais e calcular o total; 13 — Consultar a Comanda como Caixa; 16 — Fechar um Atendimento confirmado.

**Status:** resolved

- [x] Uma operação local concluída atualiza a tela imediatamente com o resultado confirmado pelo backend.
- [x] Telas abertas consultam o estado aproximadamente a cada dois segundos.
- [x] Mudanças feitas por outro dispositivo aparecem sem exigir recarregamento manual completo.
- [x] A atualização não cria Atendimento nem repete operações mutáveis.
- [x] A solução não exige WebSocket.
- [x] Testes de interface com tempo controlado cobrem atualização externa, ausência de mudança e encerramento do ciclo ao sair da tela.

## Answer

As consultas do Garçom, do Caixa e a conferência de Fechamento carregam um
JavaScript local que executa somente GET a cada dois segundos. O script impede
consultas simultâneas, compara a revisão persistida antes de substituir a região
visual e cancela o intervalo e a requisição ativa no evento `pagehide`.

Resumo, histórico, Total e revisão são preparados no mesmo snapshot curto de
leitura. Assim, Lançamentos, cancelamentos e Fechamento feitos por outro
dispositivo aparecem juntos e a revisão da confirmação acompanha exatamente o
estado exibido. Se o Atendimento for encerrado durante a conferência, o GET
redireciona ao resumo final.

Os POSTs existentes continuam devolvendo imediatamente o resultado confirmado
pelo backend; o polling não conhece nem reutiliza requisições mutáveis. Os testes
com timers controlados cobrem intervalo, ausência de mudança, atualização,
contenção de chamadas concorrentes, GET exclusivo e encerramento do ciclo.

