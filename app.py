import streamlit as st
import pandas as pd
import yfinance as yf
import glob
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(page_title="CTO Juju", layout="wide")
st.title("📈 CTO Juju")

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

@st.cache_data(ttl=86400)
def get_noms(tickers):
    noms = {}
    for ticker in tickers:
        try:
            info = yf.Ticker(ticker).info
            noms[ticker] = info.get('longName', ticker)
        except:
            noms[ticker] = ticker
    return noms

noms = get_noms(bilan_clean['Ticker'].tolist())
bilan_clean['Nom'] = bilan_clean['Ticker'].map(noms)

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
    fig1 = px.pie(
        bilan_clean,
        values=col_valeur,
        names='Ticker',
        title=f'Répartition du portefeuille ({devise_affichage})',
        hole=0.45,
        color_discrete_sequence=px.colors.qualitative.Set3
    )
    fig1.update_traces(
        textposition='outside',
        textinfo='label+percent',
        textfont_size=12,
        pull=[0.03] * len(bilan_clean)
    )
    fig1.update_layout(
        showlegend=False,
        margin=dict(t=60, b=60, l=60, r=60)
    )
    st.plotly_chart(fig1, use_container_width=True)
    
with col_b:
    tab1, tab2 = st.tabs(["Rendement %", "Gain volume"])
    
    with tab1:
        fig2 = px.bar(
            bilan_clean.sort_values(col_rendement, ascending=False),
            x='Ticker', y=col_rendement,
            color=col_rendement,
            color_continuous_scale=['red', 'lightgrey', 'green'],
            color_continuous_midpoint=0,
            text=col_rendement
        )
        fig2.update_traces(
            texttemplate='%{text:.1f}%',
            textposition='outside'
        )
        fig2.update_layout(
            title=f'Rendement par position (%, {devise_affichage})',
            xaxis_title='',
            yaxis_title='',
            coloraxis_showscale=False,
            margin=dict(t=60, b=20)
        )
        st.plotly_chart(fig2, use_container_width=True)
    
    with tab2:
        fig2b = px.bar(
            bilan_clean.sort_values(col_gain, ascending=False),
            x='Ticker', y=col_gain,
            color=col_gain,
            color_continuous_scale=['red', 'lightgrey', 'green'],
            color_continuous_midpoint=0,
            text=col_gain
        )
        fig2b.update_traces(
            texttemplate='%{text:+,.0f}',
            textposition='outside'
        )
        fig2b.update_layout(
            title=f'Gain par position ({symbole}, {devise_affichage})',
            xaxis_title='',
            yaxis_title='',
            coloraxis_showscale=False,
            margin=dict(t=60, b=20)
        )
        st.plotly_chart(fig2b, use_container_width=True)
        
# --- TABLEAU ---
st.subheader(f"Détail des positions ({devise_affichage})")
display = bilan_clean[['Ticker', 'Nom', 'quantite_actuelle', col_prix_revient,
                        col_prix_actuel, col_gain, col_rendement]].copy()

display['Valeur investie'] = display['quantite_actuelle'] * display[col_prix_revient]
display['Valeur actuelle'] = display['quantite_actuelle'] * display[col_prix_actuel]

display = display[['Ticker', 'Nom', 'quantite_actuelle', col_prix_revient, 'Valeur investie',
                    col_prix_actuel, 'Valeur actuelle', col_gain, col_rendement]]

display.columns = ['Ticker', 'Société', 'Quantité', 'Prix achat', f'Investi ({symbole})',
                   'Prix actuel', f'Valeur ({symbole})', f'Gain ({symbole})', 'Rendement %']
display = display.sort_values(f'Gain ({symbole})', ascending=False)

# Ligne total
total_row = pd.DataFrame([{
    'Ticker': 'TOTAL',
    'Société': '',
    'Quantité': '',
    'Prix achat': '',
    f'Investi ({symbole})': display[f'Investi ({symbole})'].sum(),
    'Prix actuel': '',
    f'Valeur ({symbole})': display[f'Valeur ({symbole})'].sum(),
    f'Gain ({symbole})': display[f'Gain ({symbole})'].sum(),
    'Rendement %': '',
}])

display = pd.concat([display, total_row], ignore_index=True)

st.dataframe(display.style.format({
    'Quantité': lambda x: f'{x:.1f}' if isinstance(x, float) else x,
    'Prix achat': lambda x: f'{x:.1f}' if isinstance(x, float) else x,
    f'Investi ({symbole})': lambda x: f'{x:.1f}' if isinstance(x, float) else x,
    'Prix actuel': lambda x: f'{x:.1f}' if isinstance(x, float) else x,
    f'Valeur ({symbole})': lambda x: f'{x:.1f}' if isinstance(x, float) else x,
    f'Gain ({symbole})': lambda x: f'{x:+.1f}' if isinstance(x, float) else x,
    'Rendement %': lambda x: f'{x:+.1f}%' if isinstance(x, float) else x,
}), use_container_width=True)

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

# --- PLUS-VALUES RÉALISÉES ---
st.divider()
st.subheader("Plus-values réalisées")

splits_manuels = {
    'CMG': {'date': pd.Timestamp('2024-06-27'), 'ratio': 50}
}

