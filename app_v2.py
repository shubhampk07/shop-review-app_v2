import streamlit as st
from pdfminer.high_level import extract_text as pdfminer_extract_text
import pandas as pd
import re
import io
from typing import Dict, List
import numpy as np  # (you can remove later if unused)

# Configure page
st.set_page_config(page_title="Shop Drawing Review Tool", layout="wide")
st.title("📐 Shop Drawing Review Tool")
st.write("Upload structural and shop drawings to compare member sizes and identify discrepancies.")

class PDFProcessor:
    """Handles PDF text extraction (no OCR, Cloud-friendly)"""

    def __init__(self):
        self.text_content = ""
        self.extraction_method = ""

    def extract_text_from_pdf(self, pdf_file, page_range=None) -> str:
        """Extract text from PDF using pdfminer.six (no OCR)."""
        try:
            pdf_file.seek(0)
            pdf_bytes = pdf_file.read()

            # pdfminer works with file-like objects too
            text = pdfminer_extract_text(io.BytesIO(pdf_bytes))

            self.extraction_method = "Direct PDF text extraction (pdfminer.six)"
            return text or ""
        except Exception as e:
            st.error(f"Error processing PDF: {str(e)}")
            return ""

    def _has_meaningful_content(self, text: str) -> bool:
        """Check if extracted text contains meaningful Australian structural drawing content"""
        keywords = [
            'ub', 'uc', 'wb', 'shs', 'rhs', 'chs', 'pfc', 'ua', 'ea', 'angle', 'channel',
            'beam', 'column', 'member', 'size', 'steel', 'section', 'mm', 'metre', 'meter',
            'tfb', 'wc', 'bt', 'flat', 'plate'
        ]
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in keywords)


