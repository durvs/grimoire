import pytest

SAMPLE_PY = '''import re

CPF_RE = re.compile(r"\\d{11}")


def validate_cpf(cpf: str) -> bool:
    """Valida formato de CPF (11 dígitos)."""
    return bool(CPF_RE.fullmatch(cpf))


def format_document(doc: str) -> str:
    return doc.strip().replace(".", "").replace("-", "")


class UserService:
    def __init__(self, repo):
        self.repo = repo

    def get_user_by_id(self, user_id: int):
        return self.repo.find(user_id)
'''

SAMPLE_TS = '''export function getUserById(id: number): Promise<User> {
  return api.get(`/users/${id}`);
}

export class OrderService {
  calculateDiscount(total: number): number {
    return total > 100 ? total * 0.1 : 0;
  }
}
'''

SAMPLE_MD = '''# Projeto

Visão geral do projeto.

## Regras de negócio

Desconto de 10% acima de 100 reais.

## Setup

Rode npm install.
'''


@pytest.fixture
def sample_repo(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "users.py").write_text(SAMPLE_PY)
    (tmp_path / "src" / "orders.ts").write_text(SAMPLE_TS)
    (tmp_path / "README.md").write_text(SAMPLE_MD)
    (tmp_path / ".gitignore").write_text("secret.txt\n")
    (tmp_path / "secret.txt").write_text("senha123")
    (tmp_path / "logo.bin").write_bytes(b"\x00\x01\x02binary")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "lib.js").write_text("ignored")
    return tmp_path
