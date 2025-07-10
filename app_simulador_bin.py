# app_simulador_bin.py

import streamlit as st
import pandas as pd
import sqlite3
import os
import io
import time
import datetime

# --- Atualiza o banco SQLite diretamente ---
PASTA_CSV = "arquivos"
ARQUIVOS_CSV = {
    "info_tipo_bin": "info_tipo_bin.csv",
    "info_posicao_bin": "info_posicao_bin.csv"
}

conn = sqlite3.connect("logistica.db")

for tabela, nome_arquivo in ARQUIVOS_CSV.items():
    caminho = os.path.join(PASTA_CSV, nome_arquivo)
    if os.path.exists(caminho):
        try:
            df = pd.read_csv(caminho, sep=";", engine="python", encoding="latin1")
            df.columns = [c.strip().replace(" ", "_") for c in df.columns]

            if tabela == "info_tipo_bin" and "Volume_(L)" in df.columns:
                df["Volume_(L)"] = df["Volume_(L)"].astype(str).str.replace(",", ".", regex=False)
                df["Volume_(L)"] = pd.to_numeric(df["Volume_(L)"], errors="coerce").fillna(0)

            df.to_sql(tabela, conn, if_exists="replace", index=False)
            print(f"🔄 Atualizado: {tabela}")
        except Exception as e:
            print(f"❌ Erro ao processar {nome_arquivo}: {e}")
    else:
        print(f"⚠️ Arquivo não encontrado: {nome_arquivo}")

conn.close()
print("✅ Banco logistica.db atualizado com sucesso.")

# --- Configuração inicial ---
st.set_page_config(page_title="Simulador de Bins de Picking", page_icon="📦", layout="wide")
st.title("📦 Simulador de Quantidade de Bins por Posição de Picking")

# --- Upload do arquivo do cliente ---
arquivo = st.file_uploader("📂 Selecionar arquivo de simulação (.xlsx)", type=["xlsx"])

