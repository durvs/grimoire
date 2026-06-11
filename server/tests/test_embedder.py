import pytest


@pytest.mark.slow
def test_real_model_embeds_384_dims():
    from grimoire_mcp.embedder import embed_texts

    vecs = embed_texts(["onde valida CPF?", "def validate_cpf(cpf):"])
    assert len(vecs) == 2
    assert len(vecs[0]) == 384
