import os
from dotenv import load_dotenv
from pinecone import Pinecone
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_pinecone import PineconeVectorStore
from langchain.prompts import PromptTemplate
from langchain.chains import RetrievalQA
from pydantic import SecretStr, BaseModel
from typing import List

class SermonSummary(BaseModel):
    summary: str
    source_documents: List[str]

load_dotenv()

# load from env
openai_api_key: SecretStr = SecretStr(os.getenv("OPENAI_API_KEY", ""))
pinecone_api_key = os.getenv("PINECONE_API_KEY", "")
index_name = os.getenv("PINECONE_INDEX_NAME", "khotbah-summarizer-app")

# inisialisasi koneksi ke Pinecone
pc = Pinecone(
        api_key=pinecone_api_key
        )

# inisialisasi model embeddings
embeddings_model = OpenAIEmbeddings(
        model="text-embedding-3-small",
        )

# inisialisasi llm untuk tugas routing
router_llm = ChatOpenAI(
        model="gpt-4o-mini-2024-07-18",
        temperature=0,
        api_key=openai_api_key,
        )

# inisialisasi json parser untuk parsing output
json_parser = JsonOutputParser()

# prompt untuk menggunakan teknik few-shot prompting
prompt_router = ChatPromptTemplate.from_messages([
    ("system",
     """Anda adalah AI router yang sangat efisien. Tugas Anda adalah menganalisis input pengguna terkait sebuah khotbah dan mengklasifikasikannya ke dalam salah satu dari tiga kategori niat: 'topic_summary', 'general_summary', atau 'irrelevant'.

     - 'topic_summary': Gunakan ini jika pengguna menyebutkan topik, peristiwa, nama, atau pertanyaan spesifik. Ekstrak topik itu sebagai 'query'.
     - 'general_summary': Gunakan ini jika pengguna meminta ringkasan umum tanpa topik jelas. 'query' harus berupa kalimat perintah umum.
     - 'irrelevant': Gunakan ini jika input pengguna adalah sapaan, chit-chat, atau pertanyaan yang sama sekali tidak berhubungan. 'query' harus null.

     Anda HARUS memberikan output HANYA dalam format JSON yang valid.

     CONTOH (SHOTS):
     Input: "Tolong ringkaskan khotbah tentang kasih"
     Output: {{"intent": "topic_summary", "query": "khotbah tentang kasih"}}

     Input: "gimana intinya?"
     Output: {{"intent": "general_summary", "query": "Buatkan ringkasan umum dari keseluruhan khotbah ini."}}

     Input: "Peristiwa Daud dan Goliat"
     Output: {{"intent": "topic_summary", "query": "Peristiwa Daud dan Goliat"}}

     Input: "Terima kasih ya"
     Output: {{"intent": "irrelevant", "query": null}}
     """
    ),
    ("human", "Analisis input berikut: {user_input}"),
    ])

# merge semua komponen menjadi satu rantai
# alurnya, prompt_router -> router_llm -> json_parser
router_chain = prompt_router | router_llm | json_parser

# menghubungkan ke vector database yang sudaha ada
vectorstore = PineconeVectorStore.from_existing_index(
        index_name=index_name,
        embedding=embeddings_model,
        )

# buat retriever 
retriever = vectorstore.as_retriever(search_kwargs={'k': 5})

# inisialiasi llm untuk summarization
summarization_llm = ChatOpenAI(
        model="gpt-4o-mini-2024-07-18", 
        temperature=0.2, 
        api_key=openai_api_key
        )

prompt_template_text = """
Anda adalah asisten AI yang ahli dalam teologi dan analisis teks keagamaan.
Gunakan potongan-potongan KONTEKS berikut untuk menjawab PERTANYAAN di akhir.
Jawablah secara mendalam, jelas, dan hanya berdasarkan informasi dari konteks yang diberikan.

### KONTEKS
{context}
### AKHIR KONTEKS

### INSTRUKSI BERPIKIR (Chain-of-Thought)
Sebelum menjawab, lakukan langkah-langkah internal berikut:
1.  Identifikasi poin-poin utama dari setiap bagian konteks yang relevan dengan pertanyaan.
2.  Sintesis poin-poin tersebut untuk menemukan pesan atau argumen sentral.
3.  Rancang struktur jawaban Anda: pembukaan, isi (poin-poin utama), dan penutup/kesimpulan.

### PERTANYAAN
{question}

JAWABAN ANDA:
"""

RAG_PROMPT = PromptTemplate(
        template=prompt_template_text,
        input_variables=["context", "question"]
        )

# merge semua komponenen menjadi satu rantai RetrievalQA
rag_chain = RetrievalQA.from_chain_type(
        llm=summarization_llm,
        chain_type="stuff",
        retriever=retriever,
        return_source_documents=True,
        chain_type_kwargs={"prompt": RAG_PROMPT}
        )


def summarize_sermon(user_input: str)-> SermonSummary:
    """
    fungsi untuk meringkas khotbah berdasarkan input pengguna
    """
    route = router_chain.invoke({"user_input": user_input})
    intent = route["intent"]
    query = route["query"]

    summary: str = ""
    source_documents = []

    print("masih berpikir...")

    if intent == "irrelevant":
        summary = "Input tidak relevan dengan khotbah. Silakan berikan pertanyaan atau topik yang lebih spesifik."
    elif intent in ["topic_summary", "general_summary"]:
        rag_result = rag_chain.invoke({"query": query})
        list_of_source = []

        source_docs = rag_result.get("source_documents", [])
        if source_docs:
            for i, doc in enumerate(source_docs):
                source_file = doc.metadata.get("source", "N/A")
                list_of_source.append(source_file)

        summary = rag_result.get("result", "Tidak ada ringkasan yang ditemukan.")
        source_documents = list_of_source

    return SermonSummary(
        summary=summary,
        source_documents=source_documents
    )
