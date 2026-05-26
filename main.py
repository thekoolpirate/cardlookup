import streamlit as st
import requests
from streamlit_cookies_manager import EncryptedCookieManager

FIREBASE_API_KEY = "AIzaSyBqbxgaaGlpeb1F6HRvEW319OcuCsbkAHM"
COOKIE_PASSWORD = "cardlookup-secret-key-2024"

cookies = EncryptedCookieManager(prefix="cardlookup/", password=COOKIE_PASSWORD)
if not cookies.ready():
    st.stop()

st.set_page_config(page_title="CardLookup", page_icon="🃏", layout="wide")

st.markdown("""
<style>
.cl-value { font-size: 1.8rem; font-weight: 600; color: #1D9E75; }
.total-box { background: #EAF3DE; border-radius: 10px; padding: 1rem 1.5rem; text-align: center; margin-top: 1rem; }
.total-label { font-size: 0.85rem; color: #3B6D11; font-weight: 500; }
.total-value { font-size: 2rem; font-weight: 700; color: #1D9E75; }
</style>
""", unsafe_allow_html=True)

st.title("🃏 CardLookup")
st.caption("Scan or enter PSA cert numbers — powered by CardLadder data")

if "token" not in st.session_state:
    st.session_state.token = cookies.get("token") or None
if "logged_in" not in st.session_state:
    st.session_state.logged_in = bool(st.session_state.token)
if "cert_list" not in st.session_state:
    st.session_state.cert_list = []
if "results" not in st.session_state:
    st.session_state.results = {}
if "last_scanned" not in st.session_state:
    st.session_state.last_scanned = ""

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

def get_sales(profile_id, grade, token):
    url = "https://firestore.googleapis.com/v1/projects/cardladder-71d53/databases/(default)/documents:runQuery"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    query = {
        "structuredQuery": {
            "from": [{"collectionId": "sales"}],
            "where": {
                "compositeFilter": {
                    "op": "AND",
                    "filters": [
                        {"fieldFilter": {"field": {"fieldPath": "profileId"}, "op": "EQUAL", "value": {"stringValue": profile_id}}},
                        {"fieldFilter": {"field": {"fieldPath": "grade"}, "op": "EQUAL", "value": {"stringValue": grade}}}
                    ]
                }
            },
            "orderBy": [{"field": {"fieldPath": "date"}, "direction": "DESCENDING"}],
            "limit": 5
        }
    }
    r = requests.post(url, headers=headers, json=query)
    docs = r.json()
    sales = []
    for doc in docs:
        if "document" in doc:
            fields = doc["document"].get("fields", {})
            price = fields.get("price", {}).get("doubleValue") or fields.get("price", {}).get("integerValue")
            date = fields.get("date", {}).get("timestampValue", "")[:10]
            if price:
                sales.append({"price": float(price), "date": date})
    return sales

def lookup_cert(cert):
    try:
        card = get_card_info(cert, st.session_state.token)
        if not card:
            return {"error": "Not found"}
        cl = get_cl_value(card.get("profileId"), card.get("grade"), st.session_state.token)
        sales = get_sales(card.get("profileId"), card.get("grade"), st.session_state.token)
        return {"card": card, "cl": cl, "sales": sales}
    except Exception as e:
        return {"error": str(e)}

def grade_label(g):
    if not g: return ""
    return "PSA " + g.replace("g", "")

def fmt_price(p):
    if p is None: return "N/A"
    return f"${float(p):,.0f}"

with st.sidebar:
    st.header("Account")
    if st.session_state.logged_in:
        st.success("Logged in")
        if st.button("Log out"):
            cookies["token"] = ""
            cookies.save()
            st.session_state.token = None
            st.session_state.logged_in = False
            st.rerun()
    else:
        email = st.text_input("CardLadder email")
        password = st.text_input("CardLadder password", type="password")
        if st.button("Login", type="primary"):
            with st.spinner("Logging in..."):
                token = get_token(email, password)
                if token:
                    st.session_state.token = token
                    st.session_state.logged_in = True
                    cookies["token"] = token
                    cookies.save()
                    st.rerun()
                else:
                    st.error("Login failed — check your credentials")
    st.divider()
    st.header("Lookup mode")
    auto_lookup = st.toggle("Auto lookup on scan", value=False)

