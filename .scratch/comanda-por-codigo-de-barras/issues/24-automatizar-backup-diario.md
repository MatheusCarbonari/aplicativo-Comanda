# 24: Automatizar backup diário

**What to build:** executar automaticamente o backup seguro uma vez por dia no ambiente principal Windows e conservar somente as sete cópias diárias mais recentes.

**Blocked by:** 23 — Criar backup SQLite seguro.

**Status:** resolved

- [x] A automação reutiliza o comando seguro de backup, sem duplicar sua lógica.
- [x] Existe uma forma documentada e automatizável de agendamento diário no Windows.
- [x] O mecanismo permanece adaptável a agendamento equivalente em Linux sem alterar regras de domínio.
- [x] Após sucesso, somente as sete cópias diárias mais recentes são mantidas segundo ordem determinística.
- [x] Uma falha de backup não elimina previamente uma cópia válida necessária à retenção.
- [x] Execuções repetidas ou sobrepostas são tratadas com segurança e deixam resultado observável em logs.
- [x] Testes cobrem acionamento, retenção, ordenação e falha durante uma execução agendada.

## Answer

Implementado o comando `python manage.py executar_backup_diario`. Ele adquire um
lock local em um arquivo SQLite de coordenação, chama o comando público
`criar_backup` do Ticket 23 e somente depois do sucesso aplica a retenção.

A retenção reconhece apenas nomes publicados no formato
`restaurante-<timestamp UTC>[-<sufixo>].sqlite3`, ordena timestamp e sufixo
numericamente e mantém os sete mais recentes. O timestamp precisa representar
uma data e hora UTC real; timestamps impossíveis, nomes parciais, arquivos
estranhos, `.incompleto` e o banco de lock não participam. Falha no backup
preserva todas as cópias anteriores; falha de retenção interrompe novas
remoções, mantém observáveis as remoções já concluídas e não invalida o novo
backup já publicado.

O lock usa `BEGIN IMMEDIATE` com espera zero, é liberado automaticamente ao
fechar a conexão e não deixa estado preso após término do processo. Uma segunda
execução simultânea sai com mensagem compreensível e evento estruturado, sem
iniciar outro backup ou retenção.

O wrapper `scripts/executar_backup_diario.ps1` e o README documentam instalação,
consulta, teste e remoção da tarefa diária via `schtasks`, com diretório de
trabalho e Python da `.venv` explícitos. A lógica Python é independente do
Windows e poderá ser acionada futuramente por `cron` ou `systemd timer`.

Validação concluída com 13 testes do Ticket 24, 203 testes Django e 21 testes
JavaScript. `manage.py check`,
`makemigrations --check --dry-run`, sintaxe PowerShell e `git diff --check`
passaram.

