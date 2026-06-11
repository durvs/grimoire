import hashlib
import re

RULE_CATEGORIES = {"validation", "calculation", "policy", "workflow", "other"}

# Sinais de que um chunk carrega regra de negócio: condicionais, guards,
# comparações e validações. Heurística barata — recall > precisão.
_SIGNAL_RE = re.compile(
    r"\b(if|elif|else|switch|case|when|raise|throw|assert|validate\w*|must|deve\w*|"
    r"limite?s?|max\w*|min\w*|required|obrigat\w+)\b"
    r"|==|!=|>=|<=|(?<![-=>])>(?!>)|(?<!<)<(?!<)|%"
)

# Detecta caminhos de teste por padrões precisos (word-boundary discipline):
# - diretório tests/, test/, __tests__/, specs/, spec/ em qualquer nível
# - arquivo com sufixo _test., .test., .spec.
# - arquivo com prefixo test_ (após / ou início)
# NÃO bate em "contest", "attestation", "contest_winner.py" etc.
_TEST_PATH_RE = re.compile(
    r"(^|/)(tests?|__tests__|specs?)(/|$)|_test\.|\.test\.|\.spec\.|(^|/)test_"
)


def rule_signal_score(text: str) -> float:
    """Densidade de sinais de regra por linha não-vazia."""
    lines = [l for l in text.splitlines() if l.strip()]
    if not lines:
        return 0.0
    return len(_SIGNAL_RE.findall(text)) / len(lines)


def is_test_path(rel_path: str) -> bool:
    return bool(_TEST_PATH_RE.search(rel_path))


def rule_id(file_path: str, rule_text: str) -> str:
    return hashlib.sha256(f"{file_path}\n{rule_text}".encode()).hexdigest()[:12]


EXTRACTION_INSTRUCTIONS = """\
Você vai extrair REGRAS DE NEGÓCIO dos chunks de código a seguir.

Uma regra de negócio é um comportamento observável do domínio — algo que um
analista escreveria num requisito: validações ("CPF deve ter 11 dígitos"),
cálculos ("desconto de 10% para totais acima de 100"), políticas ("pedido
cancelado não pode ser reaberto"), fluxos ("aprovação exige dois revisores").
NÃO são regras: detalhes de implementação (cache, retry, logging, naming),
tratamento genérico de erro, ou estrutura de dados sem semântica de domínio.

Para cada regra encontrada, produza um objeto:
- "rule": enunciado claro em linguagem natural, no idioma predominante do projeto
- "category": validation | calculation | policy | workflow | other
- "file": exatamente o campo `file` do chunk de origem
- "start_line"/"end_line": as linhas DENTRO do chunk que evidenciam a regra
- "confidence": 0.0 a 1.0 — quão certo você está de que é regra de domínio real

Um chunk pode ter zero, uma ou várias regras. Não invente regra de chunk que
não tem semântica de negócio. Ao terminar o lote, chame a tool `save_rules`
com a lista; itens inválidos voltam em `rejected` com o motivo — corrija e
re-envie só esses. Se `next_cursor` não for null, chame `extract_rules` de
novo com ele para continuar.
"""
