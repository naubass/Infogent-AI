import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl.worksheet.header_footer")

import streamlit as st
import os
import pandas as pd
import sqlite3
from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI 
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langgraph.prebuilt import create_react_agent
from langchain.schema import HumanMessage
import asyncio

load_dotenv()
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.getenv("GOOGLE_APPLICATION_CREDENTIALS") 

# setup aplikasi
def setup_app():
    st.set_page_config(
        page_title="🤖 Infogent AI",
        layout="centered"
    )
    st.header("Selamat Datang di 🤖 Infogent AI")
    st.sidebar.header("Options", divider="rainbow")

def get_choice():
    return st.sidebar.radio("Choose:", [
        "Upload Excel",
        "Upload SQL Database",
    ])

def get_clear():
    return st.sidebar.button("Session Obrolan Baru", key="clear")

def read_excel(file):
    df = pd.read_excel(file)
    return df.to_string()

def read_sqlite(file):
    conn = sqlite3.connect(file)
    query = "SELECT name FROM sqlite_master WHERE type='table';"
    tables = pd.read_sql(query, conn)
    result = "Tables in database:\n" + tables.to_string(index=False) + "\n\n"
    for table in tables['name']:
        data = pd.read_sql(f"SELECT * FROM {table} LIMIT 10", conn)
        result += f"Preview of {table}:\n{data.to_string(index=False)}\n\n"
    conn.close()
    return result

def upload_temp_file(uploaded_file, temp_name):
    with open(temp_name, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return temp_name

# embedding dengan faiss
async def async_get_retriever_from_text(text: str):
    embedding = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
    texts = [t.strip() for t in text.split("\n") if t.strip()]
    vectorstore = FAISS.from_texts(texts, embedding=embedding)
    retriever = vectorstore.as_retriever()
    return retriever

def get_retriever_from_text(text: str):
    return asyncio.run(async_get_retriever_from_text(text))

# react agent logic-nya
db_conn = None
temp_path = None  # global untuk path database

@tool
def get_schema_info(_: str = "") -> dict:
    """
    Mengambil informasi schema dan contoh data dari database SQLite yang sedang terhubung.
    Fungsi ini mengembalikan nama tabel dan contoh data untuk membantu memahami struktur database.
    """
    global db_conn, temp_path
    if not db_conn or not temp_path:
        return {"schema_info": "Database belum dimuat."}

    cursor = db_conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]

    schema_info = ""
    for table in tables:
        schema_info += f"\n📌 Table: {table}\n"
        try:
            sample_data = pd.read_sql_query(f"SELECT * FROM {table} LIMIT 10", db_conn)
            schema_info += sample_data.to_string(index=False)
            schema_info += "\n" + "-"*40 + "\n"
        except Exception as e:
            schema_info += f"Error reading table: {e}\n"

    return {"schema_info": schema_info}

@tool
def execute_sql(query: str) -> dict:
    """
    Mengeksekusi query SQL pada database SQLite yang sudah dimuat.
    Mengembalikan hasil query sebagai string yang diformat, 
    atau error jika query gagal dijalankan.
    """
    global db_conn, temp_path
    if not db_conn or not temp_path:
        return {"error": "Database belum dimuat."}

    try:
        result = pd.read_sql_query(query, db_conn)
        return {"result": result.to_string(index=False)}
    except Exception as e:
        return {"error": f"Query error: {e}"}

# main logic nya
def main():
    global db_conn, temp_path

    setup_app()
    choice = get_choice()
    clear = get_clear()

    if clear:
        if "agent" in st.session_state:
            del st.session_state["agent"]
        if "excel_text" in st.session_state:
            del st.session_state["excel_text"]

        if db_conn:
            db_conn.close()
            db_conn = None
            temp_path = None

        st.rerun()

    model = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.2)

    # handle file excel
    if choice == "Upload Excel":
        uploaded_file = st.file_uploader("Upload Excel file", type=["xlsx"])
        if uploaded_file:
            text = read_excel(uploaded_file)
            st.session_state["excel_text"] = text
            retriever = get_retriever_from_text(text)
            st.success("Excel berhasil dibaca dan diindeks.")

            prompt = st.chat_input("Tanya tentang data Excel")
            if prompt:
                with st.chat_message("user"):
                    st.write(prompt)

                docs = retriever.invoke(prompt)
                context = "\n\n".join([doc.page_content for doc in docs])

                full_prompt = f"""
                Kamu adalah AI asisten untuk menganalisis data Excel.
                Berdasarkan data berikut, jawab pertanyaan pengguna.

                === Data ===
                {context}

                === Pertanyaan ===
                {prompt}
                """

                response = model.invoke([HumanMessage(content=full_prompt)])

                with st.chat_message("model", avatar="📊"):
                    st.markdown(response.content)

    # handel db sql
    elif choice == "Upload SQL Database":
        uploaded_file = st.file_uploader("Upload SQLite Database (.db)", type=["db", "sqlite"])
        if uploaded_file:
            temp_path = upload_temp_file(uploaded_file, "temp.db")

            # tutup koneksi lama kalau ada
            if db_conn:
                db_conn.close()
            db_conn = sqlite3.connect(temp_path, check_same_thread=False)

            st.success("Database berhasil dibaca.")

            if "agent" not in st.session_state:
                st.session_state.agent = create_react_agent(
                    model=model,
                    tools=[get_schema_info, execute_sql],
                    prompt="""You are a helpful assistant that can answer questions about sales data using SQL.

IMPORTANT: When a user asks a question about sales data, follow these steps:
1. FIRST, use the get_schema_info tool to understand the database structure and see sample data
2. THEN, write a SQL query based on the user's question and the database schema
3. Execute the SQL query using the execute_sql tool
4. Explain the results in a clear and concise way

When writing SQL queries:
- Use proper SQL syntax for SQLite
- Use appropriate JOINs when querying across multiple tables
- Use aliases for table names in complex queries (e.g., 'customers AS c')
- Use aggregation functions (COUNT, SUM, AVG, etc.) when appropriate
- Format the SQL query to be readable

If you encounter any errors:
- Explain what went wrong
- Fix the SQL query and try again

Remember: You must generate the SQL query yourself based on the user's question and the database schema.
Do not ask the user to provide SQL queries.
"""
                )

            prompt = st.chat_input("Tanya tentang isi database")
            if prompt and prompt.strip() != "":
                with st.chat_message("user"):
                    st.write(prompt)

                response = st.session_state.agent.invoke({"messages": [HumanMessage(content=prompt)]})

                answer = response.get("messages", [])
                if answer:
                    content = answer[-1].content
                else:
                    content = "Tidak ada jawaban dari agent."

                with st.chat_message("model", avatar="🗄️"):
                    st.markdown(content)

if __name__ == "__main__":
    main()
