"""
Camada de banco de dados (SQLite) do Simulador de Importação Ricex.
"""
import sqlite3
import json
import pandas as pd
from pathlib import Path

# Apontando exatamente para o seu arquivo oficial .db
# [CORRIGIDO] Caminho inteligente que funciona tanto localmente quanto no Streamlit Share
DB_PATH = Path(__file__).parent / "data" / "ricex_importacao.db"

if not DB_PATH.parent.exists():
    # Se a pasta 'data' não estiver dentro de 'ricex_app' (como ocorre na raiz do GitHub), aponta para a raiz
    DB_PATH = Path(__file__).parent.parent / "data" / "ricex_importacao.db"
    
    # Se ainda assim não achar (caso o arquivo esteja solto na raiz do repositório), garante o fallback
    if not DB_PATH.parent.exists():
        DB_PATH = Path("data/ricex_importacao.db")


PRODUTOS_SEED = [
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

PARAMETROS_SEED = {
    "cambio": 5.144,
    "frete_internacional": 5100.0,
    "despesas_portuarias": 15000.0,
    "ii": 0.35,
    "ipi": 0.0,
    "pis": 0.021,
    "cofins": 0.0965,
    "afrmm": 0.08,
    "icms": 0.14,
    "markup": 1.00,
}

def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(force_reseed: bool = False):
    """Cria as tabelas e sincroniza automaticamente com o arquivo Excel local superior."""
    conn = get_connection()
    cur = conn.cursor()

    # Garantimos a estrutura padrão da tabela
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
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS simulacoes_salvas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_simulacao TEXT NOT NULL,
            data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            parametros TEXT NOT NULL,
            itens TEXT NOT NULL
        )
        """
    )
    conn.commit()

    cur.execute("SELECT COUNT(*) AS n FROM parametros_gerais")
    if cur.fetchone()["n"] == 0:
        cur.executemany(
            "INSERT OR IGNORE INTO parametros_gerais (chave, valor) VALUES (?, ?)",
            list(PARAMETROS_SEED.items()),
        )
        conn.commit()

    conn.close()

    # Sincronização Ultra-Tolerante com Tratamento Geral de Erros e Conversão Limpa
    excel_path = Path(__file__).parent.parent / "database_new.xlsx"
    if excel_path.exists():
        try:
            df = pd.read_excel(excel_path)
            # Remove espaços extras das pontas dos nomes das colunas
            df.columns = [str(c).strip().lower() for c in df.columns]
            
            col_ref = 'ref' if 'ref' in df.columns else df.columns[0]
            col_prod = 'produto' if 'produto' in df.columns else df.columns[1]
            col_comp = 'composicao' if 'composicao' in df.columns else df.columns[2]
            
            col_fob = None
            for c in df.columns:
                if 'fob' in str(c):
                    col_fob = c
                    break
            if not col_fob:
                col_fob = df.columns[3]
                
            col_qtd = None
            for c in df.columns:
                if 'qtd' in str(c):
                    col_qtd = c
                    break
            if not col_qtd:
                col_qtd = df.columns

            historico_refs = {}

            for index, row in df.iterrows():
                # Força a leitura se houver qualquer dado na linha, sem pular por nulos
                if pd.isna(row[col_prod]) and pd.isna(row[col_ref]):
                    continue
                
                # Conversão e limpeza rigorosa de strings
                ref_original = str(row[col_ref]).strip() if pd.notna(row[col_ref]) else ""
                produto = str(row[col_prod]).strip() if pd.notna(row[col_prod]) else f"Item Linha {index+2}"
                composicao = str(row[col_comp]).strip() if pd.notna(row[col_comp]) else ""
                
                # Tratamento de erro numérico: remove caracteres de moeda se existirem e converte para float
                try:
                    fob_raw = str(row[col_fob]).replace("US$", "").replace("R$", "").replace(",", ".").strip()
                    fob_usd = float(fob_raw) if fob_raw and fob_raw != "nan" else 0.0
                except Exception:
                    fob_usd = 0.0

                try:
                    qtd_padrao = int(float(str(row[col_qtd]).strip())) if pd.notna(row[col_qtd]) else 1000
                except Exception:
                    qtd_padrao = 1000
                
                if ref_original:
                    # Aplicação exata da regra sequencial por NCM (ref)
                    if ref_original not in historico_refs:
                        historico_refs[ref_original] = 1
                        ref_final = ref_original
                    else:
                        historico_refs[ref_original] += 1
                        ref_final = f"{ref_original} ({historico_refs[ref_original]})"
                    
                    adicionar_produto(ref_final, produto, composicao, fob_usd, qtd_padrao)
        except Exception as e:
            print(f"Erro crítico na sincronização: {e}")
    else:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS n FROM produtos")
        if cur.fetchone()["n"] == 0 or force_reseed:
            if force_reseed:
                cur.execute("DELETE FROM produtos")
            cur.executemany(
                """
                INSERT OR IGNORE INTO produtos (ref, produto, composicao, fob_usd, qtd_padrao)
                VALUES (?, ?, ?, ?, ?)
                """,
                PRODUTOS_SEED,
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
        ON CONFLICT(ref) DO UPDATE SET
            produto = excluded.produto,
            composicao = excluded.composicao,
            fob_usd = excluded.fob_usd,
            qtd_padrao = excluded.qtd_padrao,
            ativo = 1
        """,
        (str(ref), produto, composicao, float(fob_usd), int(qtd_padrao)),
    )
    conn.commit()
    conn.close()

def remover_produto(produto_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE produtos SET ativo = 0 WHERE id = ?", (produto_id,))
    conn.commit()
    conn.close()

def salvar_modelo_simulacao(nome, parametros, itens):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO simulacoes_salvas (nome_simulacao, parametros, itens) VALUES (?, ?, ?)",
        (nome, json.dumps(parametros), json.dumps(itens))
    )
    conn.commit()
    conn.close()

def listar_modelos_simulacao():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, nome_simulacao, data_criacao FROM simulacoes_salvas ORDER BY data_criacao DESC")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def carrega_modelo_simulacao(modelo_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT parametros, itens FROM simulacoes_salvas WHERE id = ?", (modelo_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        return json.loads(row["parametros"]), json.loads(row["itens"])
    return None, None

def remover_modelo_simulacao(modelo_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM simulacoes_salvas WHERE id = ?", (modelo_id,))
    conn.commit()
    conn.close()
