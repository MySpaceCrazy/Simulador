# streamlit_simulador.py
import streamlit as st
import pandas as pd
from collections import defaultdict
import io
import plotly.express as px
import uuid
from datetime import datetime
from pathlib import Path

st.set_page_config(page_title="Simulador de Separação", layout="wide")
st.title("🧪 Simulador de Separação de Produtos")

# Colunas principais
col_esq, col_dir = st.columns([2, 2])

# Entrada de parâmetros (lado esquerdo)
with col_esq:
    tempo_produto = st.number_input("⏱️ Tempo médio por produto (s)", value=20.0, step=1.0, format="%.2f")
    tempo_deslocamento = st.number_input("🚚 Tempo entre estações (s)", value=5.0, step=1.0, format="%.2f")
    capacidade_estacao = st.number_input("📦 Capacidade máxima de caixas simultâneas por estação", value=10, min_value=1)
    pessoas_por_estacao = st.number_input("👷‍♂️ Número de pessoas por estação", value=1.0, min_value=0.01, step=0.1, format="%.2f")
    tempo_adicional_caixa = st.number_input("➕ Tempo adicional por caixa (s)", value=0.0, step=1.0, format="%.2f")
    uploaded_file = st.file_uploader("📂 Faça upload do arquivo Excel com os dados", type=["xlsx"])

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

# Botão do gráfico sempre marcado
with col_dir:
    ver_graficos = st.checkbox("📊 Ver gráficos e dashboards", value=True)
    comparar_simulacoes = st.checkbox("🔁 Comparar com simulações anteriores")

# Comparativo entre Simulações - com % e resumo de caixas
if comparar_simulacoes and "simulacoes_salvas" in st.session_state and len(st.session_state.simulacoes_salvas) > 1:
    st.markdown("---")
    st.subheader("🔁 Comparativo entre Simulações")
    col_base, col_lojas = st.columns([1, 1])

    with col_base:
        ids = list(st.session_state.simulacoes_salvas.keys())
        id1 = st.selectbox("Simulação Base", ids, index=0)
        id2 = st.selectbox("Simulação Comparada", ids, index=1 if len(ids) > 1 else 0)

        sim1 = st.session_state.simulacoes_salvas[id1]
        sim2 = st.session_state.simulacoes_salvas[id2]

        tempo1 = sim1["tempo_total"]
        tempo2 = sim2["tempo_total"]
        delta_tempo = tempo2 - tempo1
        abs_pct = abs(delta_tempo / tempo1 * 100) if tempo1 else 0
        direcao = "melhorou" if delta_tempo < 0 else "aumentou"

        caixas1 = sim1.get("total_caixas", 0)
        caixas2 = sim2.get("total_caixas", 0)
        caixas_diferenca = caixas2 - caixas1
        caixas_pct = (caixas_diferenca / caixas1 * 100) if caixas1 else 0

        tempo_formatado = formatar_tempo(abs(delta_tempo))
        st.metric("Delta de Tempo Total", f"{tempo_formatado}",
                  f"{delta_tempo:+.0f}s ({abs_pct:.1f}% {direcao})")

        st.write(f"📦 **Caixas Base:** {caixas1} | **Comparada:** {caixas2} | Δ {caixas_diferenca:+} caixas ({caixas_pct:+.1f}%)")

        # Gráfico comparativo por estação (tempo total)
        df1 = pd.DataFrame([{"Estação": est, "Tempo (s)": tempo, "Simulação": id1} for est, tempo in sim1["tempo_por_estacao"].items()])
        df2 = pd.DataFrame([{"Estação": est, "Tempo (s)": tempo, "Simulação": id2} for est, tempo in sim2["tempo_por_estacao"].items()])
        df_comp = pd.concat([df1, df2])

        if not df_comp.empty:
            fig_comp = px.bar(
                df_comp,
                x="Estação",
                y="Tempo (s)",
                color="Simulação",
                barmode="group",
                title="📊 Comparativo de Tempo por Estação"
            )
            st.plotly_chart(fig_comp, use_container_width=True)

    # Mostra o relatório na lateral direita da tela
    if "relatorio_loja" in st.session_state:
        with col_lojas:
            relatorio_loja = st.session_state["relatorio_loja"]
            st.subheader("🏪 Relatório por Loja")
            st.dataframe(
                relatorio_loja[["ID_Loja", "Num_Caixas", "Total_Produtos", "Tempo Total", "Tempo Médio por Caixa"]],
                use_container_width=True
            )

# Atualiza a forma de nomear a simulação
if uploaded_file is not None:
    nome_base = Path(uploaded_file.name).stem
    data_hora = datetime.now().strftime("%Y-%m-%d_%Hh%Mmin")
    id_simulacao = f"{nome_base}_{data_hora}"
    if "simulacoes_salvas" not in st.session_state:
        st.session_state.simulacoes_salvas = {}
    st.session_state.simulacoes_salvas[id_simulacao] = {
        "tempo_total": tempo_total_simulacao,
        "tempo_por_estacao": tempo_por_estacao,
        "relatorio_loja": relatorio_loja,
        "gargalo": tempo_gargalo,
        "total_caixas": len(caixas)
    }
    st.success(f"✅ Simulação salva como ID: {id_simulacao}")
