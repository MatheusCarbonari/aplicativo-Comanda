# Feature: Comanda por Código de Barras

Status: ready-for-agent

## Problem Statement

O restaurante precisa registrar digitalmente os produtos consumidos em comandas físicas reutilizáveis. Hoje, a comanda física identifica o atendimento, mas não carrega os consumos: garçons precisam registrar os lançamentos durante o atendimento e o caixa precisa recuperar o conteúdo correto ao ler o código de barras ou digitar o identificador. O fluxo deve preservar rastreabilidade, resistir a reenvios, concorrência e reinicializações inesperadas, sem transformar o protótipo em um sistema completo de restaurante.

## Solution

Construir uma aplicação web responsiva para uso na rede local, acessada por garçons em celulares e pelo caixa em um computador. Produtos, comandas físicas e usuários operacionais serão pré-carregados. O primeiro lançamento válido abre automaticamente um atendimento para a comanda disponível; lançamentos posteriores ficam associados ao mesmo atendimento até que o caixa confira e confirme o fechamento. O código de barras contém somente o identificador textual da comanda e usa o mesmo fluxo de consulta da entrada manual.

A implementação inicial será um monólito modular em Python e Django, com SQLite no servidor central e interface renderizada por Django Templates, HTML, CSS e JavaScript pontual. O domínio, os casos de uso, a persistência, a interface web, as ferramentas administrativas e a infraestrutura terão responsabilidades separadas dentro do mesmo projeto implantável.

## User Stories

