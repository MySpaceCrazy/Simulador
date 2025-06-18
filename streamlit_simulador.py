# streamlit_simulador.py
import streamlit as st
import pandas as pd
from collections import defaultdict
import io
import plotly.express as px

st.set_page_config(page_title="Simulador de Separação", layout="centered")
st.title("🧪 Simulador de Separação de Produtos")

# Parâmetros
tempo_produto = st.number_input("⏱️ Tempo médio por produto (s)", value=20.0)
tempo_deslocamento = st.number_input("🚚 Tempo entre estações (s)", value=5.0)
capacidade_estacao = st.number_input("📦 Capacidade máxima de caixas simultâneas por estação", value=10, min_value=1)
pessoas_por_estacao = st.number_input("👷‍♂️ Número de pessoas por estação", value=1.0, min_value=0.01, step=0.1)
tempo_adicional_caixa = st.number_input("➕ Tempo adicional por caixa (s)", value=0.0)

# Upload
uploaded_file = st.file_uploader("📂 Faça upload do arquivo Excel com os dados", type=["xlsx"])
ver_graficos = st.checkbox("📈 Ver gráficos e dashboards")

def formatar_tempo(segundos):
    if segundos < 60:
        return f"{int(round(segundos))} segundos"
    dias = int(segundos // 86400)
    segundos %= 86400
    horas = int(segundos // 3600)
    segundos %= 3600
    minutos = int(segundos // 60)
    partes = []
    if dias > 0: partes.append(f"{dias} {'dia' if dias == 1 else 'dias'}")
    if horas > 0: partes.append(f"{horas} {'hora' if horas == 1 else 'horas'}")
    if minutos > 0: partes.append(f"{minutos} {'minuto' if minutos == 1 else 'minutos'}")
    return " e ".join(partes)

# Botão principal
if st.button("▶️ Iniciar Simulação"):
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
            tempo_caixas = {}
            tempo_por_estacao = defaultdict(float)
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
                        disponibilidade_estacao[estacao] = [0.0] * int(capacidade_estacao)

                    idx_pessoa_livre = disponibilidade_estacao[estacao].index(min(disponibilidade_estacao[estacao]))
                    inicio = max(disponibilidade_estacao[estacao][idx_pessoa_livre], tempo_inicio_caixa)
                    fim = inicio + duracao
                    disponibilidade_estacao[estacao][idx_pessoa_livre] = fim
                    tempos_finais.append(fim)
                    tempo_por_estacao[estacao] += duracao

                    if disponibilidade_estacao[estacao].count(inicio) == capacidade_estacao and not gargalo_ocorrido:
                        gargalo_ocorrido = True
                        tempo_gargalo = inicio

                if tempos_finais:
                    fim_caixa = max(tempos_finais) + tempo_adicional_caixa
                    tempo_caixas[caixa] = fim_caixa - tempo_inicio_caixa
                    tempo_total_simulacao = max(tempo_total_simulacao, fim_caixa)
                else:
                    st.warning(f"⚠️ Caixa '{caixa}' não possui produtos.")
                    tempo_caixas[caixa] = 0

            # Resultados principais
            st.subheader("📊 Resultados da Simulação")
            st.write(f"🔚 **Tempo total:** {formatar_tempo(tempo_total_simulacao)} — {len(caixas)} caixas")
            st.write(f"🧱 **Gargalo:** {formatar_tempo(tempo_gargalo) if gargalo_ocorrido else 'Nenhum'}")

            resultados_exibicao = pd.DataFrame([
                {
                    "Sugestão de Ordem (Melhor Start)": idx + 1,
                    "ID_Caixa": caixa,
                    "Tempo Total": formatar_tempo(tempo_caixas[caixa])
                }
                for idx, caixa in enumerate(caixas_ordenadas)
            ])
            st.dataframe(resultados_exibicao)

            resultados_raw = pd.DataFrame([
                {
                    "Sugestão de Ordem (Melhor Start)": idx + 1,
                    "ID_Caixa": caixa,
                    "Tempo Total (s)": tempo_caixas[caixa]
                }
                for idx, caixa in enumerate(caixas_ordenadas)
            ])

            # Exportação Excel
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                resultados_raw.to_excel(writer, index=False, sheet_name='Resultados')
            st.download_button("📥 Baixar Excel", output.getvalue(), "resultado_simulacao.xlsx")

            # Gráficos
            if ver_graficos:
                st.subheader("📈 Gráficos e Dashboards")

                # Tempo total por caixa
                fig1 = px.bar(resultados_raw, x="ID_Caixa", y="Tempo Total (s)",
                              title="⏳ Tempo total por caixa", labels={"Tempo Total (s)": "Tempo (s)"})
                st.plotly_chart(fig1, use_container_width=True)

                # Estação mais utilizada
                estacoes_df = pd.DataFrame([
                    {"Estação": est, "Tempo Total (s)": tempo} for est, tempo in tempo_por_estacao.items()
                ]).sort_values(by="Tempo Total (s)", ascending=False)

                fig2 = px.bar(estacoes_df, x="Estação", y="Tempo Total (s)",
                              title="🏭 Estações mais utilizadas (tempo total)", labels={"Tempo Total (s)": "Tempo (s)"})
                st.plotly_chart(fig2, use_container_width=True)

        except Exception as e:
            st.error(f"Erro ao processar o arquivo: {e}")
    else:
        st.warning("⚠️ Envie um arquivo Excel.")
