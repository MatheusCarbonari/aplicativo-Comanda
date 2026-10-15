from restaurante.persistencia.models import UsuarioOperacional


class UsuarioOperacionalInvalido(Exception):
    pass


class PapelNaoPermitido(Exception):
    pass


def buscar_garcom(usuario_operacional_id: object) -> UsuarioOperacional:
    try:
        chave_usuario = int(usuario_operacional_id)
    except (TypeError, ValueError) as erro:
        raise UsuarioOperacionalInvalido from erro
    usuario = UsuarioOperacional.objects.filter(pk=chave_usuario).first()
    if usuario is None:
        raise UsuarioOperacionalInvalido
    if usuario.papel != UsuarioOperacional.Papel.GARCOM:
        raise PapelNaoPermitido
    return usuario
