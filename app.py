from datetime import datetime, timezone
from typing import Dict, List, Tuple

import requests
import streamlit as st
from bs4 import BeautifulSoup
from fpdf import FPDF

st.set_page_config(page_title="Verifica Agevolazioni Assunzione", layout="wide")

INSTITUTIONAL_SOURCES = [
    {
        "name": "Ministero del Lavoro - Incentivi all'assunzione",
        "url": "https://www.lavoro.gov.it/temi-e-priorita/occupazione/focus-on/incentivi-allassunzione",
        "type": "Fonte istituzionale",
    },
    {
        "name": "INPS - Portale delle Agevolazioni (ex DiResCo)",
        "url": "https://www.inps.it/it/it/dettaglio-scheda.it.schede-servizio-strumento.schede-servizi.portale-delle-agevolazioni-ex-diresco-50130.portale-delle-agevolazioni-ex-diresco.html",
        "type": "Fonte previdenziale",
    },
    {
        "name": "ANPAL - Incentivi all'occupazione",
        "url": "https://www.anpal.gov.it/incentivi",
        "type": "Politiche attive",
    },
    {
        "name": "Gazzetta Ufficiale - Normativa vigente",
        "url": "https://www.gazzettaufficiale.it/",
        "type": "Fonte normativa primaria",
    },
    {
        "name": "Agenzia delle Entrate - Agevolazioni fiscali",
        "url": "https://www.agenziaentrate.gov.it/portale/web/guest/agevolazioni",
        "type": "Fonte fiscale",
    },
]

REGIONI_SUD = ["Abruzzo", "Basilicata", "Calabria", "Campania", "Molise", "Puglia", "Sardegna", "Sicilia"]
REGIONI = REGIONI_SUD + ["Emilia-Romagna", "Friuli-Venezia Giulia", "Lazio", "Liguria", "Lombardia", "Marche", "Piemonte", "Toscana", "Trentino-Alto Adige", "Umbria", "Valle d'Aosta", "Veneto"]


def _short_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else "Pagina raggiunta"
    description = soup.find("meta", attrs={"name": "description"})
    if description and description.get("content"):
        return f"{title} — {description['content'][:220]}"
    return title[:260]


@st.cache_data(ttl=3600, show_spinner=False)
def refresh_sources() -> Tuple[List[Dict[str, str]], str]:
    """Checks institutional source availability at each access (cached for one hour)."""
    checked = []
    for source in INSTITUTIONAL_SOURCES:
        enriched = source.copy()
        try:
            response = requests.get(source["url"], timeout=8, headers={"User-Agent": "AgevolazioniAssunzioni/1.0"})
            enriched["status"] = f"HTTP {response.status_code}"
            enriched["reachable"] = "Sì" if response.ok else "Da verificare"
            enriched["evidence"] = _short_text(response.text) if response.ok else "Fonte non raggiungibile al momento"
        except requests.RequestException as exc:
            enriched["status"] = "Errore rete"
            enriched["reachable"] = "No"
            enriched["evidence"] = str(exc)[:220]
        checked.append(enriched)
    return checked, datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")


