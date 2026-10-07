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
| Domínio | Ainda não criada; este ticket não possui regras de negócio. |
| Aplicação/casos de uso | Ainda não criada; será adicionada com o primeiro caso de uso. |
| Persistência | Configuração concreta do SQLite e modelos persistidos em `persistencia`. |
| Interface web | Páginas, rotas, templates e recursos estáticos em `interface_web`. |
| Ferramentas administrativas | Entrada pelo `manage.py` e comando explícito `carregar_dados_iniciais`. |
| Infraestrutura | Configuração e entradas ASGI/WSGI em `infraestrutura`. |

Essa ausência intencional de pacotes vazios evita antecipar abstrações. Cada área ganhará código quando um ticket introduzir uma responsabilidade real.
