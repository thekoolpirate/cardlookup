import streamlit as st
import requests
import pandas as pd
from streamlit_cookies_manager import EncryptedCookieManager

FIREBASE_API_KEY = "AIzaSyBqbxgaaGlpeb1F6HRvEW319OcuCsbkAHM"
COOKIE_PASSWORD = "cardlookup-secret-key-2024"
EBAY_APP_ID = "PASTE_YOUR_EBAY_APP_ID_HERE"

cookies = EncryptedCookieManager(prefix="cardlookup/", password=COOKIE_PASSWORD)
if not cookies.ready():
    st.stop()

st.set_page_config(page_title="CardLookup", page_icon="🃏", layout="wide")

st.markdown("""
<style>
div[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }
.total-box { 
    background: linear-gradient(135deg, #0F2A1E, #1A3D2B);
    border: 1px solid #00C48C33;
    border-radius: 12px; 
    padding: 1.5rem 2rem; 
    text-align: center; 
    margin-top: 1.5rem; 
}
.total-label { font-size: 0.8rem; color: #00C48C; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; }
.total-value { font-size: 2.5rem; font-weight: 700; color: #FFFFFF; margin-top: 4px; }
.profit-card { background: #1A1D27; border: 1px solid #2A2D3A; border-radius: 12px; padding: 1.5rem; margin-bottom: 1rem; }
.payout-value { font-size: 2rem; font-weight: 700; color: #00C48C; }
.profit-value { font-size: 1.5rem; font-weight: 600; }
.cl-number { font-size: 2rem; font-weight: 700; color: #00C48C; }
section[data-testid="stSidebar"] { background-color: #13161F; border-right: 1px solid #2A2D3A; }
footer { visibility: hidden; }
#MainMenu { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

st.title("🃏 CardLookup")

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
if "app_mode" not in st.session_state:
    st.session_state.app_mode = "Bulk Comp"
if "payout_pct" not in st.session_state:
    saved_pct = cookies.get("payout_pct")
    st.session_state.payout_pct = float(saved_pct) if saved_pct else 93.0
if "obo_result" not in st.session_state:
    st.session_state.obo_result = None
if "obo_buy_price" not in st.session_state:
    st.session_state.obo_buy_price = None

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

def get_sales(cert, token):
    r = requests.post(
        "https://us-central1-cardladder-71d53.cloudfunctions.net/httpprofilesales",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"data": {"cert": str(cert), "grader": "psa", "limit": 5, "sort": "date", "direction": "desc"}}
    )
    data = r.json()
    sales = data.get("result", {}).get("sales", [])
    result = []
    for s in sales[:5]:
        price = s.get("price")
        date = s.get("date", "")[:10]
        if price is not None:
            result.append({"price": float(price), "date": date})
    return result

def get_lowest_ebay_listing(card_name, grade):
    if EBAY_APP_ID == "PASTE_YOUR_EBAY_APP_ID_HERE":
        return None
    try:
        grade_num = grade.replace("PSA ", "")
        query = f"{card_name} PSA {grade_num}"
        url = "https://svcs.ebay.com/services/search/FindingService/v1"
        params = {
            "OPERATION-NAME": "findItemsAdvanced",
            "SERVICE-VERSION": "1.0.0",
            "SECURITY-APPNAME": EBAY_APP_ID,
            "RESPONSE-DATA-FORMAT": "JSON",
            "REST-PAYLOAD": "",
            "keywords": query,
            "itemFilter(0).name": "ListingType",
            "itemFilter(0).value": "FixedPrice",
            "itemFilter(1).name": "Condition",
            "itemFilter(1).value": "3000",
            "sortOrder": "PricePlusShippingLowest",
            "paginationInput.entriesPerPage": "5"
        }
        r = requests.get(url, params=params)
        data = r.json()
        items = data.get("findItemsAdvancedResponse", [{}])[0].get("searchResult", [{}])[0].get("item", [])
        prices = []
        for item in items:
            price = float(item.get("sellingStatus", [{}])[0].get("currentPrice", [{}])[0].get("__value__", 0))
            shipping = float(item.get("shippingInfo", [{}])[0].get("shippingServiceCost", [{}])[0].get("__value__", 0))
            prices.append(price + shipping)
        return min(prices) if prices else None
    except:
        return None

def lookup_cert(cert):
    try:
        card = get_card_info(cert, st.session_state.token)
        if not card:
            return {"error": "Not found"}
        cl = get_cl_value(card.get("profileId"), card.get("grade"), st.session_state.token)
        sales = get_sales(cert, st.session_state.token)
        grade = grade_label(card.get("grade"))
        lowest_listing = get_lowest_ebay_listing(card.get("label", ""), grade)
        return {"card": card, "cl": cl, "sales": sales, "lowest_listing": lowest_listing}
    except Exception as e:
        return {"error": str(e)}

def grade_label(g):
    if not g: return ""
    return "PSA " + g.replace("g", "")

def fmt_price(p):
    if p is None: return ""
    return f"${float(p):,.2f}"

def get_true_comp(cl_val, lowest_listing, avg_last5):
    values = [v for v in [cl_val, lowest_listing, avg_last5] if v is not None]
    return min(values) if values else None

def build_table():
    rows = []
    for cert in st.session_state.cert_list:
        if cert not in st.session_state.results:
            rows.append({"Cert #": cert, "Name": "Pending...", "Grade": "", "CL Value": "", "Lowest Listed": "", "Avg Last 5": "", "True Comp": "", "Sale 1": "", "Sale 2": "", "Sale 3": "", "Sale 4": "", "Sale 5": ""})
            continue
        data = st.session_state.results[cert]
        if "error" in data:
            rows.append({"Cert #": cert, "Name": f"Error: {data['error']}", "Grade": "", "CL Value": "", "Lowest Listed": "", "Avg Last 5": "", "True Comp": "", "Sale 1": "", "Sale 2": "", "Sale 3": "", "Sale 4": "", "Sale 5": ""})
            continue
        card = data["card"]
        cl = data["cl"]
        sales = data.get("sales", [])
        lowest_listing = data.get("lowest_listing")
        cl_val = cl.get("estimatedValue")
        sale_prices = [s["price"] for s in sales if s.get("price") is not None]
        avg_last5 = sum(sale_prices) / len(sale_prices) if sale_prices else None
        true_comp = get_true_comp(cl_val, lowest_listing, avg_last5)
        row = {
            "Cert #": cert,
            "Name": card.get("label", "Unknown"),
            "Grade": grade_label(card.get("grade")),
            "CL Value": fmt_price(cl_val),
            "Lowest Listed": fmt_price(lowest_listing) if lowest_listing else "⏳ Pending API",
            "Avg Last 5": fmt_price(avg_last5),
            "True Comp": fmt_price(true_comp),
        }
        for i in range(5):
            if i < len(sales):
                row[f"Sale {i+1}"] = f"{fmt_price(sales[i]['price'])} ({sales[i]['date']})"
            else:
                row[f"Sale {i+1}"] = ""
        rows.append(row)
    return rows

# ── Sidebar ──────────────────────────────────────────────
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
    st.header("Mode")
    mode = st.radio("", ["Bulk Comp", "One by One"], index=0 if st.session_state.app_mode == "Bulk Comp" else 1, label_visibility="collapsed")
    if mode != st.session_state.app_mode:
        st.session_state.app_mode = mode
        st.rerun()

    st.divider()
    st.header("Payout %")
    payout_pct = st.number_input(
        "Your payout percentage",
        min_value=50.0, max_value=100.0,
        value=st.session_state.payout_pct,
        step=0.5,
        format="%.1f"
    )
    if payout_pct != st.session_state.payout_pct:
        st.session_state.payout_pct = payout_pct
        cookies["payout_pct"] = str(payout_pct)
        cookies.save()

    if st.session_state.app_mode == "Bulk Comp":
        st.divider()
        st.header("Lookup mode")
        auto_lookup = st.toggle("Auto lookup on scan", value=False)

# ── Main content ─────────────────────────────────────────
if st.session_state.logged_in:

    # ── ONE BY ONE MODE ───────────────────────────────────
    if st.session_state.app_mode == "One by One":
        st.subheader("One by One — Profit Calculator")
        st.caption(f"Payout rate: {st.session_state.payout_pct}% — adjust in sidebar")

        cert_input = st.text_input(
            "Enter or scan a cert number",
            placeholder="Scan barcode or type cert number...",
            key="obo_input"
        )

        if st.button("🔍 Look up", type="primary") and cert_input.strip():
            with st.spinner("Looking up card..."):
                result = lookup_cert(cert_input.strip())
                st.session_state.obo_result = result
                st.session_state.obo_buy_price = None

        if st.session_state.obo_result:
            data = st.session_state.obo_result
            if "error" in data:
                st.error(f"Error: {data['error']}")
            else:
                card = data["card"]
                cl = data["cl"]
                sales = data.get("sales", [])
                lowest_listing = data.get("lowest_listing")
                cl_val = cl.get("estimatedValue")
                sale_prices = [s["price"] for s in sales if s.get("price") is not None]
                avg_last5 = sum(sale_prices) / len(sale_prices) if sale_prices else None
                payout_amt = (cl_val * st.session_state.payout_pct / 100) if cl_val else None

                st.markdown("---")
                st.markdown(f"### {card.get('label', 'Unknown')}")
                st.caption(f"{grade_label(card.get('grade'))} · Cert #{cert_input.strip()}")

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("CL Value", fmt_price(cl_val))
                    st.caption("Your payout basis")
                with col2:
                    st.metric(f"Payout ({st.session_state.payout_pct}%)", fmt_price(payout_amt))
                    st.caption("What you get paid")
                with col3:
                    st.metric("Avg Last 5", fmt_price(avg_last5))
                    st.caption("Recent market avg")

                st.markdown("---")
                st.markdown("**Select your buy price:**")

                buy_cols = st.columns(3)
                with buy_cols[0]:
                    if avg_last5 and st.button(f"Use Avg Last 5\n{fmt_price(avg_last5)}"):
                        st.session_state.obo_buy_price = avg_last5
                        st.rerun()
                with buy_cols[1]:
                    if lowest_listing:
                        if st.button(f"Use Lowest Listed\n{fmt_price(lowest_listing)}"):
                            st.session_state.obo_buy_price = lowest_listing
                            st.rerun()
                    else:
                        st.button("Lowest Listed\n⏳ Pending API", disabled=True)
                with buy_cols[2]:
                    custom_price = st.number_input("Enter custom price", min_value=0.0, step=0.50, format="%.2f", key="custom_buy")
                    if st.button("Use custom price"):
                        st.session_state.obo_buy_price = custom_price
                        st.rerun()

                if st.session_state.obo_buy_price is not None:
                    buy = st.session_state.obo_buy_price
                    profit = payout_amt - buy if payout_amt else None
                    st.markdown("---")
                    res_col1, res_col2, res_col3 = st.columns(3)
                    with res_col1:
                        st.metric("Buy Price", fmt_price(buy))
                    with res_col2:
                        st.metric("Payout", fmt_price(payout_amt))
                    with res_col3:
                        st.metric("Profit", fmt_price(profit))

                st.markdown("---")
                if sales:
                    st.markdown("**Last 5 sales:**")
                    sale_cols = st.columns(len(sales))
                    for idx, (sale, col) in enumerate(zip(sales, sale_cols)):
                        col.metric(f"Sale {idx+1}", fmt_price(sale['price']), sale['date'])

    # ── BULK COMP MODE ────────────────────────────────────
    else:
        st.caption("Scan or enter PSA cert numbers — bulk mode")
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
                rows = build_table()
                df = pd.DataFrame(rows)
                st.markdown("### Results")
                st.dataframe(df, use_container_width=True, hide_index=True)

                total_true_comp = sum(
                    get_true_comp(
                        st.session_state.results[c]["cl"].get("estimatedValue"),
                        st.session_state.results[c].get("lowest_listing"),
                        sum([s["price"] for s in st.session_state.results[c].get("sales", []) if s.get("price")]) /
                        len([s for s in st.session_state.results[c].get("sales", []) if s.get("price")])
                        if st.session_state.results[c].get("sales") else None
                    ) or 0
                    for c in st.session_state.cert_list
                    if c in st.session_state.results and "cl" in st.session_state.results[c]
                )

                st.markdown(f"""
                <div class='total-box'>
                    <div class='total-label'>Total True Comp ({len(st.session_state.results)} cards)</div>
                    <div class='total-value'>${total_true_comp:,.0f}</div>
                </div>
                """, unsafe_allow_html=True)

else:
    st.info("Enter your CardLadder login in the sidebar to get started")
