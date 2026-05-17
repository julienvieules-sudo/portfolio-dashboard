import streamlit as st
import pandas as pd
import yfinance as yf
import glob
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title="Mon Patrimoine", layout="wide")
st.title("💼 Mon Patrimoine")

# --- TAUX EUR/USD ---
@st.cache_data(ttl=3600)
def get_eur_usd():
    return yf.Ticker("EURUSD=X").history(period="1d")['Close'].iloc[-1]

eur_usd = get_eur_usd()

# --- VALEUR CTO ---
@st.cache_data(ttl=3600)
def get_bilan_cto(eur_usd):
    df_ptf = pd.read_csv("portefeuille.csv")
    devise_map = df_ptf.set_index('ticker')['devise'].to_dict()
    valeur_actuelle = 0
    valeur_investie = 0
    for _, row in df_ptf.iterrows():
        try:
            prix = yf.Ticker(row['ticker']).history(period="1d")['Close'].iloc[-1]
            if row['devise'] == 'USD':
                valeur_actuelle += (prix * row['quantite']) / eur_usd
                valeur_investie += (row['prix_achat'] * row['quantite']) / eur_usd
            else:
                valeur_actuelle += prix * row['quantite']
                valeur_investie += row['prix_achat'] * row['quantite']
        except:
            pass
    return valeur_actuelle, valeur_investie

# --- VALEUR PEA ---
@st.cache_data(ttl=3600)
def get_bilan_pea():
    positions = [
        ('PE500.PA', 26.89, 81.0),
        ('PCEU.PA', 21.91, 17.0),
        ('PANX.PA', 32.95, 133.0),
    ]
    valeur_actuelle = 0
    valeur_investie = 0
    for ticker, prix_achat, quantite in positions:
        try:
            prix = yf.Ticker(ticker).history(period="1d")['Close'].iloc[-1]
            valeur_actuelle += prix * quantite
            valeur_investie += prix_achat * quantite
        except:
            pass
    return valeur_actuelle, valeur_investie

# --- VALEUR CRYPTO ---
@st.cache_data(ttl=300)
def get_bilan_crypto(eur_usd):
    positions = [
        ('BTC-USD', 36372.98, 0.04391),
        ('ETH-USD', 1978.57, 1.0306),
        ('SOL-USD', 71.97, 3.48),
        ('BNB-USD', 425.63, 6.6556),
    ]
    valeur_actuelle = 0
    valeur_investie = 0
    for ticker, prix_achat, quantite in positions:
        try:
            prix = yf.Ticker(ticker).history(period="1d")['Close'].iloc[-1]
            valeur_actuelle += (prix * quantite) / eur_usd
            valeur_investie += (prix_achat * quantite) / eur_usd
        except:
            pass
    return valeur_actuelle, valeur_investie

with st.spinner("Chargement..."):
    valeur_cto, investie_cto = get_bilan_cto(eur_usd)
    valeur_pea, investie_pea = get_bilan_pea()
    valeur_crypto, investie_crypto = get_bilan_crypto(eur_usd)

valeur_totale = valeur_cto + valeur_pea + valeur_crypto
investie_totale = investie_cto + investie_pea + investie_crypto
pv_cto = valeur_cto - investie_cto
pv_pea = valeur_pea - investie_pea
pv_crypto = valeur_crypto - investie_crypto
pv_totale = pv_cto + pv_pea + pv_crypto
rendement_global = (pv_totale / investie_totale) * 100

# --- METRICS GLOBALES ---
st.subheader("Vue consolidée")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Patrimoine total", f"€ {valeur_totale:,.0f}")
col2.metric("Total investi", f"€ {investie_totale:,.0f}")
col3.metric("Plus-values totales", f"€ {pv_totale:,.0f}")
col4.metric("Rendement global", f"{rendement_global:.1f}%", f"€ {pv_totale:+,.0f}")

st.divider()

# --- DETAIL PAR POCHE ---
col1, col2, col3 = st.columns(3)
col1.metric("CTO", f"€ {valeur_cto:,.0f}", f"€ {pv_cto:+,.0f}")
col2.metric("PEA", f"€ {valeur_pea:,.0f}", f"€ {pv_pea:+,.0f}")
col3.metric("Crypto", f"€ {valeur_crypto:,.0f}", f"€ {pv_crypto:+,.0f}")

st.divider()

# --- REPARTITION ---
data_rep = pd.DataFrame([
    {'Poche': 'CTO', 'Valeur': valeur_cto},
    {'Poche': 'PEA', 'Valeur': valeur_pea},
    {'Poche': 'Crypto', 'Valeur': valeur_crypto},
])

fig = px.pie(
    data_rep,
    values='Valeur',
    names='Poche',
    title='Répartition du patrimoine financier',
    hole=0.45,
    color_discrete_sequence=['#378ADD', '#1D9E75', '#F7931A']
)
fig.update_traces(
    textposition='outside',
    texttemplate='%{label}<br>%{percent:.0%}<br>€ %{value:,.0f}',
    pull=[0.03] * 3
)
fig.update_layout(showlegend=False, margin=dict(t=60, b=60, l=60, r=60))
st.plotly_chart(fig, use_container_width=True)

st.caption("Navigation : utilisez le menu à gauche pour accéder au détail de chaque poche.")
