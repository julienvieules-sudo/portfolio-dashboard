import streamlit as st
import pandas as pd
import yfinance as yf
import glob
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Mon Portefeuille", layout="wide")
st.title("📈 Mon Portefeuille")

# --- TAUX EUR/USD ---
@st.cache_data(ttl=3600)
def get_eur_usd():
    taux = yf.Ticker("EURUSD=X")
    return taux.history(period="1d")['Close'].iloc[-1]

# --- CHARGEMENT TRANSACTIONS ---
@st.cache_data(ttl=3600)
def load_transactions():
    fichiers = sorted(glob.glob("transactions_*.csv"))
    df = pd.concat([pd.read_csv(f) for f in fichiers], ignore_index=True)
    return df.sort_values('Time').reset_index(drop=True)

# --- CHARGEMENT PORTEFEUILLE ---
@st.cache_data(ttl=3600)
def load_portefeuille():
    return pd.read_csv("portefeuille.csv")

with st.spinner("Chargement des données..."):
    eur_usd = get_eur_usd()
    df_transactions = load_transactions()
    df_ptf = load_portefeuille()

st.caption(f"Taux EUR/USD : {eur_usd:.4f} — {len(df_transactions)} transactions chargées")

# --- CALCUL QUANTITES ---
def calc_positions(df):
    achats = df[df['Action'].isin(['Market buy', 'Limit buy'])].copy()
    ventes = df[df['Action'].isin(['Market sell', 'Limit sell'])].copy()
    splits_open = df[df['Action'] == 'Stock split open'].copy()
    splits_close = df[df['Action'] == 'Stock split close'].copy()

    for d in [achats, ventes, splits_open, splits_close]:
        d['No. of shares'] = pd.to_numeric(d['No. of shares'], errors='coerce')

    total_achete = achats.groupby('Ticker')['No. of shares'].sum()
    total_vendu = ventes.groupby('Ticker')['No. of shares'].sum()
    total_split_open = splits_open.groupby('Ticker')['No. of shares'].sum()
    total_split_close = splits_close.groupby('Ticker')['No. of shares'].sum()

    positions = pd.DataFrame({
        'achete': total_achete,
        'vendu': total_vendu,
        'split_open': total_split_open,
        'split_close': total_split_close
    }).fillna(0)

    positions['quantite_actuelle'] = (
        positions['achete'] - positions['vendu']
        - positions['split_close'] + positions['split_open']
    )
    return positions[positions['quantite_actuelle'] > 0.001].copy()

# --- CALCUL PRIX DE REVIENT ---
def calc_prix_revient(df, positions):
    achats = df[df['Action'].isin(['Market buy', 'Limit buy'])].copy()
    achats['No. of shares'] = pd.to_numeric(achats['No. of shares'], errors='coerce')
    achats['Price / share'] = pd.to_numeric(achats['Price / share'], errors='coerce')
    achats['montant'] = achats['No. of shares'] * achats['Price / share']

    total_investi = achats.groupby('Ticker')['montant'].sum()
    total_achete = achats.groupby('Ticker')['No. of shares'].sum()

    prix_revient = (total_investi / total_achete).reset_index()
    prix_revient.columns = ['Ticker', 'prix_revient_moyen']

    splits_open = df[df['Action'] == 'Stock split open'].copy()
    splits_close = df[df['Action'] == 'Stock split close'].copy()
    splits_open['No. of shares'] = pd.to_numeric(splits_open['No. of shares'], errors='coerce')
    splits_close['No. of shares'] = pd.to_numeric(splits_close['No. of shares'], errors='coerce')

    splits_ratio = pd.DataFrame({
        'open': splits_open.groupby('Ticker')['No. of shares'].sum(),
        'close': splits_close.groupby('Ticker')['No. of shares'].sum()
    }).dropna()
    splits_ratio['ratio'] = splits_ratio['open'] / splits_ratio['close']

    for ticker, row in splits_ratio.iterrows():
        mask = prix_revient['Ticker'] == ticker
        prix_revient.loc[mask, 'prix_revient_moyen'] /= row['ratio']

    return prix_revient