def calculate_incentives(profile: Dict[str, object]) -> List[Dict[str, object]]:
    incentives = []
    ral = float(profile["ral"])
    regione = str(profile["regione"])
    is_sud = regione in REGIONI_SUD
    contract = str(profile["contratto"])
    eta = int(profile["eta"])
    disoccupazione = int(profile["disoccupazione"])
    sesso = str(profile["sesso"])
    categoria = str(profile["categoria"])
    incremento = bool(profile["incremento"])

    if contract in ["Tempo indeterminato", "Apprendistato professionalizzante"]:
        incentives.append({
            "nome": "Maxi-deduzione costo del lavoro per nuove assunzioni stabili",
            "stima": round(ral * 0.20 * 0.24, 2),
            "priorita": "Alta" if incremento else "Media",
            "requisiti": "Contratto stabile e incremento occupazionale netto; maggiorazione rafforzata per categorie meritevoli di tutela.",
            "fonti": "Agenzia delle Entrate, normativa fiscale vigente e decreti attuativi.",
        })

    if contract == "Apprendistato professionalizzante" and 18 <= eta <= 29:
        aliquota_agevolata = 0.048 if int(profile["dipendenti"]) <= 9 else 0.10
        incentives.append({
            "nome": "Apprendistato professionalizzante - contribuzione ridotta",
            "stima": round(ral * (0.30 - aliquota_agevolata), 2),
            "priorita": "Alta",
            "requisiti": "Età ordinaria 18-29 anni, piano formativo individuale e rispetto della disciplina contrattuale.",
            "fonti": "INPS, Ministero del Lavoro, CCNL applicato.",
        })

    if contract == "Tempo indeterminato" and eta < 35:
        ceiling = 7800 if is_sud else 6000
        incentives.append({
            "nome": "Incentivo giovani under 35 per assunzione stabile",
            "stima": min(ral * 0.30, ceiling),
            "priorita": "Alta",
            "requisiti": "Assunzione/trasformazione a tempo indeterminato di giovane che non abbia avuto precedenti rapporti stabili, nei limiti UE e INPS.",
            "fonti": "Ministero del Lavoro, INPS, Gazzetta Ufficiale.",
        })

    donna_svantaggiata = sesso == "Donna" and (disoccupazione >= 6 if is_sud else disoccupazione >= 24)
    if contract in ["Tempo indeterminato", "Tempo determinato"] and donna_svantaggiata:
        incentives.append({
            "nome": "Incentivo donne svantaggiate",
            "stima": min(ral * 0.30, 7800),
            "priorita": "Alta",
            "requisiti": "Donna priva di impiego regolarmente retribuito da almeno 6 mesi in aree ammissibili o 24 mesi negli altri casi; verifica cumulabilità.",
            "fonti": "INPS, Ministero del Lavoro, normativa UE sugli aiuti di Stato.",
        })

    if categoria == "Percettore NASpI" and contract == "Tempo indeterminato":
        incentives.append({
            "nome": "Assunzione percettori NASpI",
            "stima": round(ral * 0.08, 2),
            "priorita": "Media",
            "requisiti": "Possibile incentivo collegato alla prestazione residua; da validare nel cassetto previdenziale aziendale.",
            "fonti": "INPS - circolari e Portale delle Agevolazioni.",
        })

    if categoria == "Persona con disabilità":
        incentives.append({
            "nome": "Incentivo assunzione lavoratori con disabilità",
            "stima": round(ral * 0.35, 2),
            "priorita": "Alta",
            "requisiti": "Percentuale di riduzione capacità lavorativa e durata del rapporto determinano misura e durata dell'incentivo.",
            "fonti": "INPS, Ministero del Lavoro, disciplina collocamento mirato.",
        })

    if categoria == "NEET / Garanzia Giovani" and eta < 30:
        incentives.append({
            "nome": "Misure giovani NEET e programmi regionali",
            "stima": min(ral * 0.25, 6000),
            "priorita": "Media",
            "requisiti": "Iscrizione a programma attivo e disponibilità fondi regionali/nazionali al momento della domanda.",
            "fonti": "ANPAL, Regione competente, INPS.",
        })

    return sorted(incentives, key=lambda item: (item["priorita"] != "Alta", -float(item["stima"])))


def create_pdf(profile: Dict[str, object], incentives: List[Dict[str, object]], checked_at: str) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 15)
    pdf.cell(0, 10, "Report agevolazioni assunzione", ln=True, align="C")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 8, f"Fonti verificate: {checked_at}", ln=True)
    pdf.ln(4)
    for key, value in profile.items():
        pdf.cell(0, 7, f"{key}: {value}", ln=True)
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "Agevolazioni potenzialmente applicabili", ln=True)
    pdf.set_font("Helvetica", "", 10)
    for item in incentives or [{"nome": "Nessuna agevolazione rilevata", "stima": 0, "requisiti": "Ampliare o verificare il caso con consulente del lavoro."}]:
        pdf.multi_cell(0, 6, f"- {item['nome']} | stima EUR {item['stima']} | {item['requisiti']}")
    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 9)
    pdf.multi_cell(0, 5, "Il report e' una preselezione informativa: prima della domanda verificare autorizzazioni INPS, capienza de minimis/GBER, DURC, incremento occupazionale e cumulabilita'.")
    return bytes(pdf.output(dest="S"))


