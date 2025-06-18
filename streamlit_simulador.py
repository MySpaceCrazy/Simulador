# streamlit_simulador.py
import streamlit as st
import pandas as pd
from collections import defaultdict
import io
import plotly.express as px

st.set_page_config(page_title="Simulador de Separação", layout="wide")
st.title("🧪 Simulador de Separação de Produtos")

# Colunas principais da tela
col_esq, col_dir = st.columns([2, 2])

with col_esq:
    # Parâmetros de entrada
    tempo_produto = st.number_input("⏱️ Tempo médio por produto (s)", value=20.0, step=1.0, format="%.2f")
    tempo_deslocamento = st.number_input("🚚 Tempo entre estações (s)", value=5.0, step=1.0, format="%.2f")
    capacidade_estacao = st.number_input("📦 Capacidade máxima de caixas simultâneas por estação", value=10, min_value=1)
    pessoas_por_estacao = st.number_input("👷‍♂️ Número de pessoas por estação", value=1.0, min_value=0.01, step=0.1, format="%.2f")
    tempo_adicional_caixa = st.number_input("➕ Tempo adicional por caixa (s)", value=0.0, step=1.0, format="%.2f")
    uploaded_file = st.file_uploader("📂 Faça upload do arquivo Excel com os dados", type=["xlsx"])

# Coluna para botões superiores
col_b1, col_b2 = st.columns([1, 1])
executar_simulacao = col_b1.button("▶️ Iniciar Simulação")
ver_graficos = col_b2.checkbox("📈 Ver gráficos e dashboards", value=False)

def formatar_tempo(segundos):
    if segundos < 60:
        return f"{int(round(segundos))} segundos"
    dias = int(segundos // 86400)
    segundos %= 86400
    horas = int(segundos // 3600)
    segundos %= 3600
    minutos = int(segundos // 60)
    partes = []
    if dias > 0:
        partes.append(f"{dias} {'dia' if dias == 1 else 'dias'}")
    if horas > 0:
        partes.append(f"{horas} {'hora' if horas == 1 else 'horas'}")
    if minutos > 0:
        partes.append(f"{minutos} {'minuto' if minutos == 1 else 'minutos'}")
    return " e ".join(partes)

# Executar simulação
if executar_simulacao:
    if uploaded_file is not None:
        try:
            df = pd.read_excel(uploaded_file)
            df = df.sort_values(by=["ID_Pacote", "ID_Caixas"])
            caixas = df["ID_Caixas"].unique()

            estimativas = []
            for caixa in caixas:
                caixa_df = df[df["ID_Caixas"] == caixa]
                total_produtos = caixa_df["Contagem de Produto"].sum()
                num_estacoes = caixa_df["Estação"].nunique()
                tempo_estimado = (total_produtos * tempo_produto) / pessoas_por_estacao + (num_estacoes * tempo_deslocamento) + tempo_adicional_caixa
                estimativas.append((caixa, tempo_estimado))

            caixas_ordenadas = [cx for cx, _ in sorted(estimativas, key=lambda x: x[1])]
            disponibilidade_estacao = defaultdict(list)
            tempo_por_estacao = defaultdict(float)
            tempo_caixas = {}
            gargalo_ocorrido = False
            tempo_gargalo = None
            tempo_total_simulacao = 0

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

                    if disponibilidade_estacao[estacao].count(inicio) >= capacidade_estacao and not gargalo_ocorrido:
                        gargalo_ocorrido = True
                        tempo_gargalo = inicio

                    disponibilidade_estacao[estacao][idx_pessoa_livre] = fim
                    tempo_por_estacao[estacao] += duracao
                    tempos_finais.append(fim)

                if tempos_finais:
                    fim_caixa = max(tempos_finais) + tempo_adicional_caixa
                    tempo_caixas[caixa] = fim_caixa - tempo_inicio_caixa
                    tempo_total_simulacao = max(tempo_total_simulacao, fim_caixa)
                else:
                    col_esq.warning(f"⚠️ Caixa '{caixa}' não possui produtos.")
                    tempo_caixas[caixa] = 0

            resultados_raw = pd.DataFrame([
                {"Sugestão de Ordem (Melhor Start)": idx + 1, "ID_Caixa": caixa, "Tempo Total (s)": tempo_caixas[caixa]}
                for idx, caixa in enumerate(caixas_ordenadas)
            ])
            resultados_exibicao = resultados_raw.copy()
            resultados_exibicao["Tempo Total"] = resultados_exibicao["Tempo Total (s)"].apply(formatar_tempo)

            with col_esq:
                st.subheader("📊 Resultados da Simulação")
                st.write(f"🔚 **Tempo total para separar todas as caixas:** {formatar_tempo(tempo_total_simulacao)}")
                st.write(f"🧱 **Tempo até o primeiro gargalo:** {formatar_tempo(tempo_gargalo) if gargalo_ocorrido else 'Nenhum gargalo'}")
                st.dataframe(resultados_exibicao)

                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    resultados_raw.to_excel(writer, index=False, sheet_name='Resultados')
                st.download_button("📥 Baixar resultados em Excel", output.getvalue(), "resultado_simulacao.xlsx")

            st.session_state["dados_simulacao"] = {
                "resultados_raw": resultados_raw,
                "tempo_por_estacao": tempo_por_estacao
            }

        except Exception as e:
            col_esq.error(f"Erro ao processar o arquivo: {e}")
    else:
        col_esq.warning("⚠️ Por favor, envie um arquivo Excel para prosseguir com a simulação.")

# Exibição de gráficos (ao lado direito)
if ver_graficos and "dados_simulacao" in st.session_state:
    with col_dir:
        st.subheader("📈 Dashboards Visuais")
        tempo_por_estacao = st.session_state["dados_simulacao"]["tempo_por_estacao"]

        estacoes_df = pd.DataFrame([
            {"Estação": est, "Tempo Total (s)": tempo} for est, tempo in tempo_por_estacao.items()
        ]).sort_values(by="Tempo Total (s)", ascending=False)

        estacoes_df["Tempo Formatado"] = estacoes_df["Tempo Total (s)"].apply(formatar_tempo)

        fig1 = px.bar(
            estacoes_df,
            x="Estação",
            y="Tempo Total (s)",
            title="🏭 Estações mais utilizadas (tempo total)",
            labels={"Tempo Total (s)": "Tempo (s)"},
            hover_data={"Tempo Formatado": True, "Tempo Total (s)": False}
        )

        st.plotly_chart(fig1, use_container_width=True)