1. Como Garçom, quero selecionar uma comanda física pelo identificador, para conferir seu estado antes de registrar um consumo.
2. Como Garçom, quero ver se a comanda está disponível ou em atendimento, para entender se meu próximo lançamento abrirá um atendimento ou entrará em um já existente.
3. Como Garçom, quero ver os produtos válidos e o total atual do atendimento, para conferir o consumo já registrado.
4. Como Garçom, quero acessar os lançamentos cancelados separadamente, para consultar o histórico sem confundi-lo com o consumo válido.
5. Como Garçom, quero selecionar um produto pré-cadastrado e informar uma quantidade inteira positiva, para registrar o consumo do cliente.
6. Como Garçom, quero que o primeiro lançamento válido em uma comanda disponível abra automaticamente um atendimento, para não precisar executar uma etapa de abertura separada.
7. Como Garçom, quero que apenas a confirmação do primeiro lançamento crie o atendimento, para poder consultar uma comanda disponível sem alterar seu estado.
8. Como Garçom, quero registrar quantidade maior que um no mesmo lançamento, para representar consumos como três refrigerantes.
9. Como Garçom, quero receber uma mensagem clara quando a quantidade for zero, negativa ou fracionária, para corrigir a entrada antes do registro.
10. Como Garçom, quero que cada lançamento preserve o preço vigente do produto, para que mudanças posteriores no catálogo não alterem o histórico do atendimento.
11. Como Garçom, quero registrar novamente o mesmo produto quando o cliente pedir outra unidade, para preservar cada ação como um lançamento individual.
12. Como Garçom, quero que dois lançamentos intencionais iguais sejam aceitos quando usam solicitações distintas, para não impedir consumos repetidos legítimos.
13. Como Garçom, quero que um toque duplo ou reenvio da mesma solicitação não crie lançamentos duplicados, para evitar cobrança indevida.
14. Como Garçom, quero reenviar a mesma solicitação após perder a resposta do servidor, para descobrir com segurança se ela já foi confirmada.
15. Como Garçom, quero que outros garçons possam lançar produtos no mesmo atendimento, para que a operação não dependa de um único responsável.
16. Como Garçom, quero que lançamentos simultâneos sejam preservados sem sobrescrita, para que nenhum consumo confirmado seja perdido.
17. Como Garçom, quero que primeiras solicitações simultâneas criem um único atendimento e associem ambos os lançamentos a ele, para manter a identidade correta do atendimento.
18. Como Garçom, quero cancelar integralmente um lançamento incorreto enquanto o atendimento estiver aberto, para corrigir o total sem apagar o histórico.
19. Como Garçom, quero cancelar um lançamento feito por outro Garçom, para evitar bloqueios operacionais durante o atendimento.
20. Como Garçom, quero escolher um motivo obrigatório de cancelamento, para manter a rastreabilidade da correção.
21. Como Garçom, quero descrever o motivo quando selecionar “outro”, para que o cancelamento continue compreensível.
22. Como Garçom, quero cancelar um lançamento de três unidades e criar outro com a quantidade correta, para corrigir a quantidade sem editar parcialmente o registro original.
23. Como Garçom, quero que lançamentos cancelados deixem de compor o total, para que a cobrança considere somente lançamentos válidos.
24. Como Garçom, quero que um atendimento permaneça aberto com total zero quando todos os lançamentos forem cancelados, para que seu encerramento continue sendo uma decisão explícita do Caixa.
25. Como Caixa, quero consultar uma comanda física lendo seu código de barras, para recuperar rapidamente o atendimento atual.
26. Como Caixa, quero consultar a mesma comanda digitando seu identificador e acionando “Consultar”, para trabalhar mesmo sem o leitor.
27. Como Caixa, quero que o leitor funcione como teclado, preenchendo o identificador e enviando Enter, para não depender de driver ou integração específica.
28. Como Caixa, quero receber “Comanda não encontrada” ao informar um identificador desconhecido, para saber que nenhum cadastro foi criado implicitamente.
29. Como Caixa, quero receber “Comanda disponível — nenhum atendimento aberto” ao consultar uma comanda sem atendimento, para distinguir esse caso de erro ou ausência de cadastro.
30. Como Caixa, quero ver os lançamentos válidos consolidados por produto e preço unitário, para conferir a comanda com rapidez.
31. Como Caixa, quero ver em linhas diferentes lançamentos do mesmo produto com preços registrados diferentes, para preservar a correção do resumo.
32. Como Caixa, quero ver quantidade, preço unitário, subtotal e total formatados em reais, para conferir o valor a ser encerrado.
33. Como Caixa, quero consultar separadamente os lançamentos cancelados com produto, quantidade, preço, autores, horários e motivo, para auditar as correções.
34. Como Caixa, quero confirmar o conteúdo e o total antes do fechamento, para evitar encerramentos acidentais.
35. Como Caixa, quero ser avisado quando o atendimento mudar depois que visualizei o resumo, para revisar o conteúdo e confirmar novamente o valor atualizado.
36. Como Caixa, quero que um lançamento confirmado antes do fechamento participe do total final, para não encerrar um atendimento com valor desatualizado.
37. Como Caixa, quero que lançamentos posteriores a um fechamento confirmado sejam rejeitados, para preservar a imutabilidade do atendimento encerrado.
38. Como Caixa, quero poder fechar explicitamente um atendimento com total zero, para preservar o histórico mesmo quando todos os lançamentos foram cancelados.
39. Como Caixa, quero que o fechamento seja irreversível no protótipo, para que o fluxo tenha um estado final claro.
40. Como Caixa, quero ver imediatamente o resumo do atendimento encerrado, para conferir o identificador, os horários, os itens, os cancelamentos, o total e o responsável pelo fechamento.
41. Como usuário operacional, quero selecionar Garçom 1, Garçom 2 ou Caixa 1 em uma tela inicial, para demonstrar os diferentes papéis sem autenticação completa.
42. Como usuário operacional, quero trocar de usuário apenas por uma ação explícita, para evitar mudanças de papel acidentais.
43. Como usuário operacional, quero que a interface mostre apenas as ações compatíveis com meu papel, para reduzir erros durante a operação.
44. Como responsável pelo restaurante, quero que o backend valide o usuário operacional e seu papel em cada operação, para não depender somente de controles visuais.
45. Como usuário operacional, quero que telas abertas sejam atualizadas aproximadamente a cada dois segundos, para perceber lançamentos e fechamentos feitos em outros dispositivos.
46. Como usuário operacional, quero ver “Sem comunicação com o servidor” quando o backend estiver indisponível, para não acreditar que uma operação foi concluída.
47. Como usuário operacional, quero manter visíveis os últimos dados carregados com indicação de possível desatualização, para conservar contexto durante uma falha de comunicação.
48. Como usuário operacional, quero que operações mutáveis fiquem desabilitadas sem comunicação e sejam reabilitadas após a recuperação, para evitar ações enganosas.
49. Como responsável pela demonstração, quero visualizar e imprimir uma folha com códigos Code 128 das comandas 001 a 020, para testar o fluxo com um leitor físico.
50. Como responsável pela operação, quero que dados confirmados sobrevivam a reinicializações e quedas inesperadas, para não perder atendimentos ou lançamentos.
51. Como responsável pela operação, quero iniciar o servidor com um único comando documentado após a instalação, para reduzir a complexidade operacional.
52. Como responsável pela operação, quero um endpoint de saúde, para detectar se o backend está disponível.
53. Como responsável pela operação, quero backups automáticos diários e anteriores a migrações, para reduzir o impacto de erros e mudanças de esquema.
54. Como responsável pela operação, quero reter as sete cópias de backup mais recentes, para controlar o uso de armazenamento local.
55. Como responsável pela operação, quero restaurar um backup somente por procedimento administrativo seguro, para impedir restaurações acidentais pela interface operacional.
56. Como responsável pelo desenvolvimento, quero uma carga inicial idempotente, para criar os dados de demonstração ausentes sem duplicar nem sobrescrever dados operacionais.
57. Como responsável pelo desenvolvimento, quero um comando explícito de reset que faça backup antes de apagar dados, para recriar a demonstração com segurança.
58. Como responsável técnico, quero logs locais estruturados e rotacionados, para diagnosticar inicialização, falhas, migrações, backups, restaurações e operações relevantes.
59. Como responsável técnico, quero executar a aplicação principalmente no Windows sem dependências conceituais exclusivas desse sistema, para preservar a possibilidade de implantação futura em Linux.
60. Como responsável técnico, quero que a operação na rede local não dependa da internet externa, para que uma queda do provedor não interrompa o restaurante quando servidor e rede local continuam disponíveis.

