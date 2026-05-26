import streamlit as st
import requests

FIREBASE_API_KEY = "AIzaSyBqbxgaaGlpeb1F6HRvEW319OcuCsbkAHM"

st.set_page_config(page_title="CardLookup", page_icon="🃏", layout="wide")

st.markdown("""
<style>
.cl-value { font-size: 1.8rem; font-weight: 600; color: #1D9E75; }
.total-box { background: #EAF3DE; border-radius: 10px; padding: 1rem 1.5rem; text-align: center; }
.total-label { font-size: 0.85rem; color: #3B6D11; font-weight: 500; }
.total-value { font-size: 2rem; font-weight: 700; color: #1D9E75; }
</style>
""", unsafe_allow_html=True)

st.title("🃏 CardLookup")
st.caption("Scan or enter PSA cert numbers — powered by CardLadder data")

with st.sidebar:
    st.header("Login")
    email = st.text_input("CardLadder email")
    password = st.text_input("CardLadder password", type="password")
    login_btn = st.button("Login", type="primary")
    st.divider()
    st.header("Lookup mode")
    auto_lookup = st.toggle("Auto lookup on scan", value=False, help="When ON, each cert is looked up instantly after scanning. When OFF, scan all first then click Lookup All.")

if "token" not in st.session_state:
    st.session_state.token = None
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "cert_list" not in st.session_state:
    st.session_state.cert_list = []
if "results" not in st.session_state:
    st.session_state.results = {}

def get_token(email, password):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
    r = requests.post(url, json={"email": email, "password": password, "returnSecureToken": True})
    return r.json().get("idToken")

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

def lookup_cert(cert):
    try:
        card = get_card_info(cert, st.session_state.token)
        if not card:
            return {"error": "Not found"}
        cl = get_cl_value(card.get("profileId"), card.get("grade"), st.session_state.token)
        return {"card": card, "cl": cl}
    except Exception as e:
        return {"error": str(e)}

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

    col_scan, col_clear = st.columns([4, 1])
    with col_scan:
        scanned = st.text_input(
            "Scan or type cert number — press Enter after each",
            placeholder="Scan barcode or type cert number...",
            key="scanner_input",
            label_visibility="visible"
        )
    with col_clear:
        st.markdown("<div style='margin-top:28px'>", unsafe_allow_html=True)
        if st.button("Clear all"):
            st.session_state.cert_list = []
            st.session_state.results = {}
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    if scanned and scanned.strip():
        cert = scanned.strip()
        if cert not in st.session_state.cert_list:
            st.session_state.cert_list.append(cert)
            if auto_lookup and cert not in st.session_state.results:
                with st.spinner(f"Looking up {cert}..."):
                    st.session_state.results[cert] = lookup_cert(cert)
            st.rerun()

    if st.session_state.cert_list:
        st.markdown(f"**{len(st.session_state.cert_list)} cert(s) scanned**")

        if not auto_lookup:
            if st.button("🔍 Lookup all cards", type="primary"):
                progress = st.progress(0)
                for i, cert in enumerate(st.session_state.cert_list):
                    if cert not in st.session_state.results:
                        with st.spinner(f"Looking up {cert}..."):
                            st.session_state.results[cert] = lookup_cert(cert)
                    progress.progress((i + 1) / len(st.session_state.cert_list))
                st.rerun()

        if st.session_state.results:
            total_cl = 0
            rows = []

            for cert in st.session_state.cert_list:
                if cert in st.session_state.results:
                    data = st.session_state.results[cert]
                    if "error" in data:
                        rows.append({"Cert #": cert, "Card": "Error: " + data["error"], "Grade": "", "CL Value": "", "Last Sale": "", "1-Mo Avg": "", "1-Yr Avg": "", "Pop": ""})
                    else:
                        card = data["card"]
                        cl = data["cl"]
                        cl_val = cl.get("estimatedValue")
                        if cl_val:
                            total_cl += float(cl_val)
                        rows.append({
                            "Cert #": cert,
                            "Card": card.get("label", "Unknown"),
                            "Grade": grade_label(card.get("grade")),
                            "CL Value": fmt_price(cl_val),
                            "Last Sale": fmt_price(cl.get("lastSalePrice")),
                            "1-Mo Avg": fmt_price(cl.get("oneMonthData", {}).get("averagePrice")),
                            "1-Yr Avg": fmt_price(cl.get("oneYearData", {}).get("averagePrice")),
                            "Pop": cl.get("population", "N/A")
                        })
                else:
                    rows.append({"Cert #": cert, "Card": "Pending...", "Grade": "", "CL Value": "", "Last Sale": "", "1-Mo Avg": "", "1-Yr Avg": "", "Pop": ""})

            st.dataframe(rows, use_container_width=True, hide_index=True)

            st.markdown(f"""
            <div class='total-box'>
                <div class='total-label'>Total CL Value ({len(st.session_state.results)} cards)</div>
                <div class='total-value'>${total_cl:,.0f}</div>
            </div>
            """, unsafe_allow_html=True)

else:
    st.info("Enter your CardLadder login in the sidebar to get started")
