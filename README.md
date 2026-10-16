# Aplicativo de restaurante

Protótipo web responsivo para o fluxo de comandas do restaurante. A implementação inicial usa Python, Django, Django Templates e SQLite em um monólito modular.

## Preparar o ambiente

Requer Python 3.12 ou mais recente. No Windows PowerShell:

```powershell
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Em Linux, os comandos equivalentes usam `python3` e `.venv/bin/python`.

## Iniciar

Depois de instalar as dependências:

```powershell
.venv\Scripts\python.exe manage.py runserver
```

A página-base fica disponível em `http://127.0.0.1:8000/`. A exposição controlada à rede local será tratada em um ticket posterior.

## Saúde do backend

O endpoint técnico `GET /saude/` verifica se o processo Django responde e se a
conexão com o banco executa uma consulta somente leitura `SELECT 1`. Uma resposta
saudável retorna HTTP 200 com `{"status": "ok"}`. Se a verificação da
persistência falhar, retorna HTTP 503 com `{"status": "indisponivel"}`, sem
detalhes internos. O endpoint não depende de sessão ou Usuário operacional.

## Testar

```powershell
.venv\Scripts\python.exe manage.py test
```

## Preparar banco e dados iniciais

Crie ou atualize somente a estrutura do banco:

```powershell
.venv\Scripts\python.exe manage.py migrate
```

Depois, execute explicitamente a carga de demonstração:

```powershell
.venv\Scripts\python.exe manage.py carregar_dados_iniciais
```

O comando procura cada Comanda física pelo identificador e cada Produto ou
Usuário operacional pelo nome. Ele cria somente os registros ausentes: não
sobrescreve preços ou papéis alterados, não remove registros extras e pode ser
executado novamente sem produzir duplicatas. Iniciar o Django, importar módulos
ou executar a migração estrutural não dispara essa carga automaticamente.

## Seleção do usuário operacional

A escolha feita na tela inicial é mantida pela sessão padrão do Django. O
navegador recebe somente o identificador opaco da sessão; no servidor, a sessão
guarda o identificador persistido do Usuário operacional. A cada requisição, a
aplicação busca novamente esse usuário no banco e utiliza o papel armazenado no
registro para escolher a interface.

Essa seleção serve apenas para o fluxo operacional do protótipo e não representa
autenticação. Operações futuras deverão carregar e validar novamente o Usuário
operacional no backend. A ação `Trocar usuário` remove somente essa seleção.

## Consultar uma comanda

Garçom e Caixa podem consultar uma Comanda física pelo identificador textual na
própria experiência operacional. A consulta usa GET, preserva zeros à esquerda e
somente informa se a Comanda está disponível, em atendimento ou não existe. Ela
não cria Comanda, Atendimento ou qualquer outro registro.

O modelo Atendimento representa somente os estados `ABERTO` e `ENCERRADO` nesta
etapa. Uma restrição condicional no SQLite permite vários atendimentos encerrados,
mas impede mais de um Atendimento aberto para a mesma Comanda física.

### Validar um leitor de código de barras

O leitor deve estar configurado para operar como teclado e enviar `Enter` depois
do código. Para uma validação manual futura com o dispositivo físico:

1. abra a tela do Caixa;
2. confirme que o foco está no campo Identificador da comanda;
3. escaneie o código;
4. confirme que o leitor escreveu o identificador e enviou `Enter`;
5. verifique que foi executada a mesma consulta usada na digitação manual.

Não há integração direta com o hardware: digitação, leitura seguida de
`Enter` e clique em `Consultar` submetem o mesmo formulário HTTP `GET`.

### Imprimir a folha de códigos de teste

Com os dados iniciais carregados, abra
`http://127.0.0.1:8000/utilitarios/codigos-barras/`. A página usa somente HTML,
SVG e CSS locais e apresenta as Comandas `001` a `020`; ela é exclusiva para
desenvolvimento e demonstração, não sendo recibo, documento fiscal ou Comanda
operacional.

Para validar a impressão e a leitura física:

1. abra a folha no navegador e acione a impressão em papel A4;
2. mantenha a escala em 100%, sem ajustar o conteúdo à página;
3. abra a tela do Caixa e posicione o foco no campo Identificador da comanda;
4. leia alguns códigos impressos, incluindo `001` e `020`;
5. confirme que cada leitura preserva os três caracteres e executa a consulta
   correspondente.

## Registrar o primeiro lançamento

Na experiência do Garçom, o formulário de primeiro lançamento recebe o
Identificador da comanda, um Produto do catálogo e uma quantidade inteira
positiva. A operação cria o Atendimento aberto e o Lançamento na mesma transação
curta. Caixa não recebe nem pode executar essa ação.

O Lançamento preserva o Produto, a quantidade, o preço unitário vigente em
centavos, o Garçom responsável e o horário definido pelo backend. Alterações
posteriores no preço do Produto não modificam o preço registrado. A proteção de
unicidade do Atendimento aberto permanece no SQLite. Quando duas primeiras
solicitações observam simultaneamente uma Comanda disponível, somente uma cria o
Atendimento; a outra reconhece especificamente a violação dessa unicidade,
localiza o Atendimento vencedor e registra nele seu Lançamento. Uma solicitação
enviada pelo fluxo de primeiro Lançamento também converge dessa forma se a
abertura concorrente já tiver acabado de confirmar; o fluxo de Lançamento
adicional continua separado para a operação normal de uma Comanda em atendimento.