if arquivo:
    try:
        inicio_tempo = time.time()
        df_base = pd.read_excel(arquivo, sheet_name="base_item_pacotes")
        df_posicoes_prod = pd.read_excel(arquivo, sheet_name="info_posicao_produtos")

        total_linhas_base = len(df_base)
        contador_sucesso = 0

        # --- Validação ---
        colunas_obrigatorias_base = ["Produto", "Qtd.solicitada total", "Recebedor mercadoria", "Peso", "UM peso", "Volume", "UM volume", "Área de atividade"]
        colunas_obrigatorias_pos = ["Posição no depósito", "Tipo de depósito", "Área armazmto", "Produto"]

        for col in colunas_obrigatorias_base:
            if col not in df_base.columns:
                st.error(f"Coluna obrigatória ausente na base_item_pacotes: {col}")
                st.stop()

        for col in colunas_obrigatorias_pos:
            if col not in df_posicoes_prod.columns:
                st.error(f"Coluna obrigatória ausente na info_posicao_produtos: {col}")
                st.stop()

        # --- Ajustes e normalizações ---
        df_base["Recebedor mercadoria"] = df_base["Recebedor mercadoria"].astype(str).str.zfill(5)
        df_base["Tipo_de_depósito"] = df_base["Área de atividade"].astype(str).str[:2].str.zfill(4)
        df_base["Peso"] = pd.to_numeric(df_base["Peso"], errors="coerce").fillna(0)
        df_base["Volume"] = pd.to_numeric(df_base["Volume"], errors="coerce").fillna(0)
        df_base["Qtd.solicitada total"] = pd.to_numeric(df_base["Qtd.solicitada total"], errors="coerce").fillna(1)
        df_base.loc[df_base["UM peso"] == "G", "Peso"] /= 1000
        df_base.loc[df_base["UM volume"] == "ML", "Volume"] /= 1000
        df_base["Volume unitário (L)"] = df_base["Volume"] / df_base["Qtd.solicitada total"]

        # --- Lê tabelas do banco ---
        conn = sqlite3.connect("logistica.db")
        df_tipo_bin = pd.read_sql("SELECT * FROM info_tipo_bin", conn)
        df_posicao_bin = pd.read_sql("SELECT * FROM info_posicao_bin", conn)
        conn.close()

        # --- Renomeia e normaliza colunas ---
        df_posicoes_prod = df_posicoes_prod.rename(columns={"Posição no depósito": "Posicao", "Tipo de depósito": "Tipo_de_depósito"})
        df_posicao_bin = df_posicao_bin.rename(columns={"Posição_no_depósito": "Posicao", "Tipo_de_depósito": "Tipo_de_depósito", "Qtd._Caixas_BIN_ABASTECIMENTO": "Quantidade_Bin"})
        df_tipo_bin = df_tipo_bin.rename(columns={"Tipo": "Tipo", "Volume_(L)": "Volume_max_L"})

        df_tipo_bin["Tipo"] = df_tipo_bin["Tipo"].astype(str).str.strip()
        df_posicao_bin["Tipo"] = df_posicao_bin["Tipo"].astype(str).str.strip()
        df_posicao_bin["Tipo_de_depósito"] = df_posicao_bin["Tipo_de_depósito"].astype(str).str.zfill(4).str.strip()
        df_posicoes_prod["Tipo_de_depósito"] = df_posicoes_prod["Tipo_de_depósito"].astype(str).str.zfill(4).str.strip()
        df_tipo_bin["Volume_max_L"] = pd.to_numeric(df_tipo_bin["Volume_max_L"], errors="coerce").fillna(0)

        # --- Joins ---
        df_posicoes_prod = df_posicoes_prod.merge(df_posicao_bin, on=["Posicao", "Tipo_de_depósito"], how="left")
        df_posicoes_prod = df_posicoes_prod.merge(df_tipo_bin, on="Tipo", how="left")

        # --- Cálculo das bins ---
        resultado = []
        for _, row in df_base.iterrows():
            produto = row["Produto"]
            estrutura = row["Tipo_de_depósito"]
            loja = row["Recebedor mercadoria"]
            volume_unitario = row["Volume unitário (L)"]
            qtd = row["Qtd.solicitada total"]

            posicoes = df_posicoes_prod[(df_posicoes_prod["Produto"] == produto) & (df_posicoes_prod["Tipo_de_depósito"] == estrutura)]

            if posicoes.empty:
                resultado.append({
                    "Produto": produto, "Recebedor": loja, "Estrutura": estrutura,
                    "Posicao": "N/A", "Tipo_Bin": "N/A",
                    "Bins_Necessarias": "Erro: Produto sem posição",
                    "Bins_Disponiveis": "-", "Diferença": "-",
                    "Quantidade_Total": "-", "Volume_Total": "-", "Volumetria_Máxima": "-"
                })
                continue

            volume_total = volume_unitario * qtd
            for _, pos in posicoes.iterrows():
                posicao = pos.get("Posicao", "N/A")
                tipo_bin = pos.get("Tipo", "N/A")
                volume_max = pos.get("Volume_max_L", 1)

                if pd.isna(volume_max) or volume_max <= 0:
                    resultado.append({
                        "Produto": produto, "Recebedor": loja, "Estrutura": estrutura,
                        "Posicao": posicao, "Tipo_Bin": tipo_bin,
                        "Bins_Necessarias": "Erro: Bin sem volume",
                        "Bins_Disponiveis": pos.get("Quantidade_Bin", 0), "Diferença": "-",
                        "Quantidade_Total": "-", "Volume_Total": "-", "Volumetria_Máxima": "-"
                    })
                    continue

                bins_necessarias = int(-(-volume_total // volume_max))
                bins_disponiveis = int(pos.get("Quantidade_Bin", 0))
                diferenca = bins_disponiveis - bins_necessarias
                quantidade_total = min(bins_necessarias * qtd, qtd)
                volume_total_bins = quantidade_total * volume_unitario
                volumetria_maxima = bins_disponiveis * volume_max

                resultado.append({
                    "Produto": produto, "Recebedor": loja, "Estrutura": estrutura,
                    "Posicao": posicao, "Tipo_Bin": tipo_bin,
                    "Bins_Necessarias": bins_necessarias,
                    "Bins_Disponiveis": bins_disponiveis,
                    "Diferença": diferenca,
                    "Quantidade_Total": quantidade_total,
                    "Volume_Total": round(volume_total_bins, 2),
                    "Volumetria_Máxima": round(volumetria_maxima, 2)
                })
                contador_sucesso += 1

        df_resultado = pd.DataFrame(resultado)

        # --- Relatórios e exibição ---
        # --- Relatório Resumo por Produto e Estrutura ---
        df_resumo = df_resultado.merge(
            df_posicao_bin[["Posicao", "Tipo_de_depósito", "Estrutura"]].drop_duplicates(),
            how="left",
            left_on=["Posicao", "Estrutura"],
            right_on=["Posicao", "Tipo_de_depósito"]
        )

        df_resumo = df_resumo.merge(
            df_posicoes_prod[["Produto", "Descrição breve do produto"]].drop_duplicates(),
            on="Produto",
            how="left"
        )

        df_resumo = df_resumo[[
            "Estrutura_x",
            "Estrutura_y",
            "Posicao",
            "Produto",
            "Descrição breve do produto",
            "Tipo_Bin",
            "Bins_Necessarias",
            "Bins_Disponiveis",
            "Diferença",
            "Quantidade_Total",
            "Volume_Total",
            "Volumetria_Máxima"
        ]]

        df_resumo.columns = [
            "Estrutura",
            "Descrição - estrutura",
            "Posição",
            "Produto",
            "Descrição – produto",
            "Tipo_Bin",
            "Bins_Necessarias",
            "Bins_Disponiveis",
            "Diferença",
            "Quantidade Total",
            "Volume Total",
            "Volumetria Máxima"
        ]

        # --- Exibe e download Detalhado ---
        st.subheader("📊 Detalhado por Loja, Estrutura e Produto")
        st.dataframe(df_resultado)

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            df_resultado.to_excel(writer, sheet_name="Detalhado Bins", index=False)

        st.download_button(
            label="📥 Baixar Relatório Excel",
            data=buffer.getvalue(),
            file_name="Simulacao_Bins.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        st.markdown("---")

        # --- Exibe e download Resumo por Produto e Estrutura ---
        st.subheader("📊 Resumo por Produto e Estrutura")
        st.dataframe(df_resumo)

        buffer_resumo = io.BytesIO()
        with pd.ExcelWriter(buffer_resumo, engine="xlsxwriter") as writer:
            df_resumo.to_excel(writer, sheet_name="Resumo Produto Estrutura", index=False)

        st.download_button(
            label="📥 Baixar Resumo Produto/Estrutura",
            data=buffer_resumo.getvalue(),
            file_name="Resumo_Produto_Estrutura.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # --- Calcula Resumo - Posições Não Atendem ---
        df_nao_atendem = df_resumo[df_resumo["Diferença"].apply(lambda x: pd.to_numeric(x, errors='coerce')).lt(0, fill_value=False)]
        resumo_nao_atendem = (
            df_nao_atendem.groupby("Descrição - estrutura")["Posição"]
            .nunique()
            .reset_index(name="Posições - Não Atendem")
        )
        total_geral_nao_atendem = resumo_nao_atendem["Posições - Não Atendem"].sum()

        # --- Calcula Resumo - Posições OK ---
        df_ok = df_resumo[df_resumo["Diferença"].apply(lambda x: pd.to_numeric(x, errors='coerce')).ge(0, fill_value=False)]
        resumo_ok = (
            df_ok.groupby("Descrição - estrutura")["Posição"]
            .nunique()
            .reset_index(name="Posições - OK")
        )
        total_geral_ok = resumo_ok["Posições - OK"].sum()

        # --- Exibe os dois resumos lado a lado ---
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("🚨 Resumo - Posições Não Atendem")
            st.dataframe(resumo_nao_atendem, use_container_width=True)
            st.write(f"**Total Geral: {total_geral_nao_atendem} posições**")

        with col2:
            st.subheader("✅ Resumo - Posições OK")
            st.dataframe(resumo_ok, use_container_width=True)
            st.write(f"**Total Geral: {total_geral_ok} posições**")

        st.markdown("---")
        st.success("✅ Simulação concluída com sucesso!")

        # --- Tempo total da simulação ---
        tempo_total = time.time() - inicio_tempo
        tempo_formatado = str(datetime.timedelta(seconds=int(tempo_total)))

        st.success("✅ Simulação concluída com sucesso!")
        st.write(f"⏱️ Tempo total da simulação: **{tempo_formatado}**")
        st.write(f"📄 Total de linhas da base: **{total_linhas_base}**")
        st.write(f"✔️ Linhas simuladas sem erro: **{contador_sucesso}**")


    except Exception as e:
        st.error(f"Erro no processamento: {e}")

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
</style>

<style>
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
# --- Fim do rodapé ---