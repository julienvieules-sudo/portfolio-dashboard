import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime
import glob

st.set_page_config(page_title="Mon Patrimoine", layout="wide")
st.title("💼 Mon Patrimoine")

# --- CHARGEMENT RAPIDE ---
@st.cache_data(ttl=3600)
def load_data():
    fichiers = sorted(glob.glob("transactions_*.csv"))
    df_transactions = pd.concat([pd.read_csv(f) for f in fichiers], ignore_index=True)
    df_pea = pd.read_csv("pea.csv")
    eur_usd = yf.Ticker("EURUSD=X").history(period="1d")['Close'].iloc[-1]
    return df_transactions, df_pea, eur_usd

df_transactions, df_pea, eur_usd = load_data()

# --- CTO ---
@st.cache_data(ttl=3600)
def get_valeur_cto(tickers):
    total = 0
    for ticker in tickers:
        try:
            prix = yf.Ticker(ticker).history(period="1d")['Close'].iloc[-1]
            total += prix
        except:
            pass
    return total

# Valeur CTO depuis bilan_clean — on relit le portefeuille
df_ptf = pd.read_csv("portefeuille.csv")
devise_map = df_ptf.set_index('ticker')['devise'].to_dict()

valeur_cto = 0
for _, row in df_ptf.iterrows():
    try:
        prix = yf.Ticker(row['ticker']).history(period="1d")['Close'].iloc[-1]
        valeur = prix * row['quantite']
        if row['devise'] == 'USD':
            valeur = valeur / eur_usd
        valeur_cto += valeur
    except:
        pass

# --- PEA ---
valeur_pea = 0
for _, row in df_pea.iterrows():
    try:
        prix = yf.Ticker(row['ticker']).history(period="1d")['Close'].iloc[-1]
        valeur_pea += prix * row['quantite']
    except:
        pass

# --- CRYPTO ---
@st.cache_data(ttl=300)
def get_valeur_crypto(eur_usd):
    positions = {
        'BTC-USD': 0.04391,
        'ETH-USD': 1.0306,
        'SOL-USD': 3.48,
        'BNB-USD': 6.6556
    }
    total = 0
    for ticker, quantite in positions.items():
        try:
            prix = yf.Ticker(ticker).history(period="1d")['Close'].iloc[-1]
            total += (prix * quantite) / eur_usd
        except:
            pass
    return total

valeur_crypto = get_valeur_crypto(eur_usd)

valeur_totale = valeur_cto + valeur_pea + valeur_crypto

# --- METRICS ---
st.subheader("Vue consolidée du patrimoine financier")

col1, col2, col3, col4 = st.columns(4)
col1.metric("CTO", f"€ {valeur_cto:,.0f}")
col2.metric("PEA", f"€ {valeur_pea:,.0f}")
col3.metric("Crypto", f"€ {valeur_crypto:,.0f}", "À configurer")
col4.metric("Total", f"€ {valeur_totale:,.0f}")

st.divider()

# --- REPARTITION ---
import plotly.express as px

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
    color_discrete_sequence=['#378ADD', '#1D9E75', '#E24B4A']
)
fig.update_traces(
    textposition='outside',
    textinfo='label+percent+value',
    pull=[0.03] * len(data_rep)
)
fig.update_layout(showlegend=False, margin=dict(t=60, b=60, l=60, r=60))
st.plotly_chart(fig, use_container_width=True)

st.caption("Navigation : utilisez le menu à gauche pour accéder au détail de chaque poche.")