# --- COURS EN TEMPS REEL ---
@st.cache_data(ttl=3600)
def get_cours(tickers):
    cours = []
    for ticker in tickers:
        try:
            prix = yf.Ticker(ticker).history(period="1d")['Close'].iloc[-1]
            cours.append(prix)
        except:
            cours.append(None)
    return cours

positions = calc_positions(df_transactions)
prix_revient = calc_prix_revient(df_transactions, positions)

bilan = positions[['quantite_actuelle']].copy().reset_index()
bilan = bilan.merge(prix_revient, on='Ticker', how='left')
bilan['prix_actuel'] = get_cours(bilan['Ticker'].tolist())
bilan['valeur_investie'] = bilan['prix_revient_moyen'] * bilan['quantite_actuelle']
bilan['valeur_actuelle'] = bilan['prix_actuel'] * bilan['quantite_actuelle']
bilan['gain'] = bilan['valeur_actuelle'] - bilan['valeur_investie']
bilan['rendement'] = (bilan['gain'] / bilan['valeur_investie']) * 100
bilan_clean = bilan.dropna(subset=['prix_actuel']).copy()

# --- DIVIDENDES / INTERETS / FRAIS ---
dividendes = df_transactions[df_transactions['Action'].isin([
    'Dividend (Dividends paid by us corporations)',
    'Dividend (Dividend)',
    'Dividend (Dividend manufactured payment)',
    'Dividend adjustment'
])]
interets = df_transactions[df_transactions['Action'] == 'Interest on cash']

total_dividendes = dividendes['Total'].sum()
total_interets = interets['Total'].sum()
total_frais_change = df_transactions['Currency conversion fee'].sum()
total_ttf = df_transactions['French transaction tax'].sum()
total_retenue = df_transactions['Withholding tax'].sum()
revenu_net = total_dividendes + total_interets + total_frais_change - total_ttf - total_retenue

gain_total = bilan_clean['gain'].sum()
valeur_investie_totale = bilan_clean['valeur_investie'].sum()
rendement_global = (gain_total / valeur_investie_totale) * 100

# --- METRICS ---
col1, col2, col3, col4 = st.columns(4)
col1.metric("Plus-values latentes", f"{gain_total:,.0f} $")
col2.metric("Rendement global", f"{rendement_global:.1f} %")
col3.metric("Dividendes nets", f"{total_dividendes:.0f} €")
col4.metric("Revenu net total", f"{revenu_net:.0f} €")

st.divider()

# --- GRAPHIQUES ---
col_a, col_b = st.columns(2)

with col_a:
    fig1 = px.pie(bilan_clean, values='valeur_actuelle', names='Ticker',
                  title='Répartition du portefeuille')
    st.plotly_chart(fig1, use_container_width=True)

with col_b:
    fig2 = px.bar(bilan_clean.sort_values('rendement', ascending=False),
                  x='Ticker', y='rendement', title='Rendement par position (%)',
                  color='rendement',
                  color_continuous_scale=['red', 'lightgrey', 'green'],
                  color_continuous_midpoint=0)
    st.plotly_chart(fig2, use_container_width=True)

# --- TABLEAU ---
st.subheader("Détail des positions")
display = bilan_clean[['Ticker', 'quantite_actuelle', 'prix_revient_moyen', 'prix_actuel', 'gain', 'rendement']].copy()
display.columns = ['Ticker', 'Quantité', 'Prix achat', 'Prix actuel', 'Gain', 'Rendement %']
display = display.sort_values('Gain', ascending=False)
st.dataframe(display.style.format({
    'Quantité': '{:.2f}',
    'Prix achat': '{:.2f}',
    'Prix actuel': '{:.2f}',
    'Gain': '{:+.2f}',
    'Rendement %': '{:+.1f}%'
}), use_container_width=True)

st.divider()

# --- BILAN REVENUS ---
st.subheader("Bilan revenus & frais")
col_x, col_y = st.columns(2)
with col_x:
    st.metric("Dividendes bruts", f"{total_dividendes:.2f} €")
    st.metric("Intérêts sur cash", f"{total_interets:.2f} €")
    st.metric("Revenu net", f"{revenu_net:.2f} €")
with col_y:
    st.metric("Retenue à la source", f"-{total_retenue:.2f} €")
    st.metric("TTF", f"-{total_ttf:.2f} €")
    st.metric("Frais de change", f"{total_frais_change:.2f} €")
