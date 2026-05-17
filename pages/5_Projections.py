import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date
from dateutil.relativedelta import relativedelta

st.set_page_config(page_title="Projections", layout="wide")
st.title("🔭 Projections patrimoniales")

# --- PATRIMOINE ACTUEL ---
st.subheader("Point de départ")
col1, col2, col3 = st.columns(3)
with col1:
    patrimoine_actuel = st.number_input(
        "Patrimoine financier actuel (€)",
        min_value=0, max_value=1000000,
        value=94000, step=1000,
        help="CTO + PEA + Crypto + Cash"
    )
with col2:
    dette_actuelle = st.number_input(
        "Dettes actuelles (€)",
        min_value=0, max_value=500000,
        value=26000, step=500,
        help="Crédit conso + Terrain"
    )
with col3:
    patrimoine_net_actuel = patrimoine_actuel - dette_actuelle
    st.metric("Patrimoine net actuel", f"€ {patrimoine_net_actuel:,.0f}")

st.divider()

# --- PARAMETRES ---
st.subheader("Paramètres de simulation")

col1, col2 = st.columns(2)

with col1:
    rendement_central = st.slider(
        "Rendement annuel central (%)",
        min_value=0.0, max_value=15.0,
        value=5.0, step=0.5
    )
    apport_mensuel = st.slider(
        "Apport mensuel (€)",
        min_value=0, max_value=5000,
        value=800, step=100
    )
    pee_annuel = st.slider(
        "Déblocage PEE annuel (€)",
        min_value=0, max_value=20000,
        value=10000, step=500
    )
    horizon = st.slider(
        "Horizon (années)",
        min_value=1, max_value=25,
        value=10, step=1
    )

with col2:
    st.markdown("**Crédit conso actuel**")
    crd_conso_actuel = st.number_input(
        "CRD crédit conso (€)",
        min_value=0, max_value=100000,
        value=13115, step=100
    )
    mensualite_conso = st.number_input(
        "Mensualité crédit conso (€)",
        min_value=0, max_value=2000,
        value=435, step=10
    )
    
    st.markdown("**Nouveau crédit conso à l'échéance ?**")
    nouveau_credit = st.toggle("Simuler un nouveau crédit conso", value=False)
    if nouveau_credit:
        montant_nouveau_credit = st.number_input(
            "Montant nouveau crédit (€)",
            min_value=0, max_value=100000,
            value=15000, step=500
        )
        duree_nouveau_credit = st.slider(
            "Durée (mois)",
            min_value=12, max_value=84,
            value=60, step=12
        )
        mensualite_nouveau = st.number_input(
            "Mensualité nouveau crédit (€)",
            min_value=0, max_value=2000,
            value=270, step=10
        )

st.divider()

# --- SIMULATION ---
rendement_pessimiste = max(0, rendement_central - 2)
rendement_optimiste = rendement_central + 2

def simuler(rendement_annuel, apport_mensuel, pee_annuel,
            crd_conso, mensualite_conso, horizon_mois,
            nouveau_credit=False, montant_nouveau=0,
            duree_nouveau=60, mensualite_nouveau=270):
    
    taux_mensuel = (1 + rendement_annuel / 100) ** (1/12) - 1
    taux_conso = 2.20 / 100 / 12
    
    # Mensualités terrain (ta part)
    def mensualite_terrain(d):
        if date(2026, 1, 1) <= d < date(2029, 5, 1):
            return 66
        elif date(2029, 5, 1) <= d < date(2032, 9, 1):
            return 110
        elif date(2032, 9, 1) <= d <= date(2035, 12, 1):
            return 154
        return 0

    patrimoine = patrimoine_actuel
    crd = crd_conso
    crd_terrain = 12862.0
    nouveau_crd = 0
    nouveau_actif = False
    
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
        
        # Remboursement crédit conso
        if crd > 0:
            interet = crd * taux_conso
            amort = min(mensualite_conso - interet, crd)
            crd = max(0, crd - amort)
            
            # Nouveau crédit quand le premier est fini
            if crd == 0 and nouveau_credit and not nouveau_actif:
                nouveau_crd = montant_nouveau
                nouveau_actif = True
        
        # Remboursement nouveau crédit
        if nouveau_actif and nouveau_crd > 0:
            nouveau_crd = max(0, nouveau_crd - mensualite_nouveau)
        
        # Remboursement terrain
        m_terrain = mensualite_terrain(d)
        crd_terrain = max(0, crd_terrain - m_terrain)
        
        # Patrimoine net
        dettes = crd + nouveau_crd + crd_terrain
        patrimoine_net = patrimoine - dettes
        
        resultats.append({
            'Date': d,
            'Patrimoine financier': patrimoine,
            'Dettes': dettes,
            'Patrimoine net': patrimoine_net
        })
    
    return pd.DataFrame(resultats)

