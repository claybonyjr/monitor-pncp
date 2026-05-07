import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import plotly.express as px
from io import BytesIO

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(
    page_title="Monitor PNCP - Evolutio",
    page_icon="📋",
    layout="wide"
)

# 2. CONSTANTES E FILTROS DE NEGÓCIO
# URL oficial que aceita os parâmetros de busca
API_BASE_URL = "https://pncp.gov.br/api/pncp/v1/contratacoes"
ESTADOS_FOCO = ["RO", "AC", "MT", "AM"] # Foco regional da Evolutio
TERMOS_ACEITOS = [
    "limpeza", "conservação", "serviços gerais", "portaria", "recepção", 
    "jardinagem", "apoio administrativo", "auxiliar administrativo", 
    "secretaria", "copeira", "zeladoria", "vigilância desarmada", "brigadista"
] # Serviços foco
TERMOS_NEGADOS = ["armada", "veículo", "aquisição de", "compra de", "material de construção", "peças"] # Exclusões

# 3. FUNÇÃO DE BUSCA (CORRIGIDA PARA EVITAR ERRO 404)
@st.cache_data(ttl=1800)
def buscar_dados_pncp():
    # Parâmetros corrigidos para o padrão que a API do PNCP exige
    params = {
        "pagina": 1,
        "tamanhoPagina": 100,
        "codigoModalidade": 6 # Pregão Eletrônico
    }
    
    try:
        # A requisição agora usa os nomes de parâmetros corretos
        response = requests.get(API_BASE_URL, params=params, timeout=30)
        response.raise_for_status()
        dados = response.json()
        # O PNCP entrega a lista de editais na chave 'data'
        return dados.get("data", [])
    except Exception as e:
        st.error(f"Erro na conexão com o PNCP: {str(e)}")
        return []

# 4. PROCESSAMENTO E FILTRAGEM
def processar_editais(lista_bruta):
    dados_filtrados = []
    
    for item in lista_bruta:
        # Extração segura de dados aninhados
        objeto = item.get("objeto", "").lower()
        unidade = item.get("unidadeOrgao", {})
        uf = unidade.get("ufSigla", "").upper()
        orgao_data = item.get("orgaoEntidade", {})
        orgao = orgao_data.get("razaoSocial", "")
        municipio = unidade.get("municipioNome", "")
        valor = item.get("valorTotalEstimado", 0)
        link = item.get("linkSistemaOrigem", "")
        data_pub = item.get("dataPublicacao", "")
        cnpj = orgao_data.get("cnpj", "")

        # LÓGICA DE FILTRAGEM DA EVOLUTIO
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
                "Data": data_pub[:10] if data_pub else "N/A"
            })
    
    return pd.DataFrame(dados_filtrados)

# 5. INTERFACE SIDEBAR (CONFIGURAÇÕES)
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

# Filtro extra por CNPJ se preenchido
if cnpj_filtro and not df.empty:
    df = df[df["CNPJ"].str.contains(cnpj_filtro, na=False)]

# EXIBIÇÃO DE MÉTRICAS (CORRIGIDO PARA EVITAR KEYERROR)
col1, col2, col3 = st.columns(3)
if not df.empty:
    col1.metric("📊 Oportunidades", len(df))
    col2.metric("⚠️ Alto Valor", len(df[df["Valor Estimado"] > limite_alerta]))
    col3.metric("🌎 Estados Ativos", df["UF"].nunique())
    
    # Dashboard Regional
    st.subheader("📈 Distribuição Regional")
    fig = px.bar(df["UF"].value_counts().reset_index(), x="UF", y="count", color="UF", title="Editais por Estado")
    st.plotly_chart(fig, use_container_width=True)

    # Tabela de Resultados
    st.subheader("📝 Lista de Editais Encontrados")
    
    # Cópia para exibição formatada sem alterar os dados numéricos para filtros
    df_display = df.copy()
    df_display["Valor Estimado"] = df_display["Valor Estimado"].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

    st.dataframe(
        df_display,
        column_config={
            "Link Edital": st.column_config.LinkColumn("🔗 Link Origem"),
            "Objeto": st.column_config.TextColumn("Descrição do Objeto", width="large")
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
        file_name=f"radar_evolutio_{datetime.now().strftime('%d_%m')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    st.info("Nenhuma licitação de mão de obra encontrada em RO, AC, MT ou AM nas últimas postagens do PNCP.")

st.markdown("---")
st.caption("Configuração Atual: RO, AC, MT, AM | Somente Pregão Eletrônico | Mão de Obra Terceirizada")
