import streamlit as st
from fpdf import FPDF
import base64

st.set_page_config(page_title="HR Advisor 2025", layout="wide")

# --- FUNZIONE GENERAZIONE PDF ---
def create_pdf(dati_report):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, "Report Preventivo Agevolazioni Assunzione", ln=True, align='C')
    pdf.ln(10)
    
    pdf.set_font("Arial", '', 12)
    for key, value in dati_report.items():
        pdf.cell(200, 10, f"{key}: {value}", ln=True)
    
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, "Nota: I valori sono stime basate sulle normative 2025.", ln=True)
    
    return pdf.output(dest='S').encode('latin-1')

# --- INTERFACCIA ---
st.title("💼 HR Simulator: Apprendistato & Bonus 2025")

with st.sidebar:
    st.header("Parametri Input")
    ral = st.number_input("RAL (€)", value=25000)
    tipo = st.selectbox("Tipo Contratto", ["Tempo Indeterminato", "Apprendistato Professionalizzante", "Tempo Determinato"])
    dipendenti = st.number_input("Numero Dipendenti Azienda", min_value=1, value=5)
    eta = st.number_input("Età Candidato", 15, 65, 24)
    regione = st.selectbox("Regione", ["Campania", "Puglia", "Sicilia", "Calabria", "Lombardia", "Lazio", "Veneto", "Altro"])
    is_donna = st.checkbox("Candidato Donna")
    disocc_mesi = st.slider("Mesi Disoccupazione", 0, 24, 0)

# --- LOGICA DI CALCOLO ---
sud_regioni = ["Campania", "Puglia", "Sicilia", "Calabria", "Sardegna", "Basilicata", "Molise", "Abruzzo"]
costo_standard = ral * 1.30
bonus_totale = 0
dettaglio_bonus = []

# Caso Apprendistato
if tipo == "Apprendistato Professionalizzante":
    if dipendenti <= 9:
        # Aliquota 1,5% primo anno, 3% secondo, 10% terzo. Media cautelativa: 4.8% invece di 30%
        risparmio_appr = ral * (0.30 - 0.048) 
        dettaglio_bonus.append(f"Sgravio Apprendistato Under 9 dip.: €{int(risparmio_appr)}")
        bonus_totale += risparmio_appr
    else:
        # Aliquota fissa 10% invece di 30%
        risparmio_appr = ral * (0.30 - 0.10)
        dettaglio_bonus.append(f"Sgravio Apprendistato Standard: €{int(risparmio_appr)}")
        bonus_totale += risparmio_appr

# Caso Indeterminato + Bonus Coesione
elif tipo == "Tempo Indeterminato":
    # Bonus Giovani Under 35
    if eta < 35:
        massimale = 7800 if regione in sud_regioni else 6000
        risparmio = min(ral * 0.30, massimale)
        dettaglio_bonus.append(f"Bonus Giovani (Coesione): €{int(risparmio)}")
        bonus_totale += risparmio
    
    # Bonus Donne (se applicabile)
    if is_donna and (disocc_mesi >= 6 if regione in sud_regioni else disocc_mesi >= 24):
        massimale_d = 7800
        risparmio_d = min(ral * 0.30, massimale_d)
        dettaglio_bonus.append(f"Bonus Donne Svantaggiate: €{int(risparmio_d)}")
        # Nota: spesso non cumulabili, prendiamo il migliore
        if risparmio_d > risparmio if 'risparmio' in locals() else 0:
            bonus_totale = risparmio_d

# Maxi-deduzione 120% (valore fiscale)
if tipo == "Tempo Indeterminato" or tipo == "Apprendistato Professionalizzante":
    risparmio_fiscale = (ral * 0.20) * 0.24 # RAL extra deducibile * aliquota IRES
    dettaglio_bonus.append(f"Maxi-deduzione 120% (Risparmio IRES): €{int(risparmio_fiscale)}")
    bonus_totale += risparmio_fiscale

costo_netto = costo_standard - bonus_totale

# --- VISUALIZZAZIONE ---
c1, c2, c3 = st.columns(3)
c1.metric("Costo Lordo", f"€{int(costo_standard):,}")
c2.metric("Risparmio Totale", f"€{int(bonus_totale):,}", f"{int((bonus_totale/costo_standard)*100)}%")
c3.metric("Costo Netto Reale", f"€{int(costo_netto):,}")

st.subheader("Analisi Dettagliata")
for b in dettaglio_bonus:
    st.write(f"✅ {b}")

# --- ESPORTAZIONE PDF ---
dati_per_pdf = {
    "Profilo": f"{tipo} - {eta} anni",
    "RAL": f"€{ral}",
    "Sede": regione,
    "Costo Lordo Annuale": f"€{int(costo_standard)}",
    "Risparmio Annuo": f"€{int(bonus_totale)}",
    "Costo Netto Azienda": f"€{int(costo_netto)}",
    "Dettagli": " / ".join(dettaglio_bonus)
}

pdf_bytes = create_pdf(dati_per_pdf)
st.download_button(
    label="📩 Scarica Report PDF",
    data=pdf_bytes,
    file_name="preventivo_assunzione.pdf",
    mime="application/pdf"
)
