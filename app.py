import streamlit as st
import pandas as pd
import yfinance as yf
import glob
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(page_title="Mon Portefeuille", layout="wide")
st.title("📈 Mon Portefeuille")

# --- TOGGLE DEVISE ---
devise_affichage = st.radio("Vision", ["EUR", "USD"], horizontal=True)
st.divider()

# --- CHARGEMENT DONNEES ---
@st.cache_data(ttl=3600)
def load_all():
    # Transactions
    fichiers = sorted(glob.glob("transactions_*.csv"))
    df = pd.concat([pd.read_csv(f) for f in fichiers], ignore_index=True)
    df = df.sort_values('Time').reset_index(drop=True)

    # Portefeuille
    df_ptf = pd.read_csv("portefeuille.csv")

    # Taux EUR/USD actuel
    eur_usd = yf.Ticker("EURUSD=X").history(period="1d")['Close'].iloc[-1]

    # Historique EUR/USD
    eur_usd_hist = yf.download("EURUSD=X", start="2023-07-01",
                                end=datetime.today().strftime('%Y-%m-%d'))['Close'].squeeze()
    eur_usd_hist.index = pd.to_datetime(eur_usd_hist.index).tz_localize(None)

    return df, df_ptf, eur_usd, eur_usd_hist

with st.spinner("Chargement des données..."):
    df_transactions, df_ptf, eur_usd, eur_usd_hist = load_all()

st.caption(f"Taux EUR/USD actuel : {eur_usd:.4f} — {len(df_transactions)} transactions chargées")

# --- CALCUL POSITIONS ---
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
def calc_prix_revient(df, eur_usd_hist):
    achats = df[df['Action'].isin(['Market buy', 'Limit buy'])].copy()
    achats['No. of shares'] = pd.to_numeric(achats['No. of shares'], errors='coerce')
    achats['Price / share'] = pd.to_numeric(achats['Price / share'], errors='coerce')
    achats['Exchange rate'] = pd.to_numeric(achats['Exchange rate'], errors='coerce')
    achats['Time'] = pd.to_datetime(achats['Time'])
    achats['date'] = achats['Time'].dt.normalize()

    def get_taux(row):
        if row['Currency (Price / share)'] == 'USD' and row['Exchange rate'] == 1.0:
            date = row['date']
            if date in eur_usd_hist.index:
                return eur_usd_hist.loc[date]
            idx = eur_usd_hist.index.get_indexer([date], method='nearest')[0]
            return eur_usd_hist.iloc[idx]
        return row['Exchange rate']

    achats['exchange_rate_corrige'] = achats.apply(get_taux, axis=1)
    achats['montant_local'] = achats['No. of shares'] * achats['Price / share']
    achats['montant_eur'] = achats['montant_local'] / achats['exchange_rate_corrige']

    total_investi_local = achats.groupby('Ticker')['montant_local'].sum()
    total_investi_eur = achats.groupby('Ticker')['montant_eur'].sum()
    total_achete = achats.groupby('Ticker')['No. of shares'].sum()

    prix_revient = pd.DataFrame({
        'prix_revient_local': total_investi_local / total_achete,
        'prix_revient_eur': total_investi_eur / total_achete
    }).reset_index()
    prix_revient.columns = ['Ticker', 'prix_revient_local', 'prix_revient_eur']

    # Correction splits
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
        prix_revient.loc[mask, 'prix_revient_local'] /= row['ratio']
        prix_revient.loc[mask, 'prix_revient_eur'] /= row['ratio']

    return prix_revient

# --- COURS EN TEMPS REEL ---
@st.cache_data(ttl=3600)
def get_cours(tickers):
    cours = []
    for ticker in tickers:
        try:
            prix = yf.Ticker(ticker).history(period="1d")['Close'].iloc[-1]
            cours.append(float(prix))
        except:
            cours.append(None)
    return cours

# --- CALCUL BILAN ---
positions = calc_positions(df_transactions)
prix_revient = calc_prix_revient(df_transactions, eur_usd_hist)