horizon_mois = horizon * 12

kwargs_base = dict(
    apport_mensuel=apport_mensuel,
    pee_annuel=pee_annuel,
    crd_conso=crd_conso_actuel,
    mensualite_conso=mensualite_conso,
    horizon_mois=horizon_mois,
    nouveau_credit=nouveau_credit,
    montant_nouveau=montant_nouveau_credit if nouveau_credit else 0,
    duree_nouveau=duree_nouveau_credit if nouveau_credit else 60,
    mensualite_nouveau=mensualite_nouveau if nouveau_credit else 270
)

df_central = simuler(rendement_central, **kwargs_base)
df_pessimiste = simuler(rendement_pessimiste, **kwargs_base)
df_optimiste = simuler(rendement_optimiste, **kwargs_base)

# --- GRAPHIQUE PATRIMOINE NET ---
st.subheader("Évolution du patrimoine net")

fig1 = go.Figure()

fig1.add_trace(go.Scatter(
    x=df_optimiste['Date'], y=df_optimiste['Patrimoine net'],
    name=f'Optimiste ({rendement_optimiste:.1f}%)',
    line=dict(color='#1D9E75', width=1, dash='dot'),
    fill=None
))
fig1.add_trace(go.Scatter(
    x=df_pessimiste['Date'], y=df_pessimiste['Patrimoine net'],
    name=f'Pessimiste ({rendement_pessimiste:.1f}%)',
    line=dict(color='#E24B4A', width=1, dash='dot'),
    fill='tonexty',
    fillcolor='rgba(200, 200, 200, 0.2)'
))
fig1.add_trace(go.Scatter(
    x=df_central['Date'], y=df_central['Patrimoine net'],
    name=f'Central ({rendement_central:.1f}%)',
    line=dict(color='#378ADD', width=2),
))

fig1.update_layout(
    xaxis_title='',
    yaxis_title='€',
    hovermode='x unified',
    margin=dict(t=20, b=20),
    legend=dict(orientation='h', y=-0.1)
)
st.plotly_chart(fig1, use_container_width=True)

# --- GRAPHIQUE DECOMPOSITION ---
st.subheader("Décomposition du patrimoine (scénario central)")

fig2 = go.Figure()

fig2.add_trace(go.Scatter(
    x=df_central['Date'], y=df_central['Patrimoine financier'],
    name='Patrimoine financier',
    line=dict(color='#378ADD', width=2),
    fill='tozeroy',
    fillcolor='rgba(55, 138, 221, 0.1)'
))
fig2.add_trace(go.Scatter(
    x=df_central['Date'], y=df_central['Dettes'],
    name='Dettes',
    line=dict(color='#E24B4A', width=2),
    fill='tozeroy',
    fillcolor='rgba(226, 75, 74, 0.1)'
))
fig2.add_trace(go.Scatter(
    x=df_central['Date'], y=df_central['Patrimoine net'],
    name='Patrimoine net',
    line=dict(color='#1D9E75', width=2),
))

fig2.update_layout(
    xaxis_title='',
    yaxis_title='€',
    hovermode='x unified',
    margin=dict(t=20, b=20),
    legend=dict(orientation='h', y=-0.1)
)
st.plotly_chart(fig2, use_container_width=True)

# --- JALONS ---
st.subheader("Jalons clés")

jalons = [1, 3, 5, 10]
cols = st.columns(len(jalons))

for i, ans in enumerate(jalons):
    if ans <= horizon:
        idx = min(ans * 12 - 1, len(df_central) - 1)
        val = df_central['Patrimoine net'].iloc[idx]
        val_opt = df_optimiste['Patrimoine net'].iloc[idx]
        val_pess = df_pessimiste['Patrimoine net'].iloc[idx]
        cols[i].metric(
            f"Dans {ans} an{'s' if ans > 1 else ''}",
            f"€ {val:,.0f}",
            f"△ {val_opt - val_pess:,.0f}€ d'écart"
        )

st.divider()
st.caption(f"Simulation basée sur un rendement central de {rendement_central}% | Apport mensuel : {apport_mensuel}€ | PEE : {pee_annuel}€/an")
