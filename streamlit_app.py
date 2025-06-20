# streamlit_simulador.py
import streamlit as st
import pandas as pd
from collections import defaultdict
import io
import plotly.express as px
import uuid

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

# Botão de simulação
with col_esq:
    if st.button("▶️ Iniciar Simulação"):
        if uploaded_file is not None:
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
                        st.warning(f"⚠️ Caixa '{caixa}' não possui produtos.")
                        tempo_caixas[caixa] = 0

                resultados_raw = pd.DataFrame([
                    {"Sugestão de Ordem (Melhor Start)": idx + 1, "ID_Caixa": caixa, "Tempo Total (s)": tempo_caixas[caixa]}
                    for idx, caixa in enumerate(caixas_ordenadas)
                ])
                resultados_exibicao = resultados_raw.copy()
                resultados_exibicao["Tempo Total"] = resultados_exibicao["Tempo Total (s)"].apply(formatar_tempo)

                st.subheader("📊 Resultados da Simulação")
                st.write(f"🔚 **Tempo total para separar todas as caixas:** {formatar_tempo(tempo_total_simulacao)} — Simuladas {len(caixas)} caixas diferentes")
                st.write(f"🧱 **Tempo até o primeiro gargalo:** {formatar_tempo(tempo_gargalo) if gargalo_ocorrido else 'Nenhum gargalo'}")
                st.dataframe(resultados_exibicao)

                df_lojas = df[df["ID_Caixas"].isin(caixas_ordenadas)]

                relatorio_loja = df_lojas.groupby("ID_Loja").agg(
                    Num_Caixas=("ID_Caixas", lambda x: x.nunique()),
                    Total_Produtos=("Contagem de Produto", "sum")
                ).reset_index()

                tempos_lojas = (
                    df_lojas[["ID_Caixas", "ID_Loja"]].drop_duplicates()
                    .merge(resultados_raw[["ID_Caixa", "Tempo Total (s)"]], left_on="ID_Caixas", right_on="ID_Caixa")
                )

                tempo_loja_agg = tempos_lojas.groupby("ID_Loja").agg(
                    Tempo_Total_s=("Tempo Total (s)", "max"),
                    Tempo_Médio_por_Caixa_s=("Tempo Total (s)", "mean")
                ).reset_index()

                relatorio_loja = relatorio_loja.merge(tempo_loja_agg, on="ID_Loja")
                relatorio_loja["Tempo Total"] = relatorio_loja["Tempo_Total_s"].apply(formatar_tempo)
                relatorio_loja["Tempo Médio por Caixa"] = relatorio_loja["Tempo_Médio_por_Caixa_s"].apply(formatar_tempo)
                relatorio_loja = relatorio_loja.sort_values(by="Tempo_Total_s", ascending=False)

                st.markdown("---")
                st.subheader("🏪 Relatório por Loja")
                st.dataframe(relatorio_loja[["ID_Loja", "Num_Caixas", "Total_Produtos", "Tempo Total", "Tempo Médio por Caixa"]])

                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    resultados_raw.to_excel(writer, index=False, sheet_name='Resultados')
                    relatorio_loja.to_excel(writer, index=False, sheet_name='Relatório por Loja')
                st.download_button("📥 Baixar resultados em Excel", output.getvalue(), "resultado_simulacao.xlsx")

                id_simulacao = str(uuid.uuid4())[:8]
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

                st.session_state["dados_simulacao"] = {
                    "resultados_raw": resultados_raw,
                    "tempo_por_estacao": tempo_por_estacao
                }

                # Sugestão de layout otimizado
                st.markdown("---")
                st.subheader("🧠 Sugestão de Layout Otimizado")
                df_estacoes = pd.DataFrame([
                    {"Estação": est, "Tempo Total (s)": tempo} for est, tempo in tempo_por_estacao.items()
                ])
                tempo_medio = df_estacoes["Tempo Total (s)"].mean()
                limiar = 1.5 * tempo_medio

                estacoes_sobrec = df_estacoes[df_estacoes["Tempo Total (s)"] > limiar]
                estacoes_menos_usadas = df_estacoes[df_estacoes["Tempo Total (s)"] < tempo_medio]

                if not estacoes_sobrec.empty:
                    st.warning("⚠️ Estações sobrecarregadas detectadas! Sugere-se redistribuir produtos para:")
                    st.dataframe(estacoes_sobrec.assign(Sugestao="Redistribuir para estações abaixo da média."))
                else:
                    st.success("🚀 Nenhuma estação sobrecarregada detectada.")

            except Exception as e:
                st.error(f"Erro ao processar o arquivo: {e}")
        else:
            st.warning("⚠️ Por favor, envie um arquivo Excel para prosseguir com a simulação.")



# Comparativo entre Simulações - com % e resumo de caixas
if comparar_simulacoes and "simulacoes_salvas" in st.session_state and len(st.session_state.simulacoes_salvas) > 1:
    st.markdown("---")
    st.subheader("🔁 Comparativo entre Simulações")
    col_base, col_lojas = st.columns(2)

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

    # Move o relatório principal para a coluna da direita
    with col_lojas:
        if "relatorio_loja" in st.session_state:
            relatorio_loja = st.session_state["relatorio_loja"]
            st.markdown("---")
            st.subheader("🏪 Relatório por Loja")
            st.dataframe(relatorio_loja[["ID_Loja", "Num_Caixas", "Total_Produtos", "Tempo Total", "Tempo Médio por Caixa"]], use_container_width=True)
