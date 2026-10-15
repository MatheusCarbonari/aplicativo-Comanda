class QuantidadeInvalida(ValueError):
    pass


def validar_quantidade(valor: object) -> int:
    if isinstance(valor, bool) or not isinstance(valor, (int, str)):
        raise QuantidadeInvalida
    try:
        quantidade = int(valor)
    except ValueError as erro:
        raise QuantidadeInvalida from erro
    if quantidade <= 0:
        raise QuantidadeInvalida
    return quantidade