## Implementation Decisions

### Escopo e modelo de domínio

- A Comanda física tem Identificador da comanda textual, único, permanente e reutilizável. Zeros à esquerda fazem parte da identidade.
- Somente comandas físicas previamente cadastradas podem ser usadas. A massa inicial contém os identificadores `001` a `020`; entradas desconhecidas nunca criam cadastro implicitamente.
- Cada Comanda física possui no máximo um Atendimento aberto. O primeiro Lançamento válido cria o Atendimento; consultar ou visualizar uma Comanda disponível não cria estado de domínio.
- O Atendimento possui estados aberto e encerrado. Enquanto aberto, aceita lançamentos e cancelamentos; depois do Fechamento, não aceita novas mutações.
- O Fechamento libera imediatamente a Comanda física para um novo Atendimento e preserva integralmente o Atendimento encerrado.
- Não haverá interface geral de busca histórica no protótipo. O Atendimento encerrado permanece persistido, e o resumo do Atendimento recém-fechado pode ser exibido imediatamente.
- Cada Lançamento é preservado individualmente e contém Produto, quantidade inteira positiva, preço unitário registrado, Garçom responsável e instante definido pelo backend.
- Lançamentos não são editados nem excluídos fisicamente. Correções usam Cancelamento de lançamento integral e exigem novo Lançamento quando necessário.
- O Cancelamento de lançamento preserva responsável, instante e motivo. Os motivos iniciais são lançamento duplicado, produto incorreto, quantidade incorreta, desistência do cliente e outro; “outro” exige descrição.
- Qualquer Garçom pode cancelar um Lançamento de um Atendimento aberto, independentemente de quem o registrou. Caixa não cancela lançamentos neste escopo.
- O Total do atendimento é exclusivamente a soma de quantidade multiplicada pelo preço unitário registrado em cada Lançamento válido.
- Um Atendimento com todos os lançamentos cancelados continua aberto com total zero até o Fechamento explícito pelo Caixa.
- A consolidação por Produto e preço unitário é somente uma projeção de apresentação. Lançamentos com preços diferentes permanecem em linhas diferentes, e lançamentos cancelados não entram na consolidação.
- Dinheiro é armazenado como centavos inteiros em BRL, nunca como ponto flutuante, e apresentado com formatação brasileira.
- O backend é a autoridade para abertura, lançamento, cancelamento e fechamento. Instantes são persistidos em UTC e apresentados em `America/Sao_Paulo`, com datas `dd/MM/yyyy` e horários de 24 horas.

### Usuários e autorização

- Os usuários operacionais iniciais são Garçom 1 e Garçom 2, com papel `GARCOM`, e Caixa 1, com papel `CAIXA`.
- Não haverá senha, recuperação de acesso ou gerenciamento de usuários. A tela inicial permite selecionar um usuário pré-carregado, e “Trocar usuário” realiza a mudança explicitamente.
- Cada solicitação operacional envia o identificador do usuário selecionado. O backend carrega o Usuário operacional persistido e valida o papel antes de executar o caso de uso.
- `GARCOM` pode visualizar a Comanda física, registrar lançamentos e cancelar lançamentos em Atendimento aberto. `CAIXA` pode consultar comandas e fechar atendimentos.
- A seleção de usuário não constitui autenticação forte. Por isso, o protótipo fica restrito à rede local confiável e não pode ser publicado abertamente na internet.

