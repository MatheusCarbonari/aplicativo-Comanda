---
status: accepted
---

# Tornar operações relevantes idempotentes com chaves persistidas

Cada solicitação de uma operação mutável relevante carregará uma chave única persistida pelo backend junto do resultado da operação. Reenviar a mesma solicitação retorna o resultado confirmado sem executar novamente a mudança, evitando duplicidade após falhas de comunicação ou reinicializações.

## Consequências

- A proteção continua funcionando após reiniciar o servidor.
- Solicitações intencionais diferentes precisam de chaves diferentes, mesmo quando possuem o mesmo conteúdo.
- A chave, a operação e seu resultado devem ser confirmados de forma atômica na mesma transação.
- Reutilizar uma chave com conteúdo incompatível deve ser rejeitado, não interpretado como uma nova operação.
