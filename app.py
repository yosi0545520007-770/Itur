import os
import streamlit as st
import pandas as pd
import time
import pydeck as pdk
import googlemaps
import json
import math
import re
import streamlit.components.v1 as components

# טעינה אוטומטית של מפתח Google Maps אל ה-Session (ENV/Secrets)
if not st.session_state.get("google_api_key"):
    _k = os.getenv("GOOGLE_MAPS_API_KEY")
    if not _k:
        try:
            _k = st.secrets.get("google", {}).get("api_key")  # type: ignore[attr-defined]
        except Exception:
            _k = None
    if _k:
        st.session_state["google_api_key"] = _k

# --- הגדרת מנוע הגיאוקודינג ---
# אנו יוצרים אותו פעם אחת כדי לחסוך במשאבים באמצעות המטמון של Streamlit
@st.cache_resource
def get_gmaps_client(api_key):
    """Initializes and returns a Google Maps client."""
    try:
        return googlemaps.Client(key=api_key)
    except Exception as e:
        st.error(f"שגיאה באימות מפתח ה-API: {e}")
        return None

def geocode_address_google(gmaps, address):
    """Geocodes a single address using Google Maps API."""
    geocode_result = gmaps.geocode(address, language='iw')
    return geocode_result


def _deg_to_ddm(value: float, *, is_lat: bool) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    sign = ('N' if is_lat else 'E') if value >= 0 else ('S' if is_lat else 'W')
    deg = int(abs(value))
    minutes = (abs(value) - deg) * 60
    return (f"{deg:02d}° {minutes:06.3f}' {sign}" if is_lat
            else f"{deg:03d}° {minutes:06.3f}' {sign}")


def _deg_to_dms(value: float, *, is_lat: bool) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    sign = ('N' if is_lat else 'E') if value >= 0 else ('S' if is_lat else 'W')
    deg = int(abs(value))
    rem = (abs(value) - deg) * 60
    minutes = int(rem)
    seconds = (rem - minutes) * 60
    return (f"{deg:02d}° {minutes:02d}' {seconds:05.2f}\" {sign}" if is_lat
            else f"{deg:03d}° {minutes:02d}' {seconds:05.2f}\" {sign}")

# --- פונקציה לעיבוד הנתונים ---
def geocode_dataframe(df):
    """
    Geocodes a DataFrame containing an 'Address' column and shows progress.
    """
    api_key = st.session_state.get("google_api_key")
    if not api_key:
        st.warning("יש להזין מפתח Google Maps API כדי להמשיך.")
        return None

    gmaps = get_gmaps_client(api_key)
    if not gmaps:
        st.error("לא ניתן היה ליצור חיבור ל-Google Maps. אנא בדוק את מפתח ה-API שלך.")
        return None

    if 'Address' not in df.columns:
        st.error("הקובץ חייב להכיל עמודה בשם 'Address'.")
        return None

    latitudes = []
    longitudes = []
    statuses = []
    found_addresses = []

    # יצירת שורת ההתקדמות
    progress_bar = st.progress(0, text="מתחיל עיבוד...")
    total_rows = len(df)

    # לולאה על כל כתובת עם הצגת התקדמות
    for i, address in enumerate(df['Address']):
        status = "לא נמצא"
        found_address = None
        try:
            geocode_result = geocode_address_google(gmaps, address)
            if geocode_result:
                latitudes.append(geocode_result[0]['geometry']['location']['lat'])
                longitudes.append(geocode_result[0]['geometry']['location']['lng'])
                status = "נמצא"
                # הסרת שם המדינה מהכתובת שנמצאה
                _fa = geocode_result[0]['formatted_address']
                if _fa.endswith(", Israel") or _fa.endswith(", ישראל"):
                    _fa = _fa.rsplit(',', 1)[0]
                found_address = _fa
            else:
                latitudes.append(None)
                longitudes.append(None)
        except Exception:
            latitudes.append(None)
            longitudes.append(None)
            status = "שגיאה"
        
        statuses.append(status)
        found_addresses.append(found_address)

        # עדכון שורת ההתקדמות
        progress_text = f"מעבד כתובת {i + 1} מתוך {total_rows}: {address}"
        progress_bar.progress((i + 1) / total_rows, text=progress_text)

    progress_bar.empty()  # הסתרת שורת ההתקדמות בסיום
    df['Latitude'] = latitudes
    df['Longitude'] = longitudes
    df['Status'] = statuses
    df['Found Address'] = found_addresses
    # פורמטים נוספים כדי להציג DDM ו-DMS
    try:
        df['lat_ddm'] = [ _deg_to_ddm(v, is_lat=True) if v is not None else '' for v in latitudes ]
        df['lon_ddm'] = [ _deg_to_ddm(v, is_lat=False) if v is not None else '' for v in longitudes ]
        df['lat_dms'] = [ _deg_to_dms(v, is_lat=True) if v is not None else '' for v in latitudes ]
        df['lon_dms'] = [ _deg_to_dms(v, is_lat=False) if v is not None else '' for v in longitudes ]
    except Exception:
        pass
    return df

