import streamlit as st
import streamlit.components.v1 as components
import pickle
import os

st.set_page_config(
    page_title="Territory Lead Blocks Dashboard",
    page_icon="🗺️",
    layout="wide"
)

st.title("🗺️ Territory Assignment Manager")
st.caption("Interactive Lead Allocation Dashboard")

PKL_PATH = "generated_blocks.pkl"

if os.path.exists(PKL_PATH):

    with open(PKL_PATH, "rb") as f:
        block_metadata = pickle.load(f)

    ##########################
    # KPI Row
    ##########################

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Total Lead Blocks",
        len(block_metadata)
    )

    c2.metric(
        "Target Caseload",
        "150 - 300"
    )

    c3.metric(
        "Regions",
        len(set(v["Region"] for v in block_metadata.values()))
    )

    st.divider()

    html = """
    <!DOCTYPE html>
    <html>

    <head>

    <style>

    body{
        background:#0e1117;
        margin:0;
        padding:20px;
        font-family:Arial, Helvetica, sans-serif;
    }

    .dashboard-grid{

        display:grid;

        grid-template-columns:repeat(auto-fit,minmax(300px,1fr));

        gap:22px;

    }

    .block-card{

        background:white;

        border-radius:15px;

        padding:20px;

        position:relative;

        transition:.25s;

        box-shadow:0 8px 25px rgba(0,0,0,.12);

        cursor:pointer;

        overflow:visible;

        border-top:6px solid #2563eb;

    }

    .block-card:hover{

        transform:translateY(-8px);

        box-shadow:0 18px 40px rgba(0,0,0,.25);

    }

    .block-title{

        font-size:22px;

        font-weight:bold;

        color:#1e3a8a;

        margin-bottom:12px;

    }

    .meta{

        margin:8px 0;

        color:#444;

        font-size:15px;

    }

    .badge{

        display:inline-block;

        background:#2563eb;

        color:white;

        padding:4px 12px;

        border-radius:20px;

        font-size:12px;

        margin-bottom:12px;

    }

    .tooltip{

        visibility:hidden;

        opacity:0;

        position:absolute;

        left:50%;

        transform:translateX(-50%);

        bottom:105%;

        width:330px;

        background:#111827;

        color:white;

        padding:15px;

        border-radius:10px;

        transition:.3s;

        z-index:999;

        text-align:left;

        font-size:14px;

        box-shadow:0 10px 30px rgba(0,0,0,.35);

    }

    .tooltip hr{

        border:none;

        border-top:1px solid #374151;

        margin:10px 0;

    }

    .tooltip::after{

        content:"";

        position:absolute;

        top:100%;

        left:50%;

        margin-left:-8px;

        border-width:8px;

        border-style:solid;

        border-color:#111827 transparent transparent transparent;

    }

    .block-card:hover .tooltip{

        visibility:visible;

        opacity:1;

    }

    .pincode-box{

        max-height:100px;

        overflow-y:auto;

        background:#1f2937;

        padding:8px;

        border-radius:6px;

        margin-top:8px;

        line-height:1.6;

        font-size:13px;

    }

    </style>

    </head>

    <body>

    <div class="dashboard-grid">
    """

    for block, data in block_metadata.items():

        html += f"""

        <div class="block-card">

            <div class="badge">{data['Region']}</div>

            <div class="block-title">{block}</div>

            <div class="meta"><b>🏛 State:</b> {data['State']}</div>

            <div class="meta"><b>🏢 Branch:</b> {data['Branch']}</div>

            <div class="meta"><b>📊 Cases:</b> {data['Cases Count']}</div>

            <div class="tooltip">

                <h3 style="margin-top:0;color:#60a5fa;">
                📍 {data['Region']}
                </h3>

                <b>State:</b> {data['State']}<br><br>

                <b>Branch:</b> {data['Branch']}<br><br>

                <b>Total Cases:</b> {data['Cases Count']}<br>

                <hr>

                <b>Assigned Pincodes</b>

                <div class="pincode-box">

                {data['Pincode']}

                </div>

            </div>

        </div>

        """

    html += """

    </div>

    </body>

    </html>

    """

    components.html(
        html,
        height=1300,
        scrolling=True
    )

else:

    st.warning("generated_blocks.pkl not found. Run data_processor.py first.")