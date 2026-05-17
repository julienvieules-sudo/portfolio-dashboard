import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

st.set_page_config(page_title="Bilan Patrimonial", layout="wide")
st.title("📊 Bilan Patrimonial")

# --- TAUX EUR/USD ---
@st.cache_data(ttl=3600)
def get_eur_usd():
    return yf.Ticker("EURUSD=X").history(period="1d")['Close'].iloc[-1]

eur_usd = get_eur_usd()

# --- ACTIFS DYNAMIQUES ---
@st.cache_data(ttl=3600)
def get_valeur_cto(eur_usd):
    df_ptf = pd.read_csv("portefeuille.csv")
    total = 0
    for _, row in df_ptf.iterrows():
        try:
            prix = yf.Ticker(row['ticker']).history(period="1d")['Close'].iloc[-1]
            if row['devise'] == 'USD':
                total += (prix * row['quantite']) / eur_usd
            else:
                total += prix * row['quantite']
        except:
            pass
    return total

@st.cache_data(ttl=3600)
def get_valeur_pea():
    positions = [
        ('PE500.PA', 81.0),
        ('PCEU.PA', 17.0),
        ('PANX.PA', 133.0),
    ]
    total = 0
    for ticker, quantite in positions:
        try:
            prix = yf.Ticker(ticker).history(period="1d")['Close'].iloc[-1]
            total += prix * quantite
        except:
            pass
    return total

@st.cache_data(ttl=300)
def get_valeur_crypto(eur_usd):
    positions = [
        ('BTC-USD', 0.04391),
        ('ETH-USD', 1.0306),
        ('SOL-USD', 3.48),
        ('BNB-USD', 6.6556),
    ]
    total = 0
    for ticker, quantite in positions:
        try:
            prix = yf.Ticker(ticker).history(period="1d")['Close'].iloc[-1]
            total += (prix * quantite) / eur_usd
        except:
            pass
    return total

# --- CREDIT CONSO ---
def calc_crd_conso():
    capital_initial = 20000.0
    taux_mensuel = 2.20 / 100 / 12
    mensualite = 435.0
    date_debut = date(2024, 12, 1)
    aujourd_hui = date.today()
    
    nb_mois = (aujourd_hui.year - date_debut.year) * 12 + (aujourd_hui.month - date_debut.month)
    
    crd = capital_initial
    for _ in range(nb_mois):
        interet = crd * taux_mensuel
        amortissement = mensualite - interet
        crd -= amortissement
    
    return max(0, crd)

# --- TERRAIN ---
terrain_prix_total = 30000
terrain_paye_total = 3591
terrain_ma_part = terrain_paye_total / 2
crd_terrain_ma_part = 25725 / 2

# --- AMORTISSEMENT TERRAIN ---
tableau_terrain = []
date_ref = date(2025, 12, 1)
cumul = 977.0
crd_t = 29023.0

mensualites = [(date(2026, 1, 1), date(2029, 4, 1), 132),
               (date(2029, 5, 1), date(2032, 8, 1), 220),
               (date(2032, 9, 1), date(2035, 12, 1), 308)]

def get_mensualite_terrain(d):
    for debut, fin, m in mensualites:
        if debut <= d <= fin:
            return m
    return 0

# --- CHARGEMENT ---
with st.spinner("Chargement..."):
    valeur_cto = get_valeur_cto(eur_usd)
    valeur_pea = get_valeur_pea()
    valeur_crypto = get_valeur_crypto(eur_usd)

crd_conso = calc_crd_conso()

# --- CASH MANUEL ---
st.subheader("💰 Cash disponible")
cash = st.number_input(
    "Cash disponible (€)",
    min_value=0,
    max_value=500000,
    value=5000,
    step=500,
    help="Incluez le cash sur vos comptes bancaires"
)

st.divider()

# --- CALCULS ---
pee = 29582
percol = 5782

actifs_financiers = valeur_cto + valeur_pea + valeur_crypto + pee + percol + cash
actifs_reels = terrain_ma_part
actifs_total = actifs_financiers + actifs_reels

passifs_total = crd_conso + crd_terrain_ma_part
patrimoine_net = actifs_total - passifs_total

# --- VUE GLOBALE ---
st.subheader("Vue d'ensemble")

col1, col2, col3 = st.columns(3)
col1.metric("Actifs totaux", f"€ {actifs_total:,.0f}")
col2.metric("Passifs totaux", f"€ {passifs_total:,.0f}")
col3.metric("Patrimoine net", f"€ {patrimoine_net:,.0f}")

st.divider()

# --- DETAIL ACTIFS ---
st.subheader("Actifs")