O SQLite aguarda contenções de escrita pelo tempo configurado na conexão. Se
ainda devolver `SQLITE_BUSY` ou `SQLITE_LOCKED`, o primeiro Lançamento faz somente
uma nova tentativa, totalizando no máximo duas. Cada tentativa envolve a mesma
chave idempotente e uma transação completa: se a primeira foi revertida, nada
parcial permanece; se chegou a confirmar, a repetida recupera o resultado sem
duplicar o Lançamento. Persistindo a contenção, a interface informa
indisponibilidade temporária para que o Garçom tente novamente.

Quando a consulta encontra uma Comanda em atendimento, a interface do Garçom
permite adicionar outro consumo ao Atendimento aberto existente. Cada confirmação
cria um novo Lançamento, inclusive para o mesmo Produto, e preserva separadamente
quantidade, preço registrado, autor e horário. Nenhum Atendimento é criado por
essa operação.

O Total atual é calculado em centavos pela soma de `quantidade × preço unitário
registrado` dos Lançamentos válidos do Atendimento. Lançamentos cancelados
permanecem persistidos, mas deixam de compor o Total. O cálculo não usa o preço
atual do catálogo e o valor é formatado em reais somente na interface.

Cada registro de Lançamento recebe uma chave de idempotência opaca gerada pela
interface. O backend combina essa chave com uma identidade estável da operação e
com o SHA-256 de um JSON canônico dos dados que definem a intenção. A mudança de
domínio e o resultado reutilizável são confirmados na mesma transação SQLite.
Repetir a mesma chave com a mesma intenção retorna o resultado original; reutilizar
a chave com operação ou conteúdo diferente é rejeitado. Chaves diferentes continuam
representando ações intencionais distintas.

O formulário desabilita seu botão após um envio válido para reduzir toques duplos,
mas essa é apenas uma conveniência. A garantia efetiva está no registro persistente,
cuja chave possui unicidade no banco e continua válida após reiniciar a aplicação.

## Cancelar um lançamento

Na consulta de uma Comanda em atendimento, o Garçom pode cancelar integralmente
um Lançamento válido, inclusive quando outro Garçom o registrou. O registro
original não é alterado nem apagado: um `CancelamentoLancamento` separado preserva
motivo, descrição, autor e horário. O motivo é obrigatório e deve ser Duplicado,
Produto incorreto, Quantidade incorreta, Desistência ou Outro; para Outro, uma
descrição também é obrigatória.

Cada Lançamento aceita no máximo um cancelamento por uma relação única protegida
pelo SQLite. A operação usa a identidade idempotente `CANCELAR_LANCAMENTO`, de
modo que repetir a mesma solicitação retorna o resultado confirmado e uma chave
nova não cria um segundo cancelamento. Caixa, Atendimento encerrado, Lançamento
inexistente e Lançamento já cancelado são rejeitados pelo backend. Não existe
cancelamento parcial: para corrigir uma quantidade, cancela-se o Lançamento inteiro
e registra-se outro.

## Persistência SQLite

O banco operacional fica em `.local/dados/restaurante.sqlite3`, um diretório
persistente e conhecido dentro da instalação do servidor central. Esse arquivo
pertence exclusivamente ao processo da aplicação no servidor:

- celulares e outros computadores acessam os dados somente pelo backend;
- o arquivo não deve ser colocado em pasta de rede compartilhada;
- cada conexão aplica e verifica `journal_mode=WAL` e `synchronous=FULL`;
- transações de escrita devem ser explícitas e curtas para reduzir contenção;
- a solução não pode depender de bloqueio de linha ou de `SELECT FOR UPDATE`,
  pois esse mecanismo não oferece a garantia esperada no SQLite.

O diretório `.local/` contém dados de execução e não é versionado. Backups,
restauração e comandos administrativos serão tratados em tickets próprios.

## Direção arquitetural

O projeto mantém um único processo implantável. As responsabilidades serão separadas dentro do pacote `restaurante` conforme se tornarem concretas:

| Área | Representação atual |
| --- | --- |
| Domínio | Validação da quantidade inteira positiva de um Lançamento em `dominio`. |
| Aplicação/casos de uso | Consulta da Comanda física e registro transacional do primeiro Lançamento em `aplicacao`. |
| Persistência | Configuração do SQLite e modelos persistidos, incluindo Atendimento e Lançamento, em `persistencia`. |
| Interface web | Páginas, rotas, templates e recursos estáticos em `interface_web`. |
| Ferramentas administrativas | Entrada pelo `manage.py` e comando explícito `carregar_dados_iniciais`. |
| Infraestrutura | Configuração e entradas ASGI/WSGI em `infraestrutura`. |

Essa ausência intencional de pacotes vazios evita antecipar abstrações. Cada área ganhará código quando um ticket introduzir uma responsabilidade real.
