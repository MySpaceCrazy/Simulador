# app_simulador_bin.py

import streamlit as st
import pandas as pd
import sqlite3
import os
import io
import time
import datetime


# --- Streamlit Config ---
st.set_page_config(
    page_title="Simulador de Bins",
    page_icon="https://raw.githubusercontent.com/MySpaceCrazy/Simulador_teste/refs/heads/main/imagens/CP-6423-01.ico",
    layout="wide"

)
st.markdown(
    '''
    <div style="display: flex; align-items: center;">
        <img src="https://raw.githubusercontent.com/MySpaceCrazy/Simulador_teste/refs/heads/main/imagens/CP-6423-01.ico" width="80" style="margin-right: 15px;">
        <span style="font-size: 60px; font-weight: bold;">Simulador de Quantidade de Bins</span>
    </div>
    ''',
    unsafe_allow_html=True
)

# --- Upload Excel ---
if "simulando" not in st.session_state:
    st.session_state["simulando"] = False
    
arquivo = st.file_uploader("📂 Selecionar arquivo de simulação (.xlsx)", type=["xlsx"])

if arquivo and not st.session_state["simulando"]:
    st.warning("⚠️ A simulação levará alguns minutos. Tempo médio estimado: 10 minutos a cada 200.000 linhas. Aguarde...")


