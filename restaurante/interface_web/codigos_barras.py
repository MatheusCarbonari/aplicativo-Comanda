"""Gera a representação vetorial local dos códigos da folha de teste."""

from dataclasses import dataclass


PADROES_CODE_128 = (
    "212222", "222122", "222221", "121223", "121322", "131222",
    "122213", "122312", "132212", "221213", "221312", "231212",
    "112232", "122132", "122231", "113222", "123122", "123221",
    "223211", "221132", "221231", "213212", "223112", "312131",
    "311222", "321122", "321221", "312212", "322112", "322211",
    "212123", "212321", "232121", "111323", "131123", "131321",
    "112313", "132113", "132311", "211313", "231113", "231311",
    "112133", "112331", "132131", "113123", "113321", "133121",
    "313121", "211331", "231131", "213113", "213311", "213131",
    "311123", "311321", "331121", "312113", "312311", "332111",
    "314111", "221411", "431111", "111224", "111422", "121124",
    "121421", "141122", "141221", "112214", "112412", "122114",
    "122411", "142112", "142211", "241211", "221114", "413111",
    "241112", "134111", "111242", "121142", "121241", "114212",
    "124112", "124211", "411212", "421112", "421211", "212141",
    "214121", "412121", "111143", "111341", "131141", "114113",
    "114311", "411113", "411311", "113141", "114131", "311141",
    "411131", "211412", "211214", "211232", "2331112",
)
CODIGO_INICIO_B = 104
CODIGO_PARADA = 106
MARGEM_SILENCIOSA = 10


@dataclass(frozen=True)
class Barra:
    x: int
    largura: int


@dataclass(frozen=True)
class CodigoBarrasCode128:
    identificador: str
    barras: tuple[Barra, ...]
    largura: int


def gerar_code_128(identificador: str) -> CodigoBarrasCode128:
    """Codifica texto ASCII imprimível usando o conjunto B do Code 128."""
    valores = [ord(caractere) - 32 for caractere in identificador]
    if not valores or any(valor < 0 or valor > 94 for valor in valores):
        raise ValueError("Code 128 B exige texto ASCII imprimível.")

    checksum = (
        CODIGO_INICIO_B
        + sum(
            posicao * valor
            for posicao, valor in enumerate(valores, start=1)
        )
    ) % 103
    codigos = (CODIGO_INICIO_B, *valores, checksum, CODIGO_PARADA)

    barras = []
    posicao_x = MARGEM_SILENCIOSA
    for codigo in codigos:
        for indice, modulo in enumerate(PADROES_CODE_128[codigo]):
            largura = int(modulo)
            if indice % 2 == 0:
                barras.append(Barra(x=posicao_x, largura=largura))
            posicao_x += largura

    return CodigoBarrasCode128(
        identificador=identificador,
        barras=tuple(barras),
        largura=posicao_x + MARGEM_SILENCIOSA,
    )