class MemberParser:
    """Parses and normalizes Australian steel member designations"""
    
    def __init__(self):
        # Australian steel member patterns (AS/NZS 3679) - UPDATED WITH v55 PATTERNS
        self.patterns = {
            'ub': r'(\d+)UB(\d+(?:\.\d+)?)',  # 310UB46.2, 460UB82
            'uc': r'(\d+)UC(\d+(?:\.\d+)?)',  # 200UC59.5, 310UC158
            'wb': r'(\d+)WB(\d+(?:\.\d+)?)',  # 200WB52, 250WB37
            'shs': r'SHS(\d+(?:\.\d+)?)[Xx×](\d+(?:\.\d+)?)',  # SHS100x6, SHS150×10
            'rhs': r'RHS(\d+(?:\.\d+)?)[Xx×](\d+(?:\.\d+)?)[Xx×](\d+(?:\.\d+)?)',  # RHS100x50x6
            'chs': r'CHS(\d+(?:\.\d+)?)[Xx×](\d+(?:\.\d+)?)',  # CHS114x6.0, CHS168×8
            'angle': r'(\d+(?:\.\d+)?)[Xx×](\d+(?:\.\d+)?)[Xx×](\d+(?:\.\d+)?)(?:UA|EA|L)',  # 75x75x6UA, 100x100x8EA
            'angle_ea': r'(\d+(?:\.\d+)?)EA(\d+(?:\.\d+)?)',  # 75EA6, 100EA8
            'angle_ua_alt': r'(\d+(?:\.\d+)?)[Xx×](\d+(?:\.\d+)?)UA(\d+(?:\.\d+)?)',  # 150x90UA10
            'channel': r'(\d+)(?:PFC|UCA)(\d+(?:\.\d+)?)',  # 200PFC23, 150UCA23.4
            'channel_simple': r'(\d+)PFC(?!\d)',  # 150PFC (without mass)
            'tee': r'(\d+)BT(\d+(?:\.\d+)?)',  # 180BT46.5 (Tee sections)
            'flat': r'(\d+(?:\.\d+)?)[Xx×](\d+(?:\.\d+)?)(?:FL|FLAT)',  # 200x16FL (Flat bars)
            'plate': r'(\d+(?:\.\d+)?)[Xx×](\d+(?:\.\d+)?)[Xx×](\d+(?:\.\d+)?)PL',  # 300x250x12PL
            'rod': r'M(\d+)',  # M24 (Threaded rods)
            # Alternative patterns for common variations
            'ub_alt': r'UB(\d+)[Xx×](\d+(?:\.\d+)?)',  # UB310x46.2
            'uc_alt': r'UC(\d+)[Xx×](\d+(?:\.\d+)?)',  # UC200x59.5
            'wb_alt': r'WB(\d+)[Xx×](\d+(?:\.\d+)?)',  # WB200x52
            'tfb': r'(\d+)TFB(\d+(?:\.\d+)?)',  # 180TFB46 (Taper Flange Beams)
            'wc': r'(\d+)WC(\d+(?:\.\d+)?)',  # 310WC137 (Welded Columns)
        }
    
    def extract_members_from_text(self, text: str) -> List[Dict]:
        """Extract all member designations from text"""
        members = []
        lines = text.split('\n')
        
        for line_num, line in enumerate(lines):
            for member_type, pattern in self.patterns.items():
                matches = re.finditer(pattern, line, re.IGNORECASE)
                for match in matches:
                    member_info = {
                        'raw_text': match.group(0),
                        'normalized': self._normalize_member(match.group(0), member_type),
                        'type': member_type,
                        'line_number': line_num + 1,
                        'context': line.strip()
                    }
                    members.append(member_info)
        
        # Remove duplicates while preserving order
        unique_members = []
        seen = set()
        for member in members:
            if member['normalized'] not in seen:
                unique_members.append(member)
                seen.add(member['normalized'])
        
        return unique_members
    
    def _normalize_member(self, member_str: str, member_type: str) -> str:
        """Normalize Australian member designation to standard format"""
        member_str = member_str.upper().replace('X', 'x').replace('×', 'x')
        
        # Normalize different Australian formats to consistent style
        if member_type in ['ub', 'uc', 'wb', 'tfb', 'wc']:
            # Standard format: 310UB46.2, 180TFB46, 310WC137
            if any(section in member_str for section in ['UB', 'UC', 'WB', 'TFB', 'WC']):
                return member_str
            else:
                # Handle alternative formats
                parts = re.findall(r'\d+(?:\.\d+)?', member_str)
                if len(parts) >= 2:
                    section_type = member_type.upper()
                    return f"{parts[0]}{section_type}{parts[1]}"
        
        elif member_type in ['ub_alt', 'uc_alt', 'wb_alt']:
            # Convert UB310x46.2 to 310UB46.2
            section_type = member_type.replace('_alt', '').upper()
            parts = re.findall(r'\d+(?:\.\d+)?', member_str)
            if len(parts) >= 2:
                return f"{parts[0]}{section_type}{parts[1]}"
        
        elif member_type in ['shs', 'rhs', 'chs']:
            # Standardize hollow sections: SHS100x6, RHS100x50x6, CHS114x6
            return member_str
        
        elif member_type in ['angle', 'angle_ea', 'angle_ua_alt']:
            # Standardize angles: 75x75x6UA, 75EA6, 150x90UA10
            if member_type == 'angle_ea':
                # Convert 75EA6 to 75x75x6EA
                parts = re.findall(r'\d+(?:\.\d+)?', member_str)
                if len(parts) >= 2:
                    return f"{parts[0]}x{parts[0]}x{parts[1]}EA"
            elif 'UA' in member_str:
                return member_str.replace('UA', 'UA')
            elif 'EA' in member_str:
                return member_str.replace('EA', 'EA')
            elif 'L' in member_str:
                return member_str.replace('L', 'UA')  # Convert L notation to UA
            else:
                return member_str + 'UA'  # Default to UA if no suffix
        
        elif member_type in ['channel', 'channel_simple']:
            # Standardize channels: 200PFC23, 150PFC
            if member_type == 'channel_simple':
                return member_str + '0'  # Add placeholder mass for simple format
            return member_str
        
        elif member_type == 'tee':
            # Standardize tees: 180BT46.5
            return member_str
        
        elif member_type in ['flat', 'plate']:
            # Standardize flats and plates: 200x16FL, 300x250x12PL
            return member_str
        
        elif member_type == 'rod':
            # Standardize rods: M24
            return member_str
        
        return member_str