bilan = positions[['quantite_actuelle']].copy().reset_index()
bilan = bilan.merge(prix_revient, on='Ticker', how='left')
bilan = bilan.merge(df_ptf[['ticker', 'devise']].rename(columns={'ticker': 'Ticker'}), on='Ticker', how='left')
bilan['prix_actuel'] = get_cours(bilan['Ticker'].tolist())
bilan['prix_actuel'] = pd.to_numeric(bilan['prix_actuel'], errors='coerce')

# Vision locale
bilan['valeur_investie_local'] = bilan['prix_revient_local'] * bilan['quantite_actuelle']
bilan['valeur_actuelle_local'] = bilan['prix_actuel'] * bilan['quantite_actuelle']
bilan['gain_local'] = bilan['valeur_actuelle_local'] - bilan['valeur_investie_local']
bilan['rendement_local'] = (bilan['gain_local'] / bilan['valeur_investie_local']) * 100

# Vision EUR
bilan['prix_actuel_eur'] = bilan.apply(
    lambda r: r['prix_actuel'] / eur_usd if r['devise'] == 'USD' else r['prix_actuel'], axis=1
)
bilan['valeur_investie_eur'] = bilan['prix_revient_eur'] * bilan['quantite_actuelle']
bilan['valeur_actuelle_eur'] = bilan['prix_actuel_eur'] * bilan['quantite_actuelle']
bilan['gain_eur'] = bilan['valeur_actuelle_eur'] - bilan['valeur_investie_eur']
bilan['rendement_eur'] = (bilan['gain_eur'] / bilan['valeur_investie_eur']) * 100

bilan_clean = bilan.dropna(subset=['prix_actuel']).copy()

# --- COLONNES SELON DEVISE ---
if devise_affichage == "EUR":
    col_gain = 'gain_eur'
    col_rendement = 'rendement_eur'
    col_valeur = 'valeur_actuelle_eur'
    col_investie = 'valeur_investie_eur'
    col_prix_actuel = 'prix_actuel_eur'
    col_prix_revient = 'prix_revient_eur'
    symbole = "€"
else:
    col_gain = 'gain_local'
    col_rendement = 'rendement_local'
    col_valeur = 'valeur_actuelle_local'
    col_investie = 'valeur_investie_local'
    col_prix_actuel = 'prix_actuel'
    col_prix_revient = 'prix_revient_local'
    symbole = "$"

# --- TOTAUX ---
gain_total = bilan_clean[col_gain].sum()
valeur_investie_totale = bilan_clean[col_investie].sum()
valeur_actuelle_totale = bilan_clean[col_valeur].sum()
rendement_global = (gain_total / valeur_investie_totale) * 100

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

# --- METRICS ---
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Valeur totale", f"{symbole} {valeur_actuelle_totale:,.0f}")
col2.metric("Montant investi", f"{symbole} {valeur_investie_totale:,.0f}")
col3.metric("Plus-values latentes", f"{symbole} {gain_total:,.0f}")
col4.metric("Rendement global", f"{rendement_global:.1f} %")
col5.metric("Revenu net", f"€ {revenu_net:.0f}")

st.divider()

# --- GRAPHIQUES ---
col_a, col_b = st.columns(2)

with col_a:
    fig1 = px.pie(bilan_clean, values=col_valeur, names='Ticker',
                  title=f'Répartition du portefeuille ({devise_affichage})')
    st.plotly_chart(fig1, use_container_width=True)

with col_b:
    fig2 = px.bar(bilan_clean.sort_values(col_rendement, ascending=False),
                  x='Ticker', y=col_rendement,
                  title=f'Rendement par position (%, {devise_affichage})',
                  color=col_rendement,
                  color_continuous_scale=['red', 'lightgrey', 'green'],
                  color_continuous_midpoint=0)
    st.plotly_chart(fig2, use_container_width=True)

# --- TABLEAU ---
st.subheader(f"Détail des positions ({devise_affichage})")
display = bilan_clean[['Ticker', 'quantite_actuelle', col_prix_revient,
                        col_prix_actuel, col_gain, col_rendement]].copy()