if arquivo:
    st.session_state["simulando"] = True

    try:
        inicio_tempo = time.time()

        df_base = pd.read_excel(arquivo, sheet_name="base_item_pacotes")
        df_posicoes_prod = pd.read_excel(arquivo, sheet_name="info_posicao_produtos")

        total_linhas_base = len(df_base)
        contador_sucesso = 0

        colunas_base = ["Produto", "Qtd.solicitada total", "Recebedor mercadoria", "Peso", "UM peso", "Volume", "UM volume", "Area de atividade"]
        colunas_pos = ["Posicao no deposito", "Tipo de deposito", "Area armazmto", "Produto"]

        for col in colunas_base:
            if col not in df_base.columns:
                st.error(f"Coluna ausente: {col}")
                st.stop()
        for col in colunas_pos:
            if col not in df_posicoes_prod.columns:
                st.error(f"Coluna ausente: {col}")
                st.stop()

        # --- Ajustes Base ---
        df_base["Recebedor mercadoria"] = df_base["Recebedor mercadoria"].astype(str).str.zfill(5)
        df_base["Tipo_de_deposito"] = df_base["Area de atividade"].astype(str).str[:2].str.zfill(4)
        df_base["Peso"] = pd.to_numeric(df_base["Peso"], errors="coerce").fillna(0)
        df_base["Volume"] = pd.to_numeric(df_base["Volume"], errors="coerce").fillna(0)
        df_base["Qtd.solicitada total"] = pd.to_numeric(df_base["Qtd.solicitada total"], errors="coerce").fillna(1)
        df_base.loc[df_base["UM peso"] == "G", "Peso"] /= 1000
        df_base.loc[df_base["UM volume"] == "ML", "Volume"] /= 1000
        df_base["Volume unitario (L)"] = df_base["Volume"] / df_base["Qtd.solicitada total"]

        # --- Lê Tabelas Banco ---
        conn = sqlite3.connect("logistica.db")
        df_tipo_bin = pd.read_sql("SELECT * FROM info_tipo_bin", conn)
        df_posicao_bin = pd.read_sql("SELECT * FROM info_posicao_bin", conn)
        conn.close()

        # --- Normalizações ---
        df_posicoes_prod.rename(columns={"Posicao no deposito": "Posicao", "Tipo de deposito": "Tipo_de_deposito"}, inplace=True)
        df_posicao_bin.rename(columns={"Posicao_no_deposito": "Posicao", "Tipo_de_deposito": "Tipo_de_deposito", "Qtd._Caixas_BIN_ABASTECIMENTO": "Quantidade_Bin"}, inplace=True)
        df_tipo_bin.rename(columns={"Volume_(L)": "Volume_max_L"}, inplace=True)

        df_posicao_bin["Tipo_de_deposito"] = df_posicao_bin["Tipo_de_deposito"].astype(str).str.zfill(4).str.strip()
        df_posicoes_prod["Tipo_de_deposito"] = df_posicoes_prod["Tipo_de_deposito"].astype(str).str.zfill(4).str.strip()
        df_tipo_bin["Volume_max_L"] = pd.to_numeric(df_tipo_bin["Volume_max_L"], errors="coerce").fillna(0)

        # --- Joins ---
        df_posicoes_prod = df_posicoes_prod.merge(df_posicao_bin, on=["Posicao", "Tipo_de_deposito"], how="left")
        df_posicoes_prod = df_posicoes_prod.merge(df_tipo_bin, on="Tipo", how="left")

        # --- Cálculo das Bins ---
        resultado = []
        for _, row in df_base.iterrows():
            produto, estrutura, loja = row["Produto"], row["Tipo_de_deposito"], row["Recebedor mercadoria"]
            volume_unitario, qtd = row["Volume unitario (L)"], row["Qtd.solicitada total"]
            volume_total = volume_unitario * qtd

            posicoes = df_posicoes_prod[(df_posicoes_prod["Produto"] == produto) & (df_posicoes_prod["Tipo_de_deposito"] == estrutura)]

            if posicoes.empty:
                resultado.append({
                    "Produto": produto, "Recebedor": loja, "Estrutura": estrutura,
                    "Posicao": "N/A", "Tipo_Bin": "N/A",
                    "Bins_Necessarias": "Erro: Produto sem posicao",
                    "Bins_Disponiveis": "-", "Diferença": "-",
                    "Quantidade_Total": "-", "Volume_Total": "-", "Volumetria_Máxima": "-"
                })
                continue

            for _, pos in posicoes.iterrows():
                volume_max = pos.get("Volume_max_L", 1)
                if pd.isna(volume_max) or volume_max <= 0:
                    resultado.append({
                        "Produto": produto, "Recebedor": loja, "Estrutura": estrutura,
                        "Posicao": pos.get("Posicao", "N/A"), "Tipo_Bin": pos.get("Tipo", "N/A"),
                        "Bins_Necessarias": "Erro: Bin sem volume",
                        "Bins_Disponiveis": pos.get("Quantidade_Bin", 0), "Diferença": "-",
                        "Quantidade_Total": "-", "Volume_Total": "-", "Volumetria_Máxima": "-"
                    })
                    continue

                bins_necessarias = int(-(-volume_total // volume_max))
                bins_disponiveis = int(pos.get("Quantidade_Bin", 0))
                diferenca = bins_disponiveis - bins_necessarias
                quantidade_total = qtd
                volume_total_bins = quantidade_total * volume_unitario
                volumetria_maxima = bins_disponiveis * volume_max

                resultado.append({
                    "Produto": produto, "Recebedor": loja, "Estrutura": estrutura,
                    "Posicao": pos.get("Posicao", "N/A"), "Tipo_Bin": pos.get("Tipo", "N/A"),
                    "Bins_Necessarias": bins_necessarias,
                    "Bins_Disponiveis": bins_disponiveis,
                    "Diferença": diferenca,
                    "Quantidade_Total": quantidade_total,
                    "Volume_Total": round(volume_total_bins, 2),
                    "Volumetria_Máxima": round(volumetria_maxima, 2)
                })
                contador_sucesso += 1

        df_resultado = pd.DataFrame(resultado)

        # --- Traz descrição da estrutura ---
        df_estruturas = df_posicao_bin[["Tipo_de_deposito", "Estrutura"]].drop_duplicates().rename(
            columns={"Tipo_de_deposito": "Estrutura_Codigo", "Estrutura": "Descrição - estrutura"}
        )

        # --- Relatório Resumo por Produto e Estrutura ---
        df_resumo = df_resultado.merge(
            df_estruturas,
            how="left",
            left_on="Estrutura",
            right_on="Estrutura_Codigo"
        )

        df_resumo = df_resumo.merge(
            df_posicoes_prod[["Produto", "Descricao breve do produto"]].drop_duplicates(),
            on="Produto", how="left"
        )

        df_resumo = df_resumo.rename(columns={
            "Posicao": "Posição",
            "Descricao breve do produto": "Descrição – produto"
        })

        df_resumo = df_resumo[[  
            "Estrutura_Codigo",
            "Descrição - estrutura",
            "Posição",
            "Produto",
            "Descrição – produto",
            "Tipo_Bin",
            "Bins_Necessarias",
            "Bins_Disponiveis",
            "Diferença",
            "Quantidade_Total",
            "Volume_Total",
            "Volumetria_Máxima"
        ]]

        # --- Resumos Posições Não Atendem e OK ---
        df_resumo["Diferença"] = pd.to_numeric(df_resumo["Diferença"], errors='coerce')

        resumo_nao_atendem = df_resumo[df_resumo["Diferença"] < 0].groupby("Descrição - estrutura")["Posição"].nunique().reset_index(name="Posições - Não Atendem")
        resumo_ok = df_resumo[df_resumo["Diferença"] >= 0].groupby("Descrição - estrutura")["Posição"].nunique().reset_index(name="Posições - OK")

        total_nao_atendem = resumo_nao_atendem["Posições - Não Atendem"].sum()
        total_ok = resumo_ok["Posições - OK"].sum()

        # --- Exibe os resumos lado a lado ---
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🚨 Resumo - Posições Não Atendem")
            st.dataframe(resumo_nao_atendem, use_container_width=True)
            st.write(f"**Total Geral: {total_nao_atendem} posições**")
        with col2:
            st.subheader("✅ Resumo - Posições OK")
            st.dataframe(resumo_ok, use_container_width=True)
            st.write(f"**Total Geral: {total_ok} posições**")

        # --- Exibe relatórios detalhados ---
        st.markdown("---")
        st.subheader("📊 Detalhado por Loja, Estrutura e Produto")
        st.dataframe(df_resultado)

        st.markdown("---")
        st.subheader("📊 Resumo por Produto e Estrutura")
        st.dataframe(df_resumo)

        # --- Downloads ---
        buf1 = io.BytesIO()
        with pd.ExcelWriter(buf1, engine="xlsxwriter") as writer:
            df_resultado.to_excel(writer, index=False, sheet_name="Detalhado Bins")
        st.download_button("📥 Baixar Detalhado", data=buf1.getvalue(), file_name="Simulacao_Bins.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        buf2 = io.BytesIO()
        with pd.ExcelWriter(buf2, engine="xlsxwriter") as writer:
            df_resumo.to_excel(writer, index=False, sheet_name="Resumo Produto Estrutura")
        st.download_button("📥 Baixar Resumo Produto/Estrutura", data=buf2.getvalue(), file_name="Resumo_Produto_Estrutura.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        # --- Tempo Execução ---
        tempo_execucao = str(datetime.timedelta(seconds=int(time.time() - inicio_tempo)))
        st.success(f"✅ Simulação concluída em {tempo_execucao}")
        st.write(f"📄 Linhas da base: **{total_linhas_base}**, Simuladas sem erro: **{contador_sucesso}**")

    except Exception as e:
        st.error(f"Erro no processamento: {e}")
    finally:
        st.session_state["simulando"] = False
        
# --- Rodapé ---
st.markdown("---")
st.markdown("""
<style>
.author {
    padding: 40px 20px;
    text-align: center;
    background-color: #000000;
    color: white;
}
.author img {
    width: 120px;
    height: 120px;
    border-radius: 50%;
}
.author p {
    margin-top: 15px;
    font-size: 1rem;
}
.author-name {
    font-weight: bold;
    font-size: 1.4rem;
    color: white;
}
</style>
<div class="author">
    <img src="https://avatars.githubusercontent.com/u/90271653?v=4" alt="Autor">
    <div class="author-name">
        <p>Ânderson Oliveira</p>
    </div>    
    <p>Engenheiro de Dados | Soluções Logísticas | Automações</p>
    <div style="margin: 10px 0;">
        <a href="https://github.com/MySpaceCrazy" target="_blank">
            <img src="https://raw.githubusercontent.com/MySpaceCrazy/simulador_bin/refs/heads/main/Imagens/github.ico" alt="GitHub" style="width: 32px; height: 32px; margin-right: 10px;">
        </a>
        <a href="https://www.linkedin.com/in/%C3%A2nderson-matheus-flores-de-oliveira-5b92781b4" target="_blank">
            <img src="https://raw.githubusercontent.com/MySpaceCrazy/simulador_bin/refs/heads/main/Imagens/linkedin.ico" alt="LinkedIn" style="width: 32px; height: 32px;">
        </a>
    </div>
    <p class="footer-text">© 2025 Ânderson Oliveira. Todos os direitos reservados.</p>
</div>
""", unsafe_allow_html=True)
