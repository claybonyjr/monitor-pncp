import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
from io import BytesIO

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(
    page_title="Monitor PNCP - Evolutio",
    page_icon="📋",
    layout="wide"
)

# 2. CONSTANTES E FILTROS DE NEGÓCIO
API_BASE_URL = "https://pncp.gov.br/api/pncp/v1/contratacoes"
ESTADOS_FOCO = ["RO", "AC", "MT", "AM"]
TERMOS_ACEITOS = [
    "limpeza", "conservação", "serviços gerais", "portaria", "recepção", 
    "jardinagem", "apoio administrativo", "auxiliar administrativo", 
    "secretaria", "copeira", "zeladoria", "vigilância desarmada", "brigadista"
]
TERMOS_NEGADOS = ["armada", "compra de material", "material de construção", "peças"]

# 3. FUNÇÃO DE BUSCA (CORRIGIDA)
@st.cache_data(ttl=1800)
def buscar_dados_pncp():
    # Parâmetros oficiais da API PNCP
    params = {
        "pagina": 1,
        "tamanhoPagina": 100,
        "codigoModalidade": 6 # Pregão Eletrônico
    }
    
    try:
        response = requests.get(API_BASE_URL, params=params, timeout=30)
        response.raise_for_status()
        dados = response.json()
        # O PNCP retorna a lista dentro da chave 'data'
        return dados.get("data", [])
    except Exception as e:
        st.error(f"Erro na conexão com o PNCP: {str(e)}")
        return []

# 4. PROCESSAMENTO E FILTRAGEM
def processar_editais(lista_bruta):
    dados_filtrados = []
    
    for item in lista_bruta:
        # Extração de dados com segurança (get)
        objeto = item.get("objeto", "").lower()
        uf = item.get("unidadeOrgao", {}).get("ufSigla", "").upper()
        orgao = item.get("orgaoEntidade", {}).get("razaoSocial", "")
        municipio = item.get("unidadeOrgao", {}).get("municipioNome", "")
        valor = item.get("valorTotalEstimado", 0)
        link = item.get("linkSistemaOrigem", "")
        data_pub = item.get("dataPublicacao", "")
        cnpj = item.get("orgaoEntidade", {}).get("cnpj", "")

        # APLICAÇÃO DOS FILTROS DA EVOLUTIO
        eh_estado = uf in ESTADOS_FOCO
        tem_servico = any(termo in objeto for termo in TERMOS_ACEITOS)
        eh_negado = any(termo in objeto for termo in TERMOS_NEGADOS)

        if eh_estado and tem_servico and not eh_negado:
            dados_filtrados.append({
                "Órgão": orgao,
                "Localidade": f"{municipio} - {uf}",
                "Objeto": item.get("objeto", ""),
                "Valor Estimado": valor,
                "Link Edital": link,
                "UF": uf,
                "CNPJ": cnpj,
                "Data": data_pub[:10] # Apenas YYYY-MM-DD
            })
    
    return pd.DataFrame(dados_filtrados)

# 5. INTERFACE SIDEBAR
st.sidebar.title("🔧 Configurações Evolutio")
limite_alerta = st.sidebar.number_input("Alerta de Valor (R$)", value=500000.0, step=50000.0)
cnpj_filtro = st.sidebar.text_input("Filtrar por CNPJ")

if st.sidebar.button("🔄 Atualizar Agora"):
    st.cache_data.clear()
    st.rerun()

# 6. CORPO DO SITE
st.title("📋 Monitor de Licitações PNCP - Evolutio")

with st.spinner("Varrendo o portal do governo..."):
    brutos = buscar_dados_pncp()
    df = processar_editais(brutos)

if cnpj_filtro:
    df = df[df["CNPJ"].str.contains(cnpj_filtro)]

# MÉTRICAS
col1, col2, col3 = st.columns(3)
if not df.empty:
    col1.metric("📊 Oportunidades", len(df))
    col2.metric("⚠️ Alto Valor", len(df[df["Valor Estimado"] > limite_alerta]))
    col3.metric("🌎 Estados", df["UF"].nunique())
else:
    st.info("Nenhuma licitação de mão de obra encontrada em RO, AC, MT ou AM nas últimas postagens.")

# TABELA E DASHBOARD
if not df.empty:
    st.subheader("📈 Distribuição Regional")
    fig = px.bar(df["UF"].value_counts().reset_index(), x="UF", y="count", color="UF", title="Editais por Estado")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("📝 Lista de Editais")
    
    # Formatação de Moeda para exibição
    df_display = df.copy()
    df_display["Valor Estimado"] = df_display["Valor Estimado"].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

    st.dataframe(
        df_display,
        column_config={
            "Link Edital": st.column_config.LinkColumn("🔗 Link"),
            "Objeto": st.column_config.TextColumn("Objeto", width="large")
        },
        hide_index=True,
        use_container_width=True
    )

    # BOTÃO EXCEL
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Licitações')
    
    st.download_button(
        label="📥 Baixar Planilha Excel",
        data=output.getvalue(),
        file_name="radar_evolutio.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

st.markdown("---")
st.caption("Foco: RO, AC, MT, AM | Modalidade: Pregão Eletrônico | Mão de Obra Desarmada")
