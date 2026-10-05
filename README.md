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

## Direção arquitetural

O projeto mantém um único processo implantável. As responsabilidades serão separadas dentro do pacote `restaurante` conforme se tornarem concretas:

| Área | Representação atual |
| --- | --- |
| Domínio | Ainda não criada; este ticket não possui regras de negócio. |
| Aplicação/casos de uso | Ainda não criada; será adicionada com o primeiro caso de uso. |
| Persistência | Ainda não criada; este ticket não persiste conceitos do domínio. |
| Interface web | Páginas, rotas, templates e recursos estáticos em `interface_web`. |
| Ferramentas administrativas | Entrada versionada pelo `manage.py`; comandos próprios serão adicionados somente quando necessários. |
| Infraestrutura | Configuração e entradas ASGI/WSGI em `infraestrutura`. |

Essa ausência intencional de pacotes vazios evita antecipar abstrações. Cada área ganhará código quando um ticket introduzir uma responsabilidade real.