### Concorrência, transações e idempotência

- A abertura implícita do Atendimento e o primeiro Lançamento formam uma operação atômica.
- A garantia de no máximo um Atendimento aberto por Comanda física deve existir no banco por restrição ou índice compatível com SQLite, além das validações da aplicação.
- Primeiros lançamentos simultâneos para uma Comanda disponível devem convergir para um único Atendimento, e ambos devem ser persistidos quando válidos.
- Operações críticas usam transações explícitas e curtas. A implementação não depende de bloqueio de linha ou de `SELECT FOR UPDATE`, que não fornece essa garantia no SQLite.
- Na corrida entre Lançamento e Fechamento, a primeira transação confirmada prevalece. Se o Fechamento confirmar primeiro, o Lançamento é rejeitado; se o Lançamento confirmar primeiro, ele integra o Atendimento.
- O resumo apresentado ao Caixa inclui uma versão ou revisão verificável do Atendimento. Se o conteúdo mudar antes da confirmação, o Fechamento com revisão antiga é rejeitado, o resumo é atualizado e nova confirmação é exigida.
- Cada solicitação mutável relevante possui chave de idempotência gerada no cliente e persistida no backend junto à identidade da operação, ao conteúdo da solicitação e ao resultado.
- Chave e resultado são confirmados na mesma transação da operação. Reenvio idêntico retorna o resultado já confirmado; reutilização da chave com conteúdo incompatível é rejeitada.
- Solicitações intencionais distintas usam chaves distintas, mesmo que Produto e quantidade sejam iguais. A idempotência continua funcionando após reinicialização do servidor.
- Operação interrompida antes do commit não deixa efeitos parciais. Operação cujo commit foi concluído permanece disponível após reinício, mesmo que o cliente não tenha recebido a resposta.

### Catálogo e dados iniciais

- Produto possui inicialmente apenas identificador, nome e preço atual em centavos. Não haverá interface de administração do catálogo.
- A massa inicial contém: Água mineral `500`, Refrigerante `750`, Suco `900`, Cerveja `1200`, Batata frita `2000`, Hambúrguer `2800`, Pizza `4500`, Salada `1800`, Sobremesa `1500` e Café `600`.
- Os preços da massa são dados de demonstração, não regras permanentes do domínio.
- A carga inicial é idempotente: cria somente registros ausentes e nunca remove, duplica ou sobrescreve atendimentos e lançamentos existentes.

### Interface web

- A mesma aplicação responsiva atende celular e computador. A experiência do Garçom é mobile-first; a do Caixa prioriza leitura rápida em desktop.
- A interface usa português do Brasil, controles adequados ao toque, estados evidentes, total destacado e feedback claro de sucesso, validação, conflito e indisponibilidade.
- A visão do Garçom mostra Identificador da comanda, estado, lançamentos válidos atuais, total, acesso separado aos cancelados, seleção de Produto, quantidade e confirmação.
- A visão do Caixa aceita o Identificador da comanda por digitação ou leitor configurado como teclado. Enter e o botão “Consultar” acionam o mesmo caso de uso.
- O código de barras usa Code 128 somente como representação do Identificador da comanda; o domínio não depende desse padrão.
- Uma página utilitária separada gera e apresenta os códigos das comandas iniciais em formato adequado a uma folha de teste. Ela não é um sistema operacional de impressão.
- Após cada operação bem-sucedida, a tela atualiza imediatamente. Telas abertas também consultam periodicamente o backend, aproximadamente a cada dois segundos; WebSocket não é necessário.
- A interface consulta o endpoint de saúde, preserva dados já exibidos durante falhas com indicação de possível desatualização e não apresenta uma operação como concluída sem confirmação do backend.
- O resumo após Fechamento contém Identificador da comanda, identificador do Atendimento, abertura, fechamento, itens válidos consolidados, quantidades, preços, subtotais, cancelamentos, total final e Caixa responsável.
- Fontes, scripts, estilos e ícones necessários à operação acompanham a aplicação; a interface não depende de CDN nem da internet externa.
- São suportadas versões atuais de Chrome, Edge e Safari móvel. Navegadores legados ficam fora do escopo.

### Arquitetura e persistência

