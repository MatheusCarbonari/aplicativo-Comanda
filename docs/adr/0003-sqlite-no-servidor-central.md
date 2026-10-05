---
status: accepted
---

# Usar SQLite no servidor central do protótipo

O protótipo usará SQLite porque uma única instância de backend na rede local atende ao volume e à concorrência esperados com baixa complexidade operacional. O arquivo permanecerá exclusivamente no servidor central; todos os dispositivos acessarão os dados pelo backend, com transações e restrições de banco protegendo as invariantes do domínio.

## Consequências

- O arquivo SQLite não pode ficar em pasta de rede compartilhada nem ser acessado diretamente pelos clientes.
- O banco usará WAL com `synchronous=FULL`, priorizando durabilidade dos commits diante de quedas de energia sobre alguns milissegundos de desempenho de escrita.
- Uma operação de negócio é confirmada somente depois do commit; operações interrompidas devem ser integralmente revertidas.
- Transações de escrita devem ser explícitas e curtas para reduzir contenção. A implementação não poderá depender de bloqueios de linha, como `SELECT FOR UPDATE`, porque esse mecanismo não é efetivo no SQLite.
- Invariantes concorrentes críticas devem ser expressas por restrições e índices no próprio banco sempre que possível. Em especial, a persistência deve impedir mais de um atendimento aberto para a mesma comanda física, mesmo diante de aberturas simultâneas.
- Violações de restrição e contenções de escrita devem ser tratadas como resultados possíveis da concorrência, sem deixar operações parcialmente aplicadas nem substituir a proteção do banco por estado mantido apenas em memória.
- Dados confirmados devem permanecer no banco e sobreviver a reinicializações inesperadas, sem depender da memória do processo.
- A inicialização deve recuperar atendimentos, lançamentos, cancelamentos e estados de comandas diretamente dos dados persistidos.
- A infraestrutura criará um backup seguro por dia e antes de migrações, conservando as sete cópias mais recentes.
- Backups locais no mesmo disco não protegem contra perda, destruição ou falha física do servidor; backup externo permanece uma evolução futura.
- A restauração será um procedimento administrativo fora da interface: bloquear operações, colocar o servidor em estado seguro, validar e restaurar a cópia, verificar a integridade e só então liberar o acesso.
- Um comando exclusivo de desenvolvimento poderá reinicializar os dados de demonstração somente após confirmação explícita e backup; a inicialização normal nunca apaga dados.
- Se forem necessárias múltiplas instâncias de backend ou concorrência incompatível com SQLite, PostgreSQL deverá ser reavaliado.
- A escolha da stack Django está registrada no [ADR 0007](./0007-python-django-e-templates-no-prototipo.md); ela não altera os limites de concorrência próprios do SQLite.
