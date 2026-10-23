# Aplicativo de restaurante

Protótipo web responsivo para o fluxo de comandas do restaurante. A implementação inicial usa Python, Django, Django Templates e SQLite em um monólito modular.

## Preparar o ambiente

Requer Python 3.12 ou mais recente. No Windows PowerShell:

```powershell
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Em Linux, os comandos equivalentes usam `python3` e `.venv/bin/python`.

## Iniciar na rede local

Depois da instalação e da preparação inicial do banco, inicie o servidor com um
único comando na raiz do projeto:

```powershell
.\scripts\iniciar_servidor.ps1
```

O wrapper localiza a raiz mesmo quando chamado a partir de outro diretório, usa
exclusivamente `.venv\Scripts\python.exe` e executa o Django em
`0.0.0.0:8000`, sem autoreload. Ele não executa migration, carga ou reset de
dados. A saída mostra a URL de loopback, a verificação de saúde e uma URL para
cada IPv4 local encontrado. Se o Django falhar, o script termina com o mesmo
código de erro.

No computador servidor, descubra o IPv4 atual com:

```powershell
ipconfig
```

Procure o `Endereço IPv4` do adaptador Ethernet ou Wi-Fi usado pela rede local,
sem usar endereços de loopback ou autoconfiguração `169.254.x.x`. Em outro
celular ou computador conectado à mesma LAN, abra:

```text
http://<IPv4-do-servidor>:8000/
```

O bind `0.0.0.0:8000` recebe conexões IPv4 nas interfaces do servidor; a regra
de firewall abaixo restringe a entrada ao perfil privado e à sub-rede local.
Para uma URL previsível, mantenha o IPv4 local estável por **reserva DHCP** no
roteador ou por configuração administrada do computador. O projeto não altera
essas configurações automaticamente.

### Firewall do Windows

Primeiro classifique a rede do restaurante como privada. Depois, em um
PowerShell aberto explicitamente como administrador, crie somente a regra TCP
necessária para a porta da aplicação:

```powershell
New-NetFirewallRule -DisplayName "Restaurante-LAN-8000" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8000 -Profile Private -RemoteAddress LocalSubnet
```

Verifique ou remova a regra, se a instalação deixar de servir a aplicação:

```powershell
Get-NetFirewallRule -DisplayName "Restaurante-LAN-8000"
Remove-NetFirewallRule -DisplayName "Restaurante-LAN-8000"
```

O script de inicialização nunca cria essa regra silenciosamente e nunca
desabilita o firewall. Use a aplicação somente em **rede local confiável**. Não
publique a porta na internet, não configure **port forwarding**, não ative
**UPnP**, túnel ou hospedagem externa. A operação normal não depende de internet
externa.

### Verificar servidor e persistência

Com o servidor em execução, confirme que o processo responde e que o banco está
acessível:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/saude/
```

O resultado esperado é `status: ok`. Em seguida, abra a página principal pelo
IPv4 da LAN. A interface usa CSS, JavaScript e códigos de barras distribuídos
com o próprio projeto; não há fonte, biblioteca, asset obrigatório ou **CDN**
externa.

Os dados operacionais permanecem dentro da instalação, fora de diretórios
temporários:

- `.local/dados/`: banco SQLite operacional;
- `.local/backups/`: backups manuais, diários, pré-migração e preservações;
- `.local/logs/`: log estruturado com rotação.

Esses diretórios não dependem de internet externa. O banco deve permanecer no
disco local do servidor, nunca em compartilhamento de rede.

### Diferenças mínimas no Linux

No Linux, instale as dependências na `.venv`, use o Python em `.venv/bin/` e
inicie o mesmo processo a partir da raiz:

```bash
.venv/bin/python manage.py runserver 0.0.0.0:8000 --noreload
```

O administrador deve liberar TCP/8000 somente para a sub-rede local confiável
no firewall disponível, por exemplo com uma regra `ufw` que informe
explicitamente o CIDR da LAN. O bind, a URL
`http://<IPv4-do-servidor>:8000/` e os diretórios `.local/dados/`,
`.local/backups/` e `.local/logs/` permanecem iguais. Este procedimento não
instala serviço `systemd`.

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

