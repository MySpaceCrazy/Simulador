# streamlit_simulador.py
import streamlit as st
import pandas as pd
from collections import defaultdict
import io
import plotly.express as px
from datetime import datetime
from pathlib import Path
import pytz

st.set_page_config(page_title="Simulador de Separação", layout="wide")
st.title("🔪 Simulador de Separação de Produtos")

# Colunas principais
col_esq, col_dir = st.columns([2, 2])

# Entrada de parâmetros (lado esquerdo)
with col_esq:
    tempo_produto = st.number_input("⏱️ Tempo médio por produto (s)", value=20.0, step=1.0, format="%.2f")
    tempo_deslocamento = st.number_input("🚚 Tempo entre estações (s)", value=5.0, step=1.0, format="%.2f")
    capacidade_estacao = st.number_input("📦 Capacidade máxima de caixas simultâneas por estação", value=10, min_value=1)
    pessoas_por_estacao = st.number_input("👷‍♂️ Número de pessoas por estação", value=1.0, min_value=0.01, step=0.1, format="%.2f")
    tempo_adicional_caixa = st.number_input("➕ Tempo adicional por caixa (s)", value=0.0, step=1.0, format="%.2f")
    uploaded_file = st.file_uploader("📂 Arquivo para Simulação", type=["xlsx"], key="upload_simulacao")

