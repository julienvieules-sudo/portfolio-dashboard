import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime

st.set_page_config(page_title="PEA", layout="wide")
st.title("🌱 PEA — Plan d'Épargne en Actions")

# --- CHARGEMENT ---
@st.cache_data(ttl=3600)
@st.cache_data(ttl=3600)
def load_pea():
    data = {
        'ticker': ['PE500.PA', 'PCEU.PA', 'PANX.PA'],
        'nom': ['Amundi PEA S&P 500', 'Amundi PEA MSCI Europe', 'Amundi PEA US Tech'],
        'prix_achat': [26.89, 21.91, 32.95],
        'quantite': [81.0, 17.0, 133.0]
    }
    return pd.DataFrame(data)

@st.cache_data(ttl=3600)
def get_cours_pea(tickers):
    cours = []
    for ticker in tickers:
        try:
            prix = yf.Ticker(ticker).history(period="1d")['Close'].iloc[-1]
            cours.append(float(prix))
        except:
            cours.append(None)
    return cours

df_pea = load_pea()
df_pea['prix_actuel'] = get_cours_pea(df_pea['ticker'].tolist())
df_pea['valeur_investie'] = df_pea['prix_achat'] * df_pea['quantite']
df_pea['valeur_actuelle'] = df_pea['prix_actuel'] * df_pea['quantite']
df_pea['gain'] = df_pea['valeur_actuelle'] - df_pea['valeur_investie']
df_pea['rendement'] = (df_pea['gain'] / df_pea['valeur_investie']) * 100

# --- METRICS ---
gain_total = df_pea['gain'].sum()
valeur_investie_totale = df_pea['valeur_investie'].sum()
valeur_actuelle_totale = df_pea['valeur_actuelle'].sum()
rendement_global = (gain_total / valeur_investie_totale) * 100

col1, col2, col3, col4 = st.columns(4)
col1.metric("Valeur totale", f"€ {valeur_actuelle_totale:,.0f}")
col2.metric("Montant investi", f"€ {valeur_investie_totale:,.0f}")
col3.metric("Plus-values latentes", f"€ {gain_total:,.0f}")
col4.metric("Rendement global", f"{rendement_global:.1f}%")

st.divider()

# --- TABLEAU ---
st.subheader("Détail des positions")

display = df_pea[['ticker', 'nom', 'quantite', 'prix_achat', 'valeur_investie',
                   'prix_actuel', 'valeur_actuelle', 'gain', 'rendement']].copy()
display.columns = ['Ticker', 'Nom', 'Quantité', 'Prix achat', 'Investi (€)',
                   'Prix actuel', 'Valeur (€)', 'Gain (€)', 'Rendement %']

# Ligne total
total_row = pd.DataFrame([{
    'Ticker': 'TOTAL', 'Nom': '', 'Quantité': '',
    'Prix achat': '', 'Investi (€)': valeur_investie_totale,
    'Prix actuel': '', 'Valeur (€)': valeur_actuelle_totale,
    'Gain (€)': gain_total, 'Rendement %': ''
}])
display = pd.concat([display, total_row], ignore_index=True)

st.dataframe(display.style.format({
    'Quantité': lambda x: f'{x:.2f}' if isinstance(x, float) else x,
    'Prix achat': lambda x: f'{x:.2f}' if isinstance(x, float) else x,
    'Investi (€)': lambda x: f'{x:,.1f}' if isinstance(x, float) else x,
    'Prix actuel': lambda x: f'{x:.2f}' if isinstance(x, float) else x,
    'Valeur (€)': lambda x: f'{x:,.1f}' if isinstance(x, float) else x,
    'Gain (€)': lambda x: f'{x:+,.1f}' if isinstance(x, float) else x,
    'Rendement %': lambda x: f'{x:+.1f}%' if isinstance(x, float) else x,
}), use_container_width=True)

st.divider()

# --- GRAPHIQUES ---
import plotly.express as px
import plotly.graph_objects as go

col_a, col_b = st.columns(2)

with col_a:
    fig1 = px.pie(
        df_pea.dropna(subset=['prix_actuel']),
        values='valeur_actuelle',
        names='ticker',
        title='Répartition du PEA',
        hole=0.45,
        color_discrete_sequence=px.colors.qualitative.Set2
    )
    fig1.update_traces(
        textposition='outside',
        textinfo='label+percent',
        pull=[0.03] * len(df_pea)
    )
    fig1.update_layout(showlegend=False, margin=dict(t=60, b=60, l=60, r=60))
    st.plotly_chart(fig1, use_container_width=True)

with col_b:
    fig2 = px.bar(
        df_pea.dropna(subset=['prix_actuel']).sort_values('rendement', ascending=False),
        x='ticker', y='rendement',
        title='Rendement par ETF (%)',
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

# --- HISTORIQUE DES COURS ---
st.subheader("Évolution des ETF depuis le premier achat")

@st.cache_data(ttl=3600)
def get_historique_pea(tickers, date_debut):
    return yf.download(tickers, start=date_debut,
                       end=datetime.today().strftime('%Y-%m-%d'))['Close']

date_debut_pea = "2023-01-01"
historique_pea = get_historique_pea(df_pea['ticker'].tolist(), date_debut_pea)

fig3 = go.Figure()
colors = ['#378ADD', '#1D9E75', '#E24B4A']

for i, ticker in enumerate(df_pea['ticker'].tolist()):
    if ticker in historique_pea.columns:
        serie = historique_pea[ticker].dropna()
        serie_norm = (serie / serie.iloc[0]) * 100
        fig3.add_trace(go.Scatter(
            x=serie_norm.index,
            y=serie_norm.values,
            name=ticker,
            line=dict(width=2, color=colors[i % len(colors)])
        ))

fig3.update_layout(
    title='Performance comparative des ETF (base 100)',
    xaxis_title='',
    yaxis_title='Performance (base 100)',
    hovermode='x unified',
    margin=dict(t=60, b=20)
)
st.plotly_chart(fig3, use_container_width=True)
st.caption("Note : base 100 au 01/01/2023. Cours en EUR.")