col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("**Financiers**")
    st.metric("CTO", f"€ {valeur_cto:,.0f}")
    st.metric("PEA", f"€ {valeur_pea:,.0f}")
    st.metric("Crypto", f"€ {valeur_crypto:,.0f}")
    st.metric("PEE", f"€ {pee:,.0f}", "En cours de remboursement")
    st.metric("PERCOL", f"€ {percol:,.0f}", "Bloqué retraite")
    st.metric("Cash", f"€ {cash:,.0f}")

with col2:
    st.markdown("**Immobilier**")
    pct_paye = (terrain_paye_total / terrain_prix_total) * 100
    st.metric("Terrain Yucatán (ta part)", f"€ {terrain_ma_part:,.0f}")
    st.progress(int(pct_paye), text=f"Payé : {terrain_paye_total:,.0f}€ / {terrain_prix_total:,.0f}€ ({pct_paye:.0f}%)")

with col3:
    st.markdown("**Répartition actifs**")
    data_actifs = pd.DataFrame([
        {'Catégorie': 'CTO', 'Valeur': valeur_cto},
        {'Catégorie': 'PEA', 'Valeur': valeur_pea},
        {'Catégorie': 'Crypto', 'Valeur': valeur_crypto},
        {'Catégorie': 'PEE', 'Valeur': pee},
        {'Catégorie': 'PERCOL', 'Valeur': percol},
        {'Catégorie': 'Cash', 'Valeur': cash},
        {'Catégorie': 'Terrain', 'Valeur': terrain_ma_part},
    ])
    fig_actifs = px.pie(
        data_actifs,
        values='Valeur',
        names='Catégorie',
        hole=0.45,
        color_discrete_sequence=px.colors.qualitative.Set2
    )
    fig_actifs.update_traces(textposition='outside', textinfo='label+percent')
    fig_actifs.update_layout(showlegend=False, margin=dict(t=20, b=20, l=20, r=20))
    st.plotly_chart(fig_actifs, use_container_width=True)

st.divider()

# --- DETAIL PASSIFS ---
st.subheader("Passifs")

col1, col2 = st.columns(2)

with col1:
    st.markdown("**Crédit conso**")
    st.metric("CRD", f"€ {crd_conso:,.0f}")
    st.metric("Mensualité", "435 €")
    
    # Barre de progression crédit conso
    capital_initial_conso = 20000 # approximatif
    pct_rembourse_conso = (1 - crd_conso / capital_initial_conso) * 100
    st.progress(int(min(100, pct_rembourse_conso)), 
                text=f"Remboursé : {capital_initial_conso - crd_conso:,.0f}€ / {capital_initial_conso:,.0f}€ ({pct_rembourse_conso:.0f}%)")

with col2:
    st.markdown("**Terrain Yucatán (ta part)**")
    st.metric("CRD", f"€ {crd_terrain_ma_part:,.0f}")
    
    pct_rembourse_terrain = (terrain_ma_part / (terrain_prix_total / 2)) * 100
    st.progress(int(pct_rembourse_terrain),
                text=f"Payé : {terrain_ma_part:,.0f}€ / {terrain_prix_total/2:,.0f}€ ({pct_rembourse_terrain:.0f}%)")

st.divider()

# --- EVOLUTION PATRIMOINE PROJETEE ---
st.subheader("Projection du patrimoine net")
st.caption("Basé sur les remboursements prévus — actifs financiers supposés constants")

dates_proj = []
patrimoine_proj = []

crd_conso_proj = crd_conso
crd_terrain_proj = crd_terrain_ma_part
today = date.today()

for i in range(120):  # 10 ans
    d = today + relativedelta(months=i)
    
    # Remboursement conso
    interet_conso = crd_conso_proj * (2.20 / 100 / 12)
    crd_conso_proj = max(0, crd_conso_proj - (435 - interet_conso))
    
    # Remboursement terrain
    mensualite_t = get_mensualite_terrain(d) / 2
    crd_terrain_proj = max(0, crd_terrain_proj - mensualite_t)
    
    passifs_proj = crd_conso_proj + crd_terrain_proj
    patrimoine_proj.append(actifs_total - passifs_proj)
    dates_proj.append(d)

df_proj = pd.DataFrame({'Date': dates_proj, 'Patrimoine net': patrimoine_proj})

fig_proj = px.line(
    df_proj,
    x='Date',
    y='Patrimoine net',
    title='Projection du patrimoine net sur 10 ans (actifs constants)',
    labels={'Patrimoine net': '€', 'Date': ''}
)
fig_proj.update_layout(hovermode='x unified', margin=dict(t=60, b=20))
st.plotly_chart(fig_proj, use_container_width=True)
