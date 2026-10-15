from restaurante.persistencia.models import UsuarioOperacional


class UsuarioOperacionalInvalido(Exception):
    pass


class PapelNaoPermitido(Exception):
    pass


def normalizar_identificador_usuario(
    usuario_operacional_id: object,
) -> int:
    try:
        return int(usuario_operacional_id)
    except (TypeError, ValueError) as erro:
        raise UsuarioOperacionalInvalido from erro


def buscar_garcom(usuario_operacional_id: object) -> UsuarioOperacional:
    chave_usuario = normalizar_identificador_usuario(usuario_operacional_id)
    usuario = UsuarioOperacional.objects.filter(pk=chave_usuario).first()
    if usuario is None:
        raise UsuarioOperacionalInvalido
    if usuario.papel != UsuarioOperacional.Papel.GARCOM:
        raise PapelNaoPermitido
    return usuario
