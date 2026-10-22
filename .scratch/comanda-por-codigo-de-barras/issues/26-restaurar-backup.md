# 26: Restaurar backup e verificar integridade

**What to build:** um procedimento administrativo seguro que substitua o banco por uma cópia escolhida somente quando novas operações estiverem impedidas e a integridade puder ser confirmada.

**Blocked by:** 23 — Criar backup SQLite seguro.

**Status:** resolved

- [x] A restauração não aparece na interface operacional e exige uma escolha explícita do backup.
- [x] O procedimento recusa executar enquanto a aplicação aceita novas operações ou o banco está em condição insegura.
- [x] O backup escolhido é validado antes de substituir o banco operacional.
- [x] Após a substituição, uma verificação de integridade é obrigatória antes de liberar novamente o acesso.
- [x] Falhas preservam ou permitem recuperar o banco anterior e produzem orientação compreensível ao operador.
- [x] O procedimento e a necessidade de reiniciar a aplicação são documentados.
- [x] Testes com SQLite real cobrem restauração válida, cópia corrompida e falha intermediária.

## Answer

Implementado o comando administrativo `restaurar_backup`, com escolha explícita
do arquivo e confirmação obrigatória de que a aplicação foi parada. O backup
é validado em modo somente leitura, o banco atual é preservado e validado, a
troca usa publicação atômica e uma segunda verificação de integridade precede o
sucesso. Falhas intermediárias mantêm uma cópia recuperável ou recolocam o banco
anterior quando isso é seguro. O procedimento, os eventos administrativos e a
necessidade de reinício foram documentados; a interface web permanece sem rota
ou controle de restauração.

