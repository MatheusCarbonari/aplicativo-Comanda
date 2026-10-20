# 21: Tratar perda e recuperação de comunicação

**What to build:** informar claramente quando o backend está indisponível, preservar o último contexto visível e impedir que a interface simule sucesso durante a falha.

**Blocked by:** 05 — Expor e verificar a saúde do backend; 20 — Atualizar telas abertas periodicamente.

**Status:** resolved

- [x] A interface apresenta “Sem comunicação com o servidor” ao detectar indisponibilidade.
- [x] Dados já carregados continuam visíveis e são marcados como possivelmente desatualizados.
- [x] Ações mutáveis ficam desabilitadas ou falham claramente, sem confirmação otimista enganosa.
- [x] Nenhum Lançamento é mantido somente no navegador para sincronização posterior.
- [x] A recuperação é detectada automaticamente, atualiza os dados, remove o aviso e reabilita as ações permitidas.
- [x] Testes de interface cobrem perda antes da operação, perda após envio sem resposta e recuperação posterior.

## Answer

O mesmo ciclo de atualização periódica passou a tratar erro de rede, timeout e
HTTP 503 como indisponibilidade. Ele preserva a região já renderizada, mostra o
aviso de comunicação e marca os dados como possivelmente desatualizados.

Formulários de Lançamento, cancelamento e Fechamento são bloqueados durante uma
falha conhecida. Se uma requisição mutável sair e não houver resposta, a tela
informa que o resultado é incerto, não repete o POST e mantém somente a chave de
idempotência que já estava no formulário, sem criar fila offline.

O polling continua fazendo apenas GET e não concorre com outra consulta ou com
uma mutação. Quando o backend volta, a tela consulta novamente o estado
persistido antes de retirar os avisos e reabilitar as ações. Na tela do primeiro
Lançamento, que ainda não possui estado de Comanda aberto, o mesmo ciclo usa
`/saude/` e, após uma operação incerta, direciona para a consulta da Comanda.