### Verificar durabilidade após encerramento abrupto

A verificação em nível de processo usa bancos SQLite persistentes e isolados em
`.local/testes/`, aplica as migrations reais e confirma `journal_mode=WAL` e
`synchronous=FULL`. Execute-a com:

```powershell
.venv\Scripts\python.exe manage.py test restaurante.aplicacao.test_durabilidade_encerramento_abrupto
```

O processo pai aguarda mensagens JSON explícitas do auxiliar. O sinal
`antes_commit` é emitido dentro de uma transação externa ainda aberta; o sinal
`depois_commit` só aparece depois que essa transação termina e o commit efetivo
foi confirmado. Em ambos os pontos, o pai usa encerramento abrupto real do
processo e outro processo Django reabre o mesmo arquivo para consultar o estado
persistido. Os logs eventualmente produzidos ficam no diretório temporário do
cenário, separados do log operacional.

Essa simulação comprova o comportamento do processo com SQLite em WAL e
`synchronous=FULL`, mas matar um processo não equivale a uma queda física de
energia. Ela não reproduz perda de energia durante o flush do hardware, cache
volátil de disco ou controladora, nem falha física de armazenamento.

## Logs locais

A aplicação grava logs estruturados em JSONL, uma linha JSON por evento, no
arquivo persistente `.local/logs/restaurante.jsonl`. Cada registro contém
`timestamp`, `level` e `event`; operações confirmadas acrescentam somente
identificadores técnicos úteis, como `operation_id`, `atendimento_id`,
`lancamento_id`, `cancelamento_id` e `usuario_operacional_id` quando aplicáveis.

O arquivo gira ao atingir 5 MiB. São mantidos cinco backups, nomeados de
`restaurante.jsonl.1` a `restaurante.jsonl.5`; quando o limite é excedido, o
backup mais antigo é descartado pela rotação padrão do Python. Para consultar os
eventos mais recentes no PowerShell:

```powershell
Get-Content .local\logs\restaurante.jsonl -Tail 100
```

Os logs não recebem nome do Produto, quantidade, preço, subtotal, Total, motivo
ou descrição de cancelamento, conteúdo de formulários, cookies, sessão, CSRF,
credenciais ou headers sensíveis. Erros registram o tipo da exceção e o stack
trace técnico sem copiar a mensagem da exceção.

Somente o processo operacional que serve a aplicação registra
`aplicacao_iniciada` e tenta registrar `aplicacao_encerrada` no encerramento
normal. No `runserver`, o processo auxiliar do autoreload é ignorado; entradas
WSGI/ASGI e `runserver --noreload` também são reconhecidos como operacionais.
Testes e comandos administrativos como `check` e `makemigrations` não geram esse
ciclo no log operacional. Durante `manage.py test`, qualquer outro evento usa um
arquivo isolado por processo sob `.local/testes/`.

Uma interrupção abrupta do processo ou do computador pode impedir o evento de
encerramento. Falhas ao abrir, formatar, girar ou escrever o log são ignoradas
pela fronteira de observabilidade e não mudam o commit, rollback ou resultado de
uma operação de domínio. Eventos de sucesso das mutações são agendados somente
para depois do commit efetivo; um rollback externo descarta o evento pendente.

## Backup SQLite manual

Para criar um snapshot consistente do banco SQLite em uso, execute:

```powershell
.venv\Scripts\python.exe manage.py criar_backup
```

O comando usa `sqlite3.Connection.backup()` e grava a cópia em
`.local/backups/`. O nome inclui data e horário UTC com microssegundos, por
exemplo `restaurante-20261021T173045123456Z.sqlite3`. Uma colisão recebe um
sufixo numérico e nunca substitui silenciosamente um arquivo existente.

A cópia é criada primeiro com a extensão `.incompleto`. Depois que a conexão
de destino é fechada, o comando reabre o arquivo e exige que
`PRAGMA integrity_check` retorne `ok`; somente então publica o nome `.sqlite3`.
Em caso de falha, o comando retorna erro, tenta remover o artefato temporário e
não altera o banco operacional. Se a remoção também falhar, o nome
`.incompleto` deixa claro que o arquivo não deve ser usado como backup válido.

