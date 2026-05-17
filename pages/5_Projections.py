import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date
from dateutil.relativedelta import relativedelta

st.set_page_config(page_title="Projections", layout="wide")
st.title("🔭 Projections patrimoniales")

# --- POINT DE DEPART ---
st.subheader("Point de départ")
col1, col2, col3 = st.columns(3)
with col1:
    patrimoine_actuel = st.number_input(
        "Patrimoine financier actuel (€)",
        min_value=0, max_value=1000000,
        value=94000, step=1000
    )
with col2:
    dette_actuelle = st.number_input(
        "Dettes actuelles (€)",
        min_value=0, max_value=500000,
        value=26000, step=500
    )
with col3:
    st.metric("Patrimoine net actuel", f"€ {patrimoine_actuel - dette_actuelle:,.0f}")

st.divider()

# --- PARAMETRES ---
st.subheader("Paramètres")

col1, col2 = st.columns(2)
with col1:
    rendement_central = st.slider("Rendement annuel central (%)", 0.0, 15.0, 5.0, 0.5)
    apport_mensuel = st.slider("Apport mensuel (€)", 0, 5000, 800, 100)
    pee_annuel = st.slider("Déblocage PEE annuel (€)", 0, 20000, 10000, 500)
    horizon = st.slider("Horizon (années)", 1, 25, 10, 1)

with col2:
    st.markdown("**Crédit conso actuel**")
    crd_conso_actuel = st.number_input("CRD actuel (€)", 0, 100000, 13115, 100)
    mensualite_conso_actuel = st.number_input("Mensualité actuelle (€)", 0, 2000, 435, 10)

st.divider()

# --- CREDITS CONSO FUTURS ---
st.subheader("Crédits conso futurs")

credits_futurs = []
for i in range(1, 4):
    with st.expander(f"Crédit conso {i}"):
        actif = st.toggle(f"Simuler ce crédit", key=f"toggle_{i}", value=False)
        if actif:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                annee = st.number_input(f"Année de souscription", 2025, 2045, 2030, 1, key=f"annee_{i}")
                mois = st.number_input(f"Mois", 1, 12, 1, 1, key=f"mois_{i}")
            with col2:
                montant = st.number_input(f"Montant (€)", 0, 100000, 15000, 500, key=f"montant_{i}")
            with col3:
                mensualite = st.number_input(f"Mensualité (€)", 0, 2000, 300, 10, key=f"mens_{i}")
            with col4:
                taux = st.number_input(f"Taux (%)", 0.0, 15.0, 3.5, 0.1, key=f"taux_{i}")
            
            credits_futurs.append({
                'date': date(int(annee), int(mois), 1),
                'montant': montant,
                'mensualite': mensualite,
                'taux': taux / 100 / 12,
                'crd': 0.0,
                'actif': False
            })

st.divider()

# --- LOMBARD ---
st.subheader("Crédit Lombard")

with st.expander("Simuler un Lombard"):
    lombard_actif = st.toggle("Activer le Lombard", value=False)
    if lombard_actif:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            lombard_annee = st.number_input("Année de mise en place", 2025, 2040, 2026, 1)
            lombard_mois = st.number_input("Mois", 1, 12, 6, 1)
        with col2:
            lombard_ltv = st.slider("LTV (%)", 10, 60, 40, 5)
        with col3:
            lombard_taux = st.slider("Taux d'emprunt (%)", 1.0, 8.0, 3.5, 0.25)
        with col4:
            lombard_rendement = st.slider("Rendement du capital investi (%)", 0.0, 15.0, 6.0, 0.5)
        
        st.caption(f"Gain net estimé du levier : {lombard_rendement - lombard_taux:.1f}% par an sur le montant emprunté")

st.divider()

# --- SIMULATION ---
rendement_pessimiste = max(0, rendement_central - 2)
rendement_optimiste = rendement_central + 2

def mensualite_terrain(d):
    if date(2026, 1, 1) <= d < date(2029, 5, 1):
        return 66
    elif date(2029, 5, 1) <= d < date(2032, 9, 1):
        return 110
    elif date(2032, 9, 1) <= d <= date(2035, 12, 1):
        return 154
    return 0

def simuler(rendement_annuel, apport_mensuel, pee_annuel,
            crd_conso, mensualite_conso, horizon_mois,
            credits_futurs, lombard_actif=False,
            lombard_date=None, lombard_ltv=40,
            lombard_taux=3.5, lombard_rendement=6.0):

    taux_mensuel = (1 + rendement_annuel / 100) ** (1/12) - 1
    taux_conso = 2.20 / 100 / 12

    patrimoine = patrimoine_actuel
    crd = crd_conso
    crd_terrain = 12862.0
    lombard_crd = 0.0
    lombard_mis_en_place = False

    # Copie des crédits futurs pour ne pas modifier l'original
    credits = [dict(c) for c in credits_futurs]

    resultats = []
    today = date.today()

    for i in range(horizon_mois):
        d = today + relativedelta(months=i)

        # Rendement mensuel
        patrimoine *= (1 + taux_mensuel)

        # Apport mensuel
        patrimoine += apport_mensuel

        # PEE annuel en janvier
        if d.month == 1:
            patrimoine += pee_annuel

        # Remboursement crédit conso actuel
        if crd > 0:
            interet = crd * taux_conso
            amort = min(mensualite_conso - interet, crd)
            crd = max(0, crd - amort)

        # Crédits conso futurs
        for credit in credits:
            if d >= credit['date'] and not credit['actif']:
                credit['crd'] = credit['montant']
                credit['actif'] = True
                patrimoine += credit['montant']

            if credit['actif'] and credit['crd'] > 0:
                interet = credit['crd'] * credit['taux']
                amort = min(credit['mensualite'] - interet, credit['crd'])
                credit['crd'] = max(0, credit['crd'] - amort)

        # Lombard
        if lombard_actif and lombard_date and d >= lombard_date and not lombard_mis_en_place:
            lombard_montant = patrimoine * lombard_ltv / 100
            lombard_crd = lombard_montant
            patrimoine += lombard_montant
            lombard_mis_en_place = True

        # Rendement supplémentaire du Lombard
        if lombard_mis_en_place and lombard_crd > 0:
            gain_net_mensuel = lombard_crd * ((lombard_rendement - lombard_taux) / 100 / 12)
            patrimoine += gain_net_mensuel

        # Remboursement terrain
        crd_terrain = max(0, crd_terrain - mensualite_terrain(d))

        # Total dettes
        dettes = (crd + sum(c['crd'] for c in credits) +
                  crd_terrain + lombard_crd)

        resultats.append({
            'Date': d,
            'Patrimoine financier': patrimoine,
            'Dettes': dettes,
            'Patrimoine net': patrimoine - dettes
        })

    return pd.DataFrame(resultats)

