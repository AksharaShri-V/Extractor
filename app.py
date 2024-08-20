import streamlit as st
import PyPDF2
import openai
import io
from docx import Document
import tiktoken

# Set up OpenAI API key
openai.api_key = "OPENAI_API"

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

def split_into_chunks(text, max_tokens=4000):
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

def process_chunk_with_openai(chunk):
    system_instruction = """
    You are an advanced AI assistant specialized in processing text from PDFs. Your tasks are:

    1. Directly extract and mark headings using HTML tags:
       - Main headings: <h3>Heading</h3>
       - Subheadings: <h4>Subheading</h4>
       - Sub-subheadings: <h5>Sub-subheading</h5>

    2. Extract and format normal text paragraphs without modification.

    3. For any listed data or enumerated information:
       - Convert it into an HTML unordered list using <ul> and <li> tags
       - Each item should be wrapped in <li> tags

    4. Detect any tabular data structures within the text. For each detected table:
       - Convert each row of the table into a human-readable sentence
       - Start the sentence with the first column's value as the subject
       - Connect it logically with the values from other columns
       - Present these sentences as list items using <li> tags within a <ul> tag

    5. Maintain the original order and context of the document while processing.

    Your goal is to directly extract and minimally transform the document content, preserving the original information and structure as much as possible.
    """

    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": f"Process the following text chunk from a PDF, following the instructions given:\n\n{chunk}"}
        ]
    )
    return response.choices[0].message['content']

def create_word_document(content):
    doc = Document()

    for line in content.split('\n'):
        if line.startswith('<h3>'):
            doc.add_paragraph(line.replace('<h3>', '').replace('</h3>', ''), style='Heading 3')
        elif line.startswith('<h4>'):
            doc.add_paragraph(line.replace('<h4>', '').replace('</h4>', ''), style='Heading 4')
        elif line.startswith('<h5>'):
            doc.add_paragraph(line.replace('<h5>', '').replace('</h5>', ''), style='Heading 5')
        elif line.startswith('<ul>'):
            continue  # Skip the <ul> tag
        elif line.startswith('</ul>'):
            continue  # Skip the </ul> tag
        elif line.startswith('<li>'):
            doc.add_paragraph(line.replace('<li>', '').replace('</li>', ''), style='List Bullet')
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
                    file_contents = uploaded_file.read()
                    text = extract_text_from_pdf(io.BytesIO(file_contents))
                    chunks = split_into_chunks(text)
                    processed_chunks = []

                    for i, chunk in enumerate(chunks):
                        st.text(f"Processing chunk {i+1} of {len(chunks)}...")
                        processed_chunk = process_chunk_with_openai(chunk)
                        processed_chunks.append(processed_chunk)

                    processed_text = "\n".join(processed_chunks)
                    word_buffer = create_word_document(processed_text)

                    st.success("Processing complete. Click the button below to download the Word document.")
                    
                    # Offer the processed content as a downloadable Word document
                    st.download_button(
                        label="Download",
                        data=word_buffer,
                        file_name="processed_document.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()
