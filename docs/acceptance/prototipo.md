# Aceite do protótipo de comandas

Este documento registra os critérios transversais e o principal roteiro de demonstração. Ele complementa, mas não substitui, os testes automatizados do domínio, persistência e interface.

## Idioma e localização

- Interface em português do Brasil.
- Moeda BRL com formatação brasileira.
- Datas em `dd/MM/yyyy`.
- Horários em formato de 24 horas.
- Instantes apresentados no fuso `America/Sao_Paulo`.

## Operação sem internet externa

- Fontes, scripts, estilos, ícones e recursos necessários acompanham a aplicação.
- Com servidor, banco e rede local funcionando, perder a internet externa não degrada a interface operacional.
- A URL de acesso do servidor é apresentada claramente durante a instalação ou inicialização.

## Logs

- Logs estruturados em arquivos locais com rotação registram inicialização, encerramento, erros inesperados, falhas de banco, migrações, backups, restaurações, verificações de integridade e identificadores relevantes de operações.
- Os logs não reproduzem desnecessariamente os consumos nem funcionam como uma segunda cópia do banco.

## Direção visual

- Interface funcional, limpa e responsiva.
- Experiência mobile-first para o garçom e confortável em desktop para o caixa.
- Botões adequados ao toque, informações legíveis, estados da comanda evidentes e total em destaque.
- Confirmações claras para cancelamento e fechamento.
- Feedback imediato de sucesso, erro e perda de comunicação.
- Usabilidade operacional tem prioridade sobre branding, animações ou acabamento visual sofisticado.

## Roteiro principal

1. Selecionar `Garçom 1`.
2. Selecionar a comanda `001`, inicialmente disponível.
3. Realizar o primeiro lançamento e criar implicitamente um atendimento.
4. Adicionar outros produtos.
5. `Garçom 2` acessar a mesma comanda e realizar outro lançamento.
6. Cancelar um lançamento, informando um motivo obrigatório.
7. Verificar que o lançamento cancelado permanece no histórico e deixa de compor o total.
8. No computador do caixa, selecionar `Caixa 1`.
9. Consultar a comanda `001` usando um leitor físico de código de barras.
10. Conferir itens válidos consolidados, lançamentos cancelados e total.
11. Realizar um novo lançamento depois que o caixa já visualizou o resumo.
12. Confirmar que o sistema detecta a mudança e exige nova confirmação antes do fechamento.
13. Fechar o atendimento.
14. Exibir o resumo final.
15. Confirmar que a comanda física `001` voltou ao estado disponível.
16. Reiniciar abruptamente ou normalmente o servidor.
17. Confirmar que os dados persistidos continuam corretos.
18. Reenviar uma operação usando a mesma chave de idempotência e confirmar que não ocorre duplicidade.
19. Executar um backup.
20. Executar o procedimento administrativo de restauração e verificar a integridade do banco restaurado.