def calc_pv_realisees(df, eur_usd):
    achats_all = df[df['Action'].isin(['Market buy', 'Limit buy'])].copy()
    ventes_all = df[df['Action'].isin(['Market sell', 'Limit sell'])].copy()

    for d in [achats_all, ventes_all]:
        d['No. of shares'] = pd.to_numeric(d['No. of shares'], errors='coerce')
        d['Price / share'] = pd.to_numeric(d['Price / share'], errors='coerce')
        d['Exchange rate'] = pd.to_numeric(d['Exchange rate'], errors='coerce')
        d['Time'] = pd.to_datetime(d['Time'])

    pv_realisees = []

    for ticker in ventes_all['Ticker'].unique():
        achats_ticker = achats_all[achats_all['Ticker'] == ticker].sort_values('Time').copy()
        ventes_ticker = ventes_all[ventes_all['Ticker'] == ticker].sort_values('Time')

        if ticker in splits_manuels:
            split = splits_manuels[ticker]
            mask_pre = achats_ticker['Time'] < split['date']
            achats_ticker.loc[mask_pre, 'No. of shares'] *= split['ratio']
            achats_ticker.loc[mask_pre, 'Price / share'] /= split['ratio']

        total_investi = (achats_ticker['No. of shares'] * achats_ticker['Price / share']).sum()
        total_achete = achats_ticker['No. of shares'].sum()

        if total_achete == 0:
            continue

        prix_revient_moyen = total_investi / total_achete

        for _, vente in ventes_ticker.iterrows():
            prix_vente = vente['Price / share']
            quantite = vente['No. of shares']

            if ticker in splits_manuels and vente['Time'] < splits_manuels[ticker]['date']:
                prix_vente /= splits_manuels[ticker]['ratio']
                quantite *= splits_manuels[ticker]['ratio']

            gain_local = (prix_vente - prix_revient_moyen) * quantite
            taux = vente['Exchange rate'] if vente['Exchange rate'] != 1.0 else eur_usd
            gain_eur = gain_local / taux

            pv_realisees.append({
                'Ticker': ticker,
                'Date': vente['Time'].strftime('%Y-%m-%d'),
                'Prix vente': round(prix_vente, 2),
                'Prix revient': round(prix_revient_moyen, 2),
                'Gain local': round(gain_local, 2),
                'Gain (€)': round(gain_eur, 2)
            })

    return pd.DataFrame(pv_realisees)

df_pv = calc_pv_realisees(df_transactions, eur_usd)

# Regrouper par ticker
df_pv_grouped = df_pv.groupby('Ticker').agg(
    Nb_ventes=('Gain (€)', 'count'),
    Gain_local=('Gain local', 'sum'),
    Gain_eur=('Gain (€)', 'sum')
).reset_index()

# Ajouter les noms
df_pv_grouped['Société'] = df_pv_grouped['Ticker'].map(noms)
df_pv_grouped = df_pv_grouped[['Ticker', 'Société', 'Nb_ventes', 'Gain_local', 'Gain_eur']]
df_pv_grouped.columns = ['Ticker', 'Société', 'Nb ventes', 'Gain local', 'Gain (€)']
df_pv_grouped = df_pv_grouped.sort_values('Gain (€)', ascending=False)

# Ligne total
total_row = pd.DataFrame([{
    'Ticker': 'TOTAL',
    'Société': '',
    'Nb ventes': df_pv_grouped['Nb ventes'].sum(),
    'Gain local': df_pv_grouped['Gain local'].sum(),
    'Gain (€)': df_pv_grouped['Gain (€)'].sum()
}])
df_pv_grouped = pd.concat([df_pv_grouped, total_row], ignore_index=True)

total_pv = df_pv['Gain (€)'].sum()
col1, col2 = st.columns(2)
col1.metric("Total plus-values réalisées", f"€ {total_pv:,.0f}")
col2.metric("Nombre de positions vendues", len(df_pv_grouped) - 1)

st.dataframe(df_pv_grouped.style.format({
    'Gain local': '{:+,.1f}',
    'Gain (€)': '{:+,.1f}'
}), use_container_width=True)

# --- IMPACT CHANGE ---
if devise_affichage == "EUR":
    st.divider()
    st.subheader("Impact du change sur le portefeuille")

    usd_positions = bilan_clean[bilan_clean['devise'] == 'USD'].copy()

    valeur_usd = usd_positions['valeur_actuelle_eur'].sum()
    valeur_totale = bilan_clean['valeur_actuelle_eur'].sum()

    gain_usd_local = usd_positions['gain_local'].sum()
    gain_usd_eur = usd_positions['gain_eur'].sum()
    impact_change = gain_usd_eur - (gain_usd_local / eur_usd)

    col1, col2 = st.columns(2)
    col1.metric(
        "Exposition USD",
        f"{valeur_usd / valeur_totale * 100:.1f}%",
        f"€ {valeur_usd:,.0f}"
    )
    col2.metric(
        "Perte de change latente",
        f"€ {impact_change:,.0f}",
        f"{impact_change / valeur_usd * 100:.1f}% de tes positions USD"
    )

# --- PERFORMANCE VS S&P 500 ---
st.divider()
st.subheader("Performance vs S&P 500")

@st.cache_data(ttl=3600)
def get_sp500_perf(date_debut):
    sp500 = yf.download("^GSPC", start=date_debut,
                         end=datetime.today().strftime('%Y-%m-%d'))['Close'].squeeze()
    return (sp500.iloc[-1] / sp500.iloc[0] - 1) * 100

sp500_perf = get_sp500_perf("2023-07-31")

col1, col2, col3 = st.columns(3)
col1.metric(
    "Ton rendement global",
    f"{rendement_global:.1f}%",
)
col2.metric(
    "S&P 500 depuis juil. 2023",
    f"{sp500_perf:.1f}%",
)
col3.metric(
    "Écart",
    f"{rendement_global - sp500_perf:.1f}%",
    delta_color="normal"
)

st.caption("Note : comparaison indicative. Le S&P 500 est mesuré depuis ton premier achat, sans tenir compte de tes apports progressifs.")