class MemberComparator:
    """Compares members between structural and shop drawings"""
    
    def compare_members(self, structural_members: List[Dict], 
                       shop_members: List[Dict]) -> Dict:
        """Compare member lists and identify discrepancies"""
        
        structural_set = {m['normalized'] for m in structural_members}
        shop_set = {m['normalized'] for m in shop_members}
        
        results = {
            'matching_members': list(structural_set & shop_set),
            'missing_in_shop': list(structural_set - shop_set),
            'extra_in_shop': list(shop_set - structural_set),
            'structural_count': len(structural_members),
            'shop_count': len(shop_members),
            'match_percentage': len(structural_set & shop_set) / max(len(structural_set), 1) * 100
        }
        
        return results
    
    def generate_detailed_report(self, structural_members: List[Dict], 
                               shop_members: List[Dict], 
                               comparison_results: Dict) -> pd.DataFrame:
        """Generate detailed comparison report"""
        
        # Create comprehensive member list
        all_members = set()
        all_members.update(m['normalized'] for m in structural_members)
        all_members.update(m['normalized'] for m in shop_members)
        
        report_data = []
        
        for member in sorted(all_members):
            # Find in structural
            struct_info = next((m for m in structural_members if m['normalized'] == member), None)
            shop_info = next((m for m in shop_members if m['normalized'] == member), None)
            
            status = "✅ Match"
            if struct_info and not shop_info:
                status = "❌ Missing in Shop"
            elif shop_info and not struct_info:
                status = "⚠️ Extra in Shop"
            
            report_data.append({
                'Member': member,
                'Status': status,
                'In Structural': "Yes" if struct_info else "No",
                'In Shop': "Yes" if shop_info else "No",
                'Structural Context': struct_info['context'][:50] + "..." if struct_info and len(struct_info['context']) > 50 else (struct_info['context'] if struct_info else ""),
                'Shop Context': shop_info['context'][:50] + "..." if shop_info and len(shop_info['context']) > 50 else (shop_info['context'] if shop_info else "")
            })
        
        return pd.DataFrame(report_data)

# Initialize processors
@st.cache_resource
def get_processors():
    return PDFProcessor(), MemberParser(), MemberComparator()

pdf_processor, member_parser, member_comparator = get_processors()

# UI Layout
col1, col2 = st.columns(2)

with col1:
    st.header("📋 Structural Drawing")
    structural_pdfs = st.file_uploader("Upload Structural Drawings (PDF)", type=["pdf"], key="structural", accept_multiple_files=True)
    
    # Page range selector for structural drawings
    if structural_pdfs:
        st.write("**Page Range (optional):**")
        struct_start_page = st.number_input("Start Page", min_value=0, value=0, key="struct_start")
        struct_end_page = st.number_input("End Page (0 = all)", min_value=0, value=0, key="struct_end")

with col2:
    st.header("🏗️ Shop Drawing")
    shop_pdfs = st.file_uploader("Upload Shop Drawings (PDF)", type=["pdf"], key="shop", accept_multiple_files=True)
    
    # Page range selector for shop drawings
    if shop_pdfs:
        st.write("**Page Range (optional):**")
        shop_start_page = st.number_input("Start Page", min_value=0, value=0, key="shop_start")
        shop_end_page = st.number_input("End Page (0 = all)", min_value=0, value=0, key="shop_end")

