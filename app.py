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

# 2. CONSTANTES DE FILTRAGEM
ESTADOS_FOCO = ["RO", "AC", "MT", "AM"]
TERMOS_ACEITOS = [
    "limpeza", "conservação", "serviços gerais", "portaria", "recepção", 
    "jardinagem", "apoio administrativo", "auxiliar administrativo", 
    "secretaria", "copeira", "zeladoria", "vigilância desarmada", "brigadista"
]
TERMOS_NEGADOS = ["armada", "veículo", "aquisição de", "compra de", "material de construção", "peças"]

# 3. FUNÇÃO DE BUSCA COM URL CORRIGIDA
@st.cache_data(ttl=1800)
def buscar_dados_pncp():
    # URL BASE SEM PARÂMETROS NO LINK
    URL = "https://pncp.gov.br/api/pncp/v1/contratacoes"
    
    # Parâmetros oficiais exatos
    params = {
        "pagina": 1,
        "tamanhoPagina": 100,
        "codigoModalidade": "6" # Pregão Eletrônico como String
    }
    
    headers = {
        "accept": "*/*",
        "User-Agent": "Mozilla/5.0" # Evita bloqueio de bot
    }
    
    try:
        # A requisição monta a URL automaticamente
        response = requests.get(URL, params=params, headers=headers, timeout=30)
        
        if response.status_code == 200:
            dados = response.json()
            return dados.get("data", [])
        else:
            st.error(f"Erro {response.status_code}: O PNCP recusou a conexão. Tentando novamente...")
            return []
    except Exception as e:
        st.error(f"Falha técnica: {str(e)}")
        return []

# 4. PROCESSAMENTO DOS DADOS
def processar_editais(lista_bruta):
    if not lista_bruta:
        return pd.DataFrame()
        
    dados_filtrados = []
    for item in lista_bruta:
        objeto = item.get("objeto", "").lower()
        unidade = item.get("unidadeOrgao", {})
        uf = unidade.get("ufSigla", "").upper()
        
        # Filtros de Negócio
        eh_estado = uf in ESTADOS_FOCO
        tem_servico = any(termo in objeto for termo in TERMOS_ACEITOS)
        eh_negado = any(termo in objeto for termo in TERMOS_NEGADOS)

        if eh_estado and tem_servico and not eh_negado:
            dados_filtrados.append({
                "Órgão": item.get("orgaoEntidade", {}).get("razaoSocial", ""),
                "Localidade": f"{unidade.get('municipioNome', '')} - {uf}",
                "Objeto": item.get("objeto", ""),
                "Valor Estimado": item.get("valorTotalEstimado", 0),
                "Link Edital": item.get("linkSistemaOrigem", ""),
                "UF": uf,
                "CNPJ": item.get("orgaoEntidade", {}).get("cnpj", ""),
                "Data": item.get("dataPublicacao", "")[:10]
            })
    return pd.DataFrame(dados_filtrados)

# 5. INTERFACE SIDEBAR
st.sidebar.title("🔧 Evolutio Config")
limite_alerta = st.sidebar.number_input("Destaque acima de (R$)", value=500000.0)
cnpj_filtro = st.sidebar.text_input("Filtrar por CNPJ")

if st.sidebar.button("🔄 Forçar Atualização"):
    st.cache_data.clear()
    st.rerun()

# 6. EXIBIÇÃO PRINCIPAL
st.title("📋 Monitor de Licitações PNCP - Evolutio")

brutos = buscar_dados_pncp()
df = processar_editais(brutos)

if not df.empty:
    if cnpj_filtro:
        df = df[df["CNPJ"].str.contains(cnpj_filtro, na=False)]

    # Métricas
    c1, c2, c3 = st.columns(3)
    c1.metric("📊 Oportunidades", len(df))
    c2.metric("⚠️ Alto Valor", len(df[df["Valor Estimado"] > limite_alerta]))
    c3.metric("🌎 Estados", df["UF"].nunique())

    # Tabela
    st.subheader("📝 Editais Selecionados")
    df_show = df.copy()
    df_show["Valor Estimado"] = df_show["Valor Estimado"].map(lambda x: f"R$ {x:,.2f}")
    
    st.dataframe(
        df_show,
        column_config={"Link Edital": st.column_config.LinkColumn("🔗 Abrir")},
        hide_index=True,
        use_container_width=True
    )

    # Exportar
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    st.download_button("📥 Baixar Planilha", output.getvalue(), "radar_evolutio.xlsx")

else:
    st.info("Varredura concluída: Nenhum edital de serviços nos estados RO, AC, MT ou AM foi postado nas últimas horas.")

st.markdown("---")
st.caption("Foco: RO, AC, MT, AM | Somente Pregão Eletrônico | Mão de Obra Terceirizada")
