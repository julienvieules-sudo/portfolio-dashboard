import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Crypto", layout="wide")
st.title("₿ Crypto")

# --- POSITIONS ---
@st.cache_data(ttl=3600)
def load_crypto():
    data = {
        'ticker': ['BTC-USD', 'ETH-USD', 'SOL-USD', 'BNB-USD'],
        'nom': ['Bitcoin', 'Ethereum', 'Solana', 'BNB'],
        'prix_achat': [36372.98, 1978.57, 71.97, 425.63],
        'quantite': [0.04391, 1.0306, 3.48, 6.6556]
    }
    return pd.DataFrame(data)

@st.cache_data(ttl=300)
def get_cours_crypto(tickers):
    cours = []
    for ticker in tickers:
        try:
            prix = yf.Ticker(ticker).history(period="1d")['Close'].iloc[-1]
            cours.append(float(prix))
        except:
            cours.append(None)
    return cours

@st.cache_data(ttl=3600)
def get_eur_usd():
    return yf.Ticker("EURUSD=X").history(period="1d")['Close'].iloc[-1]

df_crypto = load_crypto()
df_crypto['prix_actuel'] = get_cours_crypto(df_crypto['ticker'].tolist())
eur_usd = get_eur_usd()

df_crypto['valeur_investie'] = (df_crypto['prix_achat'] * df_crypto['quantite']) / eur_usd
df_crypto['valeur_actuelle'] = (df_crypto['prix_actuel'] * df_crypto['quantite']) / eur_usd
df_crypto['gain'] = df_crypto['valeur_actuelle'] - df_crypto['valeur_investie']
df_crypto['rendement'] = (df_crypto['gain'] / df_crypto['valeur_investie']) * 100

bilan_clean = df_crypto.dropna(subset=['prix_actuel']).copy()

# --- METRICS ---
gain_total = bilan_clean['gain'].sum()
valeur_investie_totale = bilan_clean['valeur_investie'].sum()
valeur_actuelle_totale = bilan_clean['valeur_actuelle'].sum()
rendement_global = (gain_total / valeur_investie_totale) * 100

col1, col2, col3, col4 = st.columns(4)
col1.metric("Valeur totale", f"€ {valeur_actuelle_totale:,.0f}")
col2.metric("Montant investi", f"€ {valeur_investie_totale:,.0f}")
col3.metric("Plus-values latentes", f"€ {gain_total:,.0f}")
col4.metric("Rendement global", f"{rendement_global:.1f}%")

st.caption(f"Taux EUR/USD : {eur_usd:.4f}")

st.divider()

# --- TABLEAU ---
st.subheader("Détail des positions")

display = bilan_clean[['ticker', 'nom', 'quantite', 'prix_achat',
                        'valeur_investie', 'prix_actuel',
                        'valeur_actuelle', 'gain', 'rendement']].copy()
display.columns = ['Ticker', 'Coin', 'Quantité', 'Prix achat ($)',
                   'Investi (€)', 'Prix actuel ($)',
                   'Valeur (€)', 'Gain (€)', 'Rendement %']

total_row = pd.DataFrame([{
    'Ticker': 'TOTAL', 'Coin': '', 'Quantité': '',
    'Prix achat ($)': '', 'Investi (€)': valeur_investie_totale,
    'Prix actuel ($)': '', 'Valeur (€)': valeur_actuelle_totale,
    'Gain (€)': gain_total, 'Rendement %': ''
}])
display = pd.concat([display, total_row], ignore_index=True)

st.dataframe(display.style.format({
    'Quantité': lambda x: f'{x:.4f}' if isinstance(x, float) else x,
    'Prix achat ($)': lambda x: f'{x:,.2f}' if isinstance(x, float) else x,
    'Investi (€)': lambda x: f'{x:,.1f}' if isinstance(x, float) else x,
    'Prix actuel ($)': lambda x: f'{x:,.2f}' if isinstance(x, float) else x,
    'Valeur (€)': lambda x: f'{x:,.1f}' if isinstance(x, float) else x,
    'Gain (€)': lambda x: f'{x:+,.1f}' if isinstance(x, float) else x,
    'Rendement %': lambda x: f'{x:+.1f}%' if isinstance(x, float) else x,
}), use_container_width=True)

st.divider()

# --- GRAPHIQUES ---
col_a, col_b = st.columns(2)

with col_a:
    fig1 = px.pie(
        bilan_clean,
        values='valeur_actuelle',
        names='nom',
        title='Répartition du portefeuille crypto',
        hole=0.45,
        color_discrete_sequence=['#F7931A', '#627EEA', '#9945FF', '#F3BA2F']
    )
    fig1.update_traces(
        textposition='outside',
        textinfo='label+percent',
        pull=[0.03] * len(bilan_clean)
    )
    fig1.update_layout(showlegend=False, margin=dict(t=60, b=60, l=60, r=60))
    st.plotly_chart(fig1, use_container_width=True)

with col_b:
    fig2 = px.bar(
        bilan_clean.sort_values('rendement', ascending=False),
        x='nom', y='rendement',
        title='Rendement par coin (%)',
        color='rendement',
        color_continuous_scale=['red', 'lightgrey', 'green'],
        color_continuous_midpoint=0,
        text='rendement'
    )
    fig2.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
    fig2.update_layout(
        coloraxis_showscale=False,
        xaxis_title='', yaxis_title='',
        margin=dict(t=60, b=20)
    )
    st.plotly_chart(fig2, use_container_width=True)

# --- HISTORIQUE ---
st.subheader("Évolution des cryptos depuis 2021")

@st.cache_data(ttl=3600)
def get_historique_crypto(tickers, date_debut):
    return yf.download(tickers, start=date_debut,
                       end=datetime.today().strftime('%Y-%m-%d'))['Close']

historique_crypto = get_historique_crypto(
    df_crypto['ticker'].tolist(), "2021-01-01"
)

fig3 = go.Figure()
colors = ['#F7931A', '#627EEA', '#9945FF', '#F3BA2F']

for i, (ticker, nom) in enumerate(zip(df_crypto['ticker'], df_crypto['nom'])):
    if ticker in historique_crypto.columns:
        serie = historique_crypto[ticker].dropna()
        serie_norm = (serie / serie.iloc[0]) * 100
        fig3.add_trace(go.Scatter(
            x=serie_norm.index,
            y=serie_norm.values,
            name=nom,
            line=dict(width=2, color=colors[i])
        ))

fig3.update_layout(
    title='Performance comparative (base 100 depuis jan. 2021)',
    xaxis_title='',
    yaxis_title='Performance (base 100)',
    hovermode='x unified',
    margin=dict(t=60, b=20)
)
st.plotly_chart(fig3, use_container_width=True)
