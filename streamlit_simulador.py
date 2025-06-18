# streamlit_simulador.py
import streamlit as st
import pandas as pd
from collections import defaultdict
import io
import os
from pathlib import Path

st.set_page_config(page_title="Simulador de Separação", layout="centered")
st.title("🧪 Simulador de Separação de Produtos")

# Caminho dinâmico do arquivo Excel
try:
    pasta_app = Path(__file__).parent
except NameError:
    # Caso __file__ não esteja definido (ex: Streamlit Cloud ou outros ambientes)
    pasta_app = Path(os.getcwd())

caminho_excel = pasta_app / "Dados" / "Base_Dados2.xlsx"

# Parâmetros de entrada
tempo_produto = st.number_input("⏱️ Tempo médio por produto (s)", value=20)
tempo_deslocamento = st.number_input("🚚 Tempo entre estações (s)", value=5)
capacidade_estacao = st.number_input("📦 Capacidade máxima de caixas simultâneas por estação", value=10, min_value=1)
pessoas_por_estacao = st.number_input("👷‍♂️ Número de pessoas por estação", value=1, min_value=1)
tempo_adicional_caixa = st.number_input("➕ Tempo adicional por caixa (s)", value=0)

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

if st.button("▶️ Iniciar Simulação"):
    try:
        df = pd.read_excel(caminho_excel)
        df = df.sort_values(by=["ID_Pacote", "ID_Caixas"])
        caixas = df["ID_Caixas"].unique()

        # Estimar tempo por caixa (para ordenar entrada)
        estimativas = []
        for caixa in caixas:
            caixa_df = df[df["ID_Caixas"] == caixa]
            total_produtos = caixa_df["Contagem de Produto"].sum()
            num_estacoes = caixa_df["Estação"].nunique()
            tempo_estimado = (total_produtos * tempo_produto) / pessoas_por_estacao + (num_estacoes * tempo_deslocamento) + tempo_adicional_caixa
            estimativas.append((caixa, tempo_estimado))

        caixas_ordenadas = [cx for cx, _ in sorted(estimativas, key=lambda x: x[1])]

        # Controle de tempo por estação (paralelo)
        disponibilidade_estacao = defaultdict(list)  # lista de tempos por pessoa por estação
        tempo_caixas = {}
        gargalo_ocorrido = False
        tempo_gargalo = None

        tempo_total_simulacao = 0  # maior tempo ao final de todas as caixas

        for caixa in caixas_ordenadas:
            caixa_df = df[df["ID_Caixas"] == caixa]
            tempo_inicio_caixa = 0
            tempos_finais = []

            for _, linha in caixa_df.iterrows():
                estacao = linha["Estação"]
                contagem = linha["Contagem de Produto"]

                duracao = (contagem * tempo_produto) / pessoas_por_estacao + tempo_deslocamento

                # Inicializar fila de disponibilidade por pessoa na estação
                if not disponibilidade_estacao[estacao]:
                    disponibilidade_estacao[estacao] = [0.0] * pessoas_por_estacao

                # Escolhe a pessoa com menor tempo de disponibilidade
                idx_pessoa_livre = disponibilidade_estacao[estacao].index(min(disponibilidade_estacao[estacao]))
                inicio = max(disponibilidade_estacao[estacao][idx_pessoa_livre], tempo_inicio_caixa)
                fim = inicio + duracao

                # Atualiza tempo da pessoa na estação
                disponibilidade_estacao[estacao][idx_pessoa_livre] = fim
                tempos_finais.append(fim)

                # Detecta gargalo (estação cheia)
                if disponibilidade_estacao[estacao].count(inicio) == capacidade_estacao and not gargalo_ocorrido:
                    gargalo_ocorrido = True
                    tempo_gargalo = inicio

            if tempos_finais:
                fim_caixa = max(tempos_finais) + tempo_adicional_caixa
                tempo_caixas[caixa] = fim_caixa - tempo_inicio_caixa
                tempo_total_simulacao = max(tempo_total_simulacao, fim_caixa)
            else:
                st.warning(f"⚠️ Caixa '{caixa}' não possui produtos para separação.")
                tempo_caixas[caixa] = 0

        # Exibir resultados
        st.subheader("📊 Resultados da Simulação")
        st.write(f"🔚 **Tempo total para separar todas as caixas:** {formatar_tempo(tempo_total_simulacao)}")
        st.write(f"🧱 **Tempo até o primeiro gargalo:** {formatar_tempo(tempo_gargalo) if gargalo_ocorrido else 'Nenhum gargalo'}")

        # DataFrame para exibição
        resultados_exibicao = pd.DataFrame([
            {
                "Sugestão de Ordem (Melhor Start)": idx + 1,
                "ID_Caixa": caixa,
                "Tempo Total": formatar_tempo(tempo_caixas[caixa])
            }
            for idx, caixa in enumerate(caixas_ordenadas)
        ])
        st.dataframe(resultados_exibicao)

        # DataFrame para exportação
        resultados_raw = pd.DataFrame([
            {
                "Sugestão de Ordem (Melhor Start)": idx + 1,
                "ID_Caixa": caixa,
                "Tempo Total (s)": tempo_caixas[caixa]
            }
            for idx, caixa in enumerate(caixas_ordenadas)
        ])

        # Excel export
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            resultados_raw.to_excel(writer, index=False, sheet_name='Resultados')
        dados_excel = output.getvalue()

        st.download_button(
            label="📥 Baixar resultados em Excel",
            data=dados_excel,
            file_name="resultado_simulacao.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error(f"Erro ao processar o arquivo: {e}")




# Caso não processo os python execute esse comando no terminal "C:/Users/anderson.oliveira5/AppData/Local/Programs/Python/Python313/python.exe -m streamlit run "C:/Users/anderson.oliveira5/Downloads/Simulações/streamlit_simulador.py"
# Correção botão baixar excel "pip install xlsxwriter"
# para rodar no promp "streamlit run streamlit_simulador.py"

