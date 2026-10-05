# Comandas de restaurante

Vocabulário do fluxo de registro e consulta de consumo associado a comandas físicas.

## Language

**Comanda física**:
Artefato reutilizável entregue durante o atendimento, identificado por um número único e pelo código de barras equivalente.
_Avoid_: Cartão, ficha

**Comanda disponível**:
Comanda física que não possui atendimento aberto e pode iniciar um novo atendimento a partir do primeiro lançamento válido.
_Avoid_: Comanda livre

**Comanda em atendimento**:
Comanda física associada ao seu único atendimento aberto.
_Avoid_: Comanda ocupada, comanda aberta

**Identificador da comanda**:
Texto único e permanente que identifica uma comanda física, preservando integralmente caracteres como zeros à esquerda.
_Avoid_: Número da comanda, valor do código de barras

**Atendimento**:
Utilização temporária de uma comanda física, que reúne os lançamentos de consumo entre sua abertura e seu fechamento.
_Avoid_: Comanda, conta

**Lançamento**:
Registro individual de um produto consumido, com sua quantidade e o preço unitário vigente no momento do registro.
_Avoid_: Linha consolidada, item do catálogo

**Lançamento válido**:
Lançamento que não foi cancelado e cujo valor participa do total do atendimento.
_Avoid_: Lançamento ativo

**Total do atendimento**:
Soma, em reais, da quantidade multiplicada pelo preço unitário registrado em cada lançamento válido.
_Avoid_: Saldo, valor da comanda

**Cancelamento de lançamento**:
Invalidação justificada de um lançamento de um atendimento aberto, preservando o registro original no histórico e excluindo seu valor do total.
_Avoid_: Exclusão, edição

**Fechamento**:
Encerramento definitivo de um atendimento, que preserva seu histórico e libera a comanda física para outro uso.
_Avoid_: Pagamento

**Produto**:
Item previamente cadastrado que pode ser registrado como consumo em um atendimento.
_Avoid_: Mercadoria

**Usuário operacional**:
Pessoa identificada como autora de uma ação no sistema e associada ao papel de Garçom ou Caixa.
_Avoid_: Conta autenticada

**Garçom**:
Pessoa que registra no atendimento os produtos consumidos.
_Avoid_: Atendente

**Caixa**:
Pessoa que consulta o atendimento associado a uma comanda física para conferir o consumo, o valor total e realizar o fechamento.
_Avoid_: Operador