# Função auxiliar para formatar tempo
def formatar_tempo(segundos):
    if segundos < 60:
        return f"{int(round(segundos))} segundos"
    dias = int(segundos // 86400)
    segundos %= 86400
    horas = int(segundos // 3600)
    segundos %= 3600
    minutos = int(segundos // 60)
    segundos = int(round(segundos % 60))
    partes = []
    if dias > 0: partes.append(f"{dias} {'dia' if dias == 1 else 'dias'}")
    if horas > 0: partes.append(f"{horas} {'hora' if horas == 1 else 'horas'}")
    if minutos > 0: partes.append(f"{minutos} {'minuto' if minutos == 1 else 'minutos'}")
    if segundos > 0: partes.append(f"{segundos} {'segundo' if segundos == 1 else 'segundos'}")
    return " e ".join(partes)

# Inicializa session_state
if "simulacoes_salvas" not in st.session_state:
    st.session_state.simulacoes_salvas = {}
if "ultima_simulacao" not in st.session_state:
    st.session_state.ultima_simulacao = {}
if "ordem_simulacoes" not in st.session_state:
    st.session_state.ordem_simulacoes = []

# Upload para comparação externo
st.markdown("---")
st.subheader("📁 Comparação com Outro Arquivo Excel (Opcional)")
uploaded_comp = st.file_uploader("📁 Arquivo para Comparação", type=["xlsx"], key="upload_comparacao")

# Botão de simulação
with col_esq:
    ver_graficos = st.checkbox("📊 Ver gráficos e dashboards", value=True, disabled=True)
    comparar_simulacoes = st.checkbox("🔁 Comparar com simulações anteriores", value=True)

# A simulação principal só será executada se houver upload
if uploaded_file is not None and st.button("▶️ Iniciar Simulação"):
    try:
        df = pd.read_excel(uploaded_file)
        df = df.sort_values(by=["ID_Pacote", "ID_Caixas"])
        caixas = df["ID_Caixas"].unique()

        estimativas, tempo_caixas = [], {}
        disponibilidade_estacao = defaultdict(list)
        tempo_por_estacao = defaultdict(float)
        gargalo_ocorrido = False
        tempo_gargalo = None
        tempo_total_simulacao = 0

        for caixa in caixas:
            caixa_df = df[df["ID_Caixas"] == caixa]
            total_produtos = caixa_df["Contagem de Produto"].sum()
            num_estacoes = caixa_df["Estação"].nunique()
            tempo_estimado = (total_produtos * tempo_produto) / pessoas_por_estacao + (num_estacoes * tempo_deslocamento) + tempo_adicional_caixa
            estimativas.append((caixa, tempo_estimado))

        caixas_ordenadas = [cx for cx, _ in sorted(estimativas, key=lambda x: x[1])]

        for caixa in caixas_ordenadas:
            caixa_df = df[df["ID_Caixas"] == caixa]
            tempo_inicio_caixa = 0
            tempos_finais = []

            for _, linha in caixa_df.iterrows():
                estacao = linha["Estação"]
                contagem = linha["Contagem de Produto"]
                duracao = (contagem * tempo_produto) / pessoas_por_estacao + tempo_deslocamento

                if not disponibilidade_estacao[estacao]:
                    disponibilidade_estacao[estacao] = [0.0] * int(max(1, pessoas_por_estacao))

                idx_pessoa_livre = disponibilidade_estacao[estacao].index(min(disponibilidade_estacao[estacao]))
                inicio = max(disponibilidade_estacao[estacao][idx_pessoa_livre], tempo_inicio_caixa)
                fim = inicio + duracao

                if len(disponibilidade_estacao[estacao]) >= capacidade_estacao and not gargalo_ocorrido and inicio > 0:
                    gargalo_ocorrido = True
                    tempo_gargalo = inicio

                disponibilidade_estacao[estacao][idx_pessoa_livre] = fim
                tempo_por_estacao[estacao] += duracao
                tempos_finais.append(fim)

            fim_caixa = max(tempos_finais) + tempo_adicional_caixa if tempos_finais else 0
            tempo_caixas[caixa] = fim_caixa - tempo_inicio_caixa
            tempo_total_simulacao = max(tempo_total_simulacao, fim_caixa)

        st.session_state.ultima_simulacao = {
            "tempo_total": tempo_total_simulacao,
            "tempo_por_estacao": tempo_por_estacao,
            "relatorio_loja": None,
            "gargalo": tempo_gargalo,
            "total_caixas": len(caixas)
        }

        fuso_brasil = pytz.timezone("America/Sao_Paulo")
        data_hora = datetime.now(fuso_brasil).strftime("%Y-%m-%d_%Hh%Mmin")
        nome_base = Path(uploaded_file.name).stem
        id_simulacao = f"{nome_base}_{data_hora}"
        st.session_state.simulacoes_salvas[id_simulacao] = st.session_state.ultima_simulacao

        if len(st.session_state.simulacoes_salvas) > 2:
            chaves = sorted(st.session_state.simulacoes_salvas.keys())[-2:]
            st.session_state.simulacoes_salvas = {k: st.session_state.simulacoes_salvas[k] for k in chaves}
        st.session_state.ordem_simulacoes = list(st.session_state.simulacoes_salvas.keys())

        st.success(f"✅ Simulação salva como ID: {id_simulacao}")

    except Exception as e:
        st.error(f"Erro ao processar o arquivo: {e}")

# Comparação
if comparar_simulacoes and (len(st.session_state.simulacoes_salvas) > 1 or uploaded_comp is not None):
    st.markdown("---")
    st.subheader("🔁 Comparativo entre Simulações")

    ids = st.session_state.get("ordem_simulacoes", list(st.session_state.simulacoes_salvas.keys()))
    id1 = st.selectbox("Simulação Base Anterior", ids, index=0)
    sim1 = st.session_state.simulacoes_salvas[id1]
    tempo1 = sim1["tempo_total"]

    if uploaded_comp is not None:
        try:
            df_comp_ext = pd.read_excel(uploaded_comp)
            df_comp_ext = df_comp_ext.sort_values(by=["ID_Pacote", "ID_Caixas"])
            caixas_ext = df_comp_ext["ID_Caixas"].unique()
            tempo_estacao_ext = defaultdict(float)

            for caixa in caixas_ext:
                caixa_df = df_comp_ext[df_comp_ext["ID_Caixas"] == caixa]
                for _, linha in caixa_df.iterrows():
                    estacao = linha["Estação"]
                    contagem = linha["Contagem de Produto"]
                    tempo = (contagem * tempo_produto) / pessoas_por_estacao + tempo_deslocamento
                    tempo_estacao_ext[estacao] += tempo

            df2 = pd.DataFrame([
                {"Estação": est, "Tempo (s)": tempo, "Simulação": "Arquivo Comparado"}
                for est, tempo in tempo_estacao_ext.items()
            ])
            sim2_label = "Arquivo Comparado"
            tempo2 = df2["Tempo (s)"].max()  # ✅ Corrigido aqui
            caixas2 = len(caixas_ext)

        except Exception as e:
            st.error(f"Erro ao processar arquivo de comparação: {e}")
            df2 = pd.DataFrame()
            tempo2 = 0
            caixas2 = 0
            sim2_label = "Erro"

    else:
        sim2 = st.session_state.simulacoes_salvas[ids[1] if len(ids) > 1 else 0]
        tempo_estacao_2 = sim2["tempo_por_estacao"]
        df2 = pd.DataFrame([
            {"Estação": est, "Tempo (s)": tempo, "Simulação": ids[1] if len(ids) > 1 else 0}
            for est, tempo in tempo_estacao_2.items()
        ])
        tempo2 = sim2["tempo_total"]
        caixas2 = sim2.get("total_caixas", 0)
        sim2_label = ids[1] if len(ids) > 1 else 0

    df1 = pd.DataFrame([
        {"Estação": est, "Tempo (s)": tempo, "Simulação": id1}
        for est, tempo in sim1["tempo_por_estacao"].items()
    ])
    caixas1 = sim1.get("total_caixas", 0)

    df_comp = pd.concat([df1, df2], ignore_index=True)

    if not df_comp.empty:
        st.markdown("### 📊 Comparativo de Tempo por Estação (Total)")
        fig_comp = px.bar(df_comp, x="Estação", y="Tempo (s)", color="Simulação", barmode="group")
        st.plotly_chart(fig_comp, use_container_width=True)

    delta_tempo = tempo2 - tempo1
    abs_pct = abs(delta_tempo / tempo1 * 100) if tempo1 else 0
    direcao = "melhorou" if delta_tempo < 0 else "aumentou"

    caixas_diferenca = caixas2 - caixas1
    caixas_pct = (caixas_diferenca / caixas1 * 100) if caixas1 else 0

    tempo_formatado = formatar_tempo(abs(delta_tempo))
    st.metric("Delta de Tempo Total", f"{tempo_formatado}", f"{delta_tempo:+.0f}s ({abs_pct:.1f}% {direcao})")
    st.write(f"📦 **Caixas Base:** {caixas1} | **Comparada:** {caixas2} | ∆ {caixas_diferenca:+} caixas ({caixas_pct:+.1f}%)")
