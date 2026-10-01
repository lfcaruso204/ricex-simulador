# Simulador de Importação — Ricex

Aplicativo em **Python + Streamlit** para simular a importação de peças de
vestuário: parâmetros gerais da operação (câmbio, frete, impostos), seleção
de produtos de um catálogo (SQLite), cálculo direto por markup ou reverso a
partir do preço de venda final, e geração de orçamento em PDF para o cliente.

As fórmulas replicam, item a item, os cálculos das planilhas
`Fatto_a_Mano_1.xlsx` (câmbio, frete, II, IPI, PIS, COFINS, AFRMM, ICMS
"por dentro", rateio proporcional por item e mark-up) e `Fatto_a_Mano_2.xlsx`
(catálogo de produtos, aba "1-Importacao"). A seção "PAGAMENTO EMPRÉSTIMO"
da planilha original foi propositalmente deixada de fora, conforme solicitado.

## Estrutura do projeto

```
├── app.py                 # Interface Streamlit (ponto de entrada)
├── calculations.py        # Motor de cálculo (fórmulas da planilha)
├── database.py             # Camada SQLite (produtos + parâmetros padrão)
├── pdf_generator.py        # Geração do orçamento em PDF (reportlab)
├── requirements.txt
├── assets/
│   └── Ricex_logo.png      # Logotipo exibido no app e no PDF
└── data/
    └── ricex_importacao.db # Banco SQLite (criado automaticamente)
```

## Rodando localmente

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

O navegador abrirá em `http://localhost:8501`.

---

## Como subir no GitHub e publicar no Streamlit Community Cloud

### 1. Criar o repositório no GitHub

1. Acesse [github.com/new](https://github.com/new).
2. Dê um nome ao repositório, por exemplo `ricex-simulador-importacao`.
3. Deixe como **privado** (recomendado, pois o app tem dados comerciais) ou
   público, como preferir. Não marque para criar README (já temos um).
4. Clique em **Create repository**.

### 2. Subir o código (pelo terminal, na pasta do projeto)

Abra o terminal (PowerShell ou Prompt de Comando) na pasta do projeto,
`Simulacao_Roupas`, e rode:

```bash
git init
git add .
git commit -m "Primeira versão do Simulador de Importação Ricex"
git branch -M main
git remote add origin https://github.com/SEU_USUARIO/ricex-simulador-importacao.git
git push -u origin main
```

Troque `SEU_USUARIO` pelo seu usuário do GitHub. Se o Git pedir login, use
seu usuário do GitHub e, como senha, um **Personal Access Token**
(Settings → Developer settings → Personal access tokens, no GitHub) — o
GitHub não aceita mais senha normal via linha de comando.

> Se preferir, pode usar o **GitHub Desktop** (interface gráfica), que faz
> o mesmo processo sem precisar digitar comandos: basta "Add local
> repository" apontando para esta pasta, e depois "Publish repository".

### 3. Publicar no Streamlit Community Cloud

1. Acesse [share.streamlit.io](https://share.streamlit.io) e faça login
   com sua conta GitHub.
2. Clique em **"Create app"** (ou "New app").
3. Selecione:
   - **Repository**: `SEU_USUARIO/ricex-simulador-importacao`
   - **Branch**: `main`
   - **Main file path**: `app.py`
4. (Opcional) Em "Advanced settings", escolha a versão do Python (3.11 ou
   superior) se necessário.
5. Clique em **"Deploy"**.

Em alguns minutos o Streamlit Cloud instala as dependências do
`requirements.txt` e publica o app em um link como:

```
https://ricex-simulador-importacao.streamlit.app
```

(semelhante ao exemplo `https://briks-crm.streamlit.app/` que você enviou).

### 4. Atualizações futuras

Sempre que quiser atualizar o app, basta alterar o código localmente e
rodar:

```bash
git add .
git commit -m "Descrição da alteração"
git push
```

O Streamlit Cloud detecta o novo *push* automaticamente e republica o app
em poucos instantes — não é necessário refazer o deploy manualmente.

### Observação sobre o banco de dados no Streamlit Cloud

O Streamlit Community Cloud usa armazenamento **efêmero**: a cada reinício
do app (ex.: após período de inatividade, ou um novo deploy), o arquivo
`data/ricex_importacao.db` é recriado do zero com o catálogo padrão de
produtos — ou seja, produtos adicionados manualmente pela interface do app
em produção **não serão permanentes** entre reinícios. Para um catálogo que
precise ser persistido de forma permanente em produção, considere:

- usar um banco externo (ex.: Supabase, Turso, Postgres gerenciado) no lugar
  do SQLite local; ou
- manter o cadastro de produtos no próprio repositório (editando a lista
  `PRODUTOS_SEED` em `database.py` e dando `git push`).

Para uso local (no seu computador) ou em um servidor próprio com disco
persistente, esse problema não ocorre.