Os logs estruturados registram `backup_sqlite_iniciado`,
`backup_sqlite_concluido` ou `backup_sqlite_falhou`, usando somente o
identificador técnico da execução, o nome do arquivo validado no sucesso e o
tipo do erro na falha. O conteúdo do banco não é registrado. Esses backups
locais não protegem contra perda ou falha física do mesmo computador.

## Migrações com backup

Para aplicar migrations no banco operacional, use o procedimento único:

```powershell
.venv\Scripts\python.exe manage.py migrar_com_backup
```

O comando cria e valida primeiro um backup pelo mesmo mecanismo de
`criar_backup`. A cópia é publicada como
`restaurante-pre-migracao-<timestamp UTC>.sqlite3`, portanto não participa da
retenção dos backups diários. Somente depois da publicação o comando público
`migrate` do Django é executado. Argumentos usuais continuam disponíveis, por
exemplo `migrar_com_backup persistencia 0008`.

Se o backup falhar, nenhuma migration começa. Se a migration falhar, o backup
já confirmado permanece disponível e não há tentativa automática de restore.

## Restaurar um backup

A restauração é um procedimento administrativo e não aparece na interface
operacional. Primeiro, pare completamente a aplicação e confirme que nenhum
processo web continua aceitando operações. Então escolha explicitamente uma
cópia publicada e execute, na raiz do projeto:

```powershell
.venv\Scripts\python.exe manage.py restaurar_backup --arquivo <caminho-do-backup> --confirmar-aplicacao-parada
```

Sem `--confirmar-aplicacao-parada`, o comando recusa a execução antes de tocar
nos arquivos. A confirmação é uma responsabilidade operacional: ela não tenta
substituir a parada real do servidor por um lock interno frágil. Depois de
fechar sua própria conexão Django, o comando também recusa resíduos `-wal` ou
`-shm`, que indicam uma condição insegura para a troca.

O backup escolhido é aberto em modo somente leitura e precisa passar por
`PRAGMA integrity_check`. Arquivos `.incompleto` nunca são aceitos. Antes da
troca, o banco operacional atual é copiado, validado e publicado em
`.local/backups/` como
`restaurante-antes-restauracao-<timestamp UTC>.sqlite3`. O backup escolhido é
preparado em um arquivo temporário no diretório do banco e publicado
atomicamente no caminho operacional. O novo banco é reaberto e somente é
declarado restaurado quando uma segunda verificação de integridade retorna
`ok`.

Se a publicação falhar, o banco anterior continua no caminho operacional e a
cópia preservada permanece disponível. Se a verificação posterior falhar, o
comando tenta recolocar atomicamente o banco anterior; se isso não for seguro,
informa o caminho da cópia recuperável ao operador. Não copie arquivos `-wal`
ou `-shm` manualmente.

Depois de uma restauração concluída, reinicie a aplicação antes de voltar a
aceitar operações. O reinício cria conexões novas e impede que qualquer estado
em memória ou conexão anterior seja reutilizado com o banco substituído.

## Backup diário no Windows

O comando diário reutiliza o backup seguro acima e, somente depois do sucesso,
mantém os sete arquivos `restaurante-*.sqlite3` mais recentes:

```powershell
.venv\Scripts\python.exe manage.py executar_backup_diario
```

O script `scripts\executar_backup_diario.ps1` define o diretório de trabalho
como a raiz do projeto e usa o Python de `.venv`. Para instalar uma tarefa
diária às 03:00, abra o PowerShell como administrador na raiz do projeto e
execute:

