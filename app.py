import streamlit as st
import PyPDF2
import openai
import io
from docx import Document
from docx.shared import Pt
import tiktoken
import os
import time
import re

# Set up OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

def extract_text_from_pdf(file):
    pdf_reader = PyPDF2.PdfReader(file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text() + "\n"
    return text

def num_tokens_from_string(string: str, encoding_name: str) -> int:
    encoding = tiktoken.get_encoding(encoding_name)
    num_tokens = len(encoding.encode(string))
    return num_tokens

def split_into_chunks(text, max_tokens=3000):
    encoding = tiktoken.get_encoding("cl100k_base")
    tokens = encoding.encode(text)
    chunks = []
    current_chunk = []
    current_chunk_tokens = 0

    for token in tokens:
        if current_chunk_tokens + 1 > max_tokens:
            chunks.append(encoding.decode(current_chunk))
            current_chunk = []
            current_chunk_tokens = 0
        current_chunk.append(token)
        current_chunk_tokens += 1

    if current_chunk:
        chunks.append(encoding.decode(current_chunk))

    return chunks

def extract_tables_from_text(text):
    # This is a basic pattern and might need refinement for complex tables
    table_pattern = r'(\|.*\|[\n\r])+\|.*\|'
    return re.findall(table_pattern, text)

def convert_table_to_markdown(table_text):
    lines = table_text.strip().split('\n')
    markdown_table = '| ' + ' | '.join(lines[0].strip('|').split('|')) + ' |\n'
    markdown_table += '| ' + ' | '.join(['---' for _ in range(len(lines[0].strip('|').split('|')))]) + ' |\n'
    for line in lines[1:]:
        markdown_table += '| ' + ' | '.join(line.strip('|').split('|')) + ' |\n'
    return markdown_table

def process_table_with_llm(markdown_table):
    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are an AI assistant specialized in interpreting tabular data. Your task is to analyze the given Markdown table and form meaningful sentences based on the row and column values."},
            {"role": "user", "content": f"Please analyze this table and provide a summary in natural language:\n\n{markdown_table}"}
        ]
    )
    return response.choices[0].message['content']

def process_chunk_with_openai(chunk, is_first_chunk=False):
    # Extract tables from the chunk
    tables = extract_tables_from_text(chunk)
    
    # Process tables
    processed_tables = []
    for table in tables:
        markdown_table = convert_table_to_markdown(table)
        table_summary = process_table_with_llm(markdown_table)
        processed_tables.append(f"Original Table (Markdown format):\n{markdown_table}\n\nTable Summary:\n{table_summary}")
    
    # Remove table text from the chunk
    non_table_text = re.sub(r'(\|.*\|[\n\r])+\|.*\|', '', chunk)
    
    # Process non-table text
    system_instruction = """
    You are an advanced AI assistant specialized in processing text from PDFs. Your tasks are:

    1. Identify main headings, subheadings, and side headings. Use the following format:
       MAIN HEADING: text
       SUBHEADING: text
       SIDE HEADING: text

    2. Extract and format normal text paragraphs completely. Ensure no sentences or words are left incomplete.

    3. Identify any listed data or enumerated information and preserve its format.

    4. Maintain the original order and context of the document while processing.

    5. Do not use any special characters or symbols for formatting except for the bullet points (•) for listed data.

    It is crucial that you process and include ALL content from the given chunk. Do not truncate or omit any information.

    If this is the first chunk of the document, start with 'DOCUMENT START:'. If it's the last chunk, end with 'DOCUMENT END:'.
    """

    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": f"Process the following text chunk from a PDF, following the instructions given. {'This is the first chunk of the document.' if is_first_chunk else ''}\n\n{non_table_text}"}
        ]
    )
    
    processed_text = response.choices[0].message['content']
    
    # Combine processed tables and text
    return processed_text + "\n\n" + "\n\n".join(processed_tables)

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
        elif line.startswith('Original Table (Markdown format):'):
            doc.add_paragraph(line, style='Intense Quote')
        elif line.startswith('Table Summary:'):
            doc.add_paragraph(line, style='Quote')
        else:
            doc.add_paragraph(line)

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

def main():
    st.title("Smart Extract with Table Processing!")

    uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

    if uploaded_file is not None:
        if st.button("Process PDF"):
            with st.spinner("Processing PDF and generating Word document... This may take a while."):
                try:
                    file_contents = uploaded_file.read()
                    text = extract_text_from_pdf(io.BytesIO(file_contents))
                    chunks = split_into_chunks(text)
                    processed_chunks = []

                    # Calculate delay based on file size
                    file_size = len(file_contents)
                    base_delay = max(0.5, min(3, file_size / 1000000))  # 0.5 to 3 seconds

                    loading_messages = [
                        "Reading the document... 📄",
                        "Scanning text... 🔎",
                        "Recognizing patterns... 🧠",
                        "Detecting tabular data... 📊",
                        "Extracting relevant sections... 🗂️",
                        "Sorting through the details... 🗃️",
                        "Almost there... ⏳",
                        "Processing the chunk file... 🧩",
                        "Organizing content... 🗒️",
                        "Aligning the data... 🔧",
                        "Checking consistency... ✔️",
                        "Validating structure... ✅",
                        "Rechecking with the original file... 🔄",
                        "Matching formats... 🖋️",
                        "Fine-tuning the output... ✨",
                        "Polishing details... 🪄",
                        "Your file is almost ready... 📂",
                        "Wrapping up... 🎁",
                        "Finalizing... 🚀",
                        "Your file is ready! 🎉"
                    ]

                    progress_placeholder = st.empty()
                    message_placeholder = st.empty()

                    for i, chunk in enumerate(chunks):
                        progress = (i + 1) / len(chunks)
                        progress_placeholder.progress(progress)
                        
                        message_index = min(int(progress * len(loading_messages)), len(loading_messages) - 1)
                        message_placeholder.info(loading_messages[message_index])
                        
                        processed_chunk = process_chunk_with_openai(chunk, is_first_chunk=(i==0))
                        processed_chunks.append(processed_chunk)
                        
                        time.sleep(base_delay * (1 - progress))  # Delay decreases as progress increases

                    processed_text = "\n".join(processed_chunks)
                    word_buffer = create_word_document(processed_text)

                    progress_placeholder.empty()
                    message_placeholder.success("Processing complete. You can now download the full document.")
                    
                    # Store the buffer in session state
                    st.session_state['word_buffer'] = word_buffer
                    st.session_state['original_filename'] = os.path.splitext(uploaded_file.name)[0]

                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")

    # Show download button if buffer is available
    if 'word_buffer' in st.session_state:
        st.download_button(
            label="📥 Download Processed Document",
            data=st.session_state['word_buffer'],
            file_name=f"{st.session_state['original_filename']}_processed.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

if __name__ == "__main__":
    main()