# --- בניית הממשק הגרפי ---
st.set_page_config(layout="wide", page_title="כלי להצמדת נ.צ.")

# הזרקת CSS כדי להפוך את כל האתר ל-RTL
st.markdown(
    """
    <style>
    /* הגדרת כיוון כללי מימין לשמאל עבור כל הדף והקונטיינרים הראשיים של Streamlit */
    html, body, [data-testid="stAppViewContainer"], [data-testid="stSidebar"] {
        direction: rtl;
        text-align: right;
    }
    
    /* יישור טקסט עבור שדות קלט ושטחי טקסט */
    input[type="text"], textarea, .stTextInput > div > div > input, .stTextArea > div > div > textarea {
        text-align: right;
    }
    
    /* התאמת כפתורי רדיו: יישור הטקסט לימין של העיגול */
    .stRadio > label {
        flex-direction: row-reverse; /* הופך את סדר האלמנטים בתוך התווית */
        justify-content: flex-end;   /* מיישר את התוכן לימין */
    }
    .stRadio > label > div:first-child { /* העיגול של כפתור הרדיו */
        margin-left: 0.5rem; /* רווח בין העיגול לטקסט */
        margin-right: 0;
    }
    
    /* התאמת כפתורים: לוודא שהטקסט בתוך הכפתור מיושר נכון */
    .stButton > button {
        direction: rtl;
    }
    
    /* התאמת Expander: לוודא שהכותרת והתוכן הם RTL */
    .streamlit-expanderHeader {
        direction: rtl;
        text-align: right;
    }
    .streamlit-expanderContent {
        direction: rtl;
        text-align: right;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("📍 כלי להצמדת נ.צ. לכתובות")
st.write("העלה קובץ CSV או Excel המכיל עמודה בשם `Address` והכלי יוסיף את הקואורדינטות.")

if st.button("אודות המערכת"):
    with st.expander("אודות המערכת", expanded=True):
        st.markdown("""
            ### מבוא
            מערכת 'איתור' היא כלי מתקדם להצמדת קואורדינטות גיאוגרפיות (קו רוחב וקו אורך) לרשימת כתובות. הכלי נועד לייעל תהליכי עבודה הדורשים מיקום מדויק של כתובות על גבי מפה.

            ### איך זה עובד?
            1.  **הזנת נתונים:** ניתן להזין כתובות בכמה דרכים:
                *   **העלאת קובץ:** תמיכה בקבצי `CSV` ו-`Excel` המכילים עמודה בשם `Address`.
                *   **הדבקת טקסט:** הדבקת רשימת כתובות, כאשר כל כתובת נמצאת בשורה נפרדת.
                *   **סט בדיקה:** שימוש בסט נתונים מובנה לבדיקה מהירה של יכולות המערכת.
            2.  **עיבוד:** המערכת שולחת כל כתובת לשירות **Google Maps Geocoding API** ומקבלת בחזרה את הקואורדינטות המדויקות, הכתובת כפי שהמערכת זיהתה אותה, וסטטוס הצלחה.
            3.  **הצגת תוצאות:** התוצאות מוצגות בטבלה אינטראקטיבית, כולל תצוגה של הקואורדינטות בפורמטים `DDM` ו-`DMS`. בנוסף, כל הנקודות מוצגות על גבי מפה אינטראקטיבית.

            ### תכונות נוספות
            *   **בדיקת טעויות נפוצות:** המערכת מציעה וריאציות אפשריות לכל כתובת כדי לסייע באיתור ותיקון של טעויות כתיב.
            *   **ייצוא נתונים:** ניתן להוריד את טבלת התוצאות המלאה כקובץ `CSV` בלחיצת כפתור.

            ### טכנולוגיה
            המערכת נבנתה באמצעות **Python** והספריות **Streamlit** לממשק המשתמש ו-**Pandas** לעיבוד נתונים. הגיאוקודינג והמפות מבוססים על שירותי **Google Maps API**.
            """, unsafe_allow_html=True)
# --- הגדרות API ---
st.sidebar.header("הגדרות")
api_key_input = st.sidebar.text_input("הזן מפתח Google Maps API", type="password", key="google_api_key")
st.sidebar.info("האפליקציה משתמשת ב-Google Maps API לדיוק ומהירות. איך להשיג מפתח API?")

# --- שיטת קלט ---
input_method = st.radio("בחר שיטת קלט:", ("העלאת קובץ", "הדבקת טקסט", "סט בדיקה"))

df = None

PREDEFINED_TEST_SET = [
    "בני ברק, ירושלים, 71",
    "רמת גן, ביאליק, 82",
    "בת ים, בלפור, 93",
    "הרצליה, סוקולוב, 104",
    "כפר סבא, ויצמן, 115",
    "חדרה, הנשיא ויצמן, 6",
    "לוד, הרצל, 17",
    "רמלה, הרצל, 28",
    "רעננה, אחוזה, 39",
    "גבעתיים, כצנלסון, 50",
    "נהריה, הגעתון, 61",
    "עכו, בן עמי, 72",
    "אילת, התמרים, 83",
    "טבריה, הגליל, 94",
    "צפת, ירושלים, 105",
    "קרית שמונה, תל חי, 116",
    "דימונה, שדרות הנשיא, 7",
    "יבנה, הדוגית, 18",
    "נס ציונה, ויצמן, 29",
    "רחובות, הרצל, 40",
    "אופקים, הרצל, 51",
    "שדרות, מנחם בגין, 62",
    "מודיעין-מכבים-רעות, עמק זבולון, 73",
    "בית שמש, נהר הירדן, 84",
    "אריאל, צה\"ל, 95",
    "מעלה אדומים, דרך קדם, 106",
    "אור יהודה, העצמאות, 117",
    "יהוד-מונוסון, ויצמן, 8",
    "קרית אונו, לוי אשכול, 19",
    "גבעת שמואל, הזיתים, 30",
    "קרית גת, שדרות לכיש, 41",
    "קרית ים, שדרות ירושלים, 52",
    "קרית ביאליק, קרן היסוד, 63",
    "קרית מוצקין, גושן, 74",
    "נשר, דרך השלום, 85",
    "טירת כרמל, הרצל, 96",
    "יקנעם עילית, התמר, 107",
    "כרמיאל, נשיאי ישראל, 118",
    "מגדל העמק, הנשיא, 9",
    "עפולה, הנשיא ויצמן, 20",
    "בית שאן, שאול המלך, 31",
    "ערד, חן, 42",
    "מצפה רמון, נחל ציחור, 53",
    "אשקלון, בן גוריון, 64",
    "קדימה-צורן, השקמה, 75",
    "פרדס חנה-כרכור, דרך הבנים, 86",
    "זכרון יעקב, המייסדים, 97",
    "בנימינה-גבעת עדה, העצמאות, 108",
    "הוד השרון, דרך רמתיים, 119",
    "גני תקווה, הגליל, 10",
    "כוכב יאיר, שדרות קק\"ל, 21",
]

if input_method == "העלאת קובץ":
    uploaded_file = st.file_uploader("בחר קובץ", type=['csv', 'xlsx'])
    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
            st.write("תצוגה מקדימה של 5 השורות הראשונות:", df.head())
        except Exception as e:
            st.error(f"שגיאה בקריאת הקובץ: {e}")

elif input_method == "הדבקת טקסט":
    st.write("הדבק את הכתובות למטה, כל כתובת בשורה נפרדת (לדוגמה: תל אביב, הרצל, 1):")
    text_input = st.text_area("רשימת כתובות:", height=250)
    if text_input:
        # המרת הטקסט לרשימת כתובות ויצירת DataFrame
        addresses = [line.strip() for line in text_input.split('\n') if line.strip()]
        if addresses:
            df = pd.DataFrame(addresses, columns=['Address'])
            st.write("תצוגה מקדימה של הכתובות שהוזנו:", df.head())

elif input_method == "סט בדיקה":
    st.info("נעשה שימוש בסט בדיקה קבוע המכיל כתובות תקינות ושגויות.")
    df = pd.DataFrame(PREDEFINED_TEST_SET, columns=['Address'])
    st.write("תצוגה מקדימה של סט הבדיקה:", df.head())

# שמירת ה-DataFrame במצב הסשן כדי שלא יאבד בריצה מחדש
if df is not None:
    st.session_state['df_to_process'] = df

# כפתור עיבוד ותצוגת תוצאות (משותף לשתי השיטות)
if 'df_to_process' in st.session_state and not st.session_state['df_to_process'].empty:
    if st.button("🚀 התחל להצמיד נ.צ.", use_container_width=True):
        with st.spinner("מעבד..."):
            # שמירת התוצאות במצב הסשן
            st.session_state['result_df'] = geocode_dataframe(st.session_state['df_to_process'].copy())
            if st.session_state['result_df'] is not None:
                st.balloons()

# הצגת התוצאות אם הן קיימות במצב הסשן
if 'result_df' in st.session_state and st.session_state['result_df'] is not None:
    st.success("העיבוד הסתיים בהצלחה!")
    result_df = st.session_state['result_df']
    st.dataframe(result_df)

    # טעויות כתיבה נפוצות לכל כתובת (ברשימה נפתחת)
    def _common_address_mistakes(addr: str) -> list[str]:
        a = (addr or "").strip()
        if not a:
            return []
        parts = [p.strip() for p in a.split(',') if p.strip()]
        street_part = parts[0] if parts else a
        city = parts[-1] if len(parts) > 1 else ""
        m = re.match(r"^(.*?)(?:\s+(\d+))?$", street_part)
        street = m.group(1).strip() if m else street_part
        number = m.group(2) if m and m.group(2) else ""
        variants: list[str] = []
        def add(s: str):
            s2 = s.strip()
            if s2 and s2 not in variants:
                variants.append(s2)
        # בלי מספר
        if city:
            add(f"{street}, {city}")
        add(street)
        # החלפת סדר
        if city and number:
            add(f"{city}, {street} {number}")
            add(f"{street} {number} {city}")
        elif city:
            add(f"{city}, {street}")
        # רק עיר
        if city:
            add(city)
        # קיצורים נפוצים
        rep = {"רחוב": "רח'", "שדרות": "שד'", "שדרה": "שד'", "דרך": "ד'", "כיכר": "כ'"}
        s_short = street
        for k, v in rep.items():
            s_short = re.sub(fr"\b{k}\b", v, s_short)
        if s_short != street:
            if city and number:
                add(f"{s_short} {number}, {city}")
            elif city:
                add(f"{s_short}, {city}")
            else:
                add(s_short)
        # מקף לפני מספר
        if number:
            if city:
                add(f"{street}-{number}, {city}")
            add(f"{street}-{number}")
        return variants[:10]

    # פתיחה פר‑שורה: לכל כתובת expander עצמאי
    st.markdown("**טעויות כתיבה נפוצות — לכל כתובת בנפרד:**")
    preview = result_df.head(50)
    for _, row in preview.iterrows():
        addr = str(row.get('Found Address') or row.get('Address') or '')
        if not addr:
            continue
        with st.expander(f"טעויות אפשריות: {addr}"):
            original_lat = row.get('Latitude')
            original_lon = row.get('Longitude')
            ms = _common_address_mistakes(addr)
            if ms:
                for i, mistake in enumerate(ms):
                    cols = st.columns([0.7, 0.3])
                    cols[0].code(mistake, language=None)
                    if cols[1].button("אמת", key=f"val_{row.name}_{i}"):
                        api_key = st.session_state.get("google_api_key")
                        if not api_key:
                            st.warning("יש להזין מפתח API כדי לאמת.")
                        else:
                            gmaps = get_gmaps_client(api_key)
                            with st.spinner(f"מאמת את '{mistake}'..."):
                                result = geocode_address_google(gmaps, mistake)
                                if result and original_lat is not None:
                                    res_lat = result[0]['geometry']['location']['lat']
                                    res_lon = result[0]['geometry']['location']['lng']
                                    if math.isclose(res_lat, original_lat, rel_tol=1e-4) and math.isclose(res_lon, original_lon, rel_tol=1e-4):
                                        st.success(f"אימות הצליח! הנ.צ. זהה.")
                                    else:
                                        st.error(f"אימות נכשל. נמצא נ.צ. שונה: ({res_lat:.4f}, {res_lon:.4f})")
                                else:
                                    st.error("הכתובת לא נמצאה.")
            else:
                st.caption("לא נמצאו וריאציות להצעה")

    # --- הוספת מפה ---
    map_data = result_df.dropna(subset=['Latitude', 'Longitude'])
    if not map_data.empty:
        # הגדרת נקודת ההתחלה ושאר היעדים
        start_point = map_data.iloc[0]
        destinations = map_data.iloc[1:]

        # יצירת קווים מההתחלה לכל יעד
        route_lines = []
        if not destinations.empty:
            for _, dest in destinations.iterrows():
                route_lines.append({
                    "start": [start_point['Longitude'], start_point['Latitude']],
                    "end": [dest['Longitude'], dest['Latitude']],
                })

        # הגדרת שכבת הנקודות למפה
        scatterplot_layer = pdk.Layer(
            "ScatterplotLayer",
            data=map_data,
            get_position=['Longitude', 'Latitude'],
            get_color=[34, 139, 34, 200],  # צבע ירוק
            get_radius=50,  # רדיוס הנקודות במטרים
            pickable=True,
            auto_highlight=True,
        )

        # הגדרת שכבת הקווים למפה
        line_layer = pdk.Layer(
            "LineLayer",
            data=route_lines,
            get_source_position="start",
            get_target_position="end",
            get_color=[255, 0, 0, 200],  # צבע אדום
            get_width=3,
        )

        # העברת רשימה של שתי השכבות למפה
        # מציג מפה של גוגל עם נקודות בלבד
        # בניית נקודות: אדום ברירת מחדל; אם DDM ו-DMS שונים (בגלל עיגול) מוסיפים ירוק
        def _parse_ddm(s: str) -> float | None:
            m = re.search(r"(\d+)[°º]\s*([0-9.]+)'\s*([NSEW])", str(s) if s else "")
            if not m:
                return None
            deg = int(m.group(1)); minutes = float(m.group(2)); hemi = m.group(3)
            val = deg + minutes / 60.0
            if hemi in ('S','W'):
                val = -val
            return val

        def _parse_dms(s: str) -> float | None:
            m = re.search(r"(\d+)[°º]\s*(\d+)'\s*([0-9.]+)\"\s*([NSEW])", str(s) if s else "")
            if not m:
                return None
            deg = int(m.group(1)); minutes = int(m.group(2)); seconds = float(m.group(3)); hemi = m.group(4)
            val = deg + minutes / 60.0 + seconds / 3600.0
            if hemi in ('S','W'):
                val = -val
            return val

        py_points = []
        for _, row in map_data.iterrows():
            if pd.isna(row["Latitude"]) or pd.isna(row["Longitude"]):
                continue
            title = str(row.get("Found Address") or row.get("Address") or "")
            lat = float(row["Latitude"]); lon = float(row["Longitude"]) 
            ddm_lat = _parse_ddm(row.get("lat_ddm", "")); ddm_lon = _parse_ddm(row.get("lon_ddm", ""))
            dms_lat = _parse_dms(row.get("lat_dms", "")); dms_lon = _parse_dms(row.get("lon_dms", ""))
            def _close(a, b, tol=1e-6):
                return (a is None) or (b is None) or abs(a-b) <= tol
            if ddm_lat is not None and ddm_lon is not None and dms_lat is not None and dms_lon is not None and (not _close(ddm_lat, dms_lat) or not _close(ddm_lon, dms_lon)):
                py_points.append({"lat": ddm_lat, "lng": ddm_lon, "title": f"{title} (DDM)", "color": "red"})
                py_points.append({"lat": dms_lat, "lng": dms_lon, "title": f"{title} (DMS)", "color": "green"})
            else:
                py_points.append({"lat": lat, "lng": lon, "title": title, "color": "red"})

        center = py_points[0] if py_points else {"lat": 32.08, "lng": 34.78}
        api_key_map = (st.session_state.get("google_api_key") or os.getenv("GOOGLE_MAPS_API_KEY") or "")

        if not api_key_map:
            # נפילה חזרה למפת PyDeck אם אין מפתח תקין
            scatter = pdk.Layer(
                "ScatterplotLayer",
                data=map_data,
                get_position=['Longitude', 'Latitude'],
                get_color=[255, 0, 0, 200],
                get_radius=50,
                pickable=True,
            )
            st.warning("לא זוהה מפתח Google Maps. מציג מפה חלופית (PyDeck).")
            st.pydeck_chart(pdk.Deck(layers=[scatter], initial_view_state=pdk.ViewState(latitude=map_data.iloc[0]['Latitude'], longitude=map_data.iloc[0]['Longitude'], zoom=12)))
        else:
            html = f"""
<!doctype html>
<html><head><meta charset=\"utf-8\" />
<style>html,body,#map{{height:100%;margin:0;padding:0}} .note{{font:14px Arial;padding:8px}}</style>
<script>
  const POINTS = {json.dumps(py_points)};
  function initMap() {{
    const map = new google.maps.Map(document.getElementById('map'), {{
      center: {{lat: {center['lat']}, lng: {center['lng']}}},
      zoom: 12,
      mapTypeId: 'roadmap'
    }});
    for (const p of POINTS) {{
      new google.maps.Marker({{
        position: {{lat: p.lat, lng: p.lng}},
        map: map,
        title: p.title,
        icon: p.color === 'green' ? 'http://maps.google.com/mapfiles/ms/icons/green-dot.png' : 'http://maps.google.com/mapfiles/ms/icons/red-dot.png'
      }});
    }}
  }}
  // אם הספרייה לא עולה, נציג הודעה ידידותית אחרי טיים-אאוט קצר
  setTimeout(function(){{
    if (!(window.google && google.maps)) {{
      document.getElementById('map').innerHTML = '<div class="note">בעיה בטעינת Google Maps. בדוק API Key, Billing והגבלות referrer (localhost/127.0.0.1).</div>';
    }}
  }}, 2500);
</script>
<script async defer src=\"https://maps.googleapis.com/maps/api/js?key={api_key_map}&callback=initMap\"></script>
</head>
<body>
  <div id=\"map\" style=\"height:600px\"></div>
</body></html>
"""
            components.html(html, height=600)

    csv_output = result_df.to_csv(index=False).encode('utf-8-sig')
    st.download_button(label="📥 הורד קובץ תוצאות (CSV)", data=csv_output, file_name='addresses_with_coordinates.csv', mime='text/csv', use_container_width=True)