# Add test mode for single file
if st.button("🧪 Test Member Extraction (Single File)", type="secondary"):
    if structural_pdfs:
        with st.spinner("Testing member extraction on structural drawings..."):
            all_structural_members = []
            
            # Process each structural PDF
            for pdf_file in structural_pdfs:
                st.write(f"📄 Processing: {pdf_file.name}")
                
                # Set page range if specified
                page_range = None
                if struct_end_page > 0:
                    page_range = (struct_start_page, struct_end_page)
                
                structural_text = pdf_processor.extract_text_from_pdf(pdf_file, page_range)
                st.info(f"Extraction method: {pdf_processor.extraction_method}")
                
                if structural_text.strip():
                    st.success(f"✅ Successfully extracted text from {pdf_file.name}")
                    
                    # Show first 1000 characters of extracted text
                    with st.expander(f"📄 Sample of Extracted Text from {pdf_file.name}"):
                        st.text(structural_text[:1000] + "..." if len(structural_text) > 1000 else structural_text)
                    
                    # Extract members
                    structural_members = member_parser.extract_members_from_text(structural_text)
                    all_structural_members.extend(structural_members)
                    st.success(f"Found {len(structural_members)} unique members in {pdf_file.name}")
                else:
                    st.error(f"Failed to extract text from {pdf_file.name}")
            
            if all_structural_members:
                # Remove duplicates across all files
                unique_members = []
                seen = set()
                for member in all_structural_members:
                    if member['normalized'] not in seen:
                        unique_members.append(member)
                        seen.add(member['normalized'])
                
                st.success(f"Found {len(unique_members)} total unique members across all structural drawings")
                
                # Display found members
                st.write("### 🔍 Extracted Members:")
                members_df = pd.DataFrame(unique_members)
                st.dataframe(members_df[['normalized', 'type', 'raw_text', 'context']], use_container_width=True)
                
                # Summary by type
                member_types = {}
                for member in unique_members:
                    m_type = member['type']
                    if m_type not in member_types:
                        member_types[m_type] = []
                    member_types[m_type].append(member['normalized'])
                
                st.write("### 📊 Summary by Member Type:")
                for m_type, members in member_types.items():
                    st.write(f"**{m_type.upper()}**: {', '.join(set(members))}")
            else:
                st.warning("No steel members found in any of the drawings")
    else:
        st.warning("Please upload at least one structural drawing first")