display.columns = ['Ticker', 'Quantité', 'Prix achat', 'Prix actuel', f'Gain ({symbole})', 'Rendement %']
display = display.sort_values(f'Gain ({symbole})', ascending=False)
st.dataframe(display.style.format({
    'Quantité': '{:.2f}',
    'Prix achat': '{:.2f}',
    'Prix actuel': '{:.2f}',
    f'Gain ({symbole})': '{:+.2f}',
    'Rendement %': '{:+.1f}%'
}), use_container_width=True)

st.divider()

# --- BILAN REVENUS ---
st.subheader("Bilan revenus & frais (€)")
col_x, col_y = st.columns(2)
with col_x:
    st.metric("Dividendes bruts", f"€ {total_dividendes:.2f}")
    st.metric("Intérêts sur cash", f"€ {total_interets:.2f}")
    st.metric("Revenu net", f"€ {revenu_net:.2f}")
with col_y:
    st.metric("Retenue à la source", f"-€ {total_retenue:.2f}")
    st.metric("TTF", f"-€ {total_ttf:.2f}")
    st.metric("Frais de change", f"€ {total_frais_change:.2f}")

import streamlit as st
import pandas as pd
import yfinance as yf
import glob
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(page_title="Mon Portefeuille", layout="wide")
st.title("📈 Mon Portefeuille")

# --- CHARGEMENT DONNEES ---
@st.cache_data(ttl=3600)
def load_all():
    # Transactions
    fichiers = sorted(glob.glob("transactions_*.csv"))
    df = pd.concat([pd.read_csv(f) for f in fichiers], ignore_index=True)
    df = df.sort_values('Time').reset_index(drop=True)

    # Portefeuille
    df_ptf = pd.read_csv("portefeuille.csv")

    # Taux EUR/USD actuel
    eur_usd = yf.Ticker("EURUSD=X").history(period="1d")['Close'].iloc[-1]

    # Historique EUR/USD
    eur_usd_hist = yf.download("EURUSD=X", start="2023-07-01",
                                end=datetime.today().strftime('%Y-%m-%d'))['Close'].squeeze()
    eur_usd_hist.index = pd.to_datetime(eur_usd_hist.index).tz_localize(None)

    return df, df_ptf, eur_usd, eur_usd_hist

with st.spinner("Chargement des données..."):
    df_transactions, df_ptf, eur_usd, eur_usd_hist = load_all()

st.caption(f"Taux EUR/USD actuel : {eur_usd:.4f} — {len(df_transactions)} transactions chargées")

# --- CALCUL POSITIONS ---
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
def calc_prix_revient(df, eur_usd_hist):
    achats = df[df['Action'].isin(['Market buy', 'Limit buy'])].copy()
    achats['No. of shares'] = pd.to_numeric(achats['No. of shares'], errors='coerce')
    achats['Price / share'] = pd.to_numeric(achats['Price / share'], errors='coerce')
    achats['Exchange rate'] = pd.to_numeric(achats['Exchange rate'], errors='coerce')
    achats['Time'] = pd.to_datetime(achats['Time'])
    achats['date'] = achats['Time'].dt.normalize()

    def get_taux(row):
        if row['Currency (Price / share)'] == 'USD' and row['Exchange rate'] == 1.0:
            date = row['date']
            if date in eur_usd_hist.index:
                return eur_usd_hist.loc[date]
            idx = eur_usd_hist.index.get_indexer([date], method='nearest')[0]
            return eur_usd_hist.iloc[idx]
        return row['Exchange rate']

    achats['exchange_rate_corrige'] = achats.apply(get_taux, axis=1)
    achats['montant_local'] = achats['No. of shares'] * achats['Price / share']
    achats['montant_eur'] = achats['montant_local'] / achats['exchange_rate_corrige']

    total_investi_local = achats.groupby('Ticker')['montant_local'].sum()
    total_investi_eur = achats.groupby('Ticker')['montant_eur'].sum()
    total_achete = achats.groupby('Ticker')['No. of shares'].sum()

    prix_revient = pd.DataFrame({
        'prix_revient_local': total_investi_local / total_achete,
        'prix_revient_eur': total_investi_eur / total_achete
    }).reset_index()
    prix_revient.columns = ['Ticker', 'prix_revient_local', 'prix_revient_eur']

    # Correction splits
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
        prix_revient.loc[mask, 'prix_revient_local'] /= row['ratio']
        prix_revient.loc[mask, 'prix_revient_eur'] /= row['ratio']

    return prix_revient