if st.session_state.logged_in:
    st.success("Connected to CardLadder")

    col_scan, col_clear = st.columns([4, 1])
    with col_scan:
        scanned = st.text_input(
            "Scan or type cert number — press Enter after each",
            placeholder="Scan barcode or type cert number...",
            key="scanner_input"
        )
    with col_clear:
        st.markdown("<div style='margin-top:28px'>", unsafe_allow_html=True)
        if st.button("Clear all"):
            st.session_state.cert_list = []
            st.session_state.results = {}
            st.session_state.last_scanned = ""
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    if scanned and scanned.strip() and scanned.strip() != st.session_state.last_scanned:
        cert = scanned.strip()
        st.session_state.last_scanned = cert
        if cert not in st.session_state.cert_list:
            st.session_state.cert_list.append(cert)
            if auto_lookup:
                with st.spinner(f"Looking up {cert}..."):
                    st.session_state.results[cert] = lookup_cert(cert)
        st.rerun()

    if st.session_state.cert_list:
        st.markdown(f"**{len(st.session_state.cert_list)} cert(s) scanned**")
        st.markdown("**Scanned cert list:**")

        for i, cert in enumerate(st.session_state.cert_list):
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                if cert in st.session_state.results and "card" in st.session_state.results[cert]:
                    label = st.session_state.results[cert]["card"].get("label", cert)
                    st.write(f"{i+1}. {label} ({cert})")
                else:
                    st.write(f"{i+1}. {cert}")
            with col2:
                if not auto_lookup and cert not in st.session_state.results:
                    if st.button("Lookup", key=f"lookup_{cert}"):
                        with st.spinner(f"Looking up {cert}..."):
                            st.session_state.results[cert] = lookup_cert(cert)
                        st.rerun()
            with col3:
                if st.button("🗑 Remove", key=f"remove_{cert}"):
                    st.session_state.cert_list.remove(cert)
                    if cert in st.session_state.results:
                        del st.session_state.results[cert]
                    st.rerun()

        st.divider()

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

            for cert in st.session_state.cert_list:
                if cert not in st.session_state.results:
                    continue
                data = st.session_state.results[cert]
                if "error" in data:
                    st.error(f"Cert {cert}: {data['error']}")
                    continue

                card = data["card"]
                cl = data["cl"]
                sales = data.get("sales", [])
                cl_val = cl.get("estimatedValue")
                if cl_val:
                    total_cl += float(cl_val)

                sale_prices = [s["price"] for s in sales if s.get("price")]
                cl_avg = sum(sale_prices) / len(sale_prices) if sale_prices else None

                with st.container(border=True):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.markdown(f"**{card.get('label', 'Unknown')}**")
                        pop = cl.get('population')
                        st.caption(f"Cert #{cert} · {grade_label(card.get('grade'))} · Pop {pop:,}" if isinstance(pop, int) else f"Cert #{cert} · {grade_label(card.get('grade'))}")
                    with col2:
                        st.markdown(f"<div class='cl-value'>{fmt_price(cl_val)}</div><div style='font-size:0.75rem;color:#1D9E75;'>CL value</div>", unsafe_allow_html=True)

                    st.divider()

                    c1, c2, c3, c4, c5 = st.columns(5)
                    c1.metric("Last sale", fmt_price(cl.get("lastSalePrice")))
                    c2.metric("1-month avg", fmt_price(cl.get("oneMonthData", {}).get("averagePrice")), f"{cl.get('oneMonthData', {}).get('velocity', 0)} sales")
                    c3.metric("1-quarter avg", fmt_price(cl.get("oneQuarterData", {}).get("averagePrice")), f"{cl.get('oneQuarterData', {}).get('velocity', 0)} sales")
                    c4.metric("1-year avg", fmt_price(cl.get("oneYearData", {}).get("averagePrice")), f"{cl.get('oneYearData', {}).get('velocity', 0)} sales")
                    c5.metric("Confidence", f"{cl.get('confidence', 'N/A')}/10")

                    if sales:
                        st.markdown("**Last 5 sales:**")
                        sale_cols = st.columns(len(sales))
                        for idx, (sale, col) in enumerate(zip(sales, sale_cols)):
                            col.metric(f"Sale {idx+1}", fmt_price(sale['price']), sale['date'])
                        if cl_avg:
                            st.info(f"📊 CL Avg (last {len(sales)} sales): **{fmt_price(cl_avg)}**")
                    else:
                        st.caption("No individual sales data available")

            st.markdown(f"""
            <div class='total-box'>
                <div class='total-label'>Total CL Value ({len(st.session_state.results)} cards)</div>
                <div class='total-value'>${total_cl:,.0f}</div>
            </div>
            """, unsafe_allow_html=True)

else:
    st.info("Enter your CardLadder login in the sidebar to get started")