- A implementação inicial usa Python, Django, Django Templates, HTML, CSS, JavaScript pontual e SQLite.
- O sistema é um monólito modular e uma única aplicação web operacional implantável. Não haverá frontend React, TypeScript, API independente ou múltiplos serviços sem requisito concreto.
- Os módulos internos separam domínio, casos de uso, persistência, interface web, ferramentas administrativas e infraestrutura.
- Regras de domínio e casos de uso permanecem tão independentes do Django quanto for prático. ORM, HTTP, templates e comandos de gerenciamento são adaptadores nas bordas.
- O arquivo SQLite existe exclusivamente no servidor central e nunca em pasta de rede compartilhada. Clientes acessam dados somente pelo backend.
- SQLite opera em WAL com `synchronous=FULL`. Configuração e inicialização verificam essas garantias quando possível.
- Dados confirmados não dependem de memória do processo. Atendimentos, lançamentos, cancelamentos, fechamentos, usuários, produtos, comandas e registros de idempotência sobrevivem a reinicializações.
- Windows é o ambiente principal do protótipo, mantendo compatibilidade razoável com Linux. Docker não é obrigatório e pode ser oferecido futuramente como alternativa.
- Após instalação, o servidor inicia por um único comando documentado. Banco, backups e logs usam diretórios persistentes e conhecidos.
- O protótipo considera cerca de vinte comandas iniciais, até dez dispositivos simultâneos e pelo menos dez mil lançamentos. Operações normais na rede local têm meta prática de aproximadamente um segundo, sem constituir SLA formal.
- Se múltiplas instâncias de backend ou maior concorrência ultrapassarem as características adequadas do SQLite, PostgreSQL deverá ser reavaliado.

### Operação e ferramentas administrativas

- Existe endpoint técnico de saúde do backend.
- Logs estruturados locais, com rotação, cobrem ciclo da aplicação, erros inesperados, falhas de banco, migrações, backups, restaurações, integridade e identificadores relevantes de operações, sem reproduzir desnecessariamente os consumos.
- O backup usa mecanismo seguro do SQLite, não cópia ingênua do arquivo aberto. É executado diariamente e antes de migrações, mantendo as sete cópias mais recentes.
- Backups iniciais permanecem no servidor local. A documentação explicita que cópias no mesmo disco não protegem contra falha física, perda ou destruição do computador.
- A restauração não aparece na interface operacional. O procedimento impede novas operações, coloca o servidor em estado seguro, valida o backup, restaura, verifica integridade, reinicia a aplicação e só então libera o acesso.
- Migração, backup, restauração, verificação de integridade e reset de desenvolvimento são comandos administrativos versionados, com validações, mensagens compreensíveis e falha segura.
- O reset de desenvolvimento nunca executa automaticamente, exige confirmação explícita, informa a perda de dados operacionais e realiza backup antes da limpeza.
- A instalação não configura exposição pública, port forwarding ou UPnP. A documentação orienta somente o acesso necessário pela rede local, inclusive firewall e endereço estável quando aplicável.
- Desenvolvimento pode usar internet para obter dependências. Um instalador offline não será construído agora, mas a arquitetura não impede uma entrega futura preparada sem internet.

### Diretriz para decomposição em tickets

- A futura decomposição deve preferir tickets pequenos e altamente coesos, cada um com uma responsabilidade clara e critérios de aceite verificáveis.
- Um ticket não deve misturar domínio, persistência, interface e infraestrutura quando essas responsabilidades puderem ser entregues e testadas incrementalmente.
- Testes relevantes fazem parte do próprio ticket e não são postergados para um ticket genérico de testes.
- Cada ticket deve produzir uma alteração revisável e testável isoladamente. Dependências e bloqueios entre tickets devem ser declarados explicitamente.
- Mudanças de centenas de linhas exigem avaliação cuidadosa. Uma alteração próxima ou superior a mil linhas é forte sinal de que o ticket precisa ser dividido, salvo justificativa excepcional registrada.
- Contagem de linhas é um alerta de revisão, não uma regra absoluta. Coesão, risco, testabilidade e facilidade de revisão determinam a divisão final.
- Prefere-se vários tickets pequenos em sequência a um ticket grande que implemente uma camada inteira ou todo o fluxo de uma vez.

## Testing Decisions