# Process files when both are uploaded
if structural_pdfs and shop_pdfs:
    if st.button("🔍 Compare Member Sizes", type="primary"):
        with st.spinner("Processing drawings... This may take a moment for OCR processing."):
            
            # Process structural drawings
            st.write("### Processing Structural Drawings...")
            all_structural_members = []
            
            for pdf_file in structural_pdfs:
                st.write(f"📄 Processing: {pdf_file.name}")
                
                # Set page range if specified
                page_range = None
                if struct_end_page > 0:
                    page_range = (struct_start_page, struct_end_page)
                
                structural_text = pdf_processor.extract_text_from_pdf(pdf_file, page_range)
                st.info(f"Extraction method: {pdf_processor.extraction_method}")
                
                if not structural_text.strip():
                    st.error(f"Failed to extract text from {pdf_file.name}")
                    continue
                
                structural_members = member_parser.extract_members_from_text(structural_text)
                all_structural_members.extend(structural_members)
                st.success(f"Found {len(structural_members)} unique members in {pdf_file.name}")
            
            # Remove duplicates across all structural files
            unique_structural_members = []
            seen_structural = set()
            for member in all_structural_members:
                if member['normalized'] not in seen_structural:
                    unique_structural_members.append(member)
                    seen_structural.add(member['normalized'])
            
            # Process shop drawings
            st.write("### Processing Shop Drawings...")
            all_shop_members = []
            
            for pdf_file in shop_pdfs:
                st.write(f"📄 Processing: {pdf_file.name}")
                
                # Set page range if specified
                page_range = None
                if shop_end_page > 0:
                    page_range = (shop_start_page, shop_end_page)
                
                shop_text = pdf_processor.extract_text_from_pdf(pdf_file, page_range)
                st.info(f"Extraction method: {pdf_processor.extraction_method}")
                
                if not shop_text.strip():
                    st.error(f"Failed to extract text from {pdf_file.name}")
                    continue
                
                shop_members = member_parser.extract_members_from_text(shop_text)
                all_shop_members.extend(shop_members)
                st.success(f"Found {len(shop_members)} unique members in {pdf_file.name}")
            
            # Remove duplicates across all shop files
            unique_shop_members = []
            seen_shop = set()
            for member in all_shop_members:
                if member['normalized'] not in seen_shop:
                    unique_shop_members.append(member)
                    seen_shop.add(member['normalized'])
            
            # Compare members
            st.write("### Comparison Results")
            comparison_results = member_comparator.compare_members(unique_structural_members, unique_shop_members)
            
            # Display summary
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Match Percentage", f"{comparison_results['match_percentage']:.1f}%")
            with col2:
                st.metric("Missing in Shop", len(comparison_results['missing_in_shop']))
            with col3:
                st.metric("Extra in Shop", len(comparison_results['extra_in_shop']))
            
            # Display detailed results
            if comparison_results['missing_in_shop']:
                st.error("**❌ Members Missing in Shop Drawing:**")
                for member in comparison_results['missing_in_shop']:
                    st.write(f"• {member}")
            
            if comparison_results['extra_in_shop']:
                st.warning("**⚠️ Extra Members in Shop Drawing:**")
                for member in comparison_results['extra_in_shop']:
                    st.write(f"• {member}")
            
            if comparison_results['matching_members']:
                st.success("**✅ Matching Members:**")
                for member in comparison_results['matching_members']:
                    st.write(f"• {member}")
            
            # Detailed report table
            st.write("### Detailed Comparison Report")
            detailed_report = member_comparator.generate_detailed_report(
                unique_structural_members, unique_shop_members, comparison_results
            )
            
            if not detailed_report.empty:
                st.dataframe(detailed_report, use_container_width=True)
                
                # Download option
                csv = detailed_report.to_csv(index=False)
                st.download_button(
                    label="📥 Download Report as CSV",
                    data=csv,
                    file_name="member_comparison_report.csv",
                    mime="text/csv"
                )
            
            # Debug sections (expandable)
            with st.expander("🔍 Debug: View Extracted Members"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**Structural Members:**")
                    if unique_structural_members:
                        struct_df = pd.DataFrame(unique_structural_members)
                        st.dataframe(struct_df[['normalized', 'type', 'context']])
                    else:
                        st.write("No members found")
                
                with col2:
                    st.write("**Shop Members:**")
                    if unique_shop_members:
                        shop_df = pd.DataFrame(unique_shop_members)
                        st.dataframe(shop_df[['normalized', 'type', 'context']])
                    else:
                        st.write("No members found")

# Instructions
with st.expander("📖 How to Use"):
    st.markdown("""
    ### Instructions:
    1. **Upload PDFs**: Upload one or more structural drawings and corresponding shop drawings
    2. **Set Page Ranges** (optional): Specify which pages to process if you don't need all pages
    3. **Click Compare**: The tool will extract text and identify steel members
    4. **Review Results**: Check for missing members, extra members, and matches
    
    ### What it detects (Updated with v55 patterns):
    - **UB Sections**: 310UB46.2, 460UB82, etc.
    - **UC Sections**: 200UC59.5, 310UC158, etc.
    - **WB Sections**: 200WB52, 250WB37, etc.
    - **TFB Sections**: 180TFB46 (Taper Flange Beams)
    - **WC Sections**: 310WC137 (Welded Columns)
    - **SHS**: SHS100x6, SHS150x10, etc.
    - **RHS**: RHS100x50x6, RHS150x100x8, etc.
    - **CHS**: CHS114x6, CHS168x8, etc.
    - **Angles**: 75x75x6UA, 100x100x8EA, 75EA6, 150x90UA10, etc.
    - **Channels**: 200PFC23, 150UCA23.4, 150PFC, etc.
    - **Tee Sections**: 180BT46.5, etc.
    - **Flat Bars**: 200x16FL, etc.
    - **Plates**: 300x250x12PL, etc.
    - **Threaded Rods**: M24, etc.
    
    ### New Features:
    - **Multiple File Support**: Process multiple PDFs at once
    - **Page Range Selection**: Process only specific pages
    - **Extended Pattern Recognition**: More steel member types recognized
    
    ### Notes:
    - Tool automatically handles OCR if PDFs don't have searchable text
    - Member designations are normalized for comparison
    - Results show context from original drawings for verification
    - Duplicates are automatically removed across multiple files
    """)

# Requirements note
st.sidebar.markdown("""
### Required Packages:
```
streamlit==1.36.0
pdfminer.six==20240706
Pillow==10.4.0
pandas==2.2.2
numpy==1.26.4

```

**Note**: For OCR functionality, you'll need tesseract installed on your system.
""")