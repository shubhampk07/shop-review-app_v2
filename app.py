import streamlit as st

st.set_page_config(page_title="Shop Drawing Review Prototype", layout="centered")

st.title("📐 Shop Drawing Review – Prototype")
st.write("Upload structural and shop drawings to simulate a first-pass review.")

# Upload section
structural_pdf = st.file_uploader("Upload Structural Drawing (PDF)", type=["pdf"])
shop_pdf = st.file_uploader("Upload Shop Drawing (PDF)", type=["pdf"])

# Run review (mock)
if structural_pdf and shop_pdf:
    if st.button("🔍 Run First-Pass Review"):
        st.success("✅ Review Complete!")
        st.markdown("### Issues Found:")
        st.markdown("- ❌ Missing rebar tag on slab edge\n- ⚠️ Bar spacing mismatch at Grid B–C\n- ✅ Anchor bolt locations OK")