horizon_mois = horizon * 12
lombard_date = date(int(lombard_annee), int(lombard_mois), 1) if lombard_actif else None

kwargs = dict(
    apport_mensuel=apport_mensuel,
    pee_annuel=pee_annuel,
    crd_conso=crd_conso_actuel,
    mensualite_conso=mensualite_conso_actuel,
    horizon_mois=horizon_mois,
    credits_futurs=credits_futurs,
    lombard_actif=lombard_actif,
    lombard_date=lombard_date,
    lombard_ltv=lombard_ltv if lombard_actif else 40,
    lombard_taux=lombard_taux if lombard_actif else 3.5,
    lombard_rendement=lombard_rendement if lombard_actif else 6.0,
)

df_central = simuler(rendement_central, **kwargs)
df_pessimiste = simuler(rendement_pessimiste, **kwargs)
df_optimiste = simuler(rendement_optimiste, **kwargs)

# --- GRAPHIQUE PATRIMOINE BRUT ---
st.subheader("Évolution du patrimoine financier brut")

fig1 = go.Figure()

fig1.add_trace(go.Scatter(
    x=df_optimiste['Date'], y=df_optimiste['Patrimoine financier'],
    name=f'Optimiste ({rendement_optimiste:.1f}%)',
    line=dict(color='#1D9E75', width=1, dash='dot'),
))
fig1.add_trace(go.Scatter(
    x=df_pessimiste['Date'], y=df_pessimiste['Patrimoine financier'],
    name=f'Pessimiste ({rendement_pessimiste:.1f}%)',
    line=dict(color='#E24B4A', width=1, dash='dot'),
    fill='tonexty',
    fillcolor='rgba(200, 200, 200, 0.2)'
))
fig1.add_trace(go.Scatter(
    x=df_central['Date'], y=df_central['Patrimoine financier'],
    name=f'Central ({rendement_central:.1f}%)',
    line=dict(color='#378ADD', width=2),
))

fig1.update_layout(
    xaxis_title='', yaxis_title='€',
    hovermode='x unified',
    margin=dict(t=20, b=20),
    legend=dict(orientation='h', y=-0.1)
)
st.plotly_chart(fig1, use_container_width=True)

# --- GRAPHIQUE DECOMPOSITION ---
st.subheader("Décomposition (scénario central)")

fig2 = go.Figure()
fig2.add_trace(go.Scatter(
    x=df_central['Date'], y=df_central['Patrimoine financier'],
    name='Patrimoine brut',
    line=dict(color='#378ADD', width=2),
    fill='tozeroy', fillcolor='rgba(55, 138, 221, 0.1)'
))
fig2.add_trace(go.Scatter(
    x=df_central['Date'], y=df_central['Dettes'],
    name='Dettes',
    line=dict(color='#E24B4A', width=2),
    fill='tozeroy', fillcolor='rgba(226, 75, 74, 0.1)'
))
fig2.add_trace(go.Scatter(
    x=df_central['Date'], y=df_central['Patrimoine net'],
    name='Patrimoine net',
    line=dict(color='#1D9E75', width=2),
))
fig2.update_layout(
    xaxis_title='', yaxis_title='€',
    hovermode='x unified',
    margin=dict(t=20, b=20),
    legend=dict(orientation='h', y=-0.1)
)
st.plotly_chart(fig2, use_container_width=True)

# --- JALONS ---
st.subheader("Jalons clés (patrimoine brut)")

jalons = [1, 3, 5, 10, 15, 20]
jalons_valides = [j for j in jalons if j <= horizon]
cols = st.columns(len(jalons_valides))

for i, ans in enumerate(jalons_valides):
    idx = min(ans * 12 - 1, len(df_central) - 1)
    val = df_central['Patrimoine financier'].iloc[idx]
    val_opt = df_optimiste['Patrimoine financier'].iloc[idx]
    val_pess = df_pessimiste['Patrimoine financier'].iloc[idx]
    cols[i].metric(
        f"Dans {ans} an{'s' if ans > 1 else ''}",
        f"€ {val:,.0f}",
        f"△ {val_opt - val_pess:,.0f}€"
    )

st.divider()
st.caption(f"Rendement central : {rendement_central}% | Apport : {apport_mensuel}€/mois | PEE : {pee_annuel}€/an")
