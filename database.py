"""
Camada de banco de dados (SQLite) do Simulador de Importação Ricex.

Guarda o catálogo de produtos (origem: Fatto_a_Mano_2.xlsx, aba "1-Importacao")
e os parâmetros gerais padrão da operação (câmbio, frete, impostos etc,
origem: Fatto_a_Mano_1.xlsx, aba "Custos Importação").
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "ricex_importacao.db"

# Catálogo de produtos extraído de Fatto_a_Mano_2.xlsx -> aba "1-Importacao"
PRODUTOS_SEED = [
    # ref,   produto,                              composicao,                                   fob_usd, qtd_padrao
    ("A006", "Bermuda / Shorts Chino",              "98% Algodão / 2% Elastano",                   7.00, 1000),
    ("A011", "Calça Chino 100% Algodão",            "100% Algodão",                                 7.00, 1000),
    ("A005", "Calça Chino 98/2",                    "98% Algodão / 2% Elastano",                     8.00, 1000),
    ("A009", "Calça Social Grey Check",             "70% Poliéster / 28% Algodão / 2% Elastano",    10.00, 1000),
    ("A013", "Camisa 100% Algodão - Light Grey",    "100% Algodão",                                  7.00, 1000),
    ("A017", "Camisa 100% Algodão - Red",           "100% Algodão",                                  6.50, 1000),
    ("A015", "Camisa 100% Algodão - White",         "100% Algodão",                                  6.30, 1000),
    ("A019", "Camisa 97/3 - Black/White Check",     "97% Algodão / 3% Elastano",                     7.70, 1000),
    ("A016", "Camisa 97/3 - Brown",                 "97% Algodão / 3% Elastano",                     7.50, 1000),
    ("A014", "Camisa 97/3 - Dark Grey",             "97% Algodão / 3% Elastano",                     7.50, 1000),
    ("A012", "Camisa 97/3 - Wine",                  "97% Algodão / 3% Elastano",                     7.50, 1000),
    ("A020", "Camisa Listrada 97/3",                "97% Algodão / 3% Elastano",                     7.70, 1000),
    ("A003", "Jeans",                               "83% Algodão / 15% Poliéster / 2% Elastano",     8.30, 1000),
    ("A004", "Knitted Pants / Jogger",              "75% Poliéster / 25% Elastano",                  8.25, 1000),
    ("A002", "Polo Shirt",                          "50% Algodão / 50% Outros",                      6.45, 1000),
    ("A022", "Terno / Suit Premium",                "80% Poliéster / 20% Rayon",                    28.50, 1000),
]

# Parâmetros gerais padrão extraídos de Fatto_a_Mano_1.xlsx -> aba "Custos Importação"
PARAMETROS_SEED = {
    "cambio": 5.144,            # R$ / US$
    "frete_internacional": 5100.0,   # US$ (total da remessa)
    "despesas_portuarias": 15000.0,  # R$ (total da remessa)
    "ii": 0.35,     # Imposto de Importação
    "ipi": 0.0,     # IPI
    "pis": 0.021,   # PIS-Importação
    "cofins": 0.0965,  # COFINS-Importação
    "afrmm": 0.08,  # sobre o frete internacional
    "icms": 0.14,   # ICMS Importação (cálculo "por dentro")
    "markup": 1.00,  # Mark-up padrão (100% = dobra o custo)
}


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(force_reseed: bool = False):
    """Cria as tabelas e popula com os dados padrão, se necessário."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ref TEXT UNIQUE NOT NULL,
            produto TEXT NOT NULL,
            composicao TEXT,
            fob_usd REAL NOT NULL,
            qtd_padrao INTEGER NOT NULL DEFAULT 1,
            ativo INTEGER NOT NULL DEFAULT 1
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS parametros_gerais (
            chave TEXT PRIMARY KEY,
            valor REAL NOT NULL
        )
        """
    )
    conn.commit()

    cur.execute("SELECT COUNT(*) AS n FROM produtos")
    n_produtos = cur.fetchone()["n"]
    if n_produtos == 0 or force_reseed:
        if force_reseed:
            cur.execute("DELETE FROM produtos")
        cur.executemany(
            """
            INSERT OR IGNORE INTO produtos (ref, produto, composicao, fob_usd, qtd_padrao)
            VALUES (?, ?, ?, ?, ?)
            """,
            PRODUTOS_SEED,
        )

    cur.execute("SELECT COUNT(*) AS n FROM parametros_gerais")
    n_params = cur.fetchone()["n"]
    if n_params == 0 or force_reseed:
        if force_reseed:
            cur.execute("DELETE FROM parametros_gerais")
        cur.executemany(
            "INSERT OR IGNORE INTO parametros_gerais (chave, valor) VALUES (?, ?)",
            list(PARAMETROS_SEED.items()),
        )

    conn.commit()
    conn.close()


def listar_produtos(somente_ativos: bool = True):
    conn = get_connection()
    cur = conn.cursor()
    if somente_ativos:
        cur.execute("SELECT * FROM produtos WHERE ativo = 1 ORDER BY produto")
    else:
        cur.execute("SELECT * FROM produtos ORDER BY produto")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def obter_parametros_gerais():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT chave, valor FROM parametros_gerais")
    params = {r["chave"]: r["valor"] for r in cur.fetchall()}
    conn.close()
    # garante todas as chaves, mesmo se o banco estiver incompleto
    for k, v in PARAMETROS_SEED.items():
        params.setdefault(k, v)
    return params


def salvar_parametros_gerais(params: dict):
    conn = get_connection()
    cur = conn.cursor()
    cur.executemany(
        "INSERT INTO parametros_gerais (chave, valor) VALUES (?, ?) "
        "ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor",
        list(params.items()),
    )
    conn.commit()
    conn.close()


def adicionar_produto(ref, produto, composicao, fob_usd, qtd_padrao=1):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO produtos (ref, produto, composicao, fob_usd, qtd_padrao)
        VALUES (?, ?, ?, ?, ?)
        """,
        (ref, produto, composicao, fob_usd, qtd_padrao),
    )
    conn.commit()
    conn.close()


def atualizar_produto(produto_id, **campos):
    if not campos:
        return
    conn = get_connection()
    cur = conn.cursor()
    sets = ", ".join(f"{k} = ?" for k in campos)
    valores = list(campos.values()) + [produto_id]
    cur.execute(f"UPDATE produtos SET {sets} WHERE id = ?", valores)
    conn.commit()
    conn.close()


def remover_produto(produto_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE produtos SET ativo = 0 WHERE id = ?", (produto_id,))
    conn.commit()
    conn.close()
