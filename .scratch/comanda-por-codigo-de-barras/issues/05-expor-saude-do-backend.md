# 05: Expor e verificar a saúde do backend

**What to build:** um endpoint técnico simples que permita às interfaces e à operação determinar se o processo da aplicação está respondendo.

**Blocked by:** 01 — Inicializar o monólito Django.

**Status:** resolved

- [x] O endpoint responde sem exigir um Usuário operacional selecionado.
- [x] Uma resposta saudável possui contrato mínimo estável e não expõe segredos ou dados operacionais.
- [x] Falhas internas relevantes resultam em estado não saudável ou indisponibilidade observável.
- [x] Testes automatizados cobrem a resposta saudável e o contrato público do endpoint.
- [x] O endpoint não executa mutações de domínio.

## Answer

Foi criado o endpoint técnico `GET /saude/`, independente da sessão operacional. Ele executa a consulta somente leitura `SELECT 1` na conexão padrão: sucesso retorna HTTP 200 com `{"status": "ok"}`; qualquer falha nessa verificação retorna HTTP 503 com `{"status": "indisponivel"}`. O corpo não contém detalhes internos e o endpoint aceita somente GET. Testes com SQLite real cobrem o contrato saudável, ausência de sessão e de mutações; uma falha controlada no cursor do banco comprova o comportamento indisponível.

