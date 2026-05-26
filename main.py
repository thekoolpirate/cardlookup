import streamlit as st
import requests

FIREBASE_API_KEY = "AIzaSyBqbxgaaGlpeb1F6HRvEW319OcuCsbkAHM"

st.set_page_config(page_title="CardLookup", page_icon="🃏", layout="centered")

st.markdown("""
<style>
.cl-value { font-size: 2rem; font-weight: 600; color: #1D9E75; }
.card-title { font-size: 1.1rem; font-weight: 500; }
</style>
""", unsafe_allow_html=True)

st.title("🃏 CardLookup")
st.caption("Look up PSA cards by cert number — powered by CardLadder data")

with st.sidebar:
    st.header("Login")
    email = st.text_input("CardLadder email")
    password = st.text_input("CardLadder password", type="password")
    login_btn = st.button("Login", type="primary")

if "token" not in st.session_state:
    st.session_state.token = None
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

def get_token(email, password):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
    r = requests.post(url, json={"email": email, "password": password, "returnSecureToken": True})
    d = r.json()
    return d.get("idToken")

def get_card_info(cert, token):
    r = requests.post(
        "https://us-central1-cardladder-71d53.cloudfunctions.net/httpbuildcollectioncard",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"data": {"cert": str(cert), "grader": "psa", "useTaxonomy": True}}
    )
    return r.json().get("result", {})

def get_cl_value(profile_id, grade, token):
    r = requests.post(
        "https://us-central1-cardladder-71d53.cloudfunctions.net/httpcardestimate",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"data": {"profileId": profile_id, "grader": "psa", "grade": grade, "qualifierType": None, "autographGrade": None}}
    )
    return r.json().get("result", {})

def grade_label(g):
    if not g: return ""
    return "PSA " + g.replace("g", "")

def fmt_price(p):
    if p is None: return "N/A"
    return f"${float(p):,.0f}"

if login_btn:
    with st.spinner("Logging in..."):
        token = get_token(email, password)
        if token:
            st.session_state.token = token
            st.session_state.logged_in = True
            st.sidebar.success("Logged in!")
        else:
            st.sidebar.error("Login failed — check your credentials")

if st.session_state.logged_in:
    st.success("Connected to CardLadder")

    cert_input = st.text_area(
        "Enter PSA cert numbers — one per line or comma separated",
        placeholder="98952632\n143938538\n12345678",
        height=120
    )

    if st.button("Look up cards", type="primary"):
        certs = [c.strip() for c in cert_input.replace(",", "\n").split("\n") if c.strip()]

        if not certs:
            st.warning("Please enter at least one cert number")
        else:
            for cert in certs:
                with st.spinner(f"Looking up cert {cert}..."):
                    try:
                        card = get_card_info(cert, st.session_state.token)
                        if not card:
                            st.error(f"Cert {cert}: not found")
                            continue

                        cl = get_cl_value(card.get("profileId"), card.get("grade"), st.session_state.token)

                        with st.container(border=True):
                            col1, col2 = st.columns([3, 1])
                            with col1:
                                st.markdown(f"**{card.get('label', 'Unknown')}**")
                                pop = cl.get('population')
                                st.caption(f"Cert #{cert} · {grade_label(card.get('grade'))} · Pop {pop:,}" if isinstance(pop, int) else f"Cert #{cert} · {grade_label(card.get('grade'))}")
                            with col2:
                                cl_val = cl.get("estimatedValue")
                                st.markdown(f"<div class='cl-value'>{fmt_price(cl_val)}</div><div style='font-size:0.75rem;color:#1D9E75;'>CL value</div>", unsafe_allow_html=True)

                            st.divider()

                            c1, c2, c3, c4, c5 = st.columns(5)
                            c1.metric("Last sale", fmt_price(cl.get("lastSalePrice")))
                            c2.metric("1-month avg", fmt_price(cl.get("oneMonthData", {}).get("averagePrice")), f"{cl.get('oneMonthData', {}).get('velocity', 0)} sales")
                            c3.metric("1-quarter avg", fmt_price(cl.get("oneQuarterData", {}).get("averagePrice")), f"{cl.get('oneQuarterData', {}).get('velocity', 0)} sales")
                            c4.metric("1-year avg", fmt_price(cl.get("oneYearData", {}).get("averagePrice")), f"{cl.get('oneYearData', {}).get('velocity', 0)} sales")
                            c5.metric("Confidence", f"{cl.get('confidence', 'N/A')}/10")

                    except Exception as e:
                        st.error(f"Cert {cert}: error — {str(e)}")
else:
    st.info("Enter your CardLadder login in the sidebar to get started")