```powershell
$raiz = (Resolve-Path .).Path
$acao = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$raiz\scripts\executar_backup_diario.ps1`""
schtasks.exe /Create /TN "Restaurante-BackupDiario" /SC DAILY /ST 03:00 /RU SYSTEM /RL HIGHEST /TR $acao /F
```

Para conferir a configuração e, opcionalmente, disparar uma execução de teste:

```powershell
schtasks.exe /Query /TN "Restaurante-BackupDiario" /V /FO LIST
schtasks.exe /Run /TN "Restaurante-BackupDiario"
```

Para remover o agendamento:

```powershell
schtasks.exe /Delete /TN "Restaurante-BackupDiario" /F
```

O lock local impede duas execuções de `executar_backup_diario` ao mesmo tempo.
Uma segunda execução termina com erro compreensível e não inicia backup ou
retenção. A retenção reconhece somente nomes válidos com timestamp UTC e ignora
arquivos `.incompleto`; se o backup falhar, nenhum backup antigo é removido.

A lógica do comando não depende do Agendador de Tarefas. Em uma implantação
Linux futura, o mesmo `.venv/bin/python manage.py executar_backup_diario` poderá
ser chamado por `cron` ou `systemd timer`, sem alterar backup ou retenção. Este
ticket não instala um scheduler Linux.

## Preparar banco e dados iniciais

Crie ou atualize somente a estrutura do banco:

```powershell
.venv\Scripts\python.exe manage.py migrar_com_backup
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

### Reinicializar dados de desenvolvimento

O reset completo é exclusivo do ambiente de desenvolvimento com `DEBUG=True`,
nunca roda no startup e não aparece na interface web. Execute explicitamente:

```powershell
.venv\Scripts\python.exe manage.py reinicializar_dados_desenvolvimento
```

O comando avisa que removerá Atendimentos, Lançamentos, Cancelamentos,
registros de idempotência, sessões, Comandas físicas, Produtos e Usuários
operacionais. Para prosseguir, é necessário digitar exatamente
`REINICIALIZAR`; qualquer outra resposta termina sem backup ou alteração no
banco.

Depois da confirmação, o comando reutiliza `criar_backup` e somente inicia a
limpeza quando o snapshot foi validado e publicado em `.local/backups/`. Em
seguida, remove os dados listados e chama `carregar_dados_iniciais` para recriar
as Comandas `001` a `020`, os Produtos e os Usuários operacionais aprovados no
Ticket 03.

A limpeza e a recriação acontecem na mesma transação. Se qualquer inserção
falhar, o rollback restaura integralmente o estado anterior; o backup já
confirmado permanece disponível para diagnóstico ou recuperação manual.

## Validar volume e concorrência

A verificação pesada é executada explicitamente e não faz parte da suíte rápida:

```powershell
.venv\Scripts\python.exe manage.py validar_volume_concorrencia
```

O comando cria um banco SQLite temporário exclusivo, aplica as migrations reais,
confirma `journal_mode=WAL` e `synchronous=FULL` e prepara pelo ORM pelo menos
10.000 Lançamentos. Em seguida, dez dispositivos simulados, cada um com sua
própria conexão Django, iniciam de uma barreira comum e exercitam os casos de uso
públicos de registro de Lançamento adicional, consulta e Fechamento. Uma chave é
repetida para validar a idempotência sem duplicar o Lançamento.

O resumo no terminal e o JSON criado em `.local/relatorios/` registram data UTC,
sistema operacional, versões de Python, Django e SQLite, seed, configuração do
banco, volume, dispositivos, resultados das operações, `SQLITE_BUSY`,
`SQLITE_LOCKED`, retries e tempos mínimo, mediano, p95 e máximo medidos com
relógio monotônico. O p95 é comparado informativamente com a meta prática de
aproximadamente um segundo; uma operação isolada mais lenta não reprova o teste.

A execução falha se encontrar Atendimento aberto duplicado, Total diferente dos
Lançamentos válidos persistidos, desaparecimento de Lançamento confirmado,
Lançamento posterior ao Fechamento, duplicação idempotente, Comanda que deveria
estar disponível ou falha no `PRAGMA integrity_check`. O banco e o log usados no
cenário são removidos ao final e não se misturam aos dados ou logs operacionais.
Threads locais simulam os clientes concorrentes; latência de Wi-Fi e o hardware
reais do restaurante podem produzir tempos diferentes.

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