st.title("🧭 Verifica agevolazioni per assunzioni")
st.caption("Screening operativo aggiornabile da fonti istituzionali e specialistiche del lavoro.")

sources, checked_at = refresh_sources()

with st.sidebar:
    st.header("Griglia caso di assunzione")
    ral = st.number_input("RAL annua lorda (€)", min_value=1_000, max_value=250_000, value=25_000, step=500)
    contratto = st.selectbox("Tipo contratto", ["Tempo indeterminato", "Apprendistato professionalizzante", "Tempo determinato"])
    dipendenti = st.number_input("Numero dipendenti azienda", min_value=1, value=5)
    regione = st.selectbox("Sede di lavoro", REGIONI, index=REGIONI.index("Campania"))
    sesso = st.selectbox("Sesso candidato", ["Donna", "Uomo", "Non dichiarato"])
    eta = st.number_input("Età candidato", min_value=15, max_value=74, value=29)
    disoccupazione = st.slider("Mesi senza impiego regolarmente retribuito", 0, 60, 0)
    categoria = st.selectbox("Categoria specifica", ["Nessuna", "Percettore NASpI", "Persona con disabilità", "NEET / Garanzia Giovani", "Over 50", "Beneficiario ADI/SFL"])
    incremento = st.checkbox("L'assunzione genera incremento occupazionale netto", value=True)
    st.divider()
    if st.button("🔄 Aggiorna fonti ora"):
        refresh_sources.clear()
        st.rerun()

profile = {
    "ral": ral,
    "contratto": contratto,
    "dipendenti": dipendenti,
    "regione": regione,
    "sesso": sesso,
    "eta": eta,
    "disoccupazione": disoccupazione,
    "categoria": categoria,
    "incremento": incremento,
}

incentives = calculate_incentives(profile)
total = sum(float(item["stima"]) for item in incentives)
gross_cost = ral * 1.30

c1, c2, c3, c4 = st.columns(4)
c1.metric("Costo azienda stimato", f"€ {gross_cost:,.0f}")
c2.metric("Agevolazioni potenziali", f"€ {total:,.0f}")
c3.metric("Fonti verificate", f"{sum(s['reachable'] == 'Sì' for s in sources)}/{len(sources)}")
c4.metric("Ultimo aggiornamento", checked_at)

st.subheader("Agevolazioni compatibili con il caso")
if not incentives:
    st.warning("Nessuna agevolazione automatica rilevata con i parametri inseriti. Verifica bandi regionali e condizioni aziendali.")
else:
    for item in incentives:
        with st.expander(f"{item['priorita']} · {item['nome']} · stima € {item['stima']:,.0f}", expanded=item["priorita"] == "Alta"):
            st.write(item["requisiti"])
            st.caption(f"Fonti da verificare: {item['fonti']}")

st.subheader("Checklist prima della domanda")
st.dataframe([
    {"Controllo": "DURC e regolarità contributiva", "Esito": "Obbligatorio"},
    {"Controllo": "Incremento occupazionale netto", "Esito": "Da documentare se richiesto"},
    {"Controllo": "Cumulabilità tra incentivi", "Esito": "Verificare massimali e divieti"},
    {"Controllo": "Aiuti di Stato / de minimis / GBER", "Esito": "Verificare Registro Nazionale Aiuti"},
    {"Controllo": "Autorizzazione INPS preventiva", "Esito": "Da richiedere quando prevista"},
], use_container_width=True, hide_index=True)

st.subheader("Fonti istituzionali monitorate")
st.info("Le fonti vengono interrogate a ogni accesso con cache di 1 ora; il pulsante in sidebar forza un nuovo controllo. La normativa applicabile resta quella vigente alla data della domanda e va confermata con consulente del lavoro/INPS.")
st.dataframe(sources, use_container_width=True, hide_index=True)

pdf_bytes = create_pdf(profile, incentives, checked_at)
st.download_button("📄 Scarica report PDF", data=pdf_bytes, file_name="report_agevolazioni_assunzione.pdf", mime="application/pdf")