# --- COURS EN TEMPS REEL ---
@st.cache_data(ttl=3600)
def get_cours(tickers):
    cours = []
    for ticker in tickers:
        try:
            prix = yf.Ticker(ticker).history(period="1d")['Close'].iloc[-1]
            cours.append(float(prix))
        except:
            cours.append(None)
    return cours

# --- CALCUL BILAN ---
positions = calc_positions(df_transactions)
prix_revient = calc_prix_revient(df_transactions, eur_usd_hist)

bilan = positions[['quantite_actuelle']].copy().reset_index()
bilan = bilan.merge(prix_revient, on='Ticker', how='left')
bilan = bilan.merge(df_ptf[['ticker', 'devise']].rename(columns={'ticker': 'Ticker'}), on='Ticker', how='left')
bilan['prix_actuel'] = get_cours(bilan['Ticker'].tolist())
bilan['prix_actuel'] = pd.to_numeric(bilan['prix_actuel'], errors='coerce')

# Vision locale
bilan['valeur_investie_local'] = bilan['prix_revient_local'] * bilan['quantite_actuelle']
bilan['valeur_actuelle_local'] = bilan['prix_actuel'] * bilan['quantite_actuelle']
bilan['gain_local'] = bilan['valeur_actuelle_local'] - bilan['valeur_investie_local']
bilan['rendement_local'] = (bilan['gain_local'] / bilan['valeur_investie_local']) * 100

# Vision EUR
bilan['prix_actuel_eur'] = bilan.apply(
    lambda r: r['prix_actuel'] / eur_usd if r['devise'] == 'USD' else r['prix_actuel'], axis=1
)
bilan['valeur_investie_eur'] = bilan['prix_revient_eur'] * bilan['quantite_actuelle']
bilan['valeur_actuelle_eur'] = bilan['prix_actuel_eur'] * bilan['quantite_actuelle']
bilan['gain_eur'] = bilan['valeur_actuelle_eur'] - bilan['valeur_investie_eur']
bilan['rendement_eur'] = (bilan['gain_eur'] / bilan['valeur_investie_eur']) * 100

bilan_clean = bilan.dropna(subset=['prix_actuel']).copy()

# --- COLONNES SELON DEVISE ---
if devise_affichage == "EUR":
    col_gain = 'gain_eur'
    col_rendement = 'rendement_eur'
    col_valeur = 'valeur_actuelle_eur'
    col_investie = 'valeur_investie_eur'
    col_prix_actuel = 'prix_actuel_eur'
    col_prix_revient = 'prix_revient_eur'
    symbole = "€"
else:
    col_gain = 'gain_local'
    col_rendement = 'rendement_local'
    col_valeur = 'valeur_actuelle_local'
    col_investie = 'valeur_investie_local'
    col_prix_actuel = 'prix_actuel'
    col_prix_revient = 'prix_revient_local'
    symbole = "$"

# --- TOTAUX ---
gain_total = bilan_clean[col_gain].sum()
valeur_investie_totale = bilan_clean[col_investie].sum()
valeur_actuelle_totale = bilan_clean[col_valeur].sum()
rendement_global = (gain_total / valeur_investie_totale) * 100

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

