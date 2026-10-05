# 01: Inicializar o monólito Django

**What to build:** uma aplicação Django mínima que possa ser iniciada e testada localmente, com a separação modular prevista nos ADRs e uma página-base responsiva servida sem dependências externas.

**Blocked by:** None (can start immediately).

**Status:** resolved

- [x] A aplicação inicia localmente e apresenta uma página-base em português do Brasil.
- [x] A organização inicial distingue domínio, casos de uso, persistência, interface web, ferramentas administrativas e infraestrutura sem criar serviços separados.
- [x] CSS, JavaScript, fontes e demais recursos necessários à página-base são servidos localmente.
- [x] A configuração inicial funciona no ambiente principal Windows e não introduz dependência conceitual exclusiva desse sistema.
- [x] A suíte de testes possui um comando documentado e inclui um teste automatizado da inicialização e da página-base.
- [x] O ticket permanece restrito ao esqueleto executável; não antecipa regras de Comanda física ou Atendimento.

## Answer

Foi criado o esqueleto executável do monólito Django, com configuração em português, página-base responsiva, CSS local, comandos documentados e teste pela fronteira HTTP pública. As áreas ainda sem responsabilidade concreta foram registradas na documentação arquitetural sem pacotes ou abstrações vazias. A suíte, os checks do Django, o carregamento do recurso estático e o smoke test HTTP foram executados com sucesso.