- Bons testes verificam comportamento observável e invariantes do domínio, sem acoplamento desnecessário à estrutura interna, à ordem de chamadas do ORM ou aos detalhes dos templates.
- A principal fronteira de teste será a camada pública de casos de uso integrada a um SQLite real. Ela deve cobrir autorização, transações, persistência, resultados e falhas concorrentes com o mínimo possível de mocks.
- Regras determinísticas de estado, quantidade, cancelamento, consolidação e cálculo em centavos terão testes unitários rápidos na camada de domínio.
- Testes de integração usarão SQLite real com as mesmas restrições, índices, pragmas e migrações da aplicação. Banco em memória não substituirá cenários em que WAL, processos ou durabilidade importam.
- Testes transacionais cobrirão abertura implícita, cancelamento integral, Fechamento, rollback e rejeição de mutações em Atendimento encerrado.
- Testes de concorrência cobrirão dois primeiros lançamentos simultâneos, múltiplos garçons no mesmo Atendimento e a corrida entre Lançamento e Fechamento.
- Testes de revisão desatualizada comprovarão que o Caixa não confirma um total antigo e recebe o resumo atualizado antes de tentar novamente.
- Testes de idempotência cobrirão reenvio idêntico, chaves diferentes para ações intencionais, reutilização incompatível da mesma chave e persistência da deduplicação após reinício.
- Testes de processo simularão encerramento abrupto antes e depois do commit para demonstrar ausência de estado parcial e permanência de dados confirmados.
- Testes dos comandos administrativos cobrirão backup seguro, retenção, backup anterior a migração, reset protegido, restauração e verificação de integridade.
- Testes de ponta a ponta pelo navegador cobrirão seleção de usuário, fluxo do Garçom, consulta do Caixa, cancelamento, conflito de versão, Fechamento, atualização periódica e indisponibilidade do backend.
- As interfaces serão verificadas em tamanhos representativos de celular e desktop nas versões atuais dos navegadores suportados.
- O roteiro de aceite já documentado é a referência inicial para o cenário completo. O leitor físico de código de barras será validado manualmente depois que o fluxo automatizado de entrada por teclado estiver estável.
- Como ainda não existe implementação anterior, não há suíte de código como precedente. O Glossário, os ADRs e os critérios de aceite são a fonte de verdade para nomes, invariantes e resultados esperados.
- Cada futuro ticket incluirá os testes correspondentes à sua responsabilidade e manterá a suíte verde; tickets exclusivamente destinados a “adicionar todos os testes depois” não são aceitáveis.

## Out of Scope

- Pagamentos, formas de pagamento, divisão de conta, descontos, acréscimos, taxa de serviço e gorjetas.
- Estoque, cozinha, emissão fiscal, cadastro de clientes, relatórios e integrações externas desnecessárias.
- Cadastro, edição ou exclusão de Produtos pela interface.
- Cadastro, gerenciamento, senha, recuperação de acesso ou autenticação real de usuários.
- Cancelamento por Caixa, aprovação gerencial de cancelamento, reabertura de Atendimento ou reversão de Fechamento.
- Busca geral, filtros ou relatórios de Atendimentos encerrados.
- Impressão de recibo, documento fiscal ou comanda operacional; somente a folha utilitária de códigos de barras faz parte da demonstração.
- Leitura de código de barras pelo celular, API ou driver específico para o leitor do Caixa.
- Operação offline, gravação local no navegador, fila de sincronização, resolução de conflitos, PWA offline ou arquitetura híbrida.
- WebSocket e atualização em tempo real por push.
- Hospedagem pública, nuvem obrigatória, múltiplas instâncias do backend e exposição automática da rede local.
- Docker obrigatório, inicialização automática com o Windows e instalador offline.
- Suporte a navegadores legados.
- Produtos por peso ou quantidades fracionárias.
- React, TypeScript, frontend independente ou microsserviços sem necessidade futura comprovada.

## Further Notes

- A operação futura sem internet externa permanece uma preocupação arquitetural. Servidor local, PWA, armazenamento no dispositivo, sincronização posterior e arquitetura híbrida poderão ser avaliados sem expandir este protótipo.
- Uma publicação externa futura exige autenticação real, autorização adequada e proteção das operações antes de remover a restrição de rede local confiável.
- Backup externo ou remoto deverá ser avaliado para proteger contra falha física ou perda do servidor; o backup local inicial não oferece essa proteção.
- Django, SQLite e a interface renderizada no servidor são escolhas da implementação inicial, não restrições permanentes do produto.
- A próxima etapa após aprovação desta especificação é usar `/to-tickets`, preservando integralmente a diretriz de decomposição fina registrada acima.