# --- METRICS ---
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Valeur totale", f"{symbole} {valeur_actuelle_totale:,.0f}")
col2.metric("Montant investi", f"{symbole} {valeur_investie_totale:,.0f}")
col3.metric("Plus-values latentes", f"{symbole} {gain_total:,.0f}")
col4.metric("Rendement global", f"{rendement_global:.1f} %")
col5.metric("Revenu net", f"€ {revenu_net:.0f}")

st.divider()

# --- GRAPHIQUES ---
col_a, col_b = st.columns(2)

with col_a:
    fig1 = px.pie(bilan_clean, values=col_valeur, names='Ticker',
                  title=f'Répartition du portefeuille ({devise_affichage})')
    st.plotly_chart(fig1, use_container_width=True)

with col_b:
    fig2 = px.bar(bilan_clean.sort_values(col_rendement, ascending=False),
                  x='Ticker', y=col_rendement,
                  title=f'Rendement par position (%, {devise_affichage})',
                  color=col_rendement,
                  color_continuous_scale=['red', 'lightgrey', 'green'],
                  color_continuous_midpoint=0)
    st.plotly_chart(fig2, use_container_width=True)

# --- TABLEAU ---
st.subheader(f"Détail des positions ({devise_affichage})")
display = bilan_clean[['Ticker', 'quantite_actuelle', col_prix_revient,
                        col_prix_actuel, col_gain, col_rendement]].copy()
display.columns = ['Ticker', 'Quantité', 'Prix achat', 'Prix actuel', f'Gain ({symbole})', 'Rendement %']
display = display.sort_values(f'Gain ({symbole})', ascending=False)
st.dataframe(display.style.format({
    'Quantité': '{:.2f}',
    'Prix achat': '{:.2f}',
    'Prix actuel': '{:.2f}',
    f'Gain ({symbole})': '{:+.2f}',
    'Rendement %': '{:+.1f}%'
}), use_container_width=True)

st.divider()

# --- BILAN REVENUS ---
st.subheader("Bilan revenus & frais (€)")
col_x, col_y = st.columns(2)
with col_x:
    st.metric("Dividendes bruts", f"€ {total_dividendes:.2f}")
    st.metric("Intérêts sur cash", f"€ {total_interets:.2f}")
    st.metric("Revenu net", f"€ {revenu_net:.2f}")
with col_y:
    st.metric("Retenue à la source", f"-€ {total_retenue:.2f}")
    st.metric("TTF", f"-€ {total_ttf:.2f}")
    st.metric("Frais de change", f"€ {total_frais_change:.2f}")

# --- IMPACT CHANGE ---
if devise_affichage == "EUR":
    st.divider()
    st.subheader("Impact du change sur le portefeuille")

    usd_positions = bilan_clean[bilan_clean['devise'] == 'USD'].copy()
    eur_positions = bilan_clean[bilan_clean['devise'] == 'EUR'].copy()

    valeur_usd = usd_positions['valeur_actuelle_eur'].sum()
    valeur_eur = eur_positions['valeur_actuelle_eur'].sum()
    valeur_totale = valeur_usd + valeur_eur

    gain_usd_local = usd_positions['gain_local'].sum()
    gain_usd_eur = usd_positions['gain_eur'].sum()
    impact_change = gain_usd_eur - (gain_usd_local / eur_usd)

    rendement_usd_local = (gain_usd_local / usd_positions['valeur_investie_local'].sum()) * 100
    rendement_usd_eur = (gain_usd_eur / usd_positions['valeur_investie_eur'].sum()) * 100

    col1, col2, col3 = st.columns(3)
    col1.metric(
        "Exposition USD",
        f"{valeur_usd / valeur_totale * 100:.1f}%",
        f"€ {valeur_usd:,.0f}"
    )
    col2.metric(
        "Rendement USD brut vs EUR réel",
        f"{rendement_usd_local:.1f}% → {rendement_usd_eur:.1f}%",
        f"{rendement_usd_eur - rendement_usd_local:.1f}% change"
    )
    col3.metric(
        "Perte de change latente",
        f"€ {impact_change:,.0f}",
        f"{impact_change / valeur_usd * 100:.1f}% de tes positions USD"
    )
