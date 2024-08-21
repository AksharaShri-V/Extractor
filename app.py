import streamlit as st
import base64
import requests
import json
import io
from docx import Document
from docx.shared import Pt
import os

# Set up OpenAI API key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

def encode_pdf(file):
    return base64.b64encode(file.read()).decode('utf-8')

def split_into_chunks(text, max_chars=12000):
    chunks = []
    current_chunk = ""
    for line in text.split('\n'):
        if len(current_chunk) + len(line) > max_chars:
            chunks.append(current_chunk)
            current_chunk = line
        else:
            current_chunk += '\n' + line
    if current_chunk:
        chunks.append(current_chunk)
    return chunks

def process_chunk_with_openai(chunk, is_first_chunk=False):
    system_instruction = """
    You are an advanced AI assistant specialized in processing text from PDFs. Your tasks are:

    1. Identify main headings, subheadings, and side headings. Use the following format:
       MAIN HEADING: text
       SUBHEADING: text
       SIDE HEADING: text

    2. Extract and format normal text paragraphs completely. Ensure no sentences or words are left incomplete.

    3. Identify any listed data or enumerated information and preserve its format.

    4. Detect any tabular data structures within the text. For each detected table:
       - Convert each row of the table into a bullet point
       - Start each bullet point with the first column's value
       - Include all values from all columns in the bullet point
       - Ensure that the relationship between all columns is clearly expressed
       - Do not omit any data for brevity
       For example, if a table has columns "Name", "Age", "Occupation", and "Salary", a row might be converted to:
       • John Doe, aged 30, works as a software engineer and earns $75,000 annually.

    5. Maintain the original order and context of the document while processing.

    6. Do not use any special characters or symbols for formatting except for the bullet points (•) for table data.

    7. It is crucial that you process and include ALL content from the given chunk. Do not truncate or omit any information.

    Your goal is to extract and transform the document content completely, preserving all original information and structure, while ensuring that tabular data is presented as bullet points that clearly convey the relationships between all data points.

    If this is the first chunk of the document, start with 'DOCUMENT START:'. If it's the last chunk, end with 'DOCUMENT END:'.
    """

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "gpt-4o",
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": f"Process the following text chunk from a PDF, following the instructions given. {'This is the first chunk of the document.' if is_first_chunk else ''}\n\n{chunk}"}
        ]
    }

    response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, data=json.dumps(data))
    
    if response.status_code == 200:
        return response.json()['choices'][0]['message']['content']
    else:
        raise Exception(f"Error in API call: {response.text}")

def create_word_document(content):
    doc = Document()
    
    # Define styles for different heading levels
    styles = doc.styles
    styles['Heading 1'].font.size = Pt(16)
    styles['Heading 2'].font.size = Pt(14)
    styles['Heading 3'].font.size = Pt(12)
    
    lines = content.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        if line.startswith('MAIN HEADING:'):
            doc.add_paragraph(line.replace('MAIN HEADING:', '').strip(), style='Heading 1')
        elif line.startswith('SUBHEADING:'):
            doc.add_paragraph(line.replace('SUBHEADING:', '').strip(), style='Heading 2')
        elif line.startswith('SIDE HEADING:'):
            doc.add_paragraph(line.replace('SIDE HEADING:', '').strip(), style='Heading 3')
        elif line.startswith('•'):
            doc.add_paragraph(line, style='List Bullet')
        else:
            doc.add_paragraph(line)

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

def main():
    st.title("PDF Content Extractor to Word Document")

    uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

    if uploaded_file is not None:
        if st.button("Process PDF"):
            with st.spinner("Processing PDF and generating Word document... This may take a while."):
                try:
                    encoded_pdf = encode_pdf(uploaded_file)
                    chunks = split_into_chunks(encoded_pdf)
                    processed_chunks = []

                    for i, chunk in enumerate(chunks):
                        st.text(f"Processing chunk {i+1} of {len(chunks)}...")
                        processed_chunk = process_chunk_with_openai(chunk, is_first_chunk=(i==0))
                        processed_chunks.append(processed_chunk)

                    processed_text = "\n".join(processed_chunks)
                    word_buffer = create_word_document(processed_text)

                    st.success("Processing complete. Click the button below to download the Word document.")
                    
                    # Use the original filename for the download
                    original_filename = os.path.splitext(uploaded_file.name)[0]
                    
                    # Offer the processed content as a downloadable Word document
                    st.download_button(
                        label="Download",
                        data=word_buffer,
                        file_name=f"{original_filename}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()
